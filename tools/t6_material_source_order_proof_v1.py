#!/usr/bin/env python3
"""Prove exact T6 Material definitions by replaying top-level XAsset source order.

This consumes:
- exact expanded retail bytes,
- a retained source-order anchor manifest whose anchor raw starts are already
  closed against exact contiguous XAsset runs,
- a small declarative spec listing only consecutive XAsset indices/types to
  replay from each anchor.

No post-anchor raw start is supplied. Each next start is the exact serialized end
of the preceding source-closed TechniqueSet/Material parser. The XAsset table is
checked at every index and must be inline. The final Material identity is read
from retail bytes and must match the requested target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_asset_types_v1 import MATERIAL, TECHNIQUE_SET
from t6_material_techset_top_level_walk_v1 import Cursor, FOLLOW, INSERT, parse_front

FORMAT = "t6-material-source-order-proof-v1"
SPEC_FORMAT = "t6-material-source-order-spec-v1"


class ProofError(RuntimeError): pass


def sha256(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def canonical(s: str) -> str: return s[1:] if s.startswith(",") else s

def node_name(node: dict[str, Any]) -> str:
    x=node.get("name")
    if isinstance(x,dict): x=x.get("value")
    if not isinstance(x,str) or not x: raise ProofError(f"node lacks exact inline name: {x!r}")
    return x


def parse_node(kind: str, data: bytes, blocks: tuple[int,...], start: int) -> tuple[dict[str,Any],int]:
    c=Cursor(data,start,blocks)
    if kind=="MATERIAL": node=c.material()
    elif kind=="TECHNIQUE_SET": node=c.techset()
    else: raise ProofError(f"unsupported source-order type {kind!r}")
    return node,c.p


def type_id(kind: str) -> int:
    if kind=="MATERIAL": return MATERIAL
    if kind=="TECHNIQUE_SET": return TECHNIQUE_SET
    raise ProofError(f"unsupported type {kind!r}")


def build(expanded: Path, anchors_path: Path, spec_path: Path) -> dict[str,Any]:
    data=expanded.read_bytes(); digest=sha256(data)
    spec=json.loads(spec_path.read_text(encoding="utf-8-sig"))
    if spec.get("format")!=SPEC_FORMAT: raise ProofError("unexpected spec format")
    src=spec.get("source") or {}
    if int(src.get("expandedBytes",-1))!=len(data) or str(src.get("expandedSha256") or "").lower()!=digest:
        raise ProofError("spec source fingerprint mismatch")
    anchors=json.loads(anchors_path.read_text(encoding="utf-8-sig"))
    asrc=anchors.get("source") or {}
    if int(asrc.get("expandedBytes",-1))!=len(data) or str(asrc.get("expandedSha256") or "").lower()!=digest:
        raise ProofError("anchor proof source fingerprint mismatch")
    groups={str(g["name"]):g for g in anchors.get("groups") or []}
    blocks,assets,_=parse_front(data)
    results=[]
    for target in spec.get("targets") or []:
        material=canonical(str(target.get("material") or "")); group_name=str(target.get("anchorGroup") or "")
        if not material or group_name not in groups: raise ProofError(f"bad target/group: {target!r}")
        anchor=groups[group_name].get("anchor") or {}
        seq=target.get("assetSequence") or []
        if not seq: raise ProofError(f"{material}: empty source-order sequence")
        first=seq[0]
        if int(first["xassetIndex"])!=int(anchor["assetIndex"]):
            raise ProofError(f"{material}: first index does not equal retained anchor")
        cursor=int(anchor["rawStart"]); rows=[]
        for n,item in enumerate(seq):
            xi=int(item["xassetIndex"]); kind=str(item["type"])
            if n and xi!=int(seq[n-1]["xassetIndex"])+1:
                raise ProofError(f"{material}: XAsset sequence is not consecutive at {xi}")
            if xi<0 or xi>=len(assets): raise ProofError(f"{material}: XAsset index {xi} out of range")
            asset=assets[xi]
            if int(asset["type"])!=type_id(kind):
                raise ProofError(f"{material}: XAsset {xi} type {asset['type']} != {kind}")
            if int(asset["headerRaw"]) not in (FOLLOW,INSERT):
                raise ProofError(f"{material}: XAsset {xi} is not inline")
            start=cursor; node,end=parse_node(kind,data,blocks,start); got=node_name(node)
            expected=item.get("expectedName")
            if item.get("expectedNameFromAnchor"):
                anchor_name=str(anchor.get("name") or "")
                if expected and canonical(str(expected))!=canonical(anchor_name):
                    raise ProofError(f"{material}: spec expectedName conflicts with anchor name")
                expected=anchor_name
            if expected and canonical(got)!=canonical(str(expected)):
                raise ProofError(f"{material}: XAsset {xi} identity {got!r} != {expected!r}")
            row={
                "xassetIndex":xi,"xassetType":kind,"start":start,"end":end,
                "serializedBytes":end-start,"serializedSha256":sha256(data[start:end]),
                "serializedName":got,
            }
            if kind=="MATERIAL":
                row.update(textureCount=int(node.get("textureCount",0)),constantCount=int(node.get("constantCount",0)),stateBitsCount=int(node.get("stateBitsCount",0)),techniqueSetPointer=node.get("techniqueSetPointer"))
            else:
                row.update(worldVertFormat=int(node.get("worldVertFormat",0)),techniqueRefCount=len(node.get("techniqueRefs") or []))
            rows.append(row); cursor=end
        last=rows[-1]
        if last["xassetType"]!="MATERIAL" or canonical(last["serializedName"])!=material:
            raise ProofError(f"{material}: source-order path does not end at requested Material")
        if int(last["textureCount"])<=0:
            raise ProofError(f"{material}: dependency definition unexpectedly has no textures")
        tp=last.get("techniqueSetPointer")
        if not isinstance(tp,dict) or tp.get("kind") not in ("packed","following","insert"):
            raise ProofError(f"{material}: dependency definition has no TechniqueSet")
        results.append({
            "material":material,"anchorGroup":group_name,"anchorRawStart":int(anchor["rawStart"]),
            "path":rows,"definition":last,
            "allStartsAfterAnchorDerivedBySerializedCursor":True,
        })
    return {
        "format":FORMAT,"zone":str(spec.get("zone") or ""),
        "source":{"expandedBytes":len(data),"expandedSha256":digest},
        "materials":results,
        "summary":{"materialDefinitions":len(results),"allSourceOrderPathsExact":all(x["allStartsAfterAnchorDerivedBySerializedCursor"] for x in results)},
        "proofBoundary":"The first raw start comes only from the retained exact source-order anchor. Every subsequent top-level XAsset start is derived from the exact serialized end of the previous parser, while the retail XAsset index/type/inline mode and serialized identity are checked at every step."
    }


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("expanded",type=Path);ap.add_argument("anchors",type=Path);ap.add_argument("spec",type=Path);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    out=build(a.expanded,a.anchors,a.spec);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(out["summary"],indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
