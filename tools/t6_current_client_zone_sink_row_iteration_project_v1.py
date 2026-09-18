#!/usr/bin/env python3
"""Fail-closed proof of exact 12-byte input-row iteration in the current T6 client.

Consumes the persisted entry and stride proofs and validates the exact instruction
chain that maps incoming pointer/count to a repeated +4/+8 field loop.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ENTRY_FORMAT="t6-current-client-zone-sink-entry-probe-v1"
STRIDE_FORMAT="t6-current-client-zone-sink-stride12-probe-v1"
OUT_FORMAT="t6-current-client-zone-sink-row-iteration-proof-v1"

EXPECTED={
 "0x00417574":("8b842464060000","mov","eax, dword ptr [esp + 0x664]"),
 "0x00417583":("8b9c2460060000","mov","ebx, dword ptr [esp + 0x660]"),
 "0x0041758a":("83c308","add","ebx, 8"),
 "0x0041758d":("89442414","mov","dword ptr [esp + 0x14], eax"),
 "0x00417591":("8b43fc","mov","eax, dword ptr [ebx - 4]"),
 "0x00417598":("f70300000080","test","dword ptr [ebx], 0x80000000"),
 "0x004176d0":("83c30c","add","ebx, 0xc"),
 "0x004176d3":("ff4c2414","dec","dword ptr [esp + 0x14]"),
 "0x004176d7":("0f85b4feffff","jne","0x417591"),
}

def index(doc):
 return {x["address"]:x for x in doc.get("instructions") or []}

def check(by,addr):
 exp=EXPECTED[addr];x=by.get(addr)
 if not x: raise SystemExit(f"missing instruction {addr}")
 got=(x.get("bytes"),x.get("mnemonic"),x.get("opStr"))
 if got!=exp: raise SystemExit(f"{addr}: drift {got!r} != {exp!r}")
 return x

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--entry",type=Path,required=True);ap.add_argument("--stride",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 er=a.entry.read_bytes();sr=a.stride.read_bytes();e=json.loads(er);s=json.loads(sr)
 if e.get("format")!=ENTRY_FORMAT or e.get("client",{}).get("sha256")!=CLIENT: raise SystemExit("unexpected entry proof identity")
 if s.get("format")!=STRIDE_FORMAT or s.get("client",{}).get("sha256")!=CLIENT: raise SystemExit("unexpected stride proof identity")
 eb=index(e)
 selected=[check(eb,x) for x in ["0x00417574","0x00417583","0x0041758a","0x0041758d","0x00417591","0x00417598"]]
 stride_by={h["instruction"]["address"]:h["instruction"] for h in s.get("stride12Sites") or []}
 for addr in ["0x004176d0"]:
  x=stride_by.get(addr)
  if not x: raise SystemExit(f"stride proof missing {addr}")
  exp=EXPECTED[addr];got=(x.get("bytes"),x.get("mnemonic"),x.get("opStr"))
  if got!=exp: raise SystemExit(f"{addr}: stride drift {got!r} != {exp!r}")
  selected.append(x)
 # 0x4176d3/d7 are exact context-after rows for the 0x4176d0 stride site.
 site=next((h for h in s["stride12Sites"] if h["instruction"]["address"]=="0x004176d0"),None)
 if not site: raise SystemExit("missing loop stride site")
 ctx={x["address"]:x for x in site.get("contextAfter") or []}
 for addr in ["0x004176d3","0x004176d7"]:
  x=ctx.get(addr)
  if not x: raise SystemExit(f"loop context missing {addr}")
  exp=EXPECTED[addr];got=(x.get("bytes"),x.get("mnemonic"),x.get("opStr"))
  if got!=exp: raise SystemExit(f"{addr}: loop drift {got!r} != {exp!r}")
  selected.append(x)
 out={
  "format":OUT_FORMAT,
  "client":e["client"],
  "sources":{
    "entry":{"path":str(a.entry),"bytes":len(er),"sha256":hashlib.sha256(er).hexdigest()},
    "stride":{"path":str(a.stride),"bytes":len(sr),"sha256":hashlib.sha256(sr).hexdigest()},
  },
  "exactInstructions":selected,
  "rowArray":{
    "entryPointerStackOffset":4,
    "entryCountStackOffset":8,
    "iterationPointerRegister":"ebx",
    "iterationPointerInitialOffsetFromRowBase":8,
    "countLocal":"[esp+0x14]",
    "rowStrideBytes":12,
    "loopStart":"0x00417591",
    "loopAdvance":"0x004176d0",
    "loopCountDecrement":"0x004176d3",
    "loopBackedge":"0x004176d7 -> 0x00417591",
    "perIterationPositionalReads":[
      {"offset":4,"instruction":"0x00417591"},
      {"offset":8,"instruction":"0x00417598"}
    ]
  },
  "proven":{
    "incomingRowsAreContiguous12ByteRecords":True,
    "incomingCountControlsRowIteration":True,
    "rowPlus4IsConsumedPerIteration":True,
    "rowPlus8IsConsumedPerIteration":True,
  },
  "status":"exact_current_client_input_row_iteration_only",
  "proofBoundary":"This proves exact current-client iteration over the incoming 12-byte records using the independently normalized input pointer/count and the decoded loop backedge. Positional +4/+8 fields remain unnamed. It does not name the routine or structure, establish alloc/free semantics or priority, prove historical-retail equivalence, or select any Technique winner."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"outBytes":len(payload),"outSha256":hashlib.sha256(payload).hexdigest(),"rowArray":out["rowArray"],"proven":out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
