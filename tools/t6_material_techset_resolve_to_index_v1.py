#!/usr/bin/env python3
"""Ingest t6-material-techset-resolve-v1 into the persistent retail index."""
from __future__ import annotations

import argparse,json
from pathlib import Path
from t6_retail_asset_index_v1 import AssetDefinition,AssetIndexError,AssetReference,RetailAssetIndex,ZoneFingerprint

FORMAT="t6-material-techset-resolve-v1"

def build(index:RetailAssetIndex,proof:dict)->dict:
    if proof.get("format")!=FORMAT:raise AssetIndexError(f"expected {FORMAT}, got {proof.get('format')!r}")
    if (proof.get("summary") or {}).get("allBindingsExact") is not True:raise AssetIndexError("TechniqueSet proof not exact")
    zone=str(proof.get("zone") or "");src=proof.get("source") or {}
    index.add_zone(ZoneFingerprint(zone,str(src["expandedSha256"]).lower(),int(src["expandedBytes"])))
    defs=0;refs=0
    for d in proof.get("techniqueSets") or []:
        index.add_definition(AssetDefinition(
            "material_technique_set",str(d["name"]),zone,int(d["start"]),int(d["end"]),str(d["serializedSha256"]).lower(),
            {"producerFormat":FORMAT,"xassetIndex":int(d["xassetIndex"]),"worldVertFormat":int(d.get("worldVertFormat",0)),"techniqueRefCount":int(d.get("techniqueRefCount",0))}
        ));defs+=1
    for b in proof.get("bindings") or []:
        index.add_reference(AssetReference(
            "material_technique_set",str(b["techniqueSet"]),zone,str(b["material"]),int(b["materialStart"]),
            {"kind":"material-techniqueset-packed-xasset-lattice","virtualOffset":int(b["techniqueSetPointerVirtualOffset"]),"xassetIndex":int(b["techniqueSetXAssetIndex"]),"definitionSha256":str(b["techniqueSetSha256"]).lower()}
        ));refs+=1
    return {"format":"t6-material-techset-index-ingest-v1","zone":zone,"definitionsAdded":defs,"referencesAdded":refs,"indexSummary":index.as_dict()["summary"]}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("proof",type=Path);ap.add_argument("--index",type=Path,required=True);ap.add_argument("--out-index",type=Path,required=True);ap.add_argument("--out-proof",type=Path,required=True);a=ap.parse_args();idx=RetailAssetIndex.load(a.index);p=json.loads(a.proof.read_text(encoding="utf-8"));o=build(idx,p);idx.save(a.out_index);a.out_proof.parent.mkdir(parents=True,exist_ok=True);a.out_proof.write_text(json.dumps(o,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(o,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
