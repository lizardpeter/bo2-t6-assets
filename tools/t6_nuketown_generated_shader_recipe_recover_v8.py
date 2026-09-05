#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v8: exact normal sample decode.

v7 closes secondary-normal transform ownership using two independent proofs. v8
closes the remaining pre-transform normal input by extracting the exact slot-4
``normalMapSamplerN.x/y -> decoded XY`` forensic DAG from the same pixel shader.

Each normal layer also carries the exact OAT `.tech` sampler -> material argument
assignment and an explicit portable dependency `{layerIndex, role: normalMap}`.
The renderer therefore does not need to assume BC5 signed-remap arithmetic or
infer layer identity from sampler suffixes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v7 as v7
import t6_generated_normal_sample_decode_dag_v1 as normal_decode
from t6_dxbc_material_constant_binding_v1 import parse_material_assignments
from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v8"
NORMAL_DECODE_KEY = "normalSampleDecodeV1"


class NuketownShaderRecipeRecoveryV8Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _augment_normal_sample_decode(manifest: dict, *, oat_root: Path) -> dict:
    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV8Error("v7 recovery manifest has no material rows")

    cache: dict[str, tuple[dict, dict, str]] = {}
    normal_material_count = 0
    normal_layer_occurrences = 0
    decode_pair_hashes: set[str] = set()
    component_dag_hashes: set[str] = set()
    material_arguments: set[str] = set()

    for recipe in rows:
        material = str(recipe.get("material") or "")
        technique = str(recipe.get("techniqueSet") or "")
        expected_layers = sorted(
            int(step["layerIndex"])
            for step in recipe.get("layerProgram", [])
            if bool(step.get("hasNormal"))
        )
        if not expected_layers:
            recipe[NORMAL_DECODE_KEY] = {
                "format": "t6-generated-normal-sample-decode-recipe-v1",
                "material": material,
                "techniqueSet": technique,
                "layers": [],
                "normalLayerCount": 0,
                "allDecodeLeavesExact": True,
            }
            continue

        cached = cache.get(technique)
        if cached is None:
            resolved = resolve_slot_shader(oat_root, technique, slot_index=4)
            shaders = resolved.get("pixelShaders", [])
            if len(shaders) != 1:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{technique!r}: exact slot-4 pixel shader is not unique"
                )
            shader = shaders[0]
            shader_path = Path(oat_root) / shader["relativeFile"]
            technique_path = Path(oat_root) / resolved["techniqueFile"]
            shader_bytes = shader_path.read_bytes()
            if hashlib.sha256(shader_bytes).hexdigest() != shader["sha256"]:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{technique!r}: pixel shader bytes changed after OAT resolution"
                )
            try:
                decoded = normal_decode.extract_normal_decode_dags(shader_bytes, technique)
            except Exception as exc:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{technique!r}: exact normal sample decode extraction failed: {exc}"
                ) from exc
            technique_text = technique_path.read_text(encoding="utf-8", errors="strict")
            assignments = parse_material_assignments(technique_text)
            cached = (decoded, resolved, technique_text)
            cache[technique] = cached
        decoded, resolved, technique_text = cached
        assignments = parse_material_assignments(technique_text)

        expected_ps = str(recipe.get("pixelShaderArchetype") or "")
        if expected_ps != "sha256:" + str(decoded.get("pixelShaderSha256") or ""):
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: normal decode pixel-shader identity disagrees with recipe"
            )
        if decoded.get("techniqueSet") != technique:
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: normal decode TechniqueSet identity disagrees"
            )
        decode_layers = decoded.get("layers")
        if not isinstance(decode_layers, list):
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: normal decode payload has no layers"
            )
        actual_layers = sorted(int(layer["layerIndex"]) for layer in decode_layers)
        if actual_layers != expected_layers:
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: decoded normal layers {actual_layers} != canonical hasNormal layers {expected_layers}"
            )

        transform_payload = recipe.get(v7.SHADER_BINDING_KEY)
        if not isinstance(transform_payload, dict) or not bool(transform_payload.get("crossProofAgreement")):
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: dual-proof transform binding missing before normal decode attachment"
            )
        transform_by_layer = {
            int(item["layerIndex"]): item
            for item in transform_payload.get("secondaryNormalBindings", [])
        }
        if set(transform_by_layer) != set(expected_layers):
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: transform layers {sorted(transform_by_layer)} != decode layers {expected_layers}"
            )

        attached = []
        for layer in sorted(decode_layers, key=lambda item: int(item["layerIndex"])):
            layer_index = int(layer["layerIndex"])
            resource = str(layer.get("normalResource") or "")
            if not resource:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{material!r} layer {layer_index}: empty exact normal resource"
                )
            material_argument = assignments.get(resource)
            if material_argument is None:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{material!r} layer {layer_index}: {resource!r} has no exact .tech material assignment"
                )
            transform = transform_by_layer[layer_index]
            expected_mode = str(transform.get("mode") or "")
            if str(layer.get("transformMode") or "") != expected_mode:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{material!r} layer {layer_index}: decode transform mode {layer.get('transformMode')!r} "
                    f"!= dual-proof transform mode {expected_mode!r}"
                )
            components = layer.get("components")
            if not isinstance(components, list) or [item.get("component") for item in components] != ["x", "y"]:
                raise NuketownShaderRecipeRecoveryV8Error(
                    f"{material!r} layer {layer_index}: normal decode components are not exact x/y pair"
                )
            row = {
                "layerIndex": layer_index,
                "normalResource": resource,
                "sampleChannels": ["x", "y"],
                "materialArgument": material_argument,
                "portableDependency": {"layerIndex": layer_index, "role": "normalMap"},
                "transformMode": expected_mode,
                "normalTransformIndex": transform.get("normalTransformIndex"),
                "normalTransformAttribute": transform.get("attribute"),
                "decodePairSha256": layer["decodePairSha256"],
                "components": components,
            }
            attached.append(row)
            normal_layer_occurrences += 1
            decode_pair_hashes.add(str(layer["decodePairSha256"]))
            material_arguments.add(material_argument)
            for component in components:
                component_dag_hashes.add(str(component["forensicDagSha256"]))

        payload = {
            "format": "t6-generated-normal-sample-decode-recipe-v1",
            "material": material,
            "techniqueSet": technique,
            "pixelShaderArchetype": expected_ps,
            "techniqueFile": resolved["techniqueFile"],
            "layers": attached,
            "normalLayerCount": len(attached),
            "allDecodeLeavesExact": bool(decoded.get("allDecodeLeavesSampleOnly")),
            "proof": (
                "exact current normal pair -> maximal sample-only normalMapSamplerN.x/y decode sub-DAG; "
                "exact .tech material assignment; transform mode/index cross-checked against v7 dual proof"
            ),
        }
        payload["bindingSha256"] = _jhash(payload)
        recipe[NORMAL_DECODE_KEY] = payload
        normal_material_count += 1

    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v8.py"
    rec["normalDecodeMaterialCount"] = normal_material_count
    rec["normalDecodeLayerOccurrenceCount"] = normal_layer_occurrences
    rec["uniqueNormalDecodePairDagCount"] = len(decode_pair_hashes)
    rec["uniqueNormalDecodeComponentDagCount"] = len(component_dag_hashes)
    rec["normalDecodeMaterialArguments"] = sorted(material_arguments)
    rec["normalDecodePairSetSha256"] = _jhash(sorted(decode_pair_hashes))
    rec["normalDecodeComponentSetSha256"] = _jhash(sorted(component_dag_hashes))
    rec["normalSampleDecodeCoverageComplete"] = True
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["proofBoundary"] = (
        "v7 dual-proof transform ownership plus exact slot-4 normalMapSamplerN.x/y sample-only decode DAGs "
        "and exact OAT material assignments. Renderer no longer assumes normal RG signed-remap arithmetic."
    )

    validated = validate_manifest(manifest)
    for material, row in validated.items():
        payload = row.get(NORMAL_DECODE_KEY)
        if not isinstance(payload, dict) or payload.get("material") != material:
            raise NuketownShaderRecipeRecoveryV8Error(
                f"{material!r}: normal decode binding lost during canonical validation"
            )
    return manifest


def build_from_bindings(bindings: list[dict], *, oat_root: Path, expanded_sha256: str, strict_nuketown: bool = True, **proof_paths) -> dict:
    base = v7.build_from_bindings(
        bindings, oat_root=oat_root, expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown, **proof_paths
    )
    return _augment_normal_sample_decode(base, oat_root=Path(oat_root))


def recover(*, expanded_world: Path, oat_root: Path, strict_nuketown: bool = True, **proof_paths) -> dict:
    base = v7.recover(
        expanded_world=expanded_world, oat_root=oat_root,
        strict_nuketown=strict_nuketown, **proof_paths
    )
    return _augment_normal_sample_decode(base, oat_root=Path(oat_root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded-world", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--relaxed", action="store_true")
    args = parser.parse_args()
    manifest = recover(
        expanded_world=args.expanded_world, oat_root=args.oat_root,
        strict_nuketown=not args.relaxed
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["recovery"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
