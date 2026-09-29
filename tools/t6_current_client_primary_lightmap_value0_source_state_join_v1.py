#!/usr/bin/env python3
"""Join exact value-0 primary-lightmap writer provenance to source-state layout.

Consumes retained SHA-pinned proofs and proves, for the observed 0x009BCD00 path:
  EBX = function arg1
  source = arg1 + 0x19660
  helper 0x009BAA50 is called with EAX = EBX = arg1
  helper reads [EAX + 0x1AC6C]
  0x1AC6C - 0x19660 = 0x160C = accepted codeImageSamplerStates base
  the same source object is written at +0x160C/+0x1610/+0x1614/+0x1620

Therefore arg1+0x19660 is an exact current-client occurrence conforming to the
accepted generic source-state sampler-array layout for this observed path.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

BASE=0x19660
FLAT=0x1AC6C
SAMPLER=0x160C
assert FLAT-BASE==SAMPLER

def req(c,m):
    if not c: raise RuntimeError(m)
def idx(ins):
    return {x["address"].lower():x for x in ins}
def gate(m,va,mn,op):
    x=m.get(va.lower()); req(x is not None,f"missing {va}")
    req(x["mnemonic"]==mn and x["opStr"]==op,f"drift {va}: {x}")
    return x

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-proof",type=Path,required=True)
    ap.add_argument("--barrier-proof",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    bp=json.loads(a.base_proof.read_text())
    cp=json.loads(a.barrier_proof.read_text())
    req(bp["client"]["sha256"]==cp["client"]["sha256"],"client mismatch")
    req(bp["client"]["sha256"]=="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf","sha mismatch")
    w0=next(x for x in bp["writers"] if x["writerVa"]=="0x009BD388")
    m=idx(w0["localInstructions"])
    gates=[
      gate(m,"0x009BCD06","mov","eax, dword ptr [ebp + 8]"),
      gate(m,"0x009BCD19","lea","ecx, [eax + 0x19660]"),
      gate(m,"0x009BCD26","mov","dword ptr [ebp - 8], ecx"),
      gate(m,"0x009BCD48","mov","ebx, dword ptr [ebp + 8]"),
      gate(m,"0x009BD331","mov","ecx, dword ptr [ebp - 8]"),
      gate(m,"0x009BD356","mov","ecx, dword ptr [ebp - 8]"),
      gate(m,"0x009BD365","mov","eax, ebx"),
      gate(m,"0x009BD367","call","0x9baa50"),
      gate(m,"0x009BD37C","mov","dword ptr [ecx + 0x1620], eax"),
      gate(m,"0x009BD382","mov","dword ptr [ecx + 0x1614], edx"),
      gate(m,"0x009BD388","mov","dword ptr [ecx + 0x1610], edx"),
      gate(m,"0x009BD38E","mov","dword ptr [ecx + 0x160c], eax"),
    ]
    # Value-0 sibling writer in same function uses ESI restored from same [EBP-8].
    w1=next(x for x in bp["writers"] if x["writerVa"]=="0x009BCDE7")
    m1=idx(w1["localInstructions"])
    sibling=[
      gate(m1,"0x009BCD5F","mov","esi, dword ptr [ebp - 8]"),
      gate(m1,"0x009BCDDD","mov","dword ptr [esi + 0x1614], 1"),
      gate(m1,"0x009BCDE7","mov","dword ptr [esi + 0x1610], edi"),
      gate(m1,"0x009BCDED","mov","dword ptr [esi + 0x160c], edi"),
    ]
    b=next(x for x in cp["barriers"] if x["call"]=="0x009BD367")
    hm=idx(b["helperRegion"]["instructions"])
    helper=[
      gate(hm,"0x009BAA50","cmp","dword ptr [eax + 0x19ee8], 0"),
      gate(hm,"0x009BAA59","cmp","dword ptr [eax + 0x1ac6c], 0"),
      gate(hm,"0x009BAA62","cmp","dword ptr [eax + 0x1ac70], 0"),
      gate(hm,"0x009BAA6B","cmp","dword ptr [eax + 0x1ac74], 0"),
      gate(hm,"0x009BAA74","cmp","dword ptr [eax + 0x1ac78], 0"),
      gate(hm,"0x009BAA7D","cmp","dword ptr [eax + 0x1ac7c], 0"),
      gate(hm,"0x009BAA86","cmp","dword ptr [eax + 0x1ac80], 0"),
    ]
    doc={
      "format":"t6-current-client-primary-lightmap-value0-source-state-join-v1",
      "authority":"join of exact SHA-pinned base provenance and exact helper register/body evidence",
      "client":bp["client"],
      "arithmetic":{
        "ownerToSourceOffsetHex":"0x19660",
        "ownerFlattenedSamplerBaseHex":"0x1AC6C",
        "sourceSamplerBaseHex":"0x160C",
        "identity":"0x19660 + 0x160C = 0x1AC6C"
      },
      "arg1ToSource":{
        "arg1Load":"0x009BCD06 EAX=[EBP+8]",
        "sourceFormation":"0x009BCD19 ECX=EAX+0x19660",
        "sourceSave":"0x009BCD26 [EBP-8]=ECX",
        "ownerReload":"0x009BCD48 EBX=[EBP+8]"
      },
      "helperJoin":{
        "preCall":"0x009BD365 EAX=EBX=arg1",
        "call":"0x009BD367 -> 0x009BAA50",
        "flattenedRead":"0x009BAA59 [EAX+0x1AC6C]",
        "equivalentSourceRead":"[arg1+0x19660+0x160C]"
      },
      "sourceSamplerWrites":{
        "writer9BD388Base":"ECX=[EBP-8]=arg1+0x19660",
        "writes":[x for x in gates if x["address"].lower() in {"0x009bd37c","0x009bd382","0x009bd388","0x009bd38e"}],
        "writer9BCDE7Base":"ESI=[EBP-8]=arg1+0x19660",
        "siblingWrites":sibling
      },
      "gatedInstructions":{"main":gates,"helper":helper,"sibling":sibling},
      "summary":{
        "value0WriterBase":"arg1+0x19660",
        "sourceStateOccurrenceAccepted":True,
        "basis":"exact flattened owner+0x1AC6C read equals exact source+0x160C sampler base, joined to exact arg1+0x19660 formation and same-object sampler writes",
        "writerVAs":["0x009BCDE7","0x009BD388"],
        "slot4Value":0
      },
      "proofBoundary":"Accepts arg1+0x19660 as a current-client GfxCmdBufSourceState occurrence for the observed decoded 0x009BCD00 path by exact intra-build address identity plus the established generic source-state sampler layout. Does not generalize every +0x19660 field in unrelated owner types or exclude indirect/internal entries."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
