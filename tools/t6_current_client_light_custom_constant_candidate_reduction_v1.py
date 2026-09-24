#!/usr/bin/env python3
"""Reduce broad light enum-store candidates to command-record-shaped current-client sites."""
from __future__ import annotations
import argparse,json,re,hashlib
from pathlib import Path

FMT_IN="t6-current-client-light-custom-constant-producer-locator-v1"
FMT_OUT="t6-current-client-light-custom-constant-candidate-reduction-v1"

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def offset_refs(hit):
    dest={}
    for x in hit["sameBaseRecordFieldReferences"]:
        if x["positionClass"]!="destination-or-rmw":continue
        dest.setdefault(int(x["offset"]),[]).append(x["instruction"])
    # Recover exact same-base +2 references from retained textual context too.
    base=hit["recordBaseRegister"]
    plus2=[]
    rx=re.compile(rf"\[{re.escape(base)} \+ 2\]")
    for z in hit.get("contextBefore",[])+[hit["enumStore"]]+hit.get("contextAfter",[]):
        if rx.search(z.get("opStr","")):plus2.append(z)
    return dest,plus2

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--locator",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.locator.read_text())
    if d.get("format")!=FMT_IN:raise SystemExit("locator format drift")
    rows=[]
    for h in d["hits"]:
        dest,plus2=offset_refs(h)
        fields=set(dest)
        payload=set((8,12,16,20))
        score=sum(x in fields for x in (0,8,12,16,20))
        if score<3 and not payload.issubset(fields):continue
        rows.append({
          "accessor":h["accessor"],"enumValue":h["enumValue"],"enumStore":h["enumStore"],
          "recordBaseRegister":h["recordBaseRegister"],
          "destinationOffsets":sorted(fields),
          "fullFloat4PayloadDestinationCoverage":payload.issubset(fields),
          "hasOffset0Destination":0 in fields,
          "offset2References":plus2,
          "destinationInstructionsByOffset":{str(k):v for k,v in sorted(dest.items())},
          "contextBefore":h["contextBefore"],"contextAfter":h["contextAfter"],
        })
    counts={}
    for r in rows:counts[r["accessor"]]=counts.get(r["accessor"],0)+1
    full=[r for r in rows if r["fullFloat4PayloadDestinationCoverage"]]
    doc={"format":FMT_OUT,"authority":"exact reduction of SHA-classified current-client light enum-store locator by same-base record-write shape",
      "source":{"path":str(a.locator),"sha256":sha(a.locator)},
      "summary":{"reducedCandidateCount":len(rows),"fullFloat4CandidateCount":len(full),
                 "accessorCandidateCounts":dict(sorted(counts.items())),
                 "accessorsWithFullFloat4Candidate":sorted({x["accessor"] for x in full})},
      "rows":rows,
      "proofBoundary":"Structural reduction only. Candidates retain exact machine instructions and require multiple same-base command-field writes; fullFloat4 marks exact +8/+12/+16/+20 destination coverage. Offset +0/+2 diagnostics may help identify command headers, but no candidate is promoted as RC_SET_CUSTOM_CONSTANT or as a light provider until allocator/header/dataflow semantics are independently closed."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for r in full:
        print("FULL",r["accessor"],r["enumStore"]["address"],r["recordBaseRegister"],r["destinationOffsets"],
              [(x["address"],x["mnemonic"],x["opStr"]) for x in r["offset2References"]])
if __name__=="__main__":main()
