#!/usr/bin/env python3
"""Classify exact native T6 shader-pair census against solved Blender families.

Membership is exact VS+PS DXBC SHA identity only.  Unknown pairs remain
explicitly unsolved.  This tool does not infer family membership from
TechniqueSet names, Material roles or visual similarity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FORMAT = "t6-blender-native-shader-family-coverage-v1"
CENSUS_FORMAT = "t6-oat-material-shader-census-v1"
SEMANTICS_FORMAT = "t6-retail-lprobe-lit-semantics-v1"


class NativeShaderFamilyCoverageError(RuntimeError):
    pass


def _sha(value, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise NativeShaderFamilyCoverageError(f"{label} is not SHA-256: {value!r}")
    return text


def _solved_registry(semantics: dict) -> dict[tuple[str, str], dict]:
    if semantics.get("format") != SEMANTICS_FORMAT:
        raise NativeShaderFamilyCoverageError(
            f"unsupported semantics registry {semantics.get('format')!r}"
        )
    registry = {}
    for family in semantics.get("families", []):
        family_id = str(family.get("id") or "")
        if not family_id:
            raise NativeShaderFamilyCoverageError("solved family has empty id")
        key = (
            _sha(family.get("vertexShader", {}).get("dxbcSha256"), f"{family_id} VS"),
            _sha(family.get("pixelShader", {}).get("dxbcSha256"), f"{family_id} PS"),
        )
        if key in registry:
            raise NativeShaderFamilyCoverageError(f"duplicate solved exact pair for {family_id!r}")
        registry[key] = family
    if not registry:
        raise NativeShaderFamilyCoverageError("solved registry is empty")
    return registry


def build(census: dict, semantics: dict) -> dict:
    if census.get("format") != CENSUS_FORMAT:
        raise NativeShaderFamilyCoverageError(
            f"unsupported native census {census.get('format')!r}"
        )
    registry = _solved_registry(semantics)
    groups = census.get("shaderPairGroups")
    if not isinstance(groups, list):
        raise NativeShaderFamilyCoverageError("native census has no shaderPairGroups")

    rows = []
    solved_group_count = unsolved_group_count = 0
    solved_material_count = unsolved_material_count = 0
    family_material_counts = {}

    for group in groups:
        passes = group.get("passes")
        if not isinstance(passes, list) or not passes:
            raise NativeShaderFamilyCoverageError("shader pair group has no passes")
        solved = None
        reason = None
        exact_pair = None
        if len(passes) != 1:
            reason = f"multi-pass technique ({len(passes)} passes) has no solved Blender family registry entry"
        else:
            render_pass = passes[0]
            exact_pair = (
                _sha(render_pass.get("vertexShader", {}).get("sha256"), "group VS"),
                _sha(render_pass.get("pixelShader", {}).get("sha256"), "group PS"),
            )
            solved = registry.get(exact_pair)
            if solved is None:
                reason = "exact VS+PS pair absent from solved Blender registry"

        material_count = int(group.get("materialCount", len(group.get("materials", []))))
        if material_count != len(group.get("materials", [])):
            raise NativeShaderFamilyCoverageError("group materialCount disagrees with materials array")
        if solved is not None:
            classification = "solved-exact-family"
            family_id = str(solved["id"])
            solved_group_count += 1
            solved_material_count += material_count
            family_material_counts[family_id] = family_material_counts.get(family_id, 0) + material_count
        else:
            classification = "unsolved"
            family_id = None
            unsolved_group_count += 1
            unsolved_material_count += material_count

        rows.append({
            "pairKey": group.get("pairKey"),
            "materialCount": material_count,
            "techniqueSets": group.get("techniqueSets", []),
            "techniques": group.get("techniques", []),
            "passes": passes,
            "classification": classification,
            "solvedFamily": family_id,
            "unsolvedReason": reason,
        })

    total_materials = solved_material_count + unsolved_material_count
    return {
        "format": FORMAT,
        "proofBoundary": (
            "Exact native shader-pair census classified only by exact VS+PS DXBC SHA membership in a source-closed Blender family registry. "
            "Unknown and multi-pass groups remain unsolved; no naming/texture/PBR inference."
        ),
        "summary": {
            "shaderPairGroupCount": len(rows),
            "solvedShaderPairGroupCount": solved_group_count,
            "unsolvedShaderPairGroupCount": unsolved_group_count,
            "materialCount": total_materials,
            "solvedMaterialCount": solved_material_count,
            "unsolvedMaterialCount": unsolved_material_count,
            "solvedMaterialPercent": 0.0 if not total_materials else 100.0 * solved_material_count / total_materials,
            "familyMaterialCounts": dict(sorted(family_material_counts.items())),
        },
        "groups": sorted(rows, key=lambda row: (-row["materialCount"], str(row["pairKey"]))),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--census", type=Path, required=True)
    p.add_argument(
        "--semantics",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_LPROBE_LIT_SEMANTICS_V1.json"),
    )
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(
        json.loads(a.census.read_text(encoding="utf-8")),
        json.loads(a.semantics.read_text(encoding="utf-8")),
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    for row in result["groups"][:30]:
        print(
            f"{row['materialCount']:4d} {row['classification']:19s} "
            f"family={row['solvedFamily']} pair={str(row['pairKey'])[:12]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
