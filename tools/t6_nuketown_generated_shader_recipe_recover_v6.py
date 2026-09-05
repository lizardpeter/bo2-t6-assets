#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v6: normal transform ownership.

v5 adds the exact paired slot-4 vertex shader. v6 preserves that proof and adds
a renderer-facing, Nuketown-gated binding for each secondary normal-bearing layer:

    direct
or
    transform2x2 via _T6_NORMAL_TRANSFORM_0 / _1

The binding is derived only from the retained Nuketown component ``n`` markers,
the zero-failure world normalCount relationship, the source-closed T6 world
vertex layout, and the canonical recipe's exact hasNormal/worldVertFormats.
It is not inferred from layer number or shader naming.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v5 as v5
import t6_nuketown_generated_normal_transform_binding_v1 as normal_binding
from t6_generated_shader_recipe_contract_v1 import validate_manifest


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v6"
NORMAL_BINDING_KEY = "normalTransformBindingsV1"


class NuketownShaderRecipeRecoveryV6Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _augment_normal_transform_bindings(manifest: dict) -> dict:
    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV6Error("v5 recovery manifest has no material rows")

    secondary_normal_materials = 0
    secondary_normal_layers = 0
    direct_layers = 0
    transformed_layers = 0
    slot_histogram: dict[str, int] = {}
    binding_hashes: set[str] = set()

    for recipe in rows:
        try:
            binding = normal_binding.bind_recipe(recipe, map_name=normal_binding.MAP)
        except normal_binding.NuketownNormalTransformBindingError as exc:
            raise NuketownShaderRecipeRecoveryV6Error(
                f"{recipe.get('material')!r}: normal transform binding failed: {exc}"
            ) from exc
        recipe[NORMAL_BINDING_KEY] = binding
        binding_hashes.add(binding["bindingSha256"])
        secondary = binding["secondaryNormalBindings"]
        if secondary:
            secondary_normal_materials += 1
        secondary_normal_layers += len(secondary)
        for item in secondary:
            mode = item["mode"]
            if mode == "direct":
                direct_layers += 1
            elif mode == "transform2x2":
                transformed_layers += 1
                key = str(item["transformSlot"])
                slot_histogram[key] = slot_histogram.get(key, 0) + 1
            else:
                raise NuketownShaderRecipeRecoveryV6Error(
                    f"{recipe['material']!r}: unsupported normal binding mode {mode!r}"
                )

    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v6.py"
    rec["normalTransformBoundMaterialCount"] = len(rows)
    rec["secondaryNormalMaterialCount"] = secondary_normal_materials
    rec["secondaryNormalLayerCount"] = secondary_normal_layers
    rec["directSecondaryNormalLayerCount"] = direct_layers
    rec["transformedSecondaryNormalLayerCount"] = transformed_layers
    rec["normalTransformSlotHistogram"] = dict(sorted(slot_histogram.items()))
    rec["uniqueNormalTransformBindingCount"] = len(binding_hashes)
    rec["normalTransformBindingSetSha256"] = _jhash(sorted(binding_hashes))
    rec["normalTransformBindingCoverageComplete"] = True
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["proofBoundary"] = (
        "v5 exact paired VS/PS and generated height recipe plus Nuketown-only normal transform "
        "ownership from retained n markers, exact world normalCount/format layout, and canonical "
        "hasNormal layers. Normal-map sampled XY decode remains a separate shader proof."
    )

    validated = validate_manifest(manifest)
    for material, row in validated.items():
        payload = row.get(NORMAL_BINDING_KEY)
        if not isinstance(payload, dict):
            raise NuketownShaderRecipeRecoveryV6Error(
                f"{material!r} lost normal transform binding during canonical validation"
            )
        if payload.get("material") != material or payload.get("format") != normal_binding.FORMAT:
            raise NuketownShaderRecipeRecoveryV6Error(
                f"{material!r} canonical normal transform binding identity changed"
            )
    return manifest


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
) -> dict:
    base = v5.build_from_bindings(
        bindings,
        oat_root=oat_root,
        expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown,
    )
    return _augment_normal_transform_bindings(base)


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
) -> dict:
    base = v5.recover(
        expanded_world=expanded_world,
        oat_root=oat_root,
        strict_nuketown=strict_nuketown,
    )
    return _augment_normal_transform_bindings(base)


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
