#!/usr/bin/env python3
"""Exact current-client sink argument/third-field provenance probe.

Archives the entry prologue of the byte-proven 12-byte-row sink at 0x004174b0,
all bounded-CFG accesses to the high stack slots 0x660/0x664/0x668, and the
exact 12-byte-stride +8 test region. Current-client evidence only.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone.x86_const import X86_OP_MEM
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg

EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK=0x004174B0
STACK={0x660,0x664,0x668}
TARGET_ADDRS={0x00417700,0x00417707,0x0041770B,0x00417713}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw);graph,_=cfg.build_cfg(raw,secs,SINK)
 blocks=graph.get("blocks") or []
 by={}
 stack=[]
 target=[]
 for block in blocks:
  ins=block.get("instructions") or []
  for i,row in enumerate(ins):
   by[row["address"]]=row
   matches=[]
   for oi,op in enumerate(row.get("operands") or []):
    if op.get("type")=="mem" and op.get("base")=="esp" and op.get("disp") in STACK:
     matches.append({"operandIndex":oi,"disp":op["disp"],"index":op.get("index"),"scale":op.get("scale")})
   if matches:
    stack.append({"blockStart":block["start"],"instruction":row,"stackOperands":matches,
                  "before":ins[max(0,i-8):i],"after":ins[i+1:min(len(ins),i+9)]})
   if int(row["address"],16) in TARGET_ADDRS:
    target.append({"blockStart":block["start"],"instruction":row,
                   "before":ins[max(0,i-10):i],"after":ins[i+1:min(len(ins),i+11)]})
 # Exact entry prefix from block beginning at the known sink.
 entry=next((b for b in blocks if b.get("start")==f"0x{SINK:08x}"),None)
 if entry is None:raise SystemExit("sink entry block absent")
 prefix=(entry.get("instructions") or [])[:80]
 for addr in TARGET_ADDRS:
  if f"0x{addr:08x}" not in by:raise SystemExit(f"required target instruction 0x{addr:08x} absent")
 out={
  "format":"t6-current-client-zone-sink-argument-provenance-probe-v1",
  "authority":"SHA-classified current Plutonium client only",
  "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
  "sink":f"0x{SINK:08x}",
  "cfgSummary":{"instructions":graph["instructionCount"],"basicBlocks":graph["basicBlockCount"],"truncated":graph["truncated"]},
  "entryPrefix":prefix,
  "highStackSlotAccesses":stack,
  "thirdFieldCandidateRegion":target,
  "summary":{"highStackSlotAccessCount":len(stack),"thirdFieldCandidateInstructionCount":len(target)},
  "proofBoundary":"Exact decoded evidence for the classified current client. Stack-slot and 12-byte-stride relationships are archived without assuming source argument names. The +8 bit test is not promoted to an input-row semantic unless its base is independently linked to the proven row-array argument. No historical-retail identity, alloc/free flag name, precedence rule, or Technique winner is inferred."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest(),"summary":out["summary"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
