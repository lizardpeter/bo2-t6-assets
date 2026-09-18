#!/usr/bin/env python3
"""Exact current-client dynamic 0x8000 row-family CFG/provenance probe.

Anchored by the exact row-sink call at 0x00622670 where prior proof shows
12-byte indexed records with field +4 = 0x8000. This probe recovers a bounded
function-region disassembly, all global direct callers of the anchor region,
and exact register-write history for EDI/EBX/ESI around the row construction.
No map/source symbol is assigned from the address alone.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_GRP_CALL,CS_GRP_RET
from capstone.x86_const import X86_OP_IMM
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg

EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ANCHOR_CALL=0x00622670
SINK=0x004174B0
RANGE_START=0x00622200
RANGE_END=0x00622780
REGS={"edi","ebx","esi"}

def direct(ins):
    if not getattr(ins,"operands",None): return None
    op=ins.operands[0]
    return (int(op.imm)&0xffffffff) if op.type==X86_OP_IMM else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED: raise SystemExit("client SHA drift")
    base,secs=cfg.parse_pe(raw)
    if not cfg.is_executable_va(secs,ANCHOR_CALL): raise SystemExit("anchor nonexec")
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    so=cfg.va_to_offset(secs,RANGE_START);eo=cfg.va_to_offset(secs,RANGE_END)
    if so is None or eo is None: raise SystemExit("range unmapped")
    ins=list(md.disasm(raw[so:eo],RANGE_START))
    by={x.address:x for x in ins}
    anchor=by.get(ANCHOR_CALL)
    if anchor is None or anchor.mnemonic!="call" or direct(anchor)!=SINK:
        raise SystemExit("anchor sink call drift")

    rows=[cfg.insn_json(x) for x in ins]
    relevant=[]
    for x in ins:
        try: reads,writes=x.regs_access()
        except Exception: reads,writes=(),()
        names_read={x.reg_name(r) for r in reads};names_write={x.reg_name(r) for r in writes}
        if (names_read|names_write)&REGS or x.group(CS_GRP_CALL) or x.group(CS_GRP_RET):
            relevant.append({**cfg.insn_json(x),"selectedRegsRead":sorted(names_read&REGS),"selectedRegsWrite":sorted(names_write&REGS)})

    # All executable direct callers whose target lands anywhere in this bounded region.
    callers=[]
    md2=Cs(CS_ARCH_X86,CS_MODE_32);md2.detail=True;md2.skipdata=True
    for sec in secs:
        if not sec["executable"]:continue
        blob=raw[sec["rawOffset"]:sec["rawOffset"]+sec["rawSize"]]
        for x in md2.disasm(blob,sec["va"]):
            try:
                if x.id==0 or not x.group(CS_GRP_CALL): continue
            except Exception:
                continue
            t=direct(x)
            if t is not None and RANGE_START<=t<RANGE_END:
                callers.append({"call":cfg.insn_json(x),"target":f"0x{t:08x}"})

    # Exact 0x8000 stores and their adjacent indexed row stores.
    flag_sites=[]
    for i,x in enumerate(ins):
        ops=getattr(x,"operands",())
        if x.mnemonic=="mov" and len(ops)>=2 and ops[1].type==X86_OP_IMM and (int(ops[1].imm)&0xffffffff)==0x8000:
            flag_sites.append({
              "instruction":cfg.insn_json(x),
              "contextBefore":[cfg.insn_json(y) for y in ins[max(0,i-10):i]],
              "contextAfter":[cfg.insn_json(y) for y in ins[i+1:min(len(ins),i+11)]],
            })
    out={
      "format":"t6-current-client-dynamic-8000-row-family-probe-v1",
      "authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
      "anchor":{"callSite":f"0x{ANCHOR_CALL:08x}","sink":f"0x{SINK:08x}"},
      "boundedRange":{"start":f"0x{RANGE_START:08x}","endExclusive":f"0x{RANGE_END:08x}","instructionCount":len(ins)},
      "instructions":rows,
      "selectedRegisterAndCallInstructions":relevant,
      "directCallersIntoRange":callers,
      "immediate8000Stores":flag_sites,
      "summary":{"instructionCount":len(ins),"callerCount":len(callers),"immediate8000StoreCount":len(flag_sites)},
      "status":"exact_current_client_dynamic_8000_row_family_only_no_map_symbol_or_historical_promotion",
      "proofBoundary":"0x00622670 is selected because persisted exact current-client evidence shows it calls the proven 12-byte-row sink after indexed +4=0x8000 row stores. This bounded decode and register history are exact for revision 5346 only. EDI/EBX semantics, map identity, source symbols, historical-retail behavior, and Technique winners require independent data-flow proof."
    }
    payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
    print(json.dumps({"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest(),**out["summary"],"callerTargets":sorted(set(x["target"] for x in callers))},indent=2,sort_keys=True))
if __name__=="__main__":main()
