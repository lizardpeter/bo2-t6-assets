#!/usr/bin/env python3
"""Join the independent SEAL6 TechniqueSet ownership/dependency proofs.

This adapter does not discover offsets, names, or dependencies.  It combines:

1. the exact faction_seals_mp q0..q20 source-order/XAsset-lattice proof,
2. the exact local q20 nested TechniqueSet proof, and
3. the pinned native-OAT Material->TechniqueSet/dependency proof.

Every join key and expected zone is fail-closed.  q10/q17 remain faction source
reference stubs whose canonical definitions must be native common_mp assets;
q20 must remain the full local faction definition.  No scan-ranked candidate is
promoted by this tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-techset-closure-v1"
EXPECTED = {
    10: {
        "name": "mc_sw4_3d_char_cloth_4z8fq5wu",
        "definitionZone": "common_mp",
        "classification": "comma_prefixed_reference_stub",
    },
    17: {
        "name": "mc_sw4_3d_char_skin_j92387z3",
        "definitionZone": "common_mp",
        "classification": "comma_prefixed_reference_stub",
    },
    20: {
        "name": "mc_sw4_3d_char_skin_hero_9949fq1j",
        "definitionZone": "faction_seals_mp",
        "classification": "full_local_definition",
    },
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def by_q(rows: list[dict[str, Any]], field: str) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        q = int(row[field])
        if q in out:
            raise ValueError(f"duplicate q{q}")
        out[q] = row
    return out


def build(source: dict[str, Any], q20: dict[str, Any], native: dict[str, Any]) -> dict[str, Any]:
    if source.get("format") != "t6-seal6-techset-source-order-proof-v1":
        raise ValueError("unexpected source-order proof format")
    if q20.get("format") != "t6-seal6-q20-techset-nested-proof-v1":
        raise ValueError("unexpected q20 nested proof format")
    if native.get("format") != "t6-seal6-native-oat-techset-dependency-proof-v1":
        raise ValueError("unexpected native dependency proof format")
    if native.get("errors"):
        raise ValueError(f"native dependency proof contains errors: {native['errors']!r}")

    src_targets = by_q(source.get("targetTechniqueSets") or [], "xassetIndex")
    native_defs = by_q(native.get("techniqueSetDefinitions") or [], "q")
    if set(src_targets) & set(EXPECTED) != set(EXPECTED):
        raise ValueError("source-order proof is missing a target q")
    if set(native_defs) != set(EXPECTED):
        raise ValueError(f"native definition q set drift: {sorted(native_defs)}")

    expected_materials: dict[str, tuple[int, str]] = {}
    rows = []
    for q in (10, 17, 20):
        spec = EXPECTED[q]
        src = src_targets[q]
        if src.get("canonicalName") != spec["name"]:
            raise ValueError(f"q{q} source canonical name drift")
        if src.get("classification") != spec["classification"]:
            raise ValueError(f"q{q} source classification drift")
        mats = list(src.get("materials") or [])
        if not mats:
            raise ValueError(f"q{q} has no source-bound materials")
        for material in mats:
            if material in expected_materials:
                raise ValueError(f"material occurs under multiple q targets: {material}")
            expected_materials[material] = (q, spec["name"])

        nd = native_defs[q]
        if not nd.get("resolved"):
            raise ValueError(f"q{q} native canonical definition unresolved")
        if nd.get("name") != spec["name"]:
            raise ValueError(f"q{q} native canonical name drift")
        if nd.get("definitionZone") != spec["definitionZone"]:
            raise ValueError(f"q{q} native definition zone drift")
        if int(nd.get("techniqueBindingCount", 0)) <= 0:
            raise ValueError(f"q{q} native definition has no technique bindings")

        row = {
            "xassetIndex": q,
            "canonicalName": spec["name"],
            "factionClassification": spec["classification"],
            "factionSource": {
                "start": int(src["sourceStart"]),
                "end": int(src["sourceEnd"]),
                "bytes": int(src["serializedBytes"]),
                "sha256": src["serializedSha256"],
                "serializedName": src["serializedName"],
            },
            "materials": mats,
            "canonicalDefinition": {
                "zone": spec["definitionZone"],
                "nativeDumpPath": nd["path"],
                "bytes": int(nd["bytes"]),
                "sha256": nd["sha256"],
                "techniqueBindingCount": int(nd["techniqueBindingCount"]),
                "uniqueTechniques": nd.get("uniqueTechniques") or [],
            },
        }
        rows.append(row)

    native_materials = native.get("materials") or []
    if len(native_materials) != len(expected_materials):
        raise ValueError(
            f"native Material row count {len(native_materials)} != expected {len(expected_materials)}"
        )
    seen = set()
    for row in native_materials:
        material = row.get("material")
        if material not in expected_materials:
            raise ValueError(f"unexpected native Material {material!r}")
        if material in seen:
            raise ValueError(f"duplicate native Material {material!r}")
        seen.add(material)
        q, name = expected_materials[material]
        if not row.get("resolved"):
            raise ValueError(f"native Material unresolved: {material}")
        if int(row.get("q", -1)) != q:
            raise ValueError(f"native Material q drift: {material}")
        if row.get("expectedTechniqueSet") != name or row.get("nativeTechniqueSet") != name:
            raise ValueError(f"native Material TechniqueSet drift: {material}")
    if seen != set(expected_materials):
        raise ValueError("native Material set is incomplete")

    q20_target = q20.get("target") or {}
    src20 = src_targets[20]
    for field, expected in (
        ("xassetIndex", 20),
        ("name", EXPECTED[20]["name"]),
        ("start", int(src20["sourceStart"])),
        ("end", int(src20["sourceEnd"])),
        ("bytes", int(src20["serializedBytes"])),
        ("sha256", src20["serializedSha256"]),
    ):
        if q20_target.get(field) != expected:
            raise ValueError(f"q20 nested target {field} drift")

    for row in rows:
        if row["xassetIndex"] == 20:
            row["localNestedProof"] = {
                "worldVertFormat": int(q20_target["worldVertFormat"]),
                "activeSlots": q20_target["activeSlots"],
                "inlineTechniqueCount": int(q20_target["inlineTechniqueCount"]),
                "directInlineShaderPayloadCount": int(q20_target["directInlineShaderPayloadCount"]),
                "shaderArgumentCount": int(q20_target["shaderArgumentCount"]),
                "argumentTypeCounts": q20_target["argumentTypeCounts"],
            }

    return {
        "format": FORMAT,
        "zone": "faction_seals_mp",
        "sourceExpandedSha256": source["source"]["expandedSha256"],
        "xassetArrayVirtualBase": int(source["xassetVirtualLayout"]["xassetArrayVirtualBase"]),
        "openAssetToolsCommit": native.get("openAssetToolsCommit"),
        "targets": rows,
        "summary": {
            "targetTechniqueSets": 3,
            "targetMaterials": len(expected_materials),
            "factionReferenceStubs": 2,
            "factionLocalDefinitions": 1,
            "canonicalCommonDefinitions": 2,
            "allMaterialBindingsNativeResolved": True,
            "allTechniqueSetDependenciesExact": True,
            "q20NestedRawSourceProofExact": True,
        },
        "proofBoundary": [
            "q10/q17/q20 faction XAsset identity and source extents come only from the continuous retail source-order replay plus independently loader-derived XAsset VIRTUAL lattice.",
            "q10/q17 canonical ownership is accepted only when pinned native OAT resolves every bound faction Material to the expected TechniqueSet and emits the full canonical definition from common_mp.",
            "q20 canonical ownership remains local to faction_seals_mp and is independently checked against the exact raw nested TechniqueSet proof.",
            "No byte-scan rank, name occurrence rank, adjacency, mesh similarity, visual matching or PBR approximation establishes ownership in this closure.",
            "Shader/PBR interpretation remains outside this ownership/dependency closure; exact shader arguments and direct DXBC are retained separately by the q20 nested proof and native dump products.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_order_proof", type=Path)
    ap.add_argument("q20_nested_proof", type=Path)
    ap.add_argument("native_dependency_proof", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = build(load(args.source_order_proof), load(args.q20_nested_proof), load(args.native_dependency_proof))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
