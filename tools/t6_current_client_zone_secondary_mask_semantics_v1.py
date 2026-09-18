#!/usr/bin/env python3
"""Project exact current-client secondary row-mask semantics.

Consumes the persisted exact sink-entry proof. No executable access and no
server/source symbol import.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-zone-sink-entry-probe-v1"
CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK="0x004174b0"

EXPECTED={
"0x00417583":("mov","ebx, dword ptr [esp + 0x660]"),
"0x0041758a":("add","ebx, 8"),
"0x00417591":("mov","eax, dword ptr [ebx - 4]"),
"0x00417598":("test","dword ptr [ebx], 0x80000000"),
"0x004175a4":("mov","eax, dword ptr [ebx]"),
"0x004175aa":("cmp","eax, 0x400000"),
"0x004175b1":("lea","ecx, [eax - 1]"),
"0x004175b4":("and","ecx, 0x3f800000"),
"0x004175ba":("or","ecx, eax"),
"0x004175bc":("mov","dword ptr [ebx], ecx"),
"0x004175c0":("lea","edx, [eax - 1]"),
"0x004175c3":("not","edx"),
"0x004175c5":("and","edx, 0x3fffff"),
"0x004175cb":("or","edx, eax"),
"0x004175cd":("mov","dword ptr [ebx], edx"),
"0x004175d6":("mov","eax, dword ptr [ebx]"),
"0x004175f3":("test","dword ptr [esp + 0x20], eax"),
"0x004175fd":("test","eax, 0x200000"),
"0x00417604":("lea","edx, [ebp + 4]"),
"0x00417608":("call","0x529960"),
"0x004176c6":("sub","ebp, 0x48"),
"0x004176d0":("add","ebx, 0xc"),
"0x004176d3":("dec","dword ptr [esp + 0x14]"),
"0x004176d7":("jne","0x417591"),
"0x00417700":("mov","eax, dword ptr [esp + 0x660]"),
"0x00417707":("lea","edx, [ebp + ebp*2]"),
"0x0041770b":("test","dword ptr [eax + edx*4 + 8], 0x200000"),
"0x00417713":("lea","ebx, [eax + edx*4 + 8]"),
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.source.read_bytes();d=json.loads(raw)
 if d.get("format")!=FORMAT or d.get("client",{}).get("sha256")!=CLIENT or d.get("sink")!=SINK:raise SystemExit("unexpected source identity")
 by={x["address"]:x for x in d.get("instructions") or []};selected=[]
 for addr,want in EXPECTED.items():
  x=by.get(addr)
  if x is None:raise SystemExit(f"missing {addr}")
  got=(x.get("mnemonic"),x.get("opStr"))
  if got!=want:raise SystemExit(f"{addr}: drift {got!r} != {want!r}")
  selected.append(x)
 out={
  "format":"t6-current-client-zone-secondary-mask-semantics-v1",
  "authority":d.get("authority"),
  "client":d.get("client"),
  "source":{"path":str(a.source),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},
  "rowGeometry":{"strideBytes":12,"secondaryMaskOffset":8},
  "secondaryMask":{
   "fieldOffset":8,
   "mutableInPlace":True,
   "signBitTestMask":"0x80000000",
   "threshold":"0x00400000",
   "normalizationBranches":[
    {"condition":"value > 0x00400000","expression":"value | ((value - 1) & 0x3f800000)"},
    {"condition":"0 <= value <= 0x00400000","expression":"value | (~(value - 1) & 0x003fffff)"},
    {"condition":"negative / sign bit set","expression":"not normalized by this branch"}
   ],
   "overlapUse":{
    "existingTableStrideBytes":72,
    "operation":"test normalized_row_plus8_mask against existing_table_entry dword",
    "existingEntryBitSpecialCase":"0x00200000",
    "specialCaseHelper":"0x00529960",
   },
   "allRowsIteration":{"sourceStrideBytes":12,"countDecremented":True},
   "independentIndexedUse":{"mask":"0x00200000","address":"0x0041770b","effectiveAddress":"incoming_row_pointer + index*12 + 8"},
  },
  "proven":{
   "plus8IsCurrentClientMutableSecondaryControlMask":True,
   "plus8IsNormalizedAround0x00400000":True,
   "plus8ParticipatesInBitmaskOverlapTests":True,
   "plus8Bit0x00200000HasDedicatedControlFlow":True,
   "plus8IsIteratedAt12ByteRowStride":True,
  },
  "exactInstructions":selected,
  "proofBoundary":"The positional +8 field is byte-proven in the SHA-classified current client as a mutable secondary control mask used for normalization and overlap/bit tests. It is deliberately not source-named freeFlags. The existing 0x48-stride table is described only geometrically; helper 0x00529960 is not source-named. No historical-retail equivalence, duplicate-XAsset winner rule, or Technique winner is inferred."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
