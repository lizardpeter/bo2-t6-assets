#!/usr/bin/env python3
"""Project exact current-client zone classifier semantics from zone-core proof.

Fail-closed over persisted decoded evidence; no executable access.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-zone-core-function-probe-v1"
CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

CALLBACK="row_callback_007fdf00"
CONSUMER="persistent_record_consumer_007fdf40"

EXPECTED_CALLBACK={
"0x007fdf00":("mov","eax, dword ptr [esp + 4]"),
"0x007fdf04":("cmp","dword ptr [eax], 0"),
"0x007fdf0c":("mov","eax, dword ptr [eax + 4]"),
"0x007fdf0f":("mov","edx, dword ptr [esp + 8]"),
"0x007fdf13":("cmp","eax, 0x400000"),
"0x007fdf1a":("mov","ecx, dword ptr [edx + 4]"),
"0x007fdf1d":("cmp","ecx, 0x400000"),
"0x007fdf27":("cmp","eax, ecx"),
"0x007fdf29":("setl","al"),
"0x007fdf2f":("cmp","eax, dword ptr [edx + 4]"),
"0x007fdf32":("setg","al"),
}
EXPECTED_CONSUMER={
"0x007fdf63":("mov","ebp, dword ptr [esp + 0x138]"),
"0x007fdf75":("mov","edi, dword ptr [esp + 0x144]"),
"0x007fdf8e":("test","edi, 0x4092214"),
"0x007fe185":("cmp","edi, 0x400000"),
"0x007fe210":("mov","ebp, edi"),
"0x007fe212":("and","ebp, 0x20000000"),
"0x007fe21c":("test","edi, 0x200000"),
"0x007fe25e":("test","edi, 0x14000"),
"0x007fe266":("mov","ecx, edi"),
"0x007fe268":("shr","ecx, 0xf"),
"0x007fe26b":("and","ecx, 1"),
"0x007fe298":("push","edi"),
}

def flattened(target):
 return [i for b in target["cfg"]["blocks"] for i in b.get("instructions",[])]

def check(target,expected):
 by={i["address"]:i for i in flattened(target)}
 for addr,want in expected.items():
  row=by.get(addr)
  if row is None:raise SystemExit(f"missing {addr}")
  got=(row.get("mnemonic"),row.get("opStr"))
  if got!=want:raise SystemExit(f"{addr}: drift {got!r} != {want!r}")
 return by

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--core-proof",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.core_proof.read_bytes();doc=json.loads(raw)
 if doc.get("format")!=FORMAT or doc.get("client",{}).get("sha256")!=CLIENT:raise SystemExit("unexpected core proof identity")
 targets={t["name"]:t for t in doc.get("targets",[])}
 if CALLBACK not in targets or CONSUMER not in targets:raise SystemExit("required targets missing")
 check(targets[CALLBACK],EXPECTED_CALLBACK);check(targets[CONSUMER],EXPECTED_CONSUMER)

 out={
  "format":"t6-current-client-zone-classifier-semantics-v1",
  "authority":doc.get("authority"),
  "client":doc.get("client"),
  "source":{"path":str(a.core_proof),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},
  "rowOrdering":{
   "callback":"0x007fdf00",
   "firstRecordPointerArgumentOffset":4,
   "secondRecordPointerArgumentOffset":8,
   "recordNamePointerOffset":0,
   "classifierOffset":4,
   "threshold":"0x00400000",
   "behavior":[
    {"condition":"first +4 < 0x00400000 AND second +4 < 0x00400000","predicate":"first +4 < second +4"},
    {"condition":"otherwise","predicate":"first +4 > second +4"}
   ],
   "thirdFieldOffset8Read":False,
  },
  "persistentRuntimeConsumer":{
   "target":"0x007fdf40",
   "argument1":"persistent_record_pointer",
   "argument2":"persistent_trailing_classifier",
   "classifierMasksAndThresholds":[
    "0x04092214","0x00400000","0x20000000","0x00200000","0x00014000"
   ],
   "classifierBit15IsExtracted":True,
   "classifierForwardedAsCallArgument":True,
  },
  "proven":{
   "plus4IsCurrentClientRecordOrderingKey":True,
   "plus4Threshold0x00400000ChangesOrderingDirection":True,
   "plus4PersistsIntoRuntimeFlagTests":True,
   "plus8DoesNotParticipateInRowComparator":True,
  },
  "proofBoundary":"These semantics are forced by exact persisted current-client instructions. The positional +4 dword may now be called the current-client row ordering/classifier field. It is not source-named allocFlags, and +8 is not source-named freeFlags. No historical-retail identity, duplicate-XAsset precedence policy, or Technique winner is promoted."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
