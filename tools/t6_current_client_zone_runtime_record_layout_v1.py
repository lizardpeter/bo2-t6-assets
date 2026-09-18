#!/usr/bin/env python3
"""Project exact current-client persistent -> runtime zone-record transformation.

Consumes the persisted zone-core CFG proof. No executable access and no source
symbol import.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-zone-core-function-probe-v1"
CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET="persistent_record_consumer_007fdf40"

EXPECTED={
"0x007fdf63":("mov","ebp, dword ptr [esp + 0x138]"),
"0x007fdf75":("mov","edi, dword ptr [esp + 0x144]"),
"0x007fe0d2":("mov","dword ptr [0x143329c], eax"),
"0x007fe0e0":("cmp","dword ptr [ecx + 0x1804950], eax"),
"0x007fe0e8":("add","ecx, 0x4c"),
"0x007fe0fd":("imul","eax, eax, 0x4c"),
"0x007fe100":("push","0x40"),
"0x007fe102":("lea","edx, [eax + 0x1804908]"),
"0x007fe108":("push","ebp"),
"0x007fe10a":("mov","dword ptr [eax + 0x1804950], 1"),
"0x007fe114":("call","0x424f00"),
"0x007fe119":("mov","eax, dword ptr [0x143329c]"),
"0x007fe11e":("imul","eax, eax, 0x4c"),
"0x007fe122":("mov","dword ptr [eax + 0x1804948], edi"),
"0x007fe128":("call","0x451090"),
"0x007fe12d":("mov","ecx, dword ptr [0x143329c]"),
"0x007fe135":("imul","edx, edx, 0x4c"),
"0x007fe13a":("mov","word ptr [esi], cx"),
"0x007fe13d":("mov","dword ptr [esi + 4], edi"),
"0x007fe140":("add","esi, 8"),
"0x007fe146":("mov","dword ptr [edx + 0x180494c], eax"),
"0x007fe14c":("call","0xa72f60"),
"0x007fe151":("inc","dword ptr [0x13de624]"),
"0x007fe2a2":("add","edx, 0x1804908"),
"0x007fe2a8":("push","edx"),
"0x007fe2af":("call","0x4d8ce0"),
"0x007fe301":("test","bl, bl"),
"0x007fe30e":("mov","dword ptr [edx + 0x1804950], 2"),
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--core-proof",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.core_proof.read_bytes();d=json.loads(raw)
 if d.get("format")!=FORMAT or d.get("client",{}).get("sha256")!=CLIENT:raise SystemExit("unexpected source identity")
 ts=[x for x in d.get("targets",[]) if x.get("name")==TARGET]
 if len(ts)!=1:raise SystemExit(f"expected one target, got {len(ts)}")
 flat=[i for b in ts[0]["cfg"]["blocks"] for i in b.get("instructions",[])]
 by={i["address"]:i for i in flat};selected=[]
 for addr,want in EXPECTED.items():
  x=by.get(addr)
  if x is None:raise SystemExit(f"missing {addr}")
  got=(x.get("mnemonic"),x.get("opStr"))
  if got!=want:raise SystemExit(f"{addr}: drift {got!r} != {want!r}")
  selected.append(x)
 out={
  "format":"t6-current-client-zone-runtime-record-layout-v1",
  "authority":d.get("authority"),
  "client":d.get("client"),
  "source":{"path":str(a.core_proof),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},
  "persistentInput":{"recordPointerRegister":"ebp","classifierRegister":"edi","recordStrideBytes":68},
  "runtimeRecord":{
   "base":"0x01804908",
   "strideBytes":76,
   "fields":[
    {"offset":0,"widthBytes":64,"semantic":"bounded_name_storage","source":"persistent record name via exact 0x40-byte copy"},
    {"offset":64,"widthBytes":4,"semantic":"current_client_zone_classifier","source":"persistent trailing classifier / EDI"},
    {"offset":68,"widthBytes":4,"semantic":"helper_0x00451090_result","source":"return value of 0x00451090"},
    {"offset":72,"widthBytes":4,"semantic":"runtime_record_state","observedWrites":[1,2]},
   ],
   "slotIndexGlobal":"0x0143329c",
   "activeRecordCountGlobal":"0x013de624",
   "stateSearchStrideBytes":76,
   "recordPointerPassedTo":"0x004d8ce0",
  },
  "proven":{
   "runtimeRecordStrideIs76Bytes":True,
   "nameCopiedAs64Bytes":True,
   "classifierStoredAtRuntimeOffset64":True,
   "helperResultStoredAtRuntimeOffset68":True,
   "stateStoredAtRuntimeOffset72":True,
   "runtimeRecordPointerPassedTo0x004d8ce0":True,
  },
  "exactInstructions":selected,
  "proofBoundary":"This is exact SHA-classified current-client data flow. Runtime record field names are positional/descriptive only. Function 0x004d8ce0 and helper 0x00451090 are not source-named. No historical-retail equivalence, XZoneInfo source naming, duplicate-XAsset winner rule, or Technique winner is inferred."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
