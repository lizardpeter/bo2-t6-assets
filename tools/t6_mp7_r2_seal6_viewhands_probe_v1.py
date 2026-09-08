#!/usr/bin/env python3
"""Probe retail SEAL6 first-person viewhands against the proven T6 hands carrier.

The candidate names are locators only. Promotion comes from exact raw inline-name
XModel records, resolved retail bone names/topology, and strict normalized mesh
payloads. Cross-FastFile ScriptString numeric ids are retained but never compared
as global identities because each expanded XFile has its own serialized string
table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_xmodel_serialized_walker import XModelWalker, XMODEL_SIZE
from t6_xmodel_skeleton_normalize_v2 import normalize_skeleton
from t6_xmodel_mesh_normalize_v1 import Normalizer

FOLLOWING = 0xFFFFFFFF
COMMON_BYTES = 206_493_911
COMMON_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
CARRIER = "viewmodel_hands_no_model"
CANDIDATES = [
    "c_usa_mp_seal6_longsleeve_viewhands",
    "c_usa_mp_seal6_shortsleeve_viewhands",
]

class ProbeError(RuntimeError):
    pass

def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ProbeError(msg)

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def find_inline_xmodel(data: bytes, name: str) -> dict:
    needle = name.encode("ascii") + b"\0"
    positions=[]; p=0
    while True:
        h=data.find(needle,p)
        if h < 0: break
        positions.append(h); p=h+1
    matches=[]
    for h in positions:
        start=h-XMODEL_SIZE
        if start < 0 or struct.unpack_from("<I",data,start)[0] != FOLLOWING:
            continue
        try:
            w=XModelWalker(data,start).walk_xmodel()
        except Exception:
            continue
        if w.get("xmodel",{}).get("name") == name and w.get("assetFixedStart") == start:
            matches.append(w)
    require(len(matches)==1, f"{name}: expected one exact raw inline-name XModel, got {len(matches)} from {len(positions)} literal occurrences")
    return matches[0]

def bone_rows(skel: dict) -> list[dict]:
    return skel["skeleton"]["bones"]

def topology_by_name(skel: dict) -> dict[str, str | None]:
    bones=bone_rows(skel)
    names=[b["name"] for b in bones]
    require(all(names), f"{skel['identity']['name']}: unresolved bone name")
    out={}
    for b in bones:
        parent=b["parentIndex"]
        out[b["name"]] = None if parent is None else names[parent]
    require(len(out)==len(bones), f"{skel['identity']['name']}: duplicate resolved bone names")
    return out

def compare_skeletons(carrier: dict, candidate: dict) -> dict:
    ctop=topology_by_name(carrier); vtop=topology_by_name(candidate)
    cset=set(ctop); vset=set(vtop)
    shared=sorted(cset & vset)
    topology_disagreements=[]
    for name in shared:
        cp=ctop[name]; vp=vtop[name]
        if cp != vp:
            topology_disagreements.append({"bone":name,"carrierParent":cp,"candidateParent":vp})
    return {
        "carrierBoneCount":len(ctop),
        "candidateBoneCount":len(vtop),
        "sharedBoneCount":len(shared),
        "carrierCoverageFraction":len(shared)/len(ctop) if ctop else 1.0,
        "candidateCoverageFraction":len(shared)/len(vtop) if vtop else 1.0,
        "sameResolvedBoneNameSet":cset==vset,
        "sharedBoneTopologyAgreement":len(topology_disagreements)==0,
        "topologyDisagreements":topology_disagreements,
        "missingFromCandidate":sorted(cset-vset),
        "extraInCandidate":sorted(vset-cset),
        "sharedBoneNames":shared,
    }

def mesh_summary(mesh: dict) -> dict:
    surfs=mesh["surfaces"]
    verts=sum(int(s["vertCount"]) for s in surfs)
    tris=sum(int(s["triCount"]) for s in surfs)
    unweighted=sum(int(s["unweightedVertexCount"]) for s in surfs)
    return {
        "surfaceCount":len(surfs),
        "vertexCount":verts,
        "triangleCount":tris,
        "unweightedVertexCount":unweighted,
        "allVerticesWeighted":unweighted==0,
        "meaningfulVisibleGeometry":verts>100 and tris>100,
        "meshOwnedSerializedBytes":mesh["source"]["meshOwnedSerializedBytes"],
        "meshOwnedSerializedSha256":mesh["source"]["meshOwnedSerializedSha256"],
        "normalizedMeshCanonicalSha256":hashlib.sha256(json.dumps(mesh,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
    }

def model_record(data: bytes, name: str) -> tuple[dict,dict,dict]:
    walk=find_inline_xmodel(data,name)
    require(not walk["blockers"], f"{name}: serialized XModel blockers {walk['blockers']}")
    skel=normalize_skeleton(data,walk["assetFixedStart"],identity_name=name)
    require(skel["validation"]["allBoneNamesResolved"], f"{name}: unresolved bones")
    require(skel["validation"]["hierarchyValid"], f"{name}: invalid hierarchy")
    mesh=Normalizer(data,walk["assetFixedStart"]).normalize()
    return walk,skel,mesh

def build(common_path: Path, map_path: Path) -> dict:
    common=common_path.read_bytes(); mp=map_path.read_bytes()
    require(len(common)==COMMON_BYTES, f"common expanded bytes {len(common)} != {COMMON_BYTES}")
    require(sha256(common)==COMMON_SHA256, "common expanded SHA mismatch")

    cwalk,cskel,cmesh=model_record(common,CARRIER)
    candidates=[]
    for name in CANDIDATES:
        walk,skel,mesh=model_record(mp,name)
        ms=mesh_summary(mesh)
        require(ms["meaningfulVisibleGeometry"], f"{name}: only {ms['vertexCount']} verts/{ms['triangleCount']} tris")
        require(ms["allVerticesWeighted"], f"{name}: {ms['unweightedVertexCount']} unweighted vertices")
        comp=compare_skeletons(cskel,skel)
        candidates.append({
            "name":name,
            "xmodelFixedStart":walk["assetFixedStart"],
            "xmodelSerializedEnd":walk["assetSerializedEnd"],
            "xmodelSerializedBytes":walk["assetSerializedBytes"],
            "xmodelSerializedSha256":walk["assetSerializedSha256"],
            "numBones":walk["xmodel"]["numBones"],
            "numRootBones":walk["xmodel"]["numRootBones"],
            "numSurfs":walk["xmodel"]["numSurfs"],
            "numLods":walk["xmodel"]["numLods"],
            "localScriptStringIds":[int(b["scriptStringId"]) for b in bone_rows(skel)],
            "boneNames":[b["name"] for b in bone_rows(skel)],
            "mesh":ms,
            "carrierComparison":comp,
        })

    return {
        "format":"t6-mp7-r2-seal6-viewhands-probe-v1",
        "source":{
            "expandedCommonMp":{"bytes":len(common),"sha256":sha256(common)},
            "expandedMpCarrier":{"bytes":len(mp),"sha256":sha256(mp)},
        },
        "carrier":{
            "name":CARRIER,
            "xmodelFixedStart":cwalk["assetFixedStart"],
            "xmodelSerializedSha256":cwalk["assetSerializedSha256"],
            "numBones":cwalk["xmodel"]["numBones"],
            "localScriptStringIds":[int(b["scriptStringId"]) for b in bone_rows(cskel)],
            "boneNames":[b["name"] for b in bone_rows(cskel)],
            "mesh":mesh_summary(cmesh),
        },
        "candidates":candidates,
        "summary":{
            "candidateCount":len(candidates),
            "allCandidatesMeaningfulGeometry":all(x["mesh"]["meaningfulVisibleGeometry"] for x in candidates),
            "allCandidatesFullyWeighted":all(x["mesh"]["allVerticesWeighted"] for x in candidates),
            "sameBoneSetCandidates":[x["name"] for x in candidates if x["carrierComparison"]["sameResolvedBoneNameSet"]],
            "topologyCompatibleCandidates":[x["name"] for x in candidates if x["carrierComparison"]["sharedBoneTopologyAgreement"]],
        },
        "proofBoundary":(
            "Candidate names are locators only. Each promoted row is an exact raw inline-name XModel from the expanded current retail mp_carrier FastFile, with a strict decoded mesh and resolved skeleton. Cross-FastFile binding comparisons use resolved bone names and parent-name topology; serialized ScriptString numeric ids are retained per XFile and are not treated as global ids. This probe establishes candidate asset ownership/compatibility, not which SEAL6 sleeve variant runtime selects for a particular player class/loadout."
        ),
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--common-stream",type=Path,required=True)
    ap.add_argument("--map-stream",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=build(a.common_stream,a.map_stream)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(d,indent=2,sort_keys=True)+"\n"
    a.out.write_text(text,encoding="utf-8")
    print(json.dumps({"out":str(a.out),"bytes":len(text.encode()),"sha256":hashlib.sha256(text.encode()).hexdigest(),"summary":d["summary"],"candidates":[{"name":x["name"],"bones":x["numBones"],"verts":x["mesh"]["vertexCount"],"tris":x["mesh"]["triangleCount"],"shared":x["carrierComparison"]["sharedBoneCount"],"sameBoneSet":x["carrierComparison"]["sameResolvedBoneNameSet"],"topologyAgreement":x["carrierComparison"]["sharedBoneTopologyAgreement"]} for x in d["candidates"]]},indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
