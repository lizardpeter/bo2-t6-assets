#!/usr/bin/env python3
"""Close current-client five-root duplicate visibility from independently persisted proofs.

This is CURRENT-CLIENT authority only. Historical retail remains intentionally null.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def load(path,fmt):
    d=json.loads(path.read_text())
    if d.get("format")!=fmt:raise SystemExit(f"{path}: wrong format {d.get('format')}")
    return d

def client_sha(d):
    c=d.get("client")
    if isinstance(c,dict):return c.get("sha256")
    return d.get("clientSha256")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--scalar",type=Path,required=True)
    ap.add_argument("--chain",type=Path,required=True)
    ap.add_argument("--deferred",type=Path,required=True)
    ap.add_argument("--exchange",type=Path,required=True)
    ap.add_argument("--lookup",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    scalar=load(a.scalar,"t6-current-client-five-root-scalar-relation-v1")
    chain=load(a.chain,"t6-current-client-linked-record-chain-order-v1")
    deferred=load(a.deferred,"t6-current-client-linked-record-deferred-replay-v1")
    exchange=load(a.exchange,"t6-current-client-linked-record-payload-exchange-v1")
    lookup=load(a.lookup,"t6-current-client-linked-record-lookup-semantics-v1")
    for name,d in [("scalar",scalar),("chain",chain),("deferred",deferred),("exchange",exchange),("lookup",lookup)]:
        if client_sha(d)!=CLIENT:raise SystemExit(f"{name}: client identity drift {client_sha(d)}")
    if scalar["summary"]!={"conflictCount":58,"relations":{"owner0_lt_owner1":58},"winnerCount":0}:raise SystemExit(f"scalar summary drift {scalar['summary']}")
    if not chain["proven"].get("thereforeNonJgeBranchMaintainsGreaterScalarBeforeLowerScalarOrder"):raise SystemExit("chain order not closed")
    if not chain["proven"].get("directLookupWalksSecondaryLinksToTerminalRecord"):raise SystemExit("terminal traversal not closed")
    if not deferred["proven"].get("twoPhaseDeferredReplayLifecycleClosed"):raise SystemExit("deferred replay not closed")
    if not exchange["proven"].get("incomingLogicalPayloadAndZoneMetadataMoveToExistingHeadStorage"):raise SystemExit("incoming promotion exchange not closed")
    if not exchange["proven"].get("oldHeadLogicalPayloadAndZoneMetadataMoveToIncomingLinkedStorage"):raise SystemExit("old-head demotion exchange not closed")
    if not lookup["exactFindings"].get("directLookupReturnsPayloadDword"):raise SystemExit("lookup payload return not closed")

    rows=[]
    for c in scalar["conflicts"]:
        os=c["ownerScalars"]
        if len(os)!=2:raise SystemExit(f"unexpected owner count {c}")
        if c.get("scalarRelation")!="owner0_lt_owner1":raise SystemExit(f"unexpected relation {c}")
        if not os[0]["scalar"]<os[1]["scalar"]:raise SystemExit(f"numeric relation drift {c}")
        rows.append({
          "techniqueSet":c["techniqueSet"],
          "technique":c["technique"],
          "parentOwners":c["parentOwners"],
          "ownerScalars":os,
          "currentClientVisibleOwner":os[0]["owner"],
          "currentClientVisibleScalar":os[0]["scalar"],
          "currentClientRule":"minimum scalar logical duplicate is terminal in descending-scalar +0x0c chain; direct lookup returns terminal +4 payload",
          "currentClientWinnerAuthority":True,
          "historicalRetailWinner":None,
          "historicalRetailWinnerAuthority":False,
        })
    winners={}
    for r in rows:winners[r["currentClientVisibleOwner"]]=winners.get(r["currentClientVisibleOwner"],0)+1
    out={
      "format":"t6-current-client-five-root-visibility-v1",
      "authority":"Exact SHA-classified current Plutonium client projection over the persisted five-root conflict/scalar census",
      "client":{"sha256":CLIENT,"revision":chain["client"]["revision"]},
      "derivation":{
        "logicalSecondaryOrder":"descending scalar after immediate lower-scalar insertion and deferred flag=1 higher/equal replay",
        "higherEqualReplay":"incoming payload contents and zone-index metadata move to existing head storage; old-head logical contents move to newly linked record",
        "lookup":"duplicate lookup traverses +0x0c to terminal record and returns terminal +4 payload",
        "visibilityRule":"minimum scalar is lookup-visible for non-tied duplicates on this current-client path",
      },
      "summary":{
        "conflictCount":len(rows),
        "currentClientWinnerCount":sum(1 for r in rows if r["currentClientWinnerAuthority"]),
        "historicalRetailWinnerCount":0,
        "visibleOwnerCounts":winners,
        "allCurrentClientWinnersAreLowerScalarOwner":all(r["currentClientVisibleScalar"]==min(x["scalar"] for x in r["ownerScalars"]) for r in rows),
      },
      "conflicts":rows,
      "sources":{
        "scalar":str(a.scalar),"chain":str(a.chain),"deferred":str(a.deferred),"exchange":str(a.exchange),"lookup":str(a.lookup)
      },
      "proofBoundary":"This closes duplicate visibility for the SHA-classified current Plutonium client path represented by these persisted proofs. It does NOT promote the result to SHA-256 11c7542f... historical retail t6mp.exe. Historical-retail winners remain null until that executable's duplicate insertion/lookup semantics are independently recovered or byte-equivalence is proved."
    }
    if len(rows)!=58 or out["summary"]["currentClientWinnerCount"]!=58:raise SystemExit("visibility count did not close")
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"sha256":hashlib.sha256(payload.encode()).hexdigest(),**out["summary"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
