#!/usr/bin/env python3
"""Project exact persistent-record facts from the current-client post-staging entry proof.

This is a fail-closed projector over already persisted byte-decoded evidence.
It does not read or redistribute the executable.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SOURCE_FORMAT="t6-current-client-zone-staging-callee-entry-probe-v1"
TARGET_NAME="post_staging_consumer"

EXPECTED={
"0x007fddd9":("mov","ebp, dword ptr [esp + 0x10]"),
"0x007fddf6":("mov","edi, dword ptr [esp + 0x14]"),
"0x007fde00":("mov","eax, dword ptr [edi]"),
"0x007fde06":("push","0x40"),
"0x007fde08":("push","eax"),
"0x007fde09":("lea","eax, [esi - 0x40]"),
"0x007fde0c":("push","eax"),
"0x007fde0d":("call","0x424f00"),
"0x007fde12":("mov","ecx, dword ptr [edi + 4]"),
"0x007fde18":("mov","dword ptr [esi], ecx"),
"0x007fde1b":("add","esi, 0x44"),
"0x007fde1e":("add","edi, 0xc"),
"0x007fde21":("dec","ebp"),
"0x007fde22":("jne","0x7fde00"),
"0x007fde2a":("mov","dword ptr [0x12c6f1c], ebx"),
"0x007fde3b":("mov","dword ptr [0x14deacc], ebx"),
"0x007fde42":("jmp","0x5b8bf0"),
}

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--entry-proof",type=Path,required=True)
 ap.add_argument("--out",type=Path,required=True)
 a=ap.parse_args()
 raw=a.entry_proof.read_bytes(); doc=json.loads(raw)
 if doc.get("format")!=SOURCE_FORMAT: raise SystemExit("wrong source format")
 targets=[x for x in doc.get("targets",[]) if x.get("name")==TARGET_NAME]
 if len(targets)!=1: raise SystemExit(f"expected one {TARGET_NAME}, got {len(targets)}")
 ins=targets[0].get("instructions") or []
 by={x.get("address"):x for x in ins}
 for addr,(mn,op) in EXPECTED.items():
  row=by.get(addr)
  if not row: raise SystemExit(f"missing required instruction {addr}")
  if row.get("mnemonic")!=mn or row.get("opStr")!=op:
   raise SystemExit(f"{addr}: drift: {(row.get('mnemonic'),row.get('opStr'))!r} != {(mn,op)!r}")

 out={
  "format":"t6-current-client-zone-persistent-record-layout-proof-v1",
  "authority":doc.get("authority"),
  "client":doc.get("client"),
  "source":{
   "path":str(a.entry_proof),
   "bytes":len(raw),
   "sha256":hashlib.sha256(raw).hexdigest(),
   "targetAddress":targets[0].get("address"),
  },
  "proven":{
   "inputRecordStrideBytes":12,
   "inputCountConsumed":True,
   "inputBaseConsumed":True,
   "inputField0ConditionallyCopiedAs64ByteStringRegion":True,
   "inputField4CopiedToPersistentRecordOffset64":True,
   "inputField8ReadByThisConsumer":False,
   "persistentRecordStrideBytes":68,
   "populatedRecordCountAccumulated":True,
   "populatedRecordCountStoredToGlobals":["0x012c6f1c","0x014deacc"],
  },
  "persistentRecord":{
   "strideBytes":68,
   "offsets":[
    {"offset":0,"widthBytes":64,"semantic":"bounded_string_storage_region",
     "evidence":["0x007fde00 loads source +0 pointer","0x007fde06 pushes exact size 0x40","0x007fde09 forms destination base as esi-0x40","0x007fde0d calls exact shared copy target 0x00424f00"]},
    {"offset":64,"widthBytes":4,"semantic":"copied_input_plus4_classifier",
     "evidence":["0x007fde12 loads source +4","0x007fde18 stores it at current destination dword","0x007fde1b advances destination cursor by 0x44, so current dword follows the prior 0x40-byte region"]},
   ],
  },
  "sourceIteration":{
   "sourceCursorRegister":"edi",
   "sourceStrideBytes":12,
   "countRegister":"ebp",
   "populationCounterRegister":"ebx",
   "loop":["0x007fde1e add edi,0xc","0x007fde21 dec ebp","0x007fde22 jne 0x007fde00"],
  },
  "downstream":{
   "countGlobals":["0x012c6f1c","0x014deacc"],
   "postPopulationCalls":["0x005c7d20","0x00458cc0"],
   "tailJump":"0x005b8bf0",
  },
  "proofBoundary":"This projection is forced only by exact persisted current-client instructions. The 68-byte persistent record is described positionally. The +4 dword remains a copied classifier, not source-named allocFlags; input +8 remains semantically unresolved here. Shared copy target 0x00424f00 is not source-named. No historical-retail equivalence, duplicate precedence rule, or Technique winner is inferred.",
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode()
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"out":str(a.out),"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),**out["proven"]},indent=2,sort_keys=True))

if __name__=="__main__": main()
