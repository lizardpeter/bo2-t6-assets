#!/usr/bin/env python3
"""Project current-client secondary-chain order and terminal lookup semantics.

Consumes only persisted exact proofs. Deliberately emits no duplicate winner.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def byaddr(probe):
    out={}
    for r in probe["ranges"]:
        for z in r["instructions"]:out[z["address"]]=z
    return out

def req(m,a,mn,op):
    z=m.get(a)
    if z is None:raise SystemExit(f"missing {a}")
    if z["mnemonic"]!=mn or z["opStr"]!=op:raise SystemExit(f"drift {a}: {(z['mnemonic'],z['opStr'])!r}")
    return z

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--relink",type=Path,required=True);ap.add_argument("--lookup",type=Path,required=True);ap.add_argument("--scalar",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rel=json.loads(a.relink.read_text());look=json.loads(a.lookup.read_text());sca=json.loads(a.scalar.read_text())
    if rel.get("format")!="t6-current-client-linked-record-relink-swap-probe-v1":raise SystemExit("wrong relink proof")
    if look.get("format")!="t6-current-client-linked-record-lookup-semantics-v1":raise SystemExit("wrong lookup proof")
    if sca.get("format")!="t6-current-client-five-root-scalar-relation-v1":raise SystemExit("wrong scalar proof")
    m=byaddr(rel)
    exact=[
      req(m,"0x007fdafa","cmp","edi, eax"),
      req(m,"0x007fdafc","jge","0x7fdbf7"),
      req(m,"0x007fdb02","cmp","word ptr [ebx + 0xc], 0"),
      req(m,"0x007fdb10","movzx","ecx, word ptr [edx]"),
      req(m,"0x007fdb1c","movzx","eax, byte ptr [ecx + 8]"),
      req(m,"0x007fdb2f","call","0x493440"),
      req(m,"0x007fdb37","cmp","edi, eax"),
      req(m,"0x007fdb39","jge","0x7fdb45"),
      req(m,"0x007fdb40","lea","edx, [ecx + 0xc]"),
      req(m,"0x007fdb45","mov","cx, word ptr [edx]"),
      req(m,"0x007fdb48","mov","word ptr [esi + 0xc], cx"),
      req(m,"0x007fdb56","mov","word ptr [edx], si"),
    ]
    # Direct lookup proof independently establishes terminal +0xc traversal + +4 return.
    if not look["exactFindings"].get("directLookupReturnsPayloadDword"):raise SystemExit("lookup proof does not establish payload return")
    if look["directLookup"].get("terminalReturnPayloadDwordOffset")!=4 or look["directLookup"].get("secondaryLinkWordOffset")!=12:raise SystemExit("lookup shape drift")
    if sca["summary"]!={"conflictCount":58,"relations":{"owner0_lt_owner1":58},"winnerCount":0}:raise SystemExit(f"scalar summary drift: {sca['summary']}")
    out={
      "format":"t6-current-client-linked-record-chain-order-v1",
      "authority":"Persisted exact SHA-classified current-client proofs only",
      "client":rel["client"],
      "exactInstructions":exact,
      "proven":{
        "lowerScalarCandidateTakesNonJgeInsertionBranch":True,
        "nonJgeBranchWalksSecondaryLinksWhileCandidateScalarIsLowerThanCurrentScalar":True,
        "nonJgeBranchInsertsCandidateBeforeFirstSecondaryRecordWhoseScalarIsLessThanOrEqualToCandidate":True,
        "thereforeNonJgeBranchMaintainsGreaterScalarBeforeLowerScalarOrder":True,
        "directLookupWalksSecondaryLinksToTerminalRecord":True,
        "directLookupReturnsTerminalRecordPayloadAtOffset4":True,
        "fiveRootConflictScalarsAreNonTied":True,
        "fiveRootOwner0ScalarLowerThanOwner1Count":58,
      },
      "fiveRootRelation":{"conflictCount":58,"relation":"owner0 scalar < owner1 scalar for all 58","winner":None,"winnerAuthority":False},
      "remainingGate":"Resolve the >= branch at 0x007fdbf7, especially helper 0x007fd520 payload-transfer semantics and subsequent zone-byte swap, before mapping scalar order to duplicate payload ownership.",
      "proofBoundary":"No current-client duplicate winner is selected. Descending scalar link order on the lower-scalar insertion branch plus terminal lookup is exact; the >= branch can transform payload identity and must be closed separately. Historical retail remains a separate promotion gate."
    }
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"sha256":hashlib.sha256(payload.encode()).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
