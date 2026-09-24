#!/usr/bin/env python3
"""Hard exclusions for false-positive enum37/enum60 +4 constructor candidates."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-unresolved-type1-constructor-exclusions-v1"
E37_FMT="t6-current-client-enum37-constructor-function-v1"
E60_FMT="t6-current-client-enum60-constructor-function-v1"
TYPE1_FMT="t6-current-client-generic-code-constant-type1-dispatch-join-v1"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def req(c,m):
    if not c:raise SystemExit(m)
def ops(rows):return {(r["address"],r["mnemonic"],r["opStr"]) for r in rows}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--enum37",type=Path,required=True)
    ap.add_argument("--enum60",type=Path,required=True)
    ap.add_argument("--type1",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    e37,e60,t=load(a.enum37),load(a.enum60),load(a.type1)
    req(e37.get("format")==E37_FMT,"enum37 format drift")
    req(e60.get("format")==E60_FMT,"enum60 format drift")
    req(t.get("format")==TYPE1_FMT,"type1 format drift")
    # Proven type1 ABI from joined dispatcher/setter semantics.
    abi=t["type1Record"]
    req(abi["enumValue"]=="uint32(runtimeRecord+0x04)","type1 enum ABI drift")
    req(abi["lanes"][0]=="float32(runtimeRecord+0x08)","type1 lane0 ABI drift")
    e37ops=ops(e37["constructor"]["instructions"])
    req(("0x004af867","mov","dword ptr [eax + 4], 0x25") in e37ops,"enum37 anchor drift")
    req(("0x004af86e","mov","dword ptr [eax + 8], ecx") in e37ops,"enum37 payload drift")
    allocops=ops(e37["allocator"]["instructions"])
    req(("0x004fb751","mov","dword ptr [ecx + 4], 0") in allocops,"enum37 allocator +4 reset drift")
    req(("0x004fb758","mov","dword ptr [ecx], 0") in allocops,"enum37 allocator +0 reset drift")
    consops=ops(e37["consumer"]["instructions"])
    req(("0x006e4f54","mov","dword ptr [ecx*4 + 0x2e7836c], edx") in consops,"enum37 queue consumer drift")

    e60ops=ops(e60["function"]["instructions"])
    for gate in [
      ("0x00736c7c","mov","dword ptr [ebx + 4], 0x3c"),
      ("0x00736c83","mov","dword ptr [ebx], 0"),
      ("0x00736bcc","mov","byte ptr [ebx + 8], cl"),
      ("0x00736c58","mov","dword ptr [ebx + 0xc], eax"),
      ("0x00736c6d","mov","dword ptr [ebx + 0x10], eax"),
      ("0x00736c76","mov","dword ptr [ebx + 0x14], eax"),
      ("0x00736c79","mov","dword ptr [ebx + 0x18], ecx"),
    ]: req(gate in e60ops,f"enum60 gate drift {gate}")

    exclusions=[
      {
        "accessor":"shadowmapSwitchPartition","enumValue":37,
        "candidateVa":"0x004af867","type1RecordCandidate":False,
        "reason":"freelist queue node: allocator resets dword +0/+4, constructor stores enum-like tag at +4 and one payload dword at +8, then consumer enqueues the pointer into a 1024-entry ring; no type-1 size/type header or four-lane payload exists"
      },
      {
        "accessor":"spotShadowmapPixelAdjust","enumValue":60,
        "candidateVa":"0x00736c7c","type1RecordCandidate":False,
        "reason":"configuration/result object: dword +0 is forced zero (therefore uint16 size/type header is zero), byte +8 is a mode flag, value words extend through +0x18, and +0x1C/+0x20 are separate subobjects; layout contradicts the proven type-1 ABI"
      }
    ]
    doc={
      "format":FORMAT,
      "authority":"exact candidate bodies joined against the independently proven current-client type-1 runtime-record ABI",
      "type1Source":{"path":str(a.type1),"sha256":sha(a.type1),"format":t["format"]},
      "candidateSources":[
        {"path":str(a.enum37),"sha256":sha(a.enum37),"format":e37["format"]},
        {"path":str(a.enum60),"sha256":sha(a.enum60),"format":e60["format"]},
      ],
      "exclusions":exclusions,
      "summary":{"excludedCandidateCount":2,"remainingPromotedCandidateCount":0},
      "proofBoundary":"Hard negative classification for these two specific +4 immediate candidates only. It does not prove the unresolved runtime inputs lack dynamically built type-1 records elsewhere; upstream table-copy/record-construction paths remain the search frontier."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
