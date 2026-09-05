#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v7: dual-proof normal transforms.

v6 attaches a Nuketown-specific transform binding from retained component n
markers and world normalCount layout. v7 independently runs the exact shader
routing proof (`t6_generated_normal_transform_layer_mapping_v1`) and requires the
two proofs to agree for every secondary normal layer before emitting a recipe.

The shader proof uses exact OAT slot-4 `.tech` normalTransform routing, paired VS
input/output ancestry and the exact PS transformed-normal dependencies. Therefore
v7 no longer relies on layout ordering alone for renderer transform ownership.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v6 as v6
import t6_generated_normal_transform_layer_mapping_v1 as shader_mapping
from t6_generated_shader_recipe_contract_v1 import validate_manifest


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v7"
SHADER_BINDING_KEY = "normalTransformShaderBindingsV1"


class NuketownShaderRecipeRecoveryV7Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _augment_shader_transform_proof(
    manifest: dict,
    *,
    oat_root: Path,
    paired_vs_probe_path: Path = Path("tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py"),
    base_verifier_path: Path = Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    compositor_path: Path = Path("tools/t6_retail_layered_lmap_compositor_v1.py"),
    normal_proof_path: Path = Path("tools/t6_retail_layered_normal_reconstruction_v1.py"),
) -> dict:
    try:
        proof = shader_mapping.build(
            manifest,
            oat_root=Path(oat_root),
            paired_vs_probe_path=paired_vs_probe_path,
            base_verifier_path=base_verifier_path,
            compositor_path=compositor_path,
            normal_proof_path=normal_proof_path,
        )
    except Exception as exc:
        raise NuketownShaderRecipeRecoveryV7Error(
            f"exact shader normal-transform mapping failed: {exc}"
        ) from exc
    if proof.get("format") != shader_mapping.FORMAT:
        raise NuketownShaderRecipeRecoveryV7Error(
            f"unexpected shader normal-transform proof {proof.get('format')!r}"
        )
    if not bool(proof.get("summary", {}).get("allTransformedLayersUniquelyMapped")):
        raise NuketownShaderRecipeRecoveryV7Error(
            "shader proof did not uniquely map every transformed normal layer"
        )

    profiles = proof.get("profiles")
    if not isinstance(profiles, list):
        raise NuketownShaderRecipeRecoveryV7Error("shader normal-transform proof has no profiles")
    by_techset: dict[str, dict] = {}
    for profile in profiles:
        technique = str(profile.get("techniqueSet") or "")
        if not technique or technique in by_techset:
            raise NuketownShaderRecipeRecoveryV7Error(
                f"duplicate/empty shader transform profile {technique!r}"
            )
        by_techset[technique] = profile

    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV7Error("v6 manifest has no material rows")

    cross_checked_materials = 0
    cross_checked_layers = 0
    direct_layers = 0
    transformed_layers = 0
    binding_hashes: set[str] = set()
    for recipe in rows:
        material = str(recipe.get("material") or "")
        technique = str(recipe.get("techniqueSet") or "")
        layout = recipe.get(v6.NORMAL_BINDING_KEY)
        if not isinstance(layout, dict):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: v6 layout normal binding missing"
            )
        layout_rows = layout.get("secondaryNormalBindings")
        if not isinstance(layout_rows, list):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: invalid v6 secondary normal binding rows"
            )
        if not layout_rows:
            # Shader mapping intentionally profiles only recipes with a secondary
            # hasNormal step. Nothing to cross-check for base-only/no-normal rows.
            recipe[SHADER_BINDING_KEY] = {
                "format": "t6-generated-normal-transform-recipe-binding-v1",
                "material": material,
                "techniqueSet": technique,
                "secondaryNormalBindings": [],
                "crossProofAgreement": True,
            }
            continue

        profile = by_techset.get(technique)
        if profile is None:
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: no exact shader transform profile for {technique!r}"
            )
        expected_vs = str(recipe.get("vertexShaderArchetype") or "")
        expected_ps = str(recipe.get("pixelShaderArchetype") or "")
        if expected_vs != "sha256:" + str(profile.get("vertexShaderSha256") or ""):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: shader transform proof VS identity disagrees"
            )
        if expected_ps != "sha256:" + str(profile.get("pixelShaderSha256") or ""):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: shader transform proof PS identity disagrees"
            )
        shader_rows = profile.get("normalLayers")
        if not isinstance(shader_rows, list):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: shader transform profile has no normalLayers"
            )
        shader_by_layer = {int(row["layerIndex"]): row for row in shader_rows}
        if len(shader_by_layer) != len(shader_rows):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: duplicate shader normal layer mapping"
            )
        layout_by_layer = {int(row["layerIndex"]): row for row in layout_rows}
        if set(shader_by_layer) != set(layout_by_layer):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r}: shader normal layers {sorted(shader_by_layer)} != "
                f"layout normal layers {sorted(layout_by_layer)}"
            )

        attached = []
        for layer in sorted(layout_by_layer):
            layout_row = layout_by_layer[layer]
            shader_row = shader_by_layer[layer]
            layout_mode = str(layout_row.get("mode") or "")
            shader_required = bool(shader_row.get("normalTransformRequired"))
            shader_kind = str(shader_row.get("normalPairKind") or "")
            if layout_mode == "direct":
                if shader_required or shader_kind != "direct" or shader_row.get("normalTransformIndex") is not None:
                    raise NuketownShaderRecipeRecoveryV7Error(
                        f"{material!r} layer {layer}: layout says direct but exact shader mapping is {shader_row}"
                    )
                direct_layers += 1
                attribute = None
                transform_index = None
            elif layout_mode == "transform2x2":
                layout_index = int(layout_row.get("transformSlot"))
                shader_index = shader_row.get("normalTransformIndex")
                if not shader_required or shader_kind != "matrix2x2" or int(shader_index) != layout_index:
                    raise NuketownShaderRecipeRecoveryV7Error(
                        f"{material!r} layer {layer}: layout transform {layout_index} != exact shader mapping {shader_row}"
                    )
                transformed_layers += 1
                transform_index = layout_index
                attribute = f"_T6_NORMAL_TRANSFORM_{layout_index}"
                if layout_row.get("attribute") != attribute:
                    raise NuketownShaderRecipeRecoveryV7Error(
                        f"{material!r} layer {layer}: v6 transform attribute identity changed"
                    )
            else:
                raise NuketownShaderRecipeRecoveryV7Error(
                    f"{material!r} layer {layer}: invalid v6 mode {layout_mode!r}"
                )
            attached.append({
                "layerIndex": layer,
                "mode": layout_mode,
                "normalTransformIndex": transform_index,
                "attribute": attribute,
                "pixelInputDependencies": list(shader_row.get("pixelInputDependencies", [])),
                "candidateTransformIndices": list(shader_row.get("candidateTransformIndices", [])),
            })
            cross_checked_layers += 1

        payload = {
            "format": "t6-generated-normal-transform-recipe-binding-v1",
            "material": material,
            "techniqueSet": technique,
            "vertexShaderArchetype": expected_vs,
            "pixelShaderArchetype": expected_ps,
            "shaderMappingFormat": shader_mapping.FORMAT,
            "secondaryNormalBindings": attached,
            "crossProofAgreement": True,
            "proof": (
                "Nuketown n-marker/world-layout ownership equals exact .tech routing + paired-VS ancestry + PS transform dependency mapping"
            ),
        }
        payload["bindingSha256"] = _jhash(payload)
        recipe[SHADER_BINDING_KEY] = payload
        binding_hashes.add(payload["bindingSha256"])
        cross_checked_materials += 1

    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v7.py"
    rec["shaderNormalTransformProofFormat"] = shader_mapping.FORMAT
    rec["shaderNormalTransformTechniqueSetCount"] = int(proof["summary"]["techniqueSetCount"])
    rec["normalTransformCrossCheckedMaterialCount"] = cross_checked_materials
    rec["normalTransformCrossCheckedLayerCount"] = cross_checked_layers
    rec["shaderDirectSecondaryNormalLayerCount"] = direct_layers
    rec["shaderTransformedSecondaryNormalLayerCount"] = transformed_layers
    rec["normalTransformCrossProofBindingSetSha256"] = _jhash(sorted(binding_hashes))
    rec["normalTransformCrossProofAgreementComplete"] = True
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["proofBoundary"] = (
        "v6 Nuketown retained component/world-layout transform ownership independently agrees with exact "
        "slot-4 .tech routing, paired-VS ancestry, and PS transformed-normal dependencies. Normal-map "
        "sample XY decode remains the next separate renderer closure."
    )

    validated = validate_manifest(manifest)
    for material, row in validated.items():
        payload = row.get(SHADER_BINDING_KEY)
        if not isinstance(payload, dict) or not bool(payload.get("crossProofAgreement")):
            raise NuketownShaderRecipeRecoveryV7Error(
                f"{material!r} lost dual-proof normal transform binding during canonical validation"
            )
    return manifest


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
    **proof_paths,
) -> dict:
    base = v6.build_from_bindings(
        bindings,
        oat_root=oat_root,
        expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown,
    )
    return _augment_shader_transform_proof(base, oat_root=Path(oat_root), **proof_paths)


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
    **proof_paths,
) -> dict:
    base = v6.recover(
        expanded_world=expanded_world,
        oat_root=oat_root,
        strict_nuketown=strict_nuketown,
    )
    return _augment_shader_transform_proof(base, oat_root=Path(oat_root), **proof_paths)


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
