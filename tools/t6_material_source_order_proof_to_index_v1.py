#!/usr/bin/env python3
"""Ingest exact Material definitions from t6-material-source-order-proof-v1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_retail_asset_index_v1 import AssetDefinition, AssetIndexError, RetailAssetIndex, ZoneFingerprint

FORMAT="t6-material-source-order-proof-v1"


def build(index:RetailAssetIndex,proof:dict)->dict:
    if proof.get("format")!=FORMAT:raise AssetIndexError(f"expected {FORMAT}, got {proof.get('format')!r}")
    if (proof.get("summary") or {}).get("allSourceOrderPathsExact") is not True:raise AssetIndexError("source-order proof is not exact")
    zone=str(proof.get("zone") or "");src=proof.get("source") or {}
    if not zone or src.get("expandedBytes") is None or not src.get("expandedSha256"):raise AssetIndexError("proof lacks zone fingerprint")
    index.add_zone(ZoneFingerprint(zone,str(src["expandedSha256"]).lower(),int(src["expandedBytes"])))
    made=[]
    for row in proof.get("materials") or []:
        name=str(row.get("material") or "");d=row.get("definition") or {}
        if not name or d.get("xassetType")!="MATERIAL":raise AssetIndexError(f"bad definition row for {name!r}")
        obj=AssetDefinition(
            "material",name,zone,int(d["start"]),int(d["end"]),str(d["serializedSha256"]).lower(),
            {"producerFormat":FORMAT,"xassetIndex":int(d["xassetIndex"]),"textureCount":int(d.get("textureCount",0)),"constantCount":int(d.get("constantCount",0)),"stateBitsCount":int(d.get("stateBitsCount",0)),"techniqueSetPointer":d.get("techniqueSetPointer"),"anchorGroup":row.get("anchorGroup")}
        )
        index.add_definition(obj);made.append(obj)
    return {"format":"t6-material-source-order-index-ingest-v1","zone":zone,"definitionsAdded":len(made),"materials":sorted(x.name for x in made),"indexSummary":index.as_dict()["summary"]}


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("proof",type=Path);ap.add_argument("--index",type=Path,required=True);ap.add_argument("--out-index",type=Path,required=True);ap.add_argument("--out-proof",type=Path,required=True);a=ap.parse_args()
    index=RetailAssetIndex.load(a.index);proof=json.loads(a.proof.read_text(encoding="utf-8"));out=build(index,proof);index.save(a.out_index);a.out_proof.parent.mkdir(parents=True,exist_ok=True);a.out_proof.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(out,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
