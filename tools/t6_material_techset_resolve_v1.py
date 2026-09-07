#!/usr/bin/env python3
"""Resolve exact Material -> MaterialTechniqueSet dependencies for a retail T6 zone.

The input Material report must already prove full local Material definitions and
retain each serialized Material::techniqueSet packed VIRTUAL pointer. This tool:

1. independently derives the top-level XAsset-array VIRTUAL base by replaying
   T6 XAssetList front allocations (ScriptStrings, dependencies, then XAssets),
2. requires every target Material pointer to land on that exact XAsset lattice,
3. maps each pointer to an exact inline type-7 XAsset index,
4. independently enumerates every inline top-level TechniqueSet serialization in
   source order and requires a 1:1 count with inline type-7 XAsset headers,
5. replays the full source-closed TechniqueSet serializer at the resolved start,
   including techniques, passes, shaders, vertex declarations and arguments,
6. hashes the complete serialized TechniqueSet extent.

No TechniqueSet is chosen from its name or Material naming convention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from t6_asset_types_v1 import TECHNIQUE_SET
from t6_material_techset_top_level_walk_v1 import Cursor, FOLLOW, INSERT, dec, parse_front
from t6_xasset_virtual_layout_v1 import derive_xasset_array_virtual_base

FORMAT="t6-material-techset-resolve-v1"

class ResolveError(RuntimeError):pass

def sha256(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def canonical(s:str)->str:return s[1:] if s.startswith(",") else s

def node_name(node:dict[str,Any])->str:
    x=node.get("name")
    if isinstance(x,dict):x=x.get("value")
    if not isinstance(x,str) or not x:raise ResolveError(f"node lacks exact name: {x!r}")
    return x


def report_materials(report:dict)->tuple[dict[str,Any],list[dict[str,Any]]]:
    fmt=report.get("format");src=report.get("source") or {};rows=[]
    if fmt=="t6-material-dependency-graph-v1":
        for x in report.get("materials") or []:
            if x.get("classification")!="local_definition":continue
            rows.append({"material":canonical(str(x["material"])),"start":int(x["start"]),"techniqueSetPointer":x["techniqueSetPointer"]})
    elif fmt=="t6-material-source-order-proof-v1":
        for x in report.get("materials") or []:
            d=x.get("definition") or {}
            rows.append({"material":canonical(str(x["material"])),"start":int(d["start"]),"techniqueSetPointer":d["techniqueSetPointer"]})
    else:raise ResolveError(f"unsupported Material report format {fmt!r}")
    if not rows:raise ResolveError("Material report has no local definitions")
    return src,rows


def scan_inline_techsets(data:bytes,blocks:tuple[int,...])->list[dict[str,Any]]:
    """Strict full-parser scan of inline TechniqueSet serialized records."""
    out=[];rx=re.compile(r"[A-Za-z0-9_./$@+~:#,-]+")
    off=64
    while True:
        off=data.find(b"\xff\xff\xff\xff",off)
        if off<0:break
        if off+152>=len(data):break
        if int.from_bytes(data[off:off+4],"little") not in (FOLLOW,INSERT):off+=1;continue
        world=data[off+4]
        if world>8 or data[off+5:off+8]!=b"\0\0\0":off+=1;continue
        ok=True;nonnull=0
        for i in range(36):
            raw=int.from_bytes(data[off+8+4*i:off+12+4*i],"little")
            if raw:
                nonnull+=1
                try:p=dec(raw,blocks)
                except Exception:ok=False;break
                if p.get("kind") not in ("packed","following","insert"):ok=False;break
        if not ok or not nonnull:off+=1;continue
        try:
            e=data.find(b"\0",off+152,min(len(data),off+152+512))
            if e<0:raise ValueError
            name=data[off+152:e].decode("latin1")
            if not name or not rx.fullmatch(name):raise ValueError
            c=Cursor(data,off,blocks);node=c.techset();got=node_name(node)
            if got!=name:raise ValueError
        except Exception:
            off+=1;continue
        out.append({"start":off,"end":c.p,"name":name,"worldVertFormat":int(node.get("worldVertFormat",0)),"techniqueRefCount":len(node.get("techniqueRefs") or [])})
        off+=152
    return out


def solve_base(rows:list[dict[str,Any]],assets:list[dict[str,Any]],expected_base:int)->tuple[int,list[int]]:
    # Full local Materials in this resolver must target inline type-7 XAssets.
    # Pointer intersections remain a useful cross-check, but they no longer get
    # to choose the base: the XAsset array base is independently derived from
    # the T6 XAssetList loader's VIRTUAL allocation order.
    q={i for i,a in enumerate(assets) if int(a["type"])==TECHNIQUE_SET and int(a["headerRaw"]) in (FOLLOW,INSERT)}
    if not q:raise ResolveError("zone has no inline TechniqueSet XAssets")
    sets=[]
    for row in rows:
        p=row.get("techniqueSetPointer")
        if not isinstance(p,dict) or p.get("kind")!="packed" or int(p.get("block",-1))!=5:
            raise ResolveError(f"{row['material']}: TechniqueSet pointer is not packed VIRTUAL: {p!r}")
        off=int(p["offset"]);sets.append({off-4-8*i for i in q})
    shared=sorted(x for x in set.intersection(*sets) if x>=0)
    if expected_base not in shared:
        raise ResolveError(
            f"loader-derived XAsset VIRTUAL base {expected_base} is not compatible with Material pointers; candidates={shared}"
        )
    return expected_base,shared


def build(expanded:Path,report_path:Path,zone:str)->dict[str,Any]:
    data=expanded.read_bytes();digest=sha256(data);report=json.loads(report_path.read_text(encoding="utf-8-sig"));src,materials=report_materials(report)
    if int(src.get("expandedBytes",-1))!=len(data) or str(src.get("expandedSha256") or "").lower()!=digest:raise ResolveError("Material report source fingerprint mismatch")
    blocks,assets,_=parse_front(data)
    layout=derive_xasset_array_virtual_base(data)
    base,candidates=solve_base(materials,assets,int(layout["xassetArrayVirtualBase"]))
    inline_q=[i for i,a in enumerate(assets) if int(a["type"])==TECHNIQUE_SET and int(a["headerRaw"]) in (FOLLOW,INSERT)]
    scanned=scan_inline_techsets(data,blocks)
    if len(scanned)!=len(inline_q):raise ResolveError(f"inline TechniqueSet parser count {len(scanned)} != inline XAsset count {len(inline_q)}")
    by_q={q:scanned[n] for n,q in enumerate(inline_q)}
    bindings=[];defs={}
    for row in materials:
        off=int(row["techniqueSetPointer"]["offset"]);delta=off-base-4
        if delta<0 or delta%8:raise ResolveError(f"{row['material']}: TechniqueSet pointer misses XAsset lattice")
        q=delta//8
        if q>=len(assets) or int(assets[q]["type"])!=TECHNIQUE_SET:raise ResolveError(f"{row['material']}: resolved XAsset {q} is not TechniqueSet")
        if int(assets[q]["headerRaw"]) not in (FOLLOW,INSERT):raise ResolveError(f"{row['material']}: TechniqueSet XAsset {q} is imported/packed; dependency replay required")
        s=by_q.get(q)
        if s is None:raise ResolveError(f"{row['material']}: no serialized TechniqueSet for XAsset {q}")
        c=Cursor(data,int(s["start"]),blocks);node=c.techset();name=node_name(node)
        if c.p!=int(s["end"]):raise ResolveError(f"TechniqueSet XAsset {q}: replay extent changed")
        d={"xassetIndex":q,"name":name,"start":int(s["start"]),"end":c.p,"serializedBytes":c.p-int(s["start"]),"serializedSha256":sha256(data[int(s["start"]):c.p]),"worldVertFormat":int(node.get("worldVertFormat",0)),"techniqueRefCount":len(node.get("techniqueRefs") or []),"node":node}
        old=defs.get(q)
        if old is not None and (old["start"],old["serializedSha256"])!=(d["start"],d["serializedSha256"]):raise ResolveError(f"TechniqueSet XAsset {q}: conflicting replay")
        defs[q]=d
        bindings.append({"material":row["material"],"materialStart":row["start"],"techniqueSetPointerVirtualOffset":off,"techniqueSetXAssetIndex":q,"techniqueSet":name,"techniqueSetStart":d["start"],"techniqueSetSha256":d["serializedSha256"]})
    return {"format":FORMAT,"zone":zone,"source":{"expandedBytes":len(data),"expandedSha256":digest},"xassetVirtualLayout":layout,"xassetPointerFieldVirtualBase":base,"pointerIntersectionCandidateBases":candidates,"bindings":bindings,"techniqueSets":[defs[q] for q in sorted(defs)],"summary":{"materials":len(bindings),"uniqueTechniqueSets":len(defs),"inlineTechniqueSetXAssets":len(inline_q),"allBindingsExact":True,"xassetBaseDerivedFromLoaderOrder":True},"proofBoundary":"Material::techniqueSet is resolved through its packed VIRTUAL offset onto the exact inline type-7 XAsset pointer-field lattice. The XAsset-array VIRTUAL base is independently derived by replaying T6 XAssetList loader allocation order; the 24-byte fixed XAssetList is loaded before XFILE_BLOCK_VIRTUAL and therefore contributes zero block bytes. Serialized TechniqueSet identity/start is assigned by a fail-closed 1:1 inline type-7 XAsset/source-order census and then fully replayed with the source-closed serializer."}


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("expanded",type=Path);ap.add_argument("material_report",type=Path);ap.add_argument("--zone",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();out=build(a.expanded,a.material_report,a.zone);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(out["summary"],indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
