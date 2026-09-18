#!/usr/bin/env python3
"""Exact current-client local zone-staging consumer inventory.

Comparative/current-client evidence only.  The probe decodes the bounded sink body
and records stack accesses into the local staging arena plus direct calls around
those accesses.  It does not import server XZoneInfo names or precedence rules.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_INS_CALL
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg
EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x00417F40
END=0x00418480
ARENA_LO=0x6c
ARENA_HI=0x660

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw);so=cfg.va_to_offset(secs,START);eo=cfg.va_to_offset(secs,END-1)
 if so is None or eo is None:raise SystemExit("probe range unmapped")
 md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
 ins=list(md.disasm(raw[so:eo+1],START)); rows=[];calls=[]
 for i,x in enumerate(ins):
  hits=[]
  for op in x.operands:
   if op.type!=X86_OP_MEM:continue
   b=x.reg_name(op.mem.base) if op.mem.base else None;ix=x.reg_name(op.mem.index) if op.mem.index else None;d=int(op.mem.disp)
   if b=="esp" and ARENA_LO<=d<ARENA_HI:
    hits.append({"base":b,"index":ix,"scale":int(op.mem.scale),"disp":d,"dispHex":f"0x{d:08x}"})
  if hits:
   rows.append({"instruction":cfg.insn_json(x),"arenaOperands":hits,"before":[cfg.insn_json(z) for z in ins[max(0,i-8):i]],"after":[cfg.insn_json(z) for z in ins[i+1:min(len(ins),i+9)]]})
  if x.id==X86_INS_CALL and x.operands and x.operands[0].type==X86_OP_IMM:
   t=int(x.operands[0].imm)&0xffffffff
   calls.append({"instruction":cfg.insn_json(x),"target":f"0x{t:08x}","nearArenaAccess":any(abs(x.address-int(r["instruction"]["address"],16))<=48 for r in rows)})
 # Normalize direct constant stack displacements to 12-byte arena slots only when exact.
 slots={}
 for r in rows:
  for m in r["arenaOperands"]:
   if m["index"] is None:
    rel=m["disp"]-ARENA_LO;slot,off=divmod(rel,12)
    slots.setdefault(str(slot),[]).append({"offset":off,"instruction":r["instruction"]})
 out={"format":"t6-current-client-zone-staging-consumers-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},"range":{"start":f"0x{START:08x}","endExclusive":f"0x{END:08x}"},"arena":{"baseEspDispHex":f"0x{ARENA_LO:x}","endEspDispExclusiveHex":f"0x{ARENA_HI:x}","candidateStrideBytes":12},"arenaAccesses":rows,"constantDispSlotProjection":slots,"directCalls":calls,"summary":{"decodedInstructions":len(ins),"arenaAccessInstructions":len(rows),"constantDispSlots":len(slots),"directCalls":len(calls)},"proofBoundary":"Exact decode and arithmetic projection only for this SHA-classified current client. Stack displacement projection is not source-level field naming. Calls, adjacency, server similarity, and slot offsets do not prove historical-retail identity or Technique ownership."}
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({"proofSha256":hashlib.sha256(payload).hexdigest(),**out["summary"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
