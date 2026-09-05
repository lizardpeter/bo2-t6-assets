#!/usr/bin/env python3
"""Nuketown generated shader recipe recovery v5: exact paired vertex shaders.

v4 closes pixel-shader identity and complete vN height execution inputs. v5 adds
the exact slot-4 vertex shader payload identity from the same OAT TechniqueSet ->
technique pass chain. This does not yet assign physical output TEXCOORD roles;
it establishes the paired VS owner needed for that separate retained-DXBC proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v4 as v4
from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v2 import resolve_slot_shaders


FORMAT = "t6-nuketown-generated-shader-recipe-recovery-v5"
VERTEX_ARCHETYPE_KEY = "vertexShaderArchetype"


class NuketownShaderRecipeRecoveryV5Error(RuntimeError):
    pass


def _jhash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _augment_vertex_shader_identities(manifest: dict, *, oat_root: Path) -> dict:
    rows = manifest.get("materials")
    if not isinstance(rows, list):
        raise NuketownShaderRecipeRecoveryV5Error("v4 recovery manifest has no material rows")

    by_techset: dict[str, dict] = {}
    vertex_sha_to_techsets: dict[str, set[str]] = {}
    paired_rows: list[dict] = []
    for recipe in rows:
        material = str(recipe.get("material") or "")
        techset = str(recipe.get("techniqueSet") or "")
        resolved = by_techset.get(techset)
        if resolved is None:
            resolved = resolve_slot_shaders(
                oat_root,
                techset,
                slot_index=4,
                require_single_vertex_shader=True,
                require_single_pixel_shader=True,
            )
            by_techset[techset] = resolved
        vertex = resolved["vertexShaders"]
        pixel = resolved["pixelShaders"]
        if len(vertex) != 1 or len(pixel) != 1:
            raise NuketownShaderRecipeRecoveryV5Error(
                f"{techset!r} does not have a unique slot-4 VS/PS pair"
            )
        vs = vertex[0]
        ps = pixel[0]
        expected_ps = str(recipe.get("pixelShaderArchetype") or "")
        actual_ps = f"sha256:{ps['sha256']}"
        if expected_ps != actual_ps:
            raise NuketownShaderRecipeRecoveryV5Error(
                f"{material!r} recovered pixel shader {expected_ps!r} != paired OAT slot-4 {actual_ps!r}"
            )
        vertex_archetype = f"sha256:{vs['sha256']}"
        existing = recipe.get(VERTEX_ARCHETYPE_KEY)
        if existing is not None and str(existing) != vertex_archetype:
            raise NuketownShaderRecipeRecoveryV5Error(
                f"{material!r} already carries conflicting vertex shader {existing!r}"
            )
        recipe[VERTEX_ARCHETYPE_KEY] = vertex_archetype
        proof = recipe.get("proof")
        if not isinstance(proof, dict):
            raise NuketownShaderRecipeRecoveryV5Error(
                f"{material!r} lacks canonical retail proof metadata"
            )
        proof["vertexShaderAsset"] = vs["asset"]
        proof["vertexShaderFile"] = vs["relativeFile"]
        proof["vertexShaderBytes"] = vs["bytes"]
        proof["vertexShaderSha256"] = vs["sha256"]
        proof["pairedVertexShaderJoin"] = (
            "same exact OAT TechniqueSet slot 4 technique/pass as canonical pixel shader"
        )
        vertex_sha_to_techsets.setdefault(vs["sha256"], set()).add(techset)
        paired_rows.append({
            "material": material,
            "techniqueSet": techset,
            "vertexShaderSha256": vs["sha256"],
            "pixelShaderSha256": ps["sha256"],
        })

    rec = manifest.setdefault("recovery", {})
    rec["baseRecoveryFormat"] = rec.get("format")
    rec["baseRecipeRowsSha256"] = rec.get("recipeRowsSha256")
    rec["format"] = FORMAT
    rec["producer"] = "tools/t6_nuketown_generated_shader_recipe_recover_v5.py"
    rec["pairedVertexShaderMaterialCount"] = len(rows)
    rec["pairedVertexShaderTechniqueSetCount"] = len(by_techset)
    rec["uniquePairedVertexShaderCount"] = len(vertex_sha_to_techsets)
    rec["vertexShaderCrossTechniqueSetReuseCount"] = sum(
        1 for names in vertex_sha_to_techsets.values() if len(names) > 1
    )
    rec["pairedVsPsRowsSha256"] = _jhash(sorted(paired_rows, key=lambda row: row["material"]))
    rec["recipeRowsSha256"] = _jhash(rows)
    rec["pairedVertexShaderCoverageComplete"] = len(paired_rows) == len(rows)
    rec["proofBoundary"] = (
        "v4 exact generated pixel/height recipe plus exact paired slot-4 OAT vertex-shader "
        "asset and verbatim DX11 payload identity. Physical VS output TEXCOORD roles remain "
        "a separate direct-bytecode proof and are not inferred from shader or TechniqueSet names."
    )

    validated = validate_manifest(manifest)
    for material, recipe in validated.items():
        vertex = str(recipe.get(VERTEX_ARCHETYPE_KEY) or "")
        proof = recipe.get("proof", {})
        if not vertex.startswith("sha256:") or vertex[7:] != str(proof.get("vertexShaderSha256") or ""):
            raise NuketownShaderRecipeRecoveryV5Error(
                f"{material!r} lost paired vertex-shader identity during canonical validation"
            )
    return manifest


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
) -> dict:
    base = v4.build_from_bindings(
        bindings,
        oat_root=oat_root,
        expanded_sha256=expanded_sha256,
        strict_nuketown=strict_nuketown,
    )
    return _augment_vertex_shader_identities(base, oat_root=Path(oat_root))


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
) -> dict:
    base = v4.recover(
        expanded_world=expanded_world,
        oat_root=oat_root,
        strict_nuketown=strict_nuketown,
    )
    return _augment_vertex_shader_identities(base, oat_root=Path(oat_root))


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
