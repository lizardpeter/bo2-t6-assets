#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v2: exact vN DAG payloads.

v1 recovers the exact 120 Material -> TechniqueSet -> slot-4 pixel-shader
identity table. v2 leaves that proof untouched and, only for recipes whose exact
TechniqueSet grammar declares a vN height layer, runs the retained direct-DXBC
symbolic compositor on that exact shader and serializes its forensic scalar
weight DAG into the recipe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v1 as v1
from t6_generated_height_weight_dag_v1 import extract_height_weight_dags
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program, validate_manifest
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v2"
HEIGHT_KEY = "heightWeightDagsV1"


class NuketownShaderRecipeRecoveryV2Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _augment_height_dags(manifest: dict, *, oat_root: Path) -> dict:
    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV2Error("v1 recovery manifest has no material rows")

    extracted_by_techset: dict[str, dict] = {}
    height_material_count = 0
    height_layer_occurrences = 0
    semantic_hashes: set[str] = set()
    forensic_hashes: set[str] = set()

    for recipe in rows:
        material = str(recipe.get("material") or "")
        techset = str(recipe.get("techniqueSet") or "")
        program = canonical_layer_program(techset)
        expected_height_layers = sorted(
            int(step["layerIndex"]) for step in program if step["heightVariant"]
        )
        if not expected_height_layers:
            if HEIGHT_KEY in recipe:
                raise NuketownShaderRecipeRecoveryV2Error(
                    f"{material!r} has a height DAG payload but no vN TechniqueSet layer"
                )
            continue

        payload = extracted_by_techset.get(techset)
        if payload is None:
            resolved = resolve_slot_shader(oat_root, techset, slot_index=v1.SLOT_INDEX)
            shaders = resolved["pixelShaders"]
            if len(shaders) != 1:
                raise NuketownShaderRecipeRecoveryV2Error(
                    f"{techset!r} does not resolve to exactly one slot-4 shader"
                )
            shader_record = shaders[0]
            shader_path = Path(oat_root) / shader_record["relativeFile"]
            shader_bytes = shader_path.read_bytes()
            actual_sha = hashlib.sha256(shader_bytes).hexdigest()
            if actual_sha != shader_record["sha256"]:
                raise NuketownShaderRecipeRecoveryV2Error(
                    f"{techset!r} shader bytes changed after OAT identity resolution"
                )
            payload = extract_height_weight_dags(shader_bytes, techset)
            if payload["pixelShaderSha256"] != actual_sha:
                raise NuketownShaderRecipeRecoveryV2Error(
                    f"{techset!r} height DAG extractor returned a different pixel-shader SHA"
                )
            extracted_by_techset[techset] = payload

        actual_layers = sorted(int(item["layerIndex"]) for item in payload["layers"])
        if actual_layers != expected_height_layers:
            raise NuketownShaderRecipeRecoveryV2Error(
                f"{material!r} exact height-DAG layers {actual_layers} != "
                f"TechniqueSet vN layers {expected_height_layers}"
            )
        expected_shader = str(recipe.get("pixelShaderArchetype") or "")
        actual_archetype = f"sha256:{payload['pixelShaderSha256']}"
        if expected_shader != actual_archetype:
            raise NuketownShaderRecipeRecoveryV2Error(
                f"{material!r} height DAG shader {actual_archetype} != recipe {expected_shader}"
            )

        recipe[HEIGHT_KEY] = payload
        height_material_count += 1
        height_layer_occurrences += len(payload["layers"])
        for item in payload["layers"]:
            semantic_hashes.add(str(item["semanticWeightDagSha256"]))
            forensic_hashes.add(str(item["forensicDag"]["forensicDagSha256"]))

    # Every height-bearing TechniqueSet was extracted once and then shared by
    # exact TechniqueSet identity; material rows still carry their own payload so
    # the embedded glTF recipe is self-contained.
    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v2.py"
    rec["heightDagMaterialCount"] = height_material_count
    rec["heightDagLayerOccurrenceCount"] = height_layer_occurrences
    rec["heightDagTechniqueSetCount"] = len(extracted_by_techset)
    rec["uniqueHeightSemanticDagCount"] = len(semantic_hashes)
    rec["uniqueHeightForensicDagCount"] = len(forensic_hashes)
    rec["heightSemanticDagSetSha256"] = _jhash(sorted(semantic_hashes))
    rec["heightForensicDagSetSha256"] = _jhash(sorted(forensic_hashes))
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["heightDagCoverageComplete"] = True
    rec["proofBoundary"] = (
        "v1 exact retail Material->TechniqueSet->slot4 pixel-shader recovery plus exact "
        "forensic vN scalar-weight subgraphs from the same shader bytes. DAG operation and "
        "argument order is preserved; no universal height formula or PBR reinterpretation."
    )

    # Canonical recipe validation must preserve the attached exact DAG payloads.
    validated = validate_manifest(manifest)
    for material, row in validated.items():
        expected = sorted(
            int(step["layerIndex"]) for step in row["layerProgram"] if step["heightVariant"]
        )
        payload = row.get(HEIGHT_KEY)
        if expected and not isinstance(payload, dict):
            raise NuketownShaderRecipeRecoveryV2Error(
                f"{material!r} lost exact height DAG payload during recipe validation"
            )
        if not expected and payload is not None:
            raise NuketownShaderRecipeRecoveryV2Error(
                f"{material!r} unexpectedly carries exact height DAG payload"
            )
    return manifest


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
) -> dict:
    base = v1.build_from_bindings(
        bindings,
        oat_root=oat_root,
        expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown,
    )
    return _augment_height_dags(base, oat_root=Path(oat_root))


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
) -> dict:
    expanded_world = Path(expanded_world)
    if not expanded_world.is_file():
        raise NuketownShaderRecipeRecoveryV2Error(
            f"expanded Nuketown world does not exist: {expanded_world}"
        )
    expanded_data = expanded_world.read_bytes()
    expanded_sha = hashlib.sha256(expanded_data).hexdigest()
    try:
        bindings = v1.retail_census.bind_map(v1.MAP, expanded_world)
    except Exception as exc:
        raise NuketownShaderRecipeRecoveryV2Error(
            f"retail Nuketown Material->TechniqueSet binding failed: {exc}"
        ) from exc
    return build_from_bindings(
        bindings,
        oat_root=Path(oat_root),
        expanded_sha256=expanded_sha,
        strict_nuketown=strict_nuketown,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded-world", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--relaxed", action="store_true")
    args = parser.parse_args()
    manifest = recover(
        expanded_world=args.expanded_world,
        oat_root=args.oat_root,
        strict_nuketown=not args.relaxed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["recovery"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
