#!/usr/bin/env python3
"""Ingest t6-material-dependency-graph-v1 into the persistent retail index.

Full local Material records become authoritative definitions using the exact
serialized interval and SHA-256 already replayed from retail bytes. Strict
zero-body import stubs become references only.  This preserves the fundamental
reference-vs-definition boundary across dependency zones.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_retail_asset_index_v1 import (
    AssetDefinition,
    AssetIndexError,
    AssetReference,
    RetailAssetIndex,
    ZoneFingerprint,
)

FORMAT = "t6-material-dependency-graph-v1"


def build(index: RetailAssetIndex, graph: dict) -> dict:
    if graph.get("format") != FORMAT:
        raise AssetIndexError(f"expected {FORMAT}, got {graph.get('format')!r}")
    zone = str(graph.get("zone") or "")
    src = graph.get("source") or {}
    if not zone or not src.get("expandedSha256") or src.get("expandedBytes") is None:
        raise AssetIndexError("dependency graph lacks exact zone fingerprint")
    index.add_zone(ZoneFingerprint(zone, str(src["expandedSha256"]).lower(), int(src["expandedBytes"])))

    local = imports = 0
    for row in graph.get("materials") or []:
        name = str(row.get("material") or "")
        cls = row.get("classification")
        if not name:
            raise AssetIndexError("Material graph row lacks identity")
        if cls == "local_definition":
            d = AssetDefinition(
                asset_type="material",
                name=name,
                zone=zone,
                start=int(row["start"]),
                end=int(row["end"]),
                sha256=str(row["serializedSha256"]).lower(),
                metadata={
                    "producerFormat": FORMAT,
                    "classification": cls,
                    "textureCount": int(row.get("textureCount", 0)),
                    "constantCount": int(row.get("constantCount", 0)),
                    "stateBitsCount": int(row.get("stateBitsCount", 0)),
                    "techniqueSetPointer": row.get("techniqueSetPointer"),
                    "startEvidence": row.get("startEvidence"),
                },
            )
            index.add_definition(d)
            local += 1
        elif cls == "import_stub":
            index.add_reference(AssetReference(
                asset_type="material",
                name=name,
                source_zone=zone,
                source_asset=None,
                owner_start=int(row["start"]),
                proof={
                    "kind": "strict-zero-body-material-import-stub",
                    "producerFormat": FORMAT,
                    "stubEnd": int(row["end"]),
                    "serializedSha256": str(row["serializedSha256"]).lower(),
                    "startEvidence": row.get("startEvidence"),
                },
            ))
            imports += 1
        else:
            raise AssetIndexError(f"{name}: unknown Material classification {cls!r}")

    return {
        "format": "t6-material-dependency-index-ingest-v1",
        "zone": zone,
        "localDefinitionsAdded": local,
        "importReferencesAdded": imports,
        "indexSummary": index.as_dict()["summary"],
        "referenceDefinitionBoundaryPreserved": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("graph", type=Path)
    ap.add_argument("--index", type=Path)
    ap.add_argument("--out-index", type=Path, required=True)
    ap.add_argument("--out-proof", type=Path, required=True)
    a = ap.parse_args()
    graph = json.loads(a.graph.read_text(encoding="utf-8"))
    index = RetailAssetIndex.load(a.index) if a.index and a.index.exists() else RetailAssetIndex()
    proof = build(index, graph)
    index.save(a.out_index)
    a.out_proof.parent.mkdir(parents=True, exist_ok=True)
    a.out_proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
