#!/usr/bin/env python3
"""Generated slot-4 final-output symbolic DAG v3: canonical identity gates.

v2 preserves complete output DAGs and hardens derivative/branch dataflow. v3
adds an independent exact-identity gate against the canonical recovered recipe
manifest before any final-output result may be promoted.

For every material:
- ``pixelShaderArchetype`` must be an exact ``sha256:<64hex>`` identity;
- ``proof.pixelShaderSha256`` (when present) must be the same identity;
- that identity must equal the OAT-resolved verbatim slot-4 CSO hash.

Strict Nuketown mode additionally re-proves the retained population invariants
from the recipe rows and from the produced shader graph:
- 120 generated materials;
- 34 exact TechniqueSets;
- 34 unique slot-4 pixel shaders;
- zero cross-TechniqueSet shader reuse;
- worldVertFormat histogram {1:95, 2:7, 3:17, 6:1};
- SM4.0 pixel shaders throughout.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

import t6_generated_shader_recipe_contract_v1 as recipe_contract
import t6_generated_slot4_final_output_symbolic_v2 as v2

FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
MAP = "mp_nuketown_2020"
EXPECTED_MATERIALS = 120
EXPECTED_TECHSETS = 34
EXPECTED_SHADERS = 34
EXPECTED_WORLD_FORMAT_HISTOGRAM = {1: 95, 2: 7, 3: 17, 6: 1}
SHA_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


class GeneratedFinalOutputSymbolicV3Error(v2.GeneratedFinalOutputSymbolicV2Error):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _declared_shader_sha(recipe: dict, material: str) -> str:
    archetype = str(recipe.get("pixelShaderArchetype") or "")
    match = SHA_RE.fullmatch(archetype)
    if not match:
        raise GeneratedFinalOutputSymbolicV3Error(
            f"{material!r}: pixelShaderArchetype is not exact sha256:<64hex>: {archetype!r}"
        )
    declared = match.group(1).lower()
    proof = recipe.get("proof")
    if isinstance(proof, dict) and proof.get("pixelShaderSha256") not in (None, ""):
        proof_sha = str(proof["pixelShaderSha256"]).lower()
        if proof_sha != declared:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"{material!r}: proof.pixelShaderSha256 {proof_sha} != archetype {declared}"
            )
    return declared


def _canonical_identity_map(recipe_manifest: dict) -> tuple[dict[str, str], dict[str, dict]]:
    try:
        validated = recipe_contract.validate_manifest(recipe_manifest)
    except Exception as exc:
        raise GeneratedFinalOutputSymbolicV3Error(
            f"invalid canonical recipe manifest: {exc}"
        ) from exc
    declared = {
        material: _declared_shader_sha(recipe, material)
        for material, recipe in validated.items()
    }
    return declared, validated


def _world_format_histogram(validated: dict[str, dict]) -> dict[int, int]:
    hist = collections.Counter()
    for material, recipe in validated.items():
        formats = recipe.get("worldVertFormats")
        if not isinstance(formats, list) or len(formats) != 1:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"{material!r}: strict Nuketown recipe must have exactly one worldVertFormat"
            )
        hist[int(formats[0])] += 1
    return dict(sorted(hist.items()))


def build(recipe_manifest: dict, *, oat_root: Path, strict_nuketown: bool = False) -> dict:
    declared, validated = _canonical_identity_map(recipe_manifest)
    result = v2.build(
        recipe_manifest,
        oat_root=oat_root,
        strict_nuketown=strict_nuketown,
    )
    if result.get("format") != v2.FORMAT:
        raise GeneratedFinalOutputSymbolicV3Error(
            f"unexpected v2 result format {result.get('format')!r}"
        )

    actual_by_material: dict[str, str] = {}
    for row in result.get("materials", []):
        material = str(row.get("material") or "")
        actual = str(row.get("pixelShaderSha256") or "").lower()
        if material in actual_by_material:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"duplicate final-output material row {material!r}"
            )
        actual_by_material[material] = actual
    if set(actual_by_material) != set(declared):
        missing = sorted(set(declared) - set(actual_by_material))
        extra = sorted(set(actual_by_material) - set(declared))
        raise GeneratedFinalOutputSymbolicV3Error(
            f"canonical/final-output material identity mismatch missing={missing[:4]} extra={extra[:4]}"
        )
    for material, expected in declared.items():
        actual = actual_by_material[material]
        if actual != expected:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"{material!r}: exact OAT slot-4 shader {actual} != canonical {expected}"
            )

    shaders = result.get("shaders", [])
    actual_shader_set = sorted(str(row["sha256"]).lower() for row in shaders)
    if len(actual_shader_set) != len(set(actual_shader_set)):
        raise GeneratedFinalOutputSymbolicV3Error("duplicate shader SHA rows in v2 result")
    shader_set_sha = _jhash(actual_shader_set)

    strict = {}
    if strict_nuketown:
        recovery = recipe_manifest.get("recovery")
        if not isinstance(recovery, dict) or recovery.get("map") != MAP:
            raise GeneratedFinalOutputSymbolicV3Error(
                "strict Nuketown final-output proof requires canonical recovery.map=mp_nuketown_2020"
            )
        if len(validated) != EXPECTED_MATERIALS:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"Nuketown canonical material count {len(validated)} != {EXPECTED_MATERIALS}"
            )
        techsets = sorted({str(recipe["techniqueSet"]) for recipe in validated.values()})
        if len(techsets) != EXPECTED_TECHSETS:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"Nuketown canonical TechniqueSet count {len(techsets)} != {EXPECTED_TECHSETS}"
            )
        if len(shaders) != EXPECTED_SHADERS:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"Nuketown final-output shader count {len(shaders)} != {EXPECTED_SHADERS}"
            )
        reused = {
            row["sha256"]: sorted(row.get("techniqueSets", []))
            for row in shaders
            if len(row.get("techniqueSets", [])) != 1
        }
        if reused:
            sha, names = sorted(reused.items())[0]
            raise GeneratedFinalOutputSymbolicV3Error(
                f"Nuketown unexpected cross-TechniqueSet slot-4 shader reuse {sha}: {names}"
            )
        histogram = _world_format_histogram(validated)
        if histogram != EXPECTED_WORLD_FORMAT_HISTOGRAM:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"Nuketown worldVertFormat histogram {histogram} != {EXPECTED_WORLD_FORMAT_HISTOGRAM}"
            )
        bad_models = [
            {"sha256": row["sha256"], "shaderModel": row.get("shaderModel")}
            for row in shaders
            if row.get("shaderModel") != "4.0"
        ]
        if bad_models:
            raise GeneratedFinalOutputSymbolicV3Error(
                f"Nuketown slot-4 shaders are not uniformly SM4.0: {bad_models[:4]}"
            )
        expected_recovery = {
            "generatedMaterialCount": EXPECTED_MATERIALS,
            "uniqueTechniqueSetCount": EXPECTED_TECHSETS,
            "uniqueSlot4PixelShaderCount": EXPECTED_SHADERS,
            "crossTechniqueSetShaderReuseCount": 0,
        }
        for key, expected in expected_recovery.items():
            if int(recovery.get(key, -1)) != expected:
                raise GeneratedFinalOutputSymbolicV3Error(
                    f"canonical recovery {key}={recovery.get(key)!r} != {expected}"
                )
        recovery_hist = {
            int(k): int(v)
            for k, v in dict(recovery.get("worldVertFormatHistogram", {})).items()
        }
        if dict(sorted(recovery_hist.items())) != EXPECTED_WORLD_FORMAT_HISTOGRAM:
            raise GeneratedFinalOutputSymbolicV3Error(
                "canonical recovery worldVertFormatHistogram disagrees with retained Nuketown invariant"
            )
        strict = {
            "map": MAP,
            "materialCount": EXPECTED_MATERIALS,
            "techniqueSetCount": EXPECTED_TECHSETS,
            "uniquePixelShaderCount": EXPECTED_SHADERS,
            "crossTechniqueSetShaderReuseCount": 0,
            "worldVertFormatHistogram": {str(k): v for k, v in EXPECTED_WORLD_FORMAT_HISTOGRAM.items()},
            "shaderModel": "4.0",
            "allCanonicalShaderIdentitiesExact": True,
            "allRecoveryInvariantsRechecked": True,
        }

    result["format"] = FORMAT
    result["baseFormat"] = v2.FORMAT
    result["canonicalShaderIdentityContract"] = "pixelShaderArchetype == sha256:<exact OAT slot-4 CSO SHA-256>"
    result["summary"]["canonicalShaderIdentityMismatchCount"] = 0
    result["summary"]["exactPixelShaderSetSha256"] = shader_set_sha
    result["summary"]["strictNuketownInvariantRecheck"] = bool(strict_nuketown)
    if strict:
        result["strictNuketown"] = strict
    result["proofBoundary"] = (
        "v2 full-output/derivative/defined-dataflow proof plus exact canonical sha256: archetype and OAT CSO identity "
        "agreement for every material. Strict Nuketown mode independently rechecks the retained 120/34/34/zero-reuse/"
        "world-format/SM4.0 population invariants. Final output remains an expression DAG without physical lighting labels."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strict-nuketown", action="store_true")
    args = parser.parse_args()
    recipe_manifest = json.loads(args.recipes.read_text(encoding="utf-8"))
    result = build(
        recipe_manifest,
        oat_root=args.oat_root,
        strict_nuketown=args.strict_nuketown,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
