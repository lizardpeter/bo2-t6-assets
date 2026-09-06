#!/usr/bin/env python3
"""T6 XModel mesh normalizer v4: exact packed top-level XModel.surfs alias.

Requires skeleton-v3 to prove that packed skeleton arrays and the target's
packed XModel.surfs pointer are one exact VIRTUAL replay sequence to a unique
earlier inline owner. The owner mesh must be fully decodable by mesh-v1.

The target XModel header and target LOD records remain authoritative. The full
XSurface array is copied from the owner because the target pointer aliases that
exact already-materialized runtime object; its nested pointers therefore refer
to the same owner payloads. Recursive packed owner geometry is not supported.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

FORMAT="t6-xmodel-mesh-normalized-v4"
SKELETON_FORMAT="t6-xmodel-skeleton-normalized-v3"


def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"cannot import {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def load_json(path:Path):
    d=json.loads(path.read_text(encoding="utf-8-sig"));
    if not isinstance(d,dict): raise ValueError(f"{path}: expected JSON object")
    return d

def _u16(data,o): return struct.unpack_from("<H",data,o)[0]
def _u32(data,o): return struct.unpack_from("<I",data,o)[0]
def ptr_kind(raw:int):
    if raw==0:return {"kind":"null","raw":raw,"rawHex":"0x00000000"}
    if raw==0xffffffff:return {"kind":"following","raw":raw,"rawHex":"0xFFFFFFFF"}
    if raw==0xfffffffe:return {"kind":"insert","raw":raw,"rawHex":"0xFFFFFFFE"}
    enc=(raw-1)&0xffffffff; return {"kind":"packed","raw":raw,"rawHex":f"0x{raw:08X}","block":enc>>29,"offset":enc&0x1fffffff}


def audit_skeleton_alias(data:bytes,target_start:int,skeleton:dict[str,Any])->dict[str,Any]:
    if skeleton.get("format")!=SKELETON_FORMAT: raise ValueError(f"skeleton format must be {SKELETON_FORMAT}")
    src=skeleton.get("source") or {}; ident=skeleton.get("identity") or {}; sk=skeleton.get("skeleton") or {}; val=skeleton.get("validation") or {}; ss=skeleton.get("skeletonSource") or {}
    actual_sha=hashlib.sha256(data).hexdigest()
    if src.get("expandedSha256")!=actual_sha: raise ValueError("skeleton expandedSha256 mismatch")
    if int(src.get("xmodelFixedStart",-1))!=int(target_start): raise ValueError("skeleton target fixed start mismatch")
    if val.get("allBoneNamesResolved") is not True or val.get("hierarchyValid") is not True: raise ValueError("skeleton integrity is not closed")
    if ss.get("mode")!="packed_reusable_owner_top_level_surfs" or ss.get("topLevelSurfsAliasProven") is not True:
        raise ValueError("skeleton-v3 did not prove packed top-level XModel.surfs alias")
    owner=ss.get("owner"); comp=ss.get("topLevelSurfsComparison")
    if not isinstance(owner,dict) or not isinstance(owner.get("fixedSourceStart"),int) or not isinstance(owner.get("name"),str): raise ValueError("skeleton-v3 owner metadata incomplete")
    if not isinstance(comp,dict) or comp.get("field")!="XModel.surfs" or comp.get("match") is not True: raise ValueError("skeleton-v3 top-level surface comparison missing")
    p=ptr_kind(_u32(data,target_start+32))
    if p.get("kind")!="packed" or p.get("block")!=5: raise ValueError("target XModel.surfs is not packed VIRTUAL")
    off=int(p["offset"])
    if int(comp.get("actualOffset",-1))!=off or int(comp.get("predictedOffset",-2))!=off: raise ValueError("top-level surface replay offset does not equal target packed pointer")
    n=data[target_start+4]; roots=data[target_start+5]; ns=data[target_start+6]
    if int(sk.get("numBones",-1))!=n or int(sk.get("numRootBones",-1))!=roots: raise ValueError("target header/skeleton cardinality mismatch")
    return {"identity":ident.get("name"),"owner":owner,"comparison":comp,"numBones":n,"numRootBones":roots,"numSurfs":ns,"pointer":p}


def build_from_owner(data:bytes,target_start:int,skeleton:dict[str,Any],owner_mesh:dict[str,Any])->dict[str,Any]:
    proof=audit_skeleton_alias(data,target_start,skeleton)
    if owner_mesh.get("format")!="t6-xmodel-mesh-normalized-v1": raise ValueError("mesh v4 currently requires a fully inline mesh-v1 owner")
    if owner_mesh.get("identity",{}).get("name")!=proof["owner"]["name"]: raise ValueError("owner mesh identity does not match skeleton-v3 owner")
    ox=owner_mesh.get("xmodel") or {}; surfaces=owner_mesh.get("surfaces")
    if not isinstance(surfaces,list) or len(surfaces)!=proof["numSurfs"]: raise ValueError("owner surface cardinality does not match target packed alias")
    if int(ox.get("numBones",-1))!=proof["numBones"] or int(ox.get("numRootBones",-1))!=proof["numRootBones"] or int(ox.get("numSurfs",-1))!=proof["numSurfs"]:
        raise ValueError("owner mesh header is incompatible with target alias")

    copied=copy.deepcopy(surfaces); total_v=0; total_t=0
    for i,s in enumerate(copied):
        if not isinstance(s,dict): raise ValueError(f"owner surface {i} malformed")
        vc=int(s.get("vertCount",-1)); tc=int(s.get("triCount",-1)); verts=s.get("vertices"); tris=s.get("triangles"); joints=s.get("joints0"); weights=s.get("weights0")
        if vc<0 or tc<0 or not isinstance(verts,list) or not isinstance(tris,list) or len(verts)!=vc or len(tris)!=tc: raise ValueError(f"owner surface {i} geometry cardinality mismatch")
        if not isinstance(joints,list) or not isinstance(weights,list) or len(joints)!=vc or len(weights)!=vc: raise ValueError(f"owner surface {i} skin-row cardinality mismatch")
        if any(not isinstance(t,list) or len(t)!=3 or (t and max(t)>=vc) for t in tris): raise ValueError(f"owner surface {i} triangle outside local range")
        for vi,(js,ws) in enumerate(zip(joints,weights)):
            if len(js)!=4 or len(ws)!=4: raise ValueError(f"owner surface {i} skin row {vi} is not vec4")
            for j,w in zip(js,ws):
                if float(w)!=0.0 and not (0<=int(j)<proof["numBones"]): raise ValueError(f"owner surface {i} weighted joint outside target skeleton")
        s["payloadProvenance"]={"mode":"aliased-with-top-level-XSurface-object","owner":proof["owner"],"topLevelSurfsComparison":proof["comparison"]}
        total_v+=vc; total_t+=tc

    num_lods=_u16(data,target_start+196)
    if num_lods>4: raise ValueError("target numLods exceeds fixed T6 XModel capacity")
    lods=[]
    for i in range(num_lods):
        b=target_start+40+i*28
        lod={"index":i,"dist":struct.unpack_from("<f",data,b)[0],"numSurfs":_u16(data,b+4),"surfIndex":_u16(data,b+6),"partBits":[_u32(data,b+8+4*j) for j in range(5)]}
        if lod["surfIndex"]+lod["numSurfs"]>proof["numSurfs"]: raise ValueError(f"target LOD{i} surface span outside aliased surface array")
        lods.append(lod)
    return {
        "format":FORMAT,"identity":{"name":proof["identity"]},"expandedSha256":hashlib.sha256(data).hexdigest(),
        "source":{"assetFixedStart":target_start},
        "xmodel":{"numBones":proof["numBones"],"numRootBones":proof["numRootBones"],"numSurfs":proof["numSurfs"],"numLods":num_lods,"lods":lods},
        "surfaces":copied,
        "reuseProof":{"mode":"exact-packed-top-level-XModel.surfs-alias","owner":proof["owner"],"topLevelSurfsPointer":proof["pointer"],"topLevelSurfsComparison":proof["comparison"],"topLevelSurfsBorrowed":True,"nestedPayloadsTransitivelyOwnedByAliasedSurfaceObject":True},
        "summary":{"vertices":total_v,"triangles":total_t},
        "validation":{"allLocalTriangleIndicesInRange":True,"targetHeaderAndLodsAuthoritative":True,"surfaceArrayExactOwnerAlias":True,"recursiveOwnerMeshReuseSupported":False}
    }


def normalize_mesh(data:bytes,target_start:int,skeleton:dict[str,Any],*,base_module=None)->dict[str,Any]:
    here=Path(__file__).resolve().parent; base=base_module or load_module(here/"t6_xmodel_mesh_normalize_v1.py","t6_mesh_v4_base")
    proof=audit_skeleton_alias(data,target_start,skeleton); owner_start=proof["owner"]["fixedSourceStart"]
    owner_mesh=base.Normalizer(data,owner_start).normalize()
    owner_mesh["expandedSha256"]=hashlib.sha256(data).hexdigest()
    return build_from_owner(data,target_start,skeleton,owner_mesh)


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("expanded",type=Path); ap.add_argument("--asset-start",required=True,type=lambda x:int(x,0)); ap.add_argument("--skeleton",type=Path,required=True); ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); data=a.expanded.read_bytes(); sk=load_json(a.skeleton); out=normalize_mesh(data,a.asset_start,sk)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"out":str(a.out),"name":out["identity"]["name"],"surfaces":len(out["surfaces"]),"vertices":out["summary"]["vertices"],"triangles":out["summary"]["triangles"],"reuseMode":out["reuseProof"]["mode"]},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
