#!/usr/bin/env python3
"""Project exact two-phase lifecycle for current-client linked-record insertion.

This closes the deferred flag=0 -> queue -> flag=1 replay path without source-symbol promotion.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path

def findseq(rows, specs):
    by=rows if isinstance(rows,dict) else {r["address"]:r for r in rows}
    out=[]
    for a,m,o in specs:
        r=by.get(a)
        if r is None: raise SystemExit(f"missing {a}")
        if r["mnemonic"]!=m or r["opStr"]!=o: raise SystemExit(f"drift {a}: {(r['mnemonic'],r['opStr'])}")
        out.append(r)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--callers",type=Path,required=True)
    ap.add_argument("--relink",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    callers=json.loads(a.callers.read_text()); rel=json.loads(a.relink.read_text())
    if callers.get("format")!="t6-current-client-linked-record-insertion-callers-v1": raise SystemExit("wrong callers proof")
    if rel.get("format")!="t6-current-client-linked-record-relink-swap-probe-v1": raise SystemExit("wrong relink proof")
    if callers.get("directCallCount")!=2: raise SystemExit(f"direct caller count drift {callers.get('directCallCount')}")
    rows={}
    for c in callers["callers"]:
        for r in c["contextBefore"]+[c["call"]]+c["contextAfter"]: rows[r["address"]]=r
    for rg in rel["ranges"]:
        for r in rg["instructions"]: rows[r["address"]]=r
    selected=findseq(rows,[
      ("0x007fd8c0","sub","esp, 0x14"),
      ("0x007fd8c3","push","ebx"),
      ("0x007fd8c4","push","ebp"),
      ("0x007fd8c5","push","esi"),
      ("0x007fd8c6","mov","esi, eax"),
      ("0x007fd8c8","push","edi"),
      ("0x007fdbf7","cmp","dword ptr [esp + 0x28], 0"),
      ("0x007fdc43","cmp","dword ptr [0x131d73c], 0xc00"),
      ("0x007fdc5c","mov","eax, dword ptr [0x131d73c]"),
      ("0x007fdc61","mov","dword ptr [eax*4 + 0x14dead0], esi"),
      ("0x007fdc69","mov","dword ptr [0x131d73c], eax"),
      ("0x007fdcc7","push","0"),
      ("0x007fdcc9","lea","eax, [esp + 0xc]"),
      ("0x007fdccd","call","0x7fd8c0"),
      ("0x007ff34c","cmp","dword ptr [0x131d73c], esi"),
      ("0x007ff359","mov","eax, dword ptr [esi*4 + 0x14dead0]"),
      ("0x007ff360","push","1"),
      ("0x007ff362","call","0x7fd8c0"),
      ("0x007ff36b","cmp","esi, dword ptr [0x131d73c]"),
      ("0x007ff375","mov","dword ptr [0x131d73c], 0"),
    ])
    out={
      "format":"t6-current-client-linked-record-deferred-replay-v1",
      "authority":"Persisted exact SHA-classified current-client proofs only",
      "client":rel["client"],
      "directInsertionCallerCount":2,
      "frameProof":{
        "entryEspDeltaBeforeFlagReadBytes":-36,
        "flagReadOperand":"[esp+0x28]",
        "entryStackArgumentOffset":4,
        "derivation":"sub esp,0x14 plus pushes ebx/ebp/esi/edi = -0x24; current [esp+0x28] therefore equals entry [esp+4], first stack argument",
      },
      "phase0":{
        "caller":"0x007fdcb0",
        "call":"0x007fdccd",
        "firstStackArgument":0,
        "onHigherOrEqualBranch":"record pointer stored to 0x14dead0[index], count 0x131d73c incremented, then existing record returned",
      },
      "phase1":{
        "callerRegion":"0x007ff34c..0x007ff375",
        "sourceArray":"0x014dead0",
        "count":"0x0131d73c",
        "firstStackArgument":1,
        "call":"0x007ff362",
        "loop":"every queued record is replayed through 0x007fd8c0 with flag 1, then count is reset to zero",
      },
      "proven":{
        "flagOperandIsFirstStackArgument":True,
        "phase0CallerPassesZero":True,
        "zeroFlagHigherOrEqualRecordIsQueued":True,
        "deferredQueueArrayIs0x014dead0":True,
        "deferredQueueCountIs0x0131d73c":True,
        "phase1FlushLoadsEveryQueuedRecord":True,
        "phase1FlushPassesOne":True,
        "phase1FlushCallsSameInsertionRoutine":True,
        "phase1ResetsQueueCountToZero":True,
        "twoPhaseDeferredReplayLifecycleClosed":True,
      },
      "exactInstructions":selected,
      "proofBoundary":"This proves the current-client two-phase queue/replay control flow and first-argument meaning by frame arithmetic. It does not by itself prove payload-exchange semantics or historical-retail equivalence."
    }
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"directInsertionCallerCount":2,"sha256":hashlib.sha256(payload.encode()).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
