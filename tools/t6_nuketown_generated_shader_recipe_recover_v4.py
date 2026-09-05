#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v4: complete exact vN leaf binding.

v4 combines:
- v2 exact shader-specific forensic vN DAGs;
- v3 per-generated-Material exact cbuffer literal bindings;
- exact nonconstant leaf bindings from each solved layer recurrence to the
  normalized portable layer-weight attribute and exact `.tech` sampler argument.

A vN recipe is emitted only if the DAG cbuffer leaves and material-constant
binding leaves agree exactly.  This makes the recipe self-contained for a
renderer adapter without teaching that adapter raw T6 semantic-name heuristics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v3 as v3
from t6_generated_height_leaf_bindings_v1 import build_height_leaf_bindings
from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v4"
HEIGHT_LEAF_KEY = "heightLeafBindingsV1"
MAP = v3.v2.v1.MAP


class NuketownShaderRecipeRecoveryV4Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _augment_leaf_bindings(manifest: dict, *, oat_root: Path) -> dict:
    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV4Error("v3 recovery manifest has no material rows")

    technique_cache: dict[str, tuple[str, dict]] = {}
    material_count = 0
    layer_count = 0
    raw_inputs: set[str] = set()
    sample_resources: set[str] = set()
    material_arguments: set[str] = set()
    binding_hashes: set[str] = set()

    for recipe in rows:
        material = str(recipe.get("material") or "")
        height = recipe.get(v3.v2.HEIGHT_KEY)
        constants = recipe.get(v3.HEIGHT_CONSTANT_KEY)
        if not isinstance(height, dict):
            if HEIGHT_LEAF_KEY in recipe:
                raise NuketownShaderRecipeRecoveryV4Error(
                    f"{material!r} has vN leaf bindings without a height DAG"
                )
            continue
        if not isinstance(constants, dict):
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} has a height DAG but no exact per-Material constant bindings"
            )

        techset = str(recipe.get("techniqueSet") or "")
        cached = technique_cache.get(techset)
        if cached is None:
            resolved = resolve_slot_shader(oat_root, techset, slot_index=4)
            technique_path = Path(oat_root) / resolved["techniqueFile"]
            technique_text = technique_path.read_text(encoding="utf-8", errors="strict")
            cached = (technique_text, resolved)
            technique_cache[techset] = cached
        technique_text, resolved = cached

        leaf_bindings = build_height_leaf_bindings(height, technique_text=technique_text)
        if leaf_bindings.get("pixelShaderSha256") != height.get("pixelShaderSha256"):
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} nonconstant leaf binding changed pixel-shader identity"
            )
        if leaf_bindings.get("techniqueSet") != techset:
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} nonconstant leaf binding changed TechniqueSet identity"
            )

        dag_constant_leaves = sorted({
            leaf
            for layer in leaf_bindings["layers"]
            for leaf in layer["constantLeaves"]
        })
        bound_constant_leaves = sorted(
            str(row["leaf"]) for row in constants.get("bindings", [])
        )
        if dag_constant_leaves != bound_constant_leaves:
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} DAG constant leaves {dag_constant_leaves} != "
                f"per-Material bindings {bound_constant_leaves}"
            )
        if int(constants.get("leafCount", -1)) != len(bound_constant_leaves):
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} constant leafCount disagrees with serialized binding rows"
            )

        leaf_bindings.update({
            "material": material,
            "materialArchiveSha256": constants.get("materialArchiveSha256"),
            "techniqueAsset": resolved["techniqueAsset"],
            "techniqueFile": resolved["techniqueFile"],
            "constantBindingsKey": v3.HEIGHT_CONSTANT_KEY,
            "constantLeafSetSha256": _jhash(dag_constant_leaves),
            "allLeavesExact": True,
        })
        recipe[HEIGHT_LEAF_KEY] = leaf_bindings
        material_count += 1
        layer_count += len(leaf_bindings["layers"])
        binding_hashes.add(str(leaf_bindings["bindingSetSha256"]))
        for layer in leaf_bindings["layers"]:
            raw_inputs.update(map(str, layer["rawVertexInputs"]))
            for sample in layer["sampleBindings"]:
                sample_resources.add(str(sample["resource"]))
                material_arguments.add(str(sample["materialArgument"]))

    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v4.py"
    rec["heightLeafBoundMaterialCount"] = material_count
    rec["heightLeafBoundLayerCount"] = layer_count
    rec["uniqueHeightRawVertexInputs"] = sorted(raw_inputs)
    rec["uniqueHeightSampleResources"] = sorted(sample_resources)
    rec["uniqueHeightSampleMaterialArguments"] = sorted(material_arguments)
    rec["uniqueHeightLeafBindingSetCount"] = len(binding_hashes)
    rec["heightLeafBindingSetSha256"] = _jhash(sorted(binding_hashes))
    rec["heightAllLeafCoverageComplete"] = True
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["proofBoundary"] = (
        "v3 exact shader DAG + direct per-Material constants, plus nonconstant leaves bound from "
        "the solved compositor layer step to normalized _T6_LAYER_WEIGHTS and exact OAT .tech "
        "sample material arguments. DAG and bound constant leaf sets must agree exactly."
    )

    validated = validate_manifest(manifest)
    for material, row in validated.items():
        height = row.get(v3.v2.HEIGHT_KEY)
        leaf = row.get(HEIGHT_LEAF_KEY)
        if isinstance(height, dict) and not isinstance(leaf, dict):
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} lost complete vN leaf bindings during recipe validation"
            )
        if not isinstance(height, dict) and leaf is not None:
            raise NuketownShaderRecipeRecoveryV4Error(
                f"{material!r} unexpectedly carries vN leaf bindings"
            )
    return manifest


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
) -> dict:
    base = v3.build_from_bindings(
        bindings,
        oat_root=oat_root,
        expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown,
    )
    return _augment_leaf_bindings(base, oat_root=Path(oat_root))


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
) -> dict:
    base = v3.recover(
        expanded_world=expanded_world,
        oat_root=oat_root,
        strict_nuketown=strict_nuketown,
    )
    return _augment_leaf_bindings(base, oat_root=Path(oat_root))


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
