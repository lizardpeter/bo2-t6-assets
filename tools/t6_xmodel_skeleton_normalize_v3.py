#!/usr/bin/env python3
"""T6 XModel skeleton normalizer v3 with packed top-level surface alias proof.

v2 resolves packed skeleton arrays by replaying a unique earlier inline owner and
uses inline target XSurface scalar records as an additional signature. v3 adds a
narrow second shape for targets whose skeleton arrays *and* top-level XModel.surfs
pointer are packed VIRTUAL aliases to the same earlier owner.

The packed boneNames offset anchors the owner's VIRTUAL allocation base. v3
replays all six skeleton allocations and the aligned XSurface fixed-array
allocation. Promotion requires every target skeleton pointer and target surfs
pointer to equal the exact predicted VIRTUAL offsets.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-xmodel-skeleton-normalized-v3"
FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE


def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise RuntimeError(f"cannot import {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def _u32(data:bytes,off:int)->int: return struct.unpack_from("<I",data,off)[0]
def _align(v:int,a:int)->int: return (v+(a-1))&~(a-1)
def _alloc(cur:int,align:int,size:int):
    start=_align(cur,align); return start,start+size

def ptr_kind(raw:int)->dict[str,Any]:
    if raw==0:return {"kind":"null","raw":raw}
    if raw==FOLLOWING:return {"kind":"following","raw":raw}
    if raw==INSERT:return {"kind":"insert","raw":raw}
    enc=(raw-1)&0xffffffff; return {"kind":"packed","raw":raw,"block":enc>>29,"offset":enc&0x1fffffff}

def packed_virtual(raw:int)->int|None:
    p=ptr_kind(raw); return int(p["offset"]) if p.get("kind")=="packed" and p.get("block")==5 else None

def _sections(walk:dict[str,Any]):
    out={}
    for s in walk.get("sections",[]):
        n=s.get("name")
        if isinstance(n,str): out.setdefault(n,[]).append(s)
    return out

def _one(sec,name):
    rows=sec.get(name,[])
    if len(rows)!=1:return None
    return rows[0]

def _record(comps:list,field:str,raw:int,predicted:int)->bool:
    actual=packed_virtual(raw)
    if actual is None:return False
    ok=actual==predicted
    comps.append({"field":field,"predictedOffset":predicted,"actualOffset":actual,"match":ok})
    return ok


def replay_owner_signature_top_surfs(data:bytes,owner_start:int,target_start:int,*,walker_cls)->dict[str,Any]|None:
    """Prove skeleton + packed top-level surfs alias to one earlier inline owner."""
    try:
        tw=walker_cls(data,target_start).walk_xmodel(); ow=walker_cls(data,owner_start).walk_xmodel()
    except Exception:
        return None
    if tw.get("blockers") or ow.get("blockers"): return None
    tx=tw.get("xmodel") or {}; ox=ow.get("xmodel") or {}
    key=lambda x:(int(x.get("numBones",-1)),int(x.get("numRootBones",-1)),int(x.get("numSurfs",-1)))
    if key(tx)!=key(ox): return None
    n,roots,ns=key(tx); nr=n-roots
    if n<0 or roots<0 or nr<0 or ns<0:return None

    owner_sections=_sections(ow)
    required=["XModel.boneNames","XModel.partClassification","XModel.baseMat","XModel.surfs.fixed"]
    if nr: required += ["XModel.parentList","XModel.quats","XModel.trans"]
    if any(_one(owner_sections,k) is None for k in required): return None

    fields=[
        ("boneNames",8,2,n*2),("parentList",12,1,nr),("quats",16,2,nr*8),
        ("trans",20,4,nr*16),("partClassification",24,1,n),("baseMat",28,4,n*32),
    ]
    # This proof shape is intentionally all-or-nothing: every non-empty skeleton
    # allocation must be a packed VIRTUAL alias to the same owner.
    for _,off,_,size in fields:
        if size and packed_virtual(_u32(data,target_start+off)) is None:return None
    if packed_virtual(_u32(data,target_start+32)) is None:return None
    # Owner must actually allocate these arrays and XSurface fixed records inline.
    for _,off,_,size in fields:
        if size and _u32(data,owner_start+off) not in (FOLLOWING,INSERT):return None
    if _u32(data,owner_start+32) not in (FOLLOWING,INSERT):return None

    base=packed_virtual(_u32(data,target_start+8))
    if base is None:return None
    cur=base; comps=[]
    for field,off,align,size in fields:
        if not size: continue
        start,cur=_alloc(cur,align,size)
        if not _record(comps,f"XModel.{field}",_u32(data,target_start+off),start):return None
    surfs_start,cur=_alloc(cur,16,ns*80)
    if not _record(comps,"XModel.surfs",_u32(data,target_start+32),surfs_start):return None
    return {
        "ownerFixedStart":owner_start,"targetFixedStart":target_start,"virtualReplayBase":base,
        "comparisonCount":len(comps),"surfaceComparisonCount":1,"comparisons":comps,"allMatch":True,
        "topLevelSurfsAlias":True,"topLevelSurfsPredictedOffset":surfs_start,
        "ownerWalk":ow,"targetWalk":tw,
    }


def resolve_reusable_owner_top_surfs(data:bytes,target_start:int,target_asset_index:int,*,base_module,walker_cls)->dict[str,Any]:
    catalog=base_module.build_xmodel_catalog(data,target_asset_index)
    matches=[]
    for idx in sorted(catalog):
        if idx>=target_asset_index:break
        rec=catalog[idx]
        proof=replay_owner_signature_top_surfs(data,int(rec["fixedSourceStart"]),target_start,walker_cls=walker_cls)
        if proof:
            proof["ownerAssetIndex"]=int(idx); proof["ownerName"]=rec.get("name"); matches.append(proof)
    if len(matches)!=1:
        slim=[{"assetIndex":x["ownerAssetIndex"],"name":x.get("ownerName"),"surfsOffset":x.get("topLevelSurfsPredictedOffset")} for x in matches]
        raise ValueError(f"top-level-surfs reusable skeleton owner is not unique: {slim}")
    return matches[0]


def normalize_skeleton(data:bytes,asset_start:int,*,xasset_index:int|None=None,identity_name:str|None=None,base_module=None,walker_cls=None)->dict[str,Any]:
    here=Path(__file__).resolve().parent
    base=base_module or load_module(here/"t6_xmodel_skeleton_normalize_v2.py","t6_skeleton_v3_base")
    if walker_cls is None: walker_cls=base.XModelWalker
    bone_packed=packed_virtual(_u32(data,asset_start+8)) is not None
    surfs_packed=packed_virtual(_u32(data,asset_start+32)) is not None
    used_top=False
    if bone_packed and surfs_packed:
        if xasset_index is None: raise ValueError("packed skeleton/surfs reuse requires --xasset-index")
        old=base.resolve_reusable_owner
        try:
            base.resolve_reusable_owner=lambda d,s,i: resolve_reusable_owner_top_surfs(d,s,i,base_module=base,walker_cls=walker_cls)
            out=base.normalize_skeleton(data,asset_start,xasset_index=xasset_index,identity_name=identity_name)
            used_top=True
        finally:
            base.resolve_reusable_owner=old
    else:
        out=base.normalize_skeleton(data,asset_start,xasset_index=xasset_index,identity_name=identity_name)
    out=dict(out); out["format"]=FORMAT; source=dict(out.get("skeletonSource") or {})
    source["baseNormalizerFormat"]="t6-xmodel-skeleton-normalized-v2"
    if used_top:
        source["mode"]="packed_reusable_owner_top_level_surfs"
        comps=source.get("comparisons") or []
        rows=[r for r in comps if isinstance(r,dict) and r.get("field")=="XModel.surfs"]
        if len(rows)!=1 or rows[0].get("match") is not True:
            raise ValueError("top-level surfs replay comparison was lost during skeleton normalization")
        source["topLevelSurfsComparison"]=rows[0]
        source["topLevelSurfsAliasProven"]=True
    else:
        source["topLevelSurfsAliasProven"]=False
    out["skeletonSource"]=source
    val=dict(out.get("validation") or {}); val["packedTopLevelSurfsAliasProof"]="exact-relative-VIRTUAL-replay" if used_top else "not-used"; out["validation"]=val
    return out


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("expanded",type=Path); ap.add_argument("--asset-start",required=True,type=lambda x:int(x,0)); ap.add_argument("--xasset-index",type=int); ap.add_argument("--name"); ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); data=a.expanded.read_bytes(); out=normalize_skeleton(data,a.asset_start,xasset_index=a.xasset_index,identity_name=a.name)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"out":str(a.out),"format":out["format"],"identity":out["identity"],"numBones":out["skeleton"]["numBones"],"sourceMode":out["skeletonSource"]["mode"],"topLevelSurfsAliasProven":out["skeletonSource"].get("topLevelSurfsAliasProven")},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
