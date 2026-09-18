#!/usr/bin/env python3
"""Exact post-validation staging-window probe for the current T6 client sink.

Disassembles the SHA-classified client range 0x00417e80..0x004181c0 and records
all instructions plus a compact index of exact 12-byte stride, memory-copy,
stack-relative, and direct-call evidence. This is structural evidence only.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_GRP_CALL
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_OP_REG
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfgmod

EXPECTED_SHA256="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x00417E80
END=0x004181C0

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED_SHA256: raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfgmod.parse_pe(raw);so=cfgmod.va_to_offset(secs,START);eo=cfgmod.va_to_offset(secs,END-1)
 if so is None or eo is None: raise SystemExit("staging window unmapped")
 md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
 ins=[cfgmod.insn_json(x) for x in md.disasm(raw[so:eo+1],START)]
 byaddr={int(x["address"],16):x for x in ins}
 stride=[];calls=[];stack=[];memrows=[];copyish=[]
 for row in ins:
  ops=row.get("operands") or []
  if row["mnemonic"] in ("add","lea","imul") and any(op.get("type")=="imm" and op.get("value")==12 for op in ops):
   stride.append(row)
  if row["mnemonic"]=="add" and len(ops)>=2 and ops[1].get("type")=="imm" and ops[1].get("value")==12:
   stride.append(row) if row not in stride else None
  if row["mnemonic"]=="lea" and len(ops)>=2 and ops[1].get("type")=="mem" and ops[1].get("disp")==12 and ops[1].get("index") is None:
   stride.append(row) if row not in stride else None
  if row["mnemonic"]=="call":
   calls.append(row)
  for op in ops:
   if op.get("type")=="mem":
    if op.get("base") in ("esp","ebp"):
     stack.append(row);break
  for op in ops:
   if op.get("type")=="mem" and op.get("disp") in (0,4,8):
    memrows.append(row);break
  if row["mnemonic"] in ("mov","movq","movdqu","movups","movaps","movlps","movhps"):
   copyish.append(row)
 # exact local contexts around known 12-byte stride sites
 contexts=[]
 for s in stride:
  addr=int(s["address"],16)
  idx=next(i for i,x in enumerate(ins) if int(x["address"],16)==addr)
  contexts.append({"instruction":s,"before":ins[max(0,idx-12):idx],"after":ins[idx+1:min(len(ins),idx+13)]})
 out={
  "format":"t6-current-client-zone-sink-staging-window-probe-v1",
  "authority":"SHA-classified current Plutonium client only; exact decoded staging-window evidence, not historical-retail authority",
  "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
  "range":{"start":f"0x{START:08x}","endExclusive":f"0x{END:08x}"},
  "instructions":ins,
  "indexes":{"stride12Contexts":contexts,"directCalls":calls,"stackRelativeInstructions":stack,"memoryDisp0_4_8Instructions":memrows,"copyLikeInstructions":copyish},
  "summary":{"instructionCount":len(ins),"stride12SiteCount":len(stride),"callCount":len(calls),"stackRelativeInstructionCount":len(stack),"memoryDisp0_4_8InstructionCount":len(memrows),"copyLikeInstructionCount":len(copyish)},
  "proofBoundary":"This is a direct decode of one fixed current-client address range. Stride/copy/stack indexes are syntactic projections only. No source symbol, row-field semantic name, zone precedence, historical-retail equivalence, or Technique winner is inferred."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest(),**out["summary"],"strideAddresses":[x["instruction"]["address"] for x in contexts]},indent=2,sort_keys=True))
if __name__=="__main__":main()
