#!/usr/bin/env python3
"""Exact current-client join: clipMap layout candidates -> MapEnt entityString accessor.

A shape-A MapEnt accessor loads an absolute slot that independent PC32 layout says
is clipMap.mapEnts at base+0xA8, then dereferences MapEnts.entityString at +4.
This projector promotes only exact address equality:
    accessor.absoluteLoadVa == candidate.baseVa + 0xA8
No score, proximity, rank, or caller similarity is used.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-clipmap-mapents-exact-address-join-v1"
CLIP_FMT="t6-current-client-clipmap-global-layout-candidates-v1"
MAP_FMT="t6-current-client-mapents-entitystring-accessor-candidates-v1"

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def h(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def iv(x):return int(str(x),16)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--clipmap",type=Path,required=True)
    ap.add_argument("--mapents",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    c=json.loads(a.clipmap.read_text());m=json.loads(a.mapents.read_text())
    req(c.get("format")==CLIP_FMT,f"clip format drift {c.get('format')!r}")
    req(m.get("format")==MAP_FMT,f"map format drift {m.get('format')!r}")
    req(c["client"]["sha256"]==m["client"]["sha256"],"client SHA mismatch")
    req(m.get("nativeLayout")=={"clipMapMapEntsOffset":168,"mapEntsEntityStringOffset":4},"MapEnt layout drift")
    req(c.get("landmarks",{}).get("168")=="mapEnts","clipMap +0xA8 landmark drift")

    clip={iv(x["baseVa"]):x for x in c.get("candidates",[])}
    req(len(clip)==len(c.get("candidates",[])),"duplicate clip candidate base")
    rows=[]
    for arow in m.get("candidates",[]):
        if arow.get("shape")!="absolute-mapents-slot-then-entityString+4":continue
        ava=iv(arow["absoluteLoadVa"])
        base=ava-168
        crow=clip.get(base)
        if crow is None:continue
        mapfield=next((f for f in crow.get("fields",[]) if int(f["offset"])==168),None)
        req(mapfield is not None,"joined candidate missing +0xA8 field row")
        req(iv(mapfield["absoluteVa"])==ava,"joined mapEnt field absolute mismatch")
        rows.append({
          "clipMapBaseVa":f"0x{base:08x}",
          "mapEntsAbsoluteSlotVa":f"0x{ava:08x}",
          "accessorStartVa":arow["startVa"],
          "accessorInstructions":arow["instructions"],
          "accessorRawRel32Callers":arow.get("rawRel32Callers",[]),
          "clipCandidateDistinctMatchedFieldCount":crow["distinctMatchedFieldCount"],
          "clipCandidateTotalAbsoluteReferenceCount":crow["totalAbsoluteReferenceCount"],
          "clipCandidateLandmarks":crow["landmarkOffsets"],
          "clipMapEntsFieldUses":mapfield["uses"],
          "clipMapEntsFieldUseCount":mapfield["referenceCount"],
        })
    doc={
      "format":FORMAT,
      "authority":"same SHA-classified current client; exact MapEnt accessor instruction shape + independently fixed PC32 clipMap/MapEnt offsets + exact absolute-address equality",
      "client":c["client"],
      "summary":{
        "clipMapCandidateCount":len(clip),
        "shapeAMapEntAccessorCount":sum(x.get("shape")=="absolute-mapents-slot-then-entityString+4" for x in m.get("candidates",[])),
        "exactAddressJoinCount":len(rows),
        "uniqueJoinedClipMapBaseCount":len({x["clipMapBaseVa"] for x in rows}),
      },
      "rows":rows,
      "sources":{
        "clipMap":{"path":str(a.clipmap),"sha256":h(a.clipmap)},
        "mapEnts":{"path":str(a.mapents),"sha256":h(a.mapents)},
      },
      "proofBoundary":"An exact row proves one current-client structural clipMap candidate's +0xA8 absolute slot is the same absolute slot consumed by a +4 MapEnt entityString accessor candidate. It does not yet prove the accessor's caller is the map-spawn path, prove loaded retail MapEnt bytes feed that slot, or prove parsed *N indexes cmodels/subModels."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for r in rows:print(r["clipMapBaseVa"],r["mapEntsAbsoluteSlotVa"],r["accessorStartVa"],r["clipCandidateDistinctMatchedFieldCount"])
if __name__=="__main__":main()
