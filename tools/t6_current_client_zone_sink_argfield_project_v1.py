#!/usr/bin/env python3
"""Fail-closed projection of exact row-pointer/count and first-row field consumption.

Consumes only the persisted SHA-gated sink-entry proof. It validates the exact
instruction addresses/bytes that establish stack-frame displacement, incoming
argument slots, row pointer adjustment, and first-row +4/+8 accesses.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SRC_FORMAT="t6-current-client-zone-sink-entry-probe-v1"
OUT_FORMAT="t6-current-client-zone-sink-argfield-proof-v1"
CLIENT_SHA256="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK="0x004174b0"

EXPECTED={
 "0x004174b0":("81ec4c060000","sub","esp, 0x64c"),
 "0x0041754a":("53","push","ebx"),
 "0x0041754b":("55","push","ebp"),
 "0x0041754c":("56","push","esi"),
 "0x0041754d":("57","push","edi"),
 "0x00417562":("68849bbf00","push","0xbf9b84"),
 "0x0041756c":("83c404","add","esp, 4"),
 "0x00417574":("8b842464060000","mov","eax, dword ptr [esp + 0x664]"),
 "0x00417583":("8b9c2460060000","mov","ebx, dword ptr [esp + 0x660]"),
 "0x0041758a":("83c308","add","ebx, 8"),
 "0x0041758d":("89442414","mov","dword ptr [esp + 0x14], eax"),
 "0x00417591":("8b43fc","mov","eax, dword ptr [ebx - 4]"),
 "0x00417594":("85c0","test","eax, eax"),
 "0x00417598":("f70300000080","test","dword ptr [ebx], 0x80000000"),
 "0x004175a4":("8b03","mov","eax, dword ptr [ebx]"),
 "0x004175aa":("3d00004000","cmp","eax, 0x400000"),
 "0x004175bc":("890b","mov","dword ptr [ebx], ecx"),
 "0x004175cd":("8913","mov","dword ptr [ebx], edx"),
 "0x004175d6":("8b03","mov","eax, dword ptr [ebx]"),
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.source.read_bytes();d=json.loads(raw)
 if d.get("format")!=SRC_FORMAT or d.get("client",{}).get("sha256")!=CLIENT_SHA256 or d.get("sink")!=SINK:
  raise SystemExit("unexpected source identity")
 by={x["address"]:x for x in d.get("instructions") or []}
 selected=[]
 for addr,(b,m,o) in EXPECTED.items():
  x=by.get(addr)
  if not x: raise SystemExit(f"missing exact instruction {addr}")
  if (x.get("bytes"),x.get("mnemonic"),x.get("opStr"))!=(b,m,o):
   raise SystemExit(f"{addr}: exact instruction drift: {x}")
  selected.append(x)
 # Exact persistent ESP displacement at the two incoming-argument loads:
 # sub esp,0x64c + four callee-save pushes; the one intervening temporary push
 # at 0x417562 is exactly balanced by add esp,4 at 0x41756c.
 frame=0x64c
 saved_push_bytes=16
 persistent_delta=frame+saved_push_bytes
 rowptr_current_disp=0x660
 count_current_disp=0x664
 rowptr_entry_disp=rowptr_current_disp-persistent_delta
 count_entry_disp=count_current_disp-persistent_delta
 if (rowptr_entry_disp,count_entry_disp)!=(4,8):
  raise SystemExit(f"unexpected normalized entry offsets {(rowptr_entry_disp,count_entry_disp)}")
 out={
  "format":OUT_FORMAT,
  "source":{"path":str(a.source),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"format":SRC_FORMAT},
  "client":d["client"],
  "sink":SINK,
  "exactInstructions":selected,
  "stackNormalization":{
   "frameAllocationBytes":frame,
   "savedRegisterPushBytes":saved_push_bytes,
   "persistentEspBelowEntryAtArgumentLoads":persistent_delta,
   "temporaryPushAt":"0x00417562",
   "temporaryPushBalancedBy":"0x0041756c",
   "rowPointerLoad":{"instruction":"0x00417583","currentEspDisp":rowptr_current_disp,"entryEspDisp":rowptr_entry_disp,"destinationRegister":"ebx"},
   "rowCountLoad":{"instruction":"0x00417574","currentEspDisp":count_current_disp,"entryEspDisp":count_entry_disp,"destinationRegister":"eax"},
  },
  "firstRowDataflow":{
   "rowPointerRegister":"ebx",
   "rowPointerAdjustment":{"instruction":"0x0041758a","bytesAdded":8,"result":"ebx = incoming_row_pointer + 8"},
   "rowPlus4Read":{"instruction":"0x00417591","effectiveAddress":"incoming_row_pointer + 4","nextUse":"test eax,eax at 0x00417594"},
   "rowPlus8Reads":[
    {"instruction":"0x00417598","effectiveAddress":"incoming_row_pointer + 8","operation":"test bitmask 0x80000000"},
    {"instruction":"0x004175a4","effectiveAddress":"incoming_row_pointer + 8","operation":"load dword"},
    {"instruction":"0x004175d6","effectiveAddress":"incoming_row_pointer + 8","operation":"load dword"},
   ],
   "rowPlus8Writes":[
    {"instruction":"0x004175bc","effectiveAddress":"incoming_row_pointer + 8","sourceRegister":"ecx"},
    {"instruction":"0x004175cd","effectiveAddress":"incoming_row_pointer + 8","sourceRegister":"edx"},
   ],
   "rowPlus8LoadedValueComparison":{"instruction":"0x004175aa","immediate":"0x00400000"},
  },
  "proven":{
   "incomingRowPointerEntryStackOffset":4,
   "incomingRowCountEntryStackOffset":8,
   "rowPointerLoadedToEbx":True,
   "rowCountLoadedToEax":True,
   "firstRowPlus4Consumed":True,
   "firstRowPlus8ConsumedAndConditionallyMutated":True,
  },
  "status":"exact_current_client_row_argument_and_positional_field_consumption_only",
  "proofBoundary":"The stack normalization and effective addresses are exact x86 stack/arithmetic consequences of the validated current-client instructions. This proves positional incoming pointer/count and +4/+8 consumption for the SHA-classified current client only. It does not assign the source-level names XZoneInfo/allocFlags/freeFlags, identify 0x004174b0 by source symbol, import dedicated-server priority semantics, establish historical-retail equivalence, or select any Technique winner."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"outBytes":len(payload),"outSha256":hashlib.sha256(payload).hexdigest(),"rowPointerEntryDisp":rowptr_entry_disp,"rowCountEntryDisp":count_entry_disp,"proven":out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
