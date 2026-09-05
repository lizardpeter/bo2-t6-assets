#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v3: material-specific vN constants.

v2 serializes each exact shader-specific vN scalar DAG. v3 closes the remaining
constant-buffer leaves for each generated Material independently by joining:

  DAG cbN[R].component
    -> exact slot-4 DXBC RDEF variable
    -> exact OAT .tech material assignment
    -> T6 R_HashString
    -> that Material's serialized retail MaterialConstantDef literal.

The DAG may be shared by TechniqueSet/shader identity; the bound literal values
are intentionally NOT shared because generated Materials can carry different
height parameters while using the same shader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v2 as v2
import t6_retail_world_material_constants_v1 as retail_constants
from t6_dxbc_material_constant_binding_v1 import bind_cb_leaves
from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v3"
HEIGHT_CONSTANT_KEY = "heightConstantBindingsV1"
CB_NAME_RE = re.compile(r"^cb\d+\[\d+\]\.[xyzw]$")


class NuketownShaderRecipeRecoveryV3Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _cb_leaves(height_payload: dict) -> list[str]:
    leaves: set[str] = set()
    for layer in height_payload.get("layers", []):
        dag = layer.get("forensicDag", {})
        for node in dag.get("nodes", []):
            if node.get("kind") != "cb":
                continue
            name = str(node.get("name") or "")
            if not CB_NAME_RE.match(name):
                raise NuketownShaderRecipeRecoveryV3Error(
                    f"unsupported exact vN cbuffer leaf syntax {name!r}"
                )
            leaves.add(name)
    return sorted(leaves)


def _augment_material_constant_bindings(
    manifest: dict,
    *,
    source_bindings: list[dict],
    oat_root: Path,
) -> dict:
    source_by_material: dict[str, dict] = {}
    for row in source_bindings:
        material = str(row.get("material") or "")
        if not material.startswith("*"):
            continue
        if material in source_by_material:
            raise NuketownShaderRecipeRecoveryV3Error(
                f"duplicate source generated Material {material!r}"
            )
        constants = row.get("constants")
        if not isinstance(constants, list):
            raise NuketownShaderRecipeRecoveryV3Error(
                f"{material!r} lacks direct serialized retail constant table"
            )
        source_by_material[material] = row

    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV3Error("v2 recovery manifest has no material rows")

    shader_cache: dict[str, tuple[bytes, str, dict]] = {}
    bound_material_count = 0
    bound_leaf_count = 0
    unique_binding_signatures: set[str] = set()
    material_constant_hashes: set[int] = set()
    leaf_names: set[str] = set()

    for recipe in rows:
        material = str(recipe.get("material") or "")
        height_payload = recipe.get(v2.HEIGHT_KEY)
        if not isinstance(height_payload, dict):
            if HEIGHT_CONSTANT_KEY in recipe:
                raise NuketownShaderRecipeRecoveryV3Error(
                    f"{material!r} has height constants without a height DAG"
                )
            continue
        leaves = _cb_leaves(height_payload)
        source = source_by_material.get(material)
        if source is None:
            raise NuketownShaderRecipeRecoveryV3Error(
                f"{material!r} has a height DAG but no direct retail Material record"
            )
        techset = str(recipe["techniqueSet"])
        cached = shader_cache.get(techset)
        if cached is None:
            resolved = resolve_slot_shader(oat_root, techset, slot_index=4)
            shaders = resolved["pixelShaders"]
            if len(shaders) != 1:
                raise NuketownShaderRecipeRecoveryV3Error(
                    f"{techset!r} does not resolve to exactly one slot-4 shader"
                )
            shader = shaders[0]
            shader_path = Path(oat_root) / shader["relativeFile"]
            technique_path = Path(oat_root) / resolved["techniqueFile"]
            shader_bytes = shader_path.read_bytes()
            technique_text = technique_path.read_text(encoding="utf-8", errors="strict")
            if hashlib.sha256(shader_bytes).hexdigest() != shader["sha256"]:
                raise NuketownShaderRecipeRecoveryV3Error(
                    f"{techset!r} slot-4 shader bytes changed after exact OAT resolution"
                )
            cached = (shader_bytes, technique_text, resolved)
            shader_cache[techset] = cached
        shader_bytes, technique_text, resolved = cached

        expected_shader = str(recipe.get("pixelShaderArchetype") or "")
        actual_shader = "sha256:" + hashlib.sha256(shader_bytes).hexdigest()
        if expected_shader != actual_shader:
            raise NuketownShaderRecipeRecoveryV3Error(
                f"{material!r} recipe shader {expected_shader!r} != binding shader {actual_shader!r}"
            )

        bindings = bind_cb_leaves(
            leaves,
            dxbc=shader_bytes,
            technique_text=technique_text,
            material_constants=source["constants"],
        )
        bindings.update({
            "material": material,
            "materialIndex": source.get("materialIndex"),
            "materialStart": source.get("materialStart"),
            "materialArchiveSha256": source.get("materialArchiveSha256"),
            "techniqueSet": techset,
            "techniqueAsset": resolved["techniqueAsset"],
            "techniqueFile": resolved["techniqueFile"],
            "pixelShaderArchetype": actual_shader,
            "bindingPolicy": (
                "per generated Material; values are never shared merely because TechniqueSet/shader is shared"
            ),
        })
        recipe[HEIGHT_CONSTANT_KEY] = bindings
        bound_material_count += 1
        bound_leaf_count += int(bindings["leafCount"])
        leaf_names.update(row["leaf"] for row in bindings["bindings"])
        for row in bindings["bindings"]:
            constant = row["materialConstant"]
            material_constant_hashes.add(int(constant["nameHash"]))
            unique_binding_signatures.add(_jhash({
                "leaf": row["leaf"],
                "nameHash": constant["nameHash"],
                "literal": constant["literal"],
                "literalComponent": constant["literalComponent"],
            }))

    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v3.py"
    rec["heightConstantBoundMaterialCount"] = bound_material_count
    rec["heightConstantBoundLeafOccurrenceCount"] = bound_leaf_count
    rec["uniqueHeightCbufferLeafNames"] = sorted(leaf_names)
    rec["uniqueHeightMaterialConstantHashes"] = [
        f"0x{value:08x}" for value in sorted(material_constant_hashes)
    ]
    rec["uniqueHeightConstantBindingSignatureCount"] = len(unique_binding_signatures)
    rec["heightConstantBindingSetSha256"] = _jhash(sorted(unique_binding_signatures))
    rec["heightConstantCoverageComplete"] = True
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["proofBoundary"] = (
        "v2 exact shader-specific vN DAGs plus per-Material constant values joined through "
        "DXBC RDEF, exact OAT .tech material assignments, T6 R_HashString, and direct "
        "serialized MaterialConstantDef bytes from the retained expanded world."
    )

    validated = validate_manifest(manifest)
    for material, row in validated.items():
        height = row.get(v2.HEIGHT_KEY)
        constants = row.get(HEIGHT_CONSTANT_KEY)
        if isinstance(height, dict) and not isinstance(constants, dict):
            raise NuketownShaderRecipeRecoveryV3Error(
                f"{material!r} lost exact height constant bindings during recipe validation"
            )
        if not isinstance(height, dict) and constants is not None:
            raise NuketownShaderRecipeRecoveryV3Error(
                f"{material!r} unexpectedly carries height constant bindings"
            )
    return manifest


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
) -> dict:
    base = v2.build_from_bindings(
        bindings,
        oat_root=oat_root,
        expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown,
    )
    return _augment_material_constant_bindings(
        base,
        source_bindings=bindings,
        oat_root=Path(oat_root),
    )


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
) -> dict:
    expanded_world = Path(expanded_world)
    if not expanded_world.is_file():
        raise NuketownShaderRecipeRecoveryV3Error(
            f"expanded Nuketown world does not exist: {expanded_world}"
        )
    data = expanded_world.read_bytes()
    expanded_sha = hashlib.sha256(data).hexdigest()
    try:
        bindings = retail_constants.bind_map(v2.v1.MAP, expanded_world)
    except Exception as exc:
        raise NuketownShaderRecipeRecoveryV3Error(
            f"direct retail generated Material constant recovery failed: {exc}"
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
