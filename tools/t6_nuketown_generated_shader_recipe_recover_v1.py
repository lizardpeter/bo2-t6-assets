#!/usr/bin/env python3
"""Rebuild the lost Nuketown generated-material shader recipe table exactly.

The old internal v31 build had 120 complete generated-material recipes but its
120-row serialization was never committed.  This tool reconstructs those rows
from two independently retained retail identities:

1. the expanded Nuketown world, where each serialized Material::techniqueSet
   pointer is rebound to the exact retail MaterialTechniqueSet XAsset and its
   worldVertFormat;
2. ordinary OpenAssetTools T6 output, where TechniqueSet slot 4 ("lit") maps to
   an exact technique asset, that .tech names its pixel shader, and T6 OAT dumps
   the DX11 shader bytecode verbatim to shader_bin/ps_<asset>.cso.

Compound '*' material grammar is used only to identify the population and by the
already source-closed canonical recipe validator to derive layer syntax.  It is
never used to guess TechniqueSet or shader identity.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

from t6_generated_shader_recipe_contract_v1 import FORMAT, validate_manifest
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader
import t6_retail_special_material_family_census_v1 as retail_census


MAP = "mp_nuketown_2020"
EXPECTED_GENERATED_MATERIALS = 120
EXPECTED_UNIQUE_TECHSETS = 34
EXPECTED_UNIQUE_SLOT4_SHADERS = 34
EXPECTED_WORLD_FORMAT_HISTOGRAM = {1: 95, 2: 7, 3: 17, 6: 1}
SLOT_INDEX = 4
SLOT_LABEL = "lit"


class NuketownShaderRecipeRecoveryError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_rows_sha(rows: list[dict]) -> str:
    payload = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )
    return _sha256(payload)


def _normalize_generated_bindings(bindings: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for raw in bindings:
        material = str(raw.get("material") or "")
        if not material.startswith("*"):
            continue
        if material in seen:
            raise NuketownShaderRecipeRecoveryError(
                f"duplicate generated material binding {material!r}"
            )
        seen.add(material)
        techset = str(raw.get("techniqueSet") or "")
        if not techset:
            raise NuketownShaderRecipeRecoveryError(
                f"generated material {material!r} has no exact TechniqueSet binding"
            )
        try:
            world_format = int(raw["worldVertFormat"])
        except Exception as exc:
            raise NuketownShaderRecipeRecoveryError(
                f"generated material {material!r} has invalid worldVertFormat"
            ) from exc
        out.append({
            "material": material,
            "techniqueSet": techset,
            "worldVertFormat": world_format,
        })
    return sorted(out, key=lambda row: row["material"])


def build_from_bindings(
    bindings: list[dict],
    *,
    oat_root: Path,
    expanded_sha256: str,
    strict_nuketown: bool = True,
) -> dict:
    """Build a canonical recipe manifest from already retail-resolved bindings."""
    generated = _normalize_generated_bindings(bindings)
    if not generated:
        raise NuketownShaderRecipeRecoveryError("no generated '*' materials in retail bindings")

    format_hist = collections.Counter(row["worldVertFormat"] for row in generated)
    techsets = sorted({row["techniqueSet"] for row in generated})

    if strict_nuketown:
        if len(generated) != EXPECTED_GENERATED_MATERIALS:
            raise NuketownShaderRecipeRecoveryError(
                f"Nuketown generated-material count {len(generated)} != {EXPECTED_GENERATED_MATERIALS}"
            )
        if len(techsets) != EXPECTED_UNIQUE_TECHSETS:
            raise NuketownShaderRecipeRecoveryError(
                f"Nuketown generated TechniqueSet count {len(techsets)} != {EXPECTED_UNIQUE_TECHSETS}"
            )
        if dict(sorted(format_hist.items())) != EXPECTED_WORLD_FORMAT_HISTOGRAM:
            raise NuketownShaderRecipeRecoveryError(
                "Nuketown generated worldVertFormat histogram mismatch: "
                f"{dict(sorted(format_hist.items()))} != {EXPECTED_WORLD_FORMAT_HISTOGRAM}"
            )

    resolved_by_techset: dict[str, dict] = {}
    sha_to_techsets: dict[str, list[str]] = collections.defaultdict(list)
    for techset in techsets:
        resolved = resolve_slot_shader(oat_root, techset, slot_index=SLOT_INDEX)
        if resolved["slotLabel"] != SLOT_LABEL:
            raise NuketownShaderRecipeRecoveryError(
                f"T6 slot {SLOT_INDEX} unexpectedly named {resolved['slotLabel']!r}"
            )
        shaders = resolved["pixelShaders"]
        if len(shaders) != 1:
            raise NuketownShaderRecipeRecoveryError(
                f"TechniqueSet {techset!r} slot {SLOT_INDEX} is not a single-shader archetype"
            )
        shader = shaders[0]
        resolved_by_techset[techset] = resolved
        sha_to_techsets[shader["sha256"]].append(techset)

    reused = {
        sha: sorted(names)
        for sha, names in sha_to_techsets.items()
        if len(names) > 1
    }
    if strict_nuketown:
        if len(sha_to_techsets) != EXPECTED_UNIQUE_SLOT4_SHADERS:
            raise NuketownShaderRecipeRecoveryError(
                f"Nuketown unique slot-4 shader count {len(sha_to_techsets)} != "
                f"{EXPECTED_UNIQUE_SLOT4_SHADERS}"
            )
        if reused:
            first_sha = sorted(reused)[0]
            raise NuketownShaderRecipeRecoveryError(
                "unexpected cross-TechniqueSet slot-4 shader reuse: "
                f"{first_sha} -> {reused[first_sha]}"
            )

    recipe_rows: list[dict] = []
    operation_hist = collections.Counter()
    for binding in generated:
        resolved = resolved_by_techset[binding["techniqueSet"]]
        shader = resolved["pixelShaders"][0]
        recipe = {
            "material": binding["material"],
            "techniqueSet": binding["techniqueSet"],
            "pixelShaderArchetype": f"sha256:{shader['sha256']}",
            "worldVertFormats": [binding["worldVertFormat"]],
            "proof": {
                "map": MAP,
                "retailExpandedSha256": expanded_sha256,
                "materialTechniqueSetJoin": (
                    "serialized retail Material::techniqueSet pointer -> exact TechniqueSet XAsset"
                ),
                "techniqueSlotIndex": SLOT_INDEX,
                "techniqueSlotLabel": SLOT_LABEL,
                "techsetFile": resolved["techsetFile"],
                "techniqueAsset": resolved["techniqueAsset"],
                "techniqueFile": resolved["techniqueFile"],
                "pixelShaderAsset": shader["asset"],
                "pixelShaderFile": shader["relativeFile"],
                "pixelShaderBytes": shader["bytes"],
                "pixelShaderSha256": shader["sha256"],
                "oatDx11PayloadRule": (
                    "T6 TechsetDumper writes prog.loadDef.program verbatim for programSize bytes"
                ),
                "shaderJoinPolicy": "exact OAT asset chain; no compound-material-name inference",
            },
        }
        recipe_rows.append(recipe)

    manifest = {
        "format": FORMAT,
        "materials": recipe_rows,
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v1",
            "producer": "tools/t6_nuketown_generated_shader_recipe_recover_v1.py",
            "map": MAP,
            "retailExpandedSha256": expanded_sha256,
            "generatedMaterialCount": len(generated),
            "uniqueTechniqueSetCount": len(techsets),
            "uniqueSlot4PixelShaderCount": len(sha_to_techsets),
            "crossTechniqueSetShaderReuseCount": len(reused),
            "worldVertFormatHistogram": {
                str(k): v for k, v in sorted(format_hist.items())
            },
            "slotIndex": SLOT_INDEX,
            "slotLabel": SLOT_LABEL,
            "recipeRowsSha256": _canonical_rows_sha(recipe_rows),
            "strictNuketownInvariants": strict_nuketown,
            "proofBoundary": (
                "Exact retail material->TechniqueSet binding plus exact OAT T6 slot-4 "
                "TechniqueSet->Technique->pixelShader->verbatim DX11 bytecode chain. "
                "Layer-program syntax is canonical/source-closed; per-shader vN height DAG "
                "execution and downstream lighting remain separate contracts."
            ),
        },
    }

    # This also source-closes the serialized layerProgram syntax and rejects any
    # generated TechniqueSet whose grammar cannot produce a canonical recipe.
    validated = validate_manifest(manifest)
    for row in validated.values():
        for step in row["layerProgram"]:
            operation_hist[step["operation"]] += 1
    manifest["recovery"]["generatedDiffuseOperationHistogram"] = dict(
        sorted(operation_hist.items())
    )
    return manifest


def recover(
    *,
    expanded_world: Path,
    oat_root: Path,
    strict_nuketown: bool = True,
) -> dict:
    expanded_world = Path(expanded_world)
    if not expanded_world.is_file():
        raise NuketownShaderRecipeRecoveryError(
            f"expanded Nuketown world does not exist: {expanded_world}"
        )
    expanded_data = expanded_world.read_bytes()
    expanded_sha = _sha256(expanded_data)

    try:
        bindings = retail_census.bind_map(MAP, expanded_world)
    except Exception as exc:
        raise NuketownShaderRecipeRecoveryError(
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
    parser.add_argument(
        "--relaxed",
        action="store_true",
        help="disable Nuketown's retained 120/34/34/world-format regression gates",
    )
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
