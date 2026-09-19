#!/usr/bin/env python3
"""Combine the retained 18-XFile XAnim census with the complete 31-map MP census.

Overlap is admitted only when exact zone labels, expected/identified counts and all
six delta-branch counts agree. The result is a corpus-union proof, not a claim that
all T6 Zombies/SP/DLC/shared target XFiles have been scanned.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

KEYS=("transKeyed","transConstant","quat2Keyed","quat2Constant","quatKeyed","quatConstant")
FMT="t6-xanim-retained-plus-mp-branch-corpus-v1"

def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--retained",type=Path,required=True)
    ap.add_argument("--mp",type=Path,required=True)
    ap.add_argument("--full-quat-proof",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    retained=json.loads(a.retained.read_text());mp=json.loads(a.mp.read_text());fq=json.loads(a.full_quat_proof.read_text())
    if retained.get("format")!="t6-retail-xanim-full-quat-census-v4":raise SystemExit("retained format drift")
    if mp.get("format")!="t6-mp-xanim-delta-branch-corpus-v1":raise SystemExit("MP format drift")
    if fq.get("format")!="t6-mp-xanim-dynamic-full-quat-compiled-v19-retail-proof-v1":raise SystemExit("full-quat proof format drift")
    ms=mp["summary"]
    if not (ms["targetMapCount"]==31 and ms["mapsScanned"]==31 and ms["mapsCountClosed"]==31 and ms["mapsPartial"]==0 and ms["mapsUnscanned"]==0):
        raise SystemExit(f"MP corpus not completely count-closed: {ms}")
    if fq["summary"].get("fixtureCount")!=6 or fq["summary"].get("allQuaternionRawInt16FramesExact") is not True:
        raise SystemExit("six-fixture exact compiled-v19 full-quat proof not closed")
    rz={z["zone"]:z for z in retained["zones"]}
    mz={z["zone"]:z for z in mp["zones"]}
    overlap=sorted(set(rz)&set(mz))
    checks=[]
    for zone in overlap:
        r=rz[zone];m=mz[zone]
        rb=r["branches"];mb=m["branches"]
        same=(r["expected"]==m["expected"] and r["identified"]==m["identified"]
              and r["countClosesExactly"] is True and m["countClosesExactly"] is True
              and all(int(rb[k])==int(mb[k]) for k in KEYS))
        if not same:raise SystemExit(f"overlap disagreement for {zone}: retained={r} mp={m}")
        checks.append({"zone":zone,"expected":r["expected"],"branches":{k:int(rb[k]) for k in KEYS},"exactAgreement":True})
    union=[]
    for zone,r in sorted(rz.items()):
        union.append({"zone":zone,"source":"retained-v4"+("+mp-confirmed" if zone in mz else ""),"expected":int(r["expected"]),"identified":int(r["identified"]),"branches":{k:int(r["branches"][k]) for k in KEYS}})
    for zone,m in sorted(mz.items()):
        if zone in rz:continue
        union.append({"zone":zone,"source":"mp-corpus-v1","expected":int(m["expected"]),"identified":int(m["identified"]),"branches":{k:int(m["branches"][k]) for k in KEYS}})
    totals={k:sum(z["branches"][k] for z in union) for k in KEYS}
    expected=sum(z["expected"] for z in union);identified=sum(z["identified"] for z in union)
    if expected!=identified:raise SystemExit("union count does not close")
    doc={
      "format":FMT,
      "sources":{
        "retained":{"path":str(a.retained),"sha256":sha(a.retained),"format":retained["format"]},
        "mp":{"path":str(a.mp),"sha256":sha(a.mp),"format":mp["format"]},
        "dynamicFullQuatCompiledV19":{"path":str(a.full_quat_proof),"sha256":sha(a.full_quat_proof),"format":fq["format"]},
      },
      "overlapChecks":checks,"zones":union,
      "summary":{
        "uniqueXFileCount":len(union),
        "overlapZoneCount":len(overlap),
        "overlapZones":overlap,
        "expectedXAnimRecords":expected,
        "structuralRecordsIdentified":identified,
        "branchTotals":totals,
        "constantFullQuatObserved":totals["quatConstant"],
        "dynamicFullQuatObserved":totals["quatKeyed"],
        "directDynamicFullQuatCompiledV19FixtureCount":fq["summary"]["fixtureCount"],
        "directDynamicFullQuatCompiledV19RawExactFixtureCount":fq["summary"]["fixtureCount"] if fq["summary"]["allQuaternionRawInt16FramesExact"] else 0,
        "allUnionXFilesCountClosed":True,
      },
      "proofBoundary":"Exact corpus union of the retained-v4 XFiles and the complete 31-map retail MP census. Overlapping zones are deduplicated only after exact expected/identified and six-branch agreement. This extends corpus-bounded absence evidence for constant full-quaternion delta tracks and independently carries the six direct dynamic-full-quaternion compiled-v19 exact-raw roundtrip fixtures. It is not exhaustive for all Zombies, campaign/SP, language, DLC dependency, or other target XFiles not represented by these two source corpora."
    }
    if doc["summary"]["constantFullQuatObserved"]!=0:raise SystemExit("constant full-quat fixture appeared; inspect before promotion")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
