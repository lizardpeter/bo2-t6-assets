#!/usr/bin/env python3
"""Merge multiplayer player-body discovery candidates with direct retail full-body proof manifests."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

FORMAT="t6-player-body-identity-registry-v1"

def load(path:Path):
    d=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(d,dict): raise ValueError(f"{path}: expected JSON object")
    return d

def sha256(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def load_candidate_tool(path:Path):
    s=importlib.util.spec_from_file_location("t6_player_body_target_census_registry",path)
    if s is None or s.loader is None: raise RuntimeError(f"cannot import {path}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def proof_row(path:Path,d:dict):
    body=d.get("fullBody"); status=d.get("status"); ff=d.get("sourceFastfile"); exp=d.get("expandedStream")
    if not all(isinstance(x,dict) for x in (body,status,ff,exp)):
        raise ValueError(f"{path}: not a supported full-player retail proof")
    name=body.get("name")
    if not isinstance(name,str) or not name: raise ValueError(f"{path}: fullBody.name missing")
    if status.get("fullBodyGeometryRetailProven") is not True or status.get("fullBodySkeletonRetailProven") is not True:
        raise ValueError(f"{path}: body geometry/skeleton not both retail-proven")
    for label,rec in (("sourceFastfile",ff),("expandedStream",exp)):
        h=rec.get("sha256")
        if not isinstance(h,str) or len(h)!=64: raise ValueError(f"{path}: {label}.sha256 missing")
    sk=body.get("skeleton")
    if not isinstance(sk,dict) or sk.get("hierarchyValid") is not True or sk.get("allBoneNamesResolved") is not True:
        raise ValueError(f"{path}: retail skeleton integrity is not closed")
    return {
        "name":name,
        "proofPath":str(path),
        "proofSha256":sha256(path),
        "proofFormat":d.get("format"),
        "proofAuthority":d.get("authority"),
        "sourceZone":ff.get("zoneName"),
        "sourceFastfileSha256":ff["sha256"],
        "expandedSha256":exp["sha256"],
        "bones":body.get("bones"),
        "rootBones":body.get("rootBones"),
        "surfaces":body.get("surfaces"),
        "fixedRecordSha256":body.get("fixedRecordSha256"),
        "fixedPlusNameSha256":body.get("fixedPlusNameSha256"),
        "skeletonNormalizedJsonSha256":sk.get("normalizedJsonSha256"),
        "mesh":body.get("mesh"),
        "retailCompiledPlayerScriptLocated":status.get("retailCompiledPlayerScriptLocated"),
    }

def build(seed:dict,proof_items:list[tuple[Path,dict]],candidate_tool):
    candidates=candidate_tool.build(seed)
    by={m["name"]:dict(m) for m in candidates["models"]}
    proofs={}
    for path,d in proof_items:
        r=proof_row(path,d); name=r["name"]
        if name not in by: raise ValueError(f"{path}: proven body {name!r} is outside candidate universe")
        if name in proofs: raise ValueError(f"duplicate full-body proof for {name}")
        proofs[name]=r
    rows=[]
    for name in sorted(by,key=str.casefold):
        base=by[name]; pr=proofs.get(name)
        rows.append({
            **base,
            "retailIdentityStatus":"retail-proven-full-body" if pr else "candidate-unresolved",
            "retailProof":pr,
        })
    return {
        "format":FORMAT,
        "authority":"candidate registry with promotion only from direct retail full-player proof manifests",
        "candidateGeneration":{
            "format":candidates["format"],
            "summary":candidates["summary"],
            "proofBoundary":candidates["proofBoundary"],
        },
        "summary":{
            "candidateBodies":len(rows),
            "retailProvenFullBodies":sum(r["retailIdentityStatus"]=="retail-proven-full-body" for r in rows),
            "unresolvedCandidateBodies":sum(r["retailIdentityStatus"]=="candidate-unresolved" for r in rows),
            "retailSkeletonsClosed":sum(bool(r.get("retailProof") and r["retailProof"].get("skeletonNormalizedJsonSha256")) for r in rows),
        },
        "bodies":rows,
        "proofBoundary":"A candidate is promoted only when a supplied full-player manifest proves both retail geometry and retail skeleton integrity and provides hash-pinned source and expanded streams. Candidate naming evidence alone never promotes identity."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",type=Path,required=True)
    ap.add_argument("--proof",type=Path,action="append",default=[])
    ap.add_argument("--candidate-tool",type=Path,default=Path(__file__).with_name("t6_player_body_target_census_v1.py"))
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    seed=load(a.seeds); ctool=load_candidate_tool(a.candidate_tool)
    out=build(seed,[(p,load(p)) for p in a.proof],ctool)
    out["sources"]={
        "seeds":{"path":str(a.seeds),"sha256":sha256(a.seeds)},
        "candidateTool":{"path":str(a.candidate_tool),"sha256":sha256(a.candidate_tool)},
        "proofs":[{"path":str(p),"sha256":sha256(p)} for p in a.proof],
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
