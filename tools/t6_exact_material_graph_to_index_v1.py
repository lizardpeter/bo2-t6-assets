#!/usr/bin/env python3
"""Promote independently proven T6 Material/TechniqueSet starts into the retail index.

This is deliberately a second proof stage.  A caller must already have an exact
binding proof naming each Material raw start and its resolved TechniqueSet raw
start.  This tool then replays the source-closed serializers at those starts,
verifies the serialized names, computes complete serialized extents and hashes,
and only then adds authoritative definitions to t6-retail-asset-index-v1.

It never consumes XModel handle-owner offsets as definition starts directly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_material_techset_top_level_walk_v1 import Cursor, parse_front
from t6_retail_asset_index_v1 import (
    AssetDefinition,
    AssetIndexError,
    RetailAssetIndex,
    StaleIndexError,
    ZoneFingerprint,
)


def canonical(name: str) -> str:
    return name[1:] if name.startswith(",") else name


def exact_name(node: dict) -> str:
    raw = node.get("name")
    if isinstance(raw, dict):
        raw = raw.get("value")
    if not isinstance(raw, str) or not raw:
        raise AssetIndexError(f"serializer did not recover an exact inline name: {raw!r}")
    return raw


def require_source_identity(proof: dict, zone: str, data: bytes) -> ZoneFingerprint:
    src = proof.get("source") or {}
    expected_size = src.get("expandedBytes")
    expected_sha = src.get("expandedSha256")
    if expected_size is None or not isinstance(expected_sha, str):
        raise AssetIndexError("binding proof lacks exact expandedBytes/expandedSha256")
    actual = ZoneFingerprint.from_bytes(zone, data)
    if int(expected_size) != actual.size or expected_sha.lower() != actual.sha256:
        raise StaleIndexError(
            f"{zone}: binding proof source mismatch: expected {expected_size}/{expected_sha}, "
            f"got {actual.size}/{actual.sha256}"
        )
    return actual


def add_definition(index: RetailAssetIndex, data: bytes, zone: str, asset_type: str,
                   name: str, start: int, end: int, metadata: dict) -> AssetDefinition:
    if start < 0 or end <= start or end > len(data):
        raise AssetIndexError(f"invalid {asset_type} extent {start}..{end} for {name}")
    d = AssetDefinition(
        asset_type=asset_type,
        name=canonical(name),
        zone=zone,
        start=start,
        end=end,
        sha256=hashlib.sha256(data[start:end]).hexdigest(),
        metadata=metadata,
    )
    index.add_definition(d)
    return d


def build(index: RetailAssetIndex, data: bytes, proof: dict, zone: str) -> dict:
    if proof.get("format") not in {
        "t6-seal6-material-technique-binding-proof-v2",
        "t6-material-technique-binding-proof-v1",
    }:
        raise AssetIndexError(f"unsupported exact binding proof format {proof.get('format')!r}")
    summary = proof.get("summary") or {}
    if proof.get("format") == "t6-seal6-material-technique-binding-proof-v2":
        if summary.get("all13MaterialStartsExact") is not True:
            raise AssetIndexError("SEAL6 binding proof does not certify exact Material starts")
        if summary.get("allTechniqueSetBindingsExact") is not True:
            raise AssetIndexError("SEAL6 binding proof does not certify exact TechniqueSet bindings")

    fp = require_source_identity(proof, zone, data)
    index.add_zone(fp)
    blocks, _assets, _body = parse_front(data)

    bindings = proof.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        raise AssetIndexError("binding proof has no bindings")

    materials: list[AssetDefinition] = []
    techsets_by_start: dict[int, AssetDefinition] = {}
    seen_material_starts: dict[int, str] = {}

    for row in bindings:
        expected_material = canonical(str(row.get("material") or ""))
        if not expected_material:
            raise AssetIndexError("binding row lacks Material identity")
        material_start = int(row["materialRawStart"])
        previous = seen_material_starts.get(material_start)
        if previous is not None and previous != expected_material:
            raise AssetIndexError(
                f"Material start {material_start} claimed by both {previous!r} and {expected_material!r}"
            )
        seen_material_starts[material_start] = expected_material

        mc = Cursor(data, material_start, blocks)
        material_node = mc.material()
        serialized_material = exact_name(material_node)
        if canonical(serialized_material) != expected_material:
            raise AssetIndexError(
                f"Material identity mismatch at {material_start}: {serialized_material!r} != {expected_material!r}"
            )
        material_end = mc.p
        materials.append(add_definition(
            index, data, zone, "material", expected_material, material_start, material_end,
            {
                "producer": "t6_exact_material_graph_to_index_v1.py",
                "bindingProofFormat": proof.get("format"),
                "serializedName": serialized_material,
                "textureCount": int(material_node.get("textureCount", 0)),
                "constantCount": int(material_node.get("constantCount", 0)),
                "stateBitsCount": int(material_node.get("stateBitsCount", 0)),
                "techniqueSetPointer": material_node.get("techniqueSetPointer"),
                "bindingTechniqueSet": row.get("techniqueSet"),
                "proofMaterialFixedSha256": row.get("materialFixedSha256"),
            },
        ))

        tech_start = int(row["techniqueSetRawStart"])
        expected_tech = canonical(str(row.get("techniqueSet") or ""))
        if not expected_tech:
            raise AssetIndexError(f"{expected_material}: binding row lacks TechniqueSet identity")
        existing = techsets_by_start.get(tech_start)
        if existing is not None:
            if existing.name != expected_tech:
                raise AssetIndexError(
                    f"TechniqueSet start {tech_start} claimed by {existing.name!r} and {expected_tech!r}"
                )
            continue

        tc = Cursor(data, tech_start, blocks)
        tech_node = tc.techset()
        serialized_tech = exact_name(tech_node)
        if canonical(serialized_tech) != expected_tech:
            raise AssetIndexError(
                f"TechniqueSet identity mismatch at {tech_start}: {serialized_tech!r} != {expected_tech!r}"
            )
        tech = add_definition(
            index, data, zone, "material_technique_set", expected_tech, tech_start, tc.p,
            {
                "producer": "t6_exact_material_graph_to_index_v1.py",
                "bindingProofFormat": proof.get("format"),
                "serializedName": serialized_tech,
                "worldVertFormat": int(tech_node.get("worldVertFormat", 0)),
                "techniqueRefCount": len(tech_node.get("techniqueRefs") or []),
                "proofTechniqueSetFixedSha256": row.get("techniqueSetFixedSha256"),
            },
        )
        techsets_by_start[tech_start] = tech

    resolved = []
    for m in materials:
        r = index.resolve("material", m.name, [zone])
        if r.start != m.start or r.sha256 != m.sha256:
            raise AssetIndexError(f"post-index Material resolution mismatch for {m.name}")
        resolved.append(m.name)

    return {
        "format": "t6-exact-material-graph-index-proof-v1",
        "zone": zone,
        "source": fp.as_dict(),
        "materialDefinitions": len(materials),
        "uniqueMaterialDefinitions": len({m.name for m in materials}),
        "techniqueSetDefinitions": len(techsets_by_start),
        "resolvedMaterials": sorted(set(resolved)),
        "allMaterialDefinitionsReplayed": True,
        "allTechniqueSetDefinitionsReplayed": True,
        "definitionStartsDerivedFromBindingProofNotHandleOwners": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("binding_proof", type=Path)
    ap.add_argument("--zone", required=True)
    ap.add_argument("--index", type=Path)
    ap.add_argument("--out-index", type=Path, required=True)
    ap.add_argument("--out-proof", type=Path, required=True)
    a = ap.parse_args()

    data = a.expanded.read_bytes()
    proof = json.loads(a.binding_proof.read_text(encoding="utf-8"))
    index = RetailAssetIndex.load(a.index) if a.index and a.index.exists() else RetailAssetIndex()
    result = build(index, data, proof, a.zone)
    index.save(a.out_index)
    a.out_proof.parent.mkdir(parents=True, exist_ok=True)
    a.out_proof.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
