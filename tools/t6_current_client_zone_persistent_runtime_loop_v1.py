#!/usr/bin/env python3
"""Project exact runtime-loop semantics from persisted current-client zone xrefs.

This is a fail-closed projector over already persisted decoded evidence. It does
not read the executable or import server symbols.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SOURCE_FORMAT="t6-current-client-zone-persistent-global-xref-probe-v1"

EXPECTED={
"0x007fe3d5":("mov","eax, dword ptr [0x14deacc]"),
"0x007fe3de":("mov","edi, dword ptr [0x14deacc]"),
"0x007fe3e4":("mov","dword ptr [0x14deacc], ebx"),
"0x007fe3f4":("mov","esi, 0x12eee98"),
"0x007fe3fb":("test","dword ptr [esi + 0x40], 0x8000"),
"0x007fe40a":("push","esi"),
"0x007fe40b":("call","0x6e09b0"),
"0x007fe413":("mov","dword ptr [ebp - 8], eax"),
"0x007fe416":("inc","dword ptr [ebp - 4]"),
"0x007fe419":("add","esi, 0x44"),
"0x007fe41c":("dec","ebx"),
"0x007fe41d":("jne","0x7fe3fb"),
"0x007fe41f":("mov","ecx, dword ptr [ebp - 4]"),
"0x007fe423":("call","0x596780"),
"0x007fe42f":("mov","esi, 0x12eee98"),
"0x007fe434":("mov","edx, dword ptr [ebp - 8]"),
"0x007fe437":("mov","eax, dword ptr [esi + 0x40]"),
"0x007fe43a":("push","edx"),
"0x007fe43b":("push","ebx"),
"0x007fe43c":("push","eax"),
"0x007fe43d":("push","esi"),
"0x007fe43e":("call","0x7fdf40"),
"0x007fe446":("test","eax, eax"),
"0x007fe467":("mov","ecx, dword ptr [esi + 0x40]"),
"0x007fe46a":("push","ebx"),
"0x007fe46b":("push","ebx"),
"0x007fe46c":("push","ecx"),
"0x007fe46d":("push","esi"),
"0x007fe46e":("call","0x7fdf40"),
"0x007fe47a":("dec","dword ptr [0x12c6f1c]"),
"0x007fe480":("add","esi, 0x44"),
"0x007fe483":("dec","edi"),
"0x007fe484":("jne","0x7fe434"),
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--xref-proof",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.xref_proof.read_bytes();src=json.loads(raw)
 if src.get("format")!=SOURCE_FORMAT: raise SystemExit("wrong source format")
 by={}
 for win in src.get("executableImmediateXrefs",[]):
  for ins in win.get("instructions",[]):
   by.setdefault(ins.get("address"),ins)
 for addr,(mn,op) in EXPECTED.items():
  row=by.get(addr)
  if row is None: raise SystemExit(f"missing required instruction {addr}")
  got=(row.get("mnemonic"),row.get("opStr"))
  if got!=(mn,op): raise SystemExit(f"{addr}: drift {got!r} != {(mn,op)!r}")
 out={
  "format":"t6-current-client-zone-persistent-runtime-loop-proof-v1",
  "authority":src.get("authority"),
  "client":src.get("client"),
  "source":{"path":str(a.xref_proof),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},
  "recordGeometry":{"base":"0x012eee98","strideBytes":68,"classifierOffset":64},
  "runtimeLoop":{
   "publishedCountGlobal":"0x014deacc",
   "publishedCountIsReadThenCleared":True,
   "firstPass":{
    "predicate":{"recordOffset":64,"operation":"bit_test","mask":"0x00008000"},
    "firstSelectedRecordHelper":"0x006e09b0",
    "selectedCountLocal":"[ebp-4]",
    "selectedCountConsumer":"0x00596780",
    "strideBytes":68,
   },
   "secondPass":{
    "recordConsumer":"0x007fdf40",
    "firstInvocationArgumentsRightToLeft":[
      "record_pointer","record_plus_0x40_classifier","zero_in_ebx","first_selected_helper_result"
    ],
    "fallbackInvocationArgumentsRightToLeft":[
      "record_pointer","record_plus_0x40_classifier","zero_in_ebx","zero_in_ebx"
    ],
    "failureDecrementsGlobal":"0x012c6f1c",
    "strideBytes":68,
   },
  },
  "proven":{
   "persistentClassifierBit0x8000ControlsFirstPassSelection":True,
   "persistentRecordAndClassifierArePassedTogetherTo0x007fdf40":True,
   "processedCountBActsAsPublishedLoopCount":True,
   "processedCountAIsConditionallyDecrementedPerRecord":True,
  },
  "proofBoundary":"All facts are forced by exact persisted current-client instructions. This proves runtime consumption of the positional trailing classifier and the 0x8000 selection bit in revision 5346. It does not assign source-level allocFlags/freeFlags names, identify 0x007fdf40/0x006e09b0/0x00596780 by source symbols, establish historical-retail equivalence, or select any Technique winner."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),**out["proven"]},indent=2,sort_keys=True))

if __name__=="__main__":main()
