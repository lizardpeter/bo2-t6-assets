#!/usr/bin/env python3
"""Exact entry-window probe for the SHA-classified current T6 client zone-row sink.

This is intentionally narrow. It records the first 0x300 bytes of decoded
instructions at 0x004174b0 and identifies exact stack-relative memory operands.
No calling convention, source symbol, field name, precedence rule, historical
retail equivalence, or Technique winner is inferred.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET
from capstone.x86_const import X86_OP_MEM, X86_REG_ESP, X86_REG_EBP
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfgmod

EXPECTED_SHA256="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK=0x004174B0
SPAN=0x300

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED_SHA256: raise SystemExit(f"unexpected current-client SHA-256 {sha}")
    base,secs=cfgmod.parse_pe(raw)
    off=cfgmod.va_to_offset(secs,SINK)
    sec=cfgmod.section_for_va(secs,SINK)
    if off is None or not sec or not sec["executable"]: raise SystemExit("sink is not executable")
    end=min(off+SPAN,sec["rawOffset"]+sec["rawSize"])
    md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True
    rows=[]; stack=[]
    for ins in md.disasm(raw[off:end],SINK):
        row=cfgmod.insn_json(ins)
        row["isCall"]=bool(ins.group(CS_GRP_CALL))
        row["isJump"]=bool(ins.group(CS_GRP_JUMP))
        row["isRet"]=bool(ins.group(CS_GRP_RET))
        rows.append(row)
        for oi,op in enumerate(getattr(ins,"operands",())):
            if op.type==X86_OP_MEM and op.mem.base in (X86_REG_ESP,X86_REG_EBP):
                stack.append({
                    "instruction":row,
                    "operandIndex":oi,
                    "base":ins.reg_name(op.mem.base),
                    "index":ins.reg_name(op.mem.index) if op.mem.index else None,
                    "scale":int(op.mem.scale),
                    "disp":int(op.mem.disp),
                    "dispHex":f"0x{int(op.mem.disp)&0xffffffff:08x}",
                })
    out={
      "format":"t6-current-client-zone-sink-entry-probe-v1",
      "authority":"SHA-classified current Plutonium client only; exact decoded bytes, not historical-retail authority",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
      "sink":f"0x{SINK:08x}",
      "spanBytes":SPAN,
      "instructions":rows,
      "stackRelativeOperands":stack,
      "summary":{
        "instructionCount":len(rows),
        "stackRelativeOperandCount":len(stack),
        "callCount":sum(1 for x in rows if x["isCall"]),
        "jumpCount":sum(1 for x in rows if x["isJump"]),
        "retCount":sum(1 for x in rows if x["isRet"]),
      },
      "proofBoundary":"All rows are direct Capstone decodes from the SHA-gated current client at the exact sink VA. Stack-relative offsets are raw instruction displacements only. No cdecl argument mapping, source symbol, XZoneInfo field name, alloc/free semantics, priority behavior, historical-retail equivalence, or Technique winner is inferred."
    }
    payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
    print(json.dumps({"outBytes":len(payload),"outSha256":hashlib.sha256(payload).hexdigest(),**out["summary"]},indent=2,sort_keys=True))
    return 0
if __name__=="__main__": raise SystemExit(main())
