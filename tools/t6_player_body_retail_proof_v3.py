#!/usr/bin/env python3
"""Retail player-body proof promoter v3 with whole-XSurface alias support.

Promoter v3 preserves v2 for ordinary mesh-v1/v2 and audited nested mesh-v3.
For skeleton-v3 + mesh-v4 it additionally cross-audits the exact packed
XModel.surfs alias before temporarily authorizing those version identifiers for
the mature v1 retail identity/hash/skeleton/geometry gates.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
from typing import Any

FORMAT="t6-player-body-retail-proof-v3"
SKELETON_V3="t6-xmodel-skeleton-normalized-v3"
MESH_V4="t6-xmodel-mesh-normalized-v4"

def load_module(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    if s is None or s.loader is None: raise RuntimeError(f"cannot import {path}")
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def load_json(path:Path):
    d=json.loads(path.read_text(encoding="utf-8-sig"));
    if not isinstance(d,dict): raise ValueError(f"{path}: expected JSON object")
    return d

def _owner_key(x):
    if not isinstance(x,dict): return None
    return (x.get("name"),x.get("xassetIndex"),x.get("fixedSourceStart"))
def _comp_key(x):
    if not isinstance(x,dict): return None
    return (x.get("field"),x.get("actualOffset"),x.get("predictedOffset"),x.get("match"))

def audit_top_level_alias(skeleton:dict[str,Any],mesh:dict[str,Any],name:str)->dict[str,Any]:
    if skeleton.get("format")!=SKELETON_V3: raise ValueError(f"top-level alias requires {SKELETON_V3}")
    if mesh.get("format")!=MESH_V4: raise ValueError(f"top-level alias requires {MESH_V4}")
    if (skeleton.get("identity") or {}).get("name")!=name or (mesh.get("identity") or {}).get("name")!=name: raise ValueError("top-level alias identity mismatch")
    ss=skeleton.get("skeletonSource") or {}; reuse=mesh.get("reuseProof") or {}; val=mesh.get("validation") or {}
    if ss.get("mode")!="packed_reusable_owner_top_level_surfs" or ss.get("topLevelSurfsAliasProven") is not True: raise ValueError("skeleton-v3 top-level surface alias is not proven")
    if reuse.get("mode")!="exact-packed-top-level-XModel.surfs-alias" or reuse.get("topLevelSurfsBorrowed") is not True: raise ValueError("mesh-v4 top-level surface alias is not proven")
    if reuse.get("nestedPayloadsTransitivelyOwnedByAliasedSurfaceObject") is not True: raise ValueError("mesh-v4 transitive nested-payload ownership is not asserted")
    if val.get("targetHeaderAndLodsAuthoritative") is not True or val.get("surfaceArrayExactOwnerAlias") is not True: raise ValueError("mesh-v4 target-header/alias validation is incomplete")
    if val.get("recursiveOwnerMeshReuseSupported") is not False: raise ValueError("mesh-v4 recursive-owner proof boundary changed")
    so=ss.get("owner"); mo=reuse.get("owner"); sc=ss.get("topLevelSurfsComparison"); mc=reuse.get("topLevelSurfsComparison")
    if _owner_key(so) is None or _owner_key(so)!=_owner_key(mo): raise ValueError("skeleton-v3 and mesh-v4 reusable owners differ")
    if _comp_key(sc) is None or _comp_key(sc)!=_comp_key(mc): raise ValueError("skeleton-v3 and mesh-v4 XModel.surfs comparisons differ")
    if sc.get("field")!="XModel.surfs" or sc.get("match") is not True or int(sc.get("actualOffset",-1))!=int(sc.get("predictedOffset",-2)): raise ValueError("top-level XModel.surfs comparison is not exact")
    surfaces=mesh.get("surfaces")
    if not isinstance(surfaces,list): raise ValueError("mesh-v4 surfaces missing")
    for i,s in enumerate(surfaces):
        p=s.get("payloadProvenance") if isinstance(s,dict) else None
        if not isinstance(p,dict) or p.get("mode")!="aliased-with-top-level-XSurface-object": raise ValueError(f"mesh-v4 surface {i} lacks whole-object alias provenance")
        if _owner_key(p.get("owner"))!=_owner_key(so) or _comp_key(p.get("topLevelSurfsComparison"))!=_comp_key(sc): raise ValueError(f"mesh-v4 surface {i} alias provenance disagrees with skeleton-v3")
    return {"owner":so,"comparison":sc,"surfaces":len(surfaces)}

def build(*,name:str,zone_name:str,fastfile_path:Path,expanded_path:Path,probe_path:Path,skeleton_path:Path,mesh_path:Path,modules=None):
    here=Path(__file__).resolve().parent
    if modules is None:
        v2=load_module(here/"t6_player_body_retail_proof_v2.py","t6_body_proof_v3_v2")
        v1=load_module(here/"t6_player_body_retail_proof_v1.py","t6_body_proof_v3_v1")
    else: v2=modules.v2; v1=modules.v1
    sk=load_json(skeleton_path); mesh=load_json(mesh_path); alias=None
    is_top=sk.get("format")==SKELETON_V3 or mesh.get("format")==MESH_V4
    if is_top:
        alias=audit_top_level_alias(sk,mesh,name)
        old_sk=v1.SKELETON_FORMAT; old_mesh=set(v1.MESH_FORMATS)
        try:
            v1.SKELETON_FORMAT=SKELETON_V3; v1.MESH_FORMATS.add(MESH_V4)
            out=v2.build(name=name,zone_name=zone_name,fastfile_path=fastfile_path,expanded_path=expanded_path,probe_path=probe_path,skeleton_path=skeleton_path,mesh_path=mesh_path,v1_module=v1)
        finally:
            v1.SKELETON_FORMAT=old_sk; v1.MESH_FORMATS.clear(); v1.MESH_FORMATS.update(old_mesh)
    else:
        out=v2.build(name=name,zone_name=zone_name,fastfile_path=fastfile_path,expanded_path=expanded_path,probe_path=probe_path,skeleton_path=skeleton_path,mesh_path=mesh_path,v1_module=v1)
    out=dict(out); out["format"]=FORMAT; out["promoterVersion"]=3
    if alias:
        full=dict(out["fullBody"]); ms=dict(full["mesh"]); ms.update({"reuseMode":"exact-packed-top-level-XModel.surfs-alias","reuseOwner":alias["owner"],"topLevelSurfsComparison":alias["comparison"],"aliasedSurfaceCount":alias["surfaces"]}); full["mesh"]=ms; out["fullBody"]=full
    out["proofBoundary"]="Promoter v3 preserves all v1/v2 retail body gates. Whole-XSurface reuse is admitted only when skeleton-v3 and mesh-v4 independently agree on the same unique owner and the same exact packed VIRTUAL XModel.surfs offset. Recursive owner mesh reuse remains unsupported."
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--name",required=True); ap.add_argument("--zone-name",required=True); ap.add_argument("--fastfile",type=Path,required=True); ap.add_argument("--expanded",type=Path,required=True); ap.add_argument("--probe",type=Path,required=True); ap.add_argument("--skeleton",type=Path,required=True); ap.add_argument("--mesh",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    out=build(name=a.name,zone_name=a.zone_name,fastfile_path=a.fastfile,expanded_path=a.expanded,probe_path=a.probe,skeleton_path=a.skeleton,mesh_path=a.mesh); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps({"out":str(a.out),"format":out["format"],"name":out["fullBody"]["name"],"meshReuseMode":out["fullBody"]["mesh"].get("reuseMode")},indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
