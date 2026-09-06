#!/usr/bin/env python3
"""Specialize glTF materials by exact T6 surface lightmap ownership for preview.

T6 GfxSurface owns `lightmapIndex`; Material does not.  Reusing one Blender
material for all surfaces with the same retail material therefore loses exact
lightmap ownership whenever those surfaces reference different lightmaps.

This metadata-only pass creates preview material shells keyed by:

    (retail glTF material index, lightmapIndex, lightmapTexCoord)

and redirects only lightmapped primitives to the appropriate shell.  Each shell
retains the complete original material/recipe/dependency metadata and adds an
exact `lightmapPreviewBindingV1`.  Canonical retail material identity remains in
that binding; the recipe's `material` field is never rewritten.

No BIN bytes, accessors, geometry, texture pixels, or T6 shader semantics change.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from t6_world_lightmap_preview_embed_v1 import FORMAT as PREVIEW_FORMAT, ROOT_KEY as PREVIEW_ROOT

FORMAT = "t6-world-lightmap-material-specialization-v1"
BINDING_KEY = "lightmapPreviewBindingV1"
ROOT_KEY = "lightmapMaterialSpecialization"


class LightmapMaterialSpecializeError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _surface_binding_map(archive: dict) -> dict[int, dict]:
    rows = archive.get("surfaceBindings")
    if not isinstance(rows, list):
        raise LightmapMaterialSpecializeError("canonical lightmap archive has no surfaceBindings")
    out: dict[int, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise LightmapMaterialSpecializeError("lightmap surface binding row is not an object")
        surface = int(row.get("surfaceIndex", -1))
        if surface < 0 or surface in out:
            raise LightmapMaterialSpecializeError(
                f"duplicate/invalid lightmap surface binding {surface}"
            )
        out[surface] = row
    return out


def _lightmap_by_index(archive: dict) -> dict[int, dict]:
    rows = archive.get("lightmaps")
    if not isinstance(rows, list):
        raise LightmapMaterialSpecializeError("canonical lightmap archive has no lightmaps")
    out = {}
    for expected, row in enumerate(rows):
        index = int(row.get("index", -1))
        if index != expected:
            raise LightmapMaterialSpecializeError(
                f"lightmap array is not dense/in-order at {expected}: {index}"
            )
        out[index] = row
    return out


def _role_binding(lightmap: dict, role: str) -> dict:
    item = lightmap.get(role)
    if not isinstance(item, dict):
        raise LightmapMaterialSpecializeError(
            f"lightmap {lightmap.get('index')} lacks {role} role"
        )
    present = bool(item.get("present"))
    out = {
        "present": present,
        "gfxImageAsset": item.get("gfxImageAsset"),
        "sourceTexture": item.get("sourceTexture"),
        "codeTextureSource": item.get("codeTextureSource"),
        "samplerAccessor": item.get("samplerAccessor"),
        "previewAvailable": False,
    }
    if not present:
        return out
    preview = item.get("preview")
    if not isinstance(preview, dict):
        # Present-but-unembedded/missing remains explicit. Do not invent a
        # renderer fallback texture.
        return out
    if preview.get("format") != PREVIEW_FORMAT:
        raise LightmapMaterialSpecializeError(
            f"lightmap {lightmap.get('index')} {role}: unexpected preview format {preview.get('format')!r}"
        )
    if preview.get("sourceDdsSha256") != item.get("sha256"):
        raise LightmapMaterialSpecializeError(
            f"lightmap {lightmap.get('index')} {role}: preview DDS identity disagrees"
        )
    out.update({
        "previewAvailable": True,
        "previewTextureIndex": int(preview["previewTextureIndex"]),
        "previewImageIndex": int(preview["previewImageIndex"]),
        "previewPngSha256": str(preview["previewPngSha256"]),
        "sourceDdsSha256": str(preview["sourceDdsSha256"]),
        "width": int(preview["width"]),
        "height": int(preview["height"]),
    })
    return out


def specialize(document: dict, raw: bytes) -> tuple[dict, bytes, dict]:
    out = copy.deepcopy(document)
    root_t6 = out.setdefault("extras", {}).setdefault("T6", {})
    if root_t6.get(ROOT_KEY) is not None:
        raise LightmapMaterialSpecializeError("lightmap material specialization already attached")
    preview_archive = root_t6.get(PREVIEW_ROOT)
    if not isinstance(preview_archive, dict) or preview_archive.get("format") != PREVIEW_FORMAT:
        raise LightmapMaterialSpecializeError(
            f"exact lightmap preview archive {PREVIEW_FORMAT} is required"
        )
    archive = root_t6.get("lightmapArchive")
    if not isinstance(archive, dict):
        raise LightmapMaterialSpecializeError("canonical lightmap archive is absent")

    materials = out.get("materials")
    meshes = out.get("meshes")
    if not isinstance(materials, list) or not isinstance(meshes, list):
        raise LightmapMaterialSpecializeError("glTF requires materials[] and meshes[]")
    source_material_count = len(materials)
    surface_bindings = _surface_binding_map(archive)
    lightmaps = _lightmap_by_index(archive)

    variant_by_key: dict[tuple[int, int, int], int] = {}
    variant_rows = []
    redirected = 0
    no_lightmap = 0
    missing_preview_role_uses = 0
    seen_surfaces: set[int] = set()

    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives")
        if not isinstance(primitives, list):
            continue
        for primitive_index, primitive in enumerate(primitives):
            t6_surface = primitive.get("extras", {}).get("T6", {})
            if not isinstance(t6_surface, dict) or t6_surface.get("index") is None:
                # Non-world meshes may coexist in a future combined artifact.
                continue
            surface = int(t6_surface["index"])
            if surface in seen_surfaces:
                raise LightmapMaterialSpecializeError(
                    f"world surface {surface} occurs in multiple primitives"
                )
            seen_surfaces.add(surface)
            binding = surface_bindings.get(surface)
            if binding is None:
                raise LightmapMaterialSpecializeError(
                    f"surface {surface}: no canonical lightmap surface binding"
                )
            primitive_lm = int(t6_surface.get("lightmapIndex", -999))
            manifest_lm = int(binding.get("lightmapIndex", -998))
            if primitive_lm != manifest_lm:
                raise LightmapMaterialSpecializeError(
                    f"surface {surface}: primitive lightmapIndex {primitive_lm} != manifest {manifest_lm}"
                )
            if not bool(binding.get("hasLightmap")):
                no_lightmap += 1
                continue
            lightmap = lightmaps.get(manifest_lm)
            if lightmap is None:
                raise LightmapMaterialSpecializeError(
                    f"surface {surface}: lightmap {manifest_lm} unavailable"
                )
            texcoord = int(binding.get("lightmapTexCoord", -1))
            attrs = primitive.get("attributes", {})
            if texcoord < 0 or f"TEXCOORD_{texcoord}" not in attrs:
                raise LightmapMaterialSpecializeError(
                    f"surface {surface}: exact lightmap TEXCOORD_{texcoord} is absent"
                )
            source_material_index = int(primitive.get("material", -1))
            if source_material_index < 0 or source_material_index >= source_material_count:
                raise LightmapMaterialSpecializeError(
                    f"surface {surface}: invalid retail material index {source_material_index}"
                )
            key = (source_material_index, manifest_lm, texcoord)
            variant_index = variant_by_key.get(key)
            if variant_index is None:
                source_material = materials[source_material_index]
                retail_name = str(source_material.get("name") or f"material_{source_material_index}")
                variant = copy.deepcopy(source_material)
                variant_name = f"{retail_name}__T6_LM{manifest_lm:04d}_TC{texcoord}"
                variant["name"] = variant_name
                vt6 = variant.setdefault("extras", {}).setdefault("T6", {})
                primary = _role_binding(lightmap, "primary")
                secondary = _role_binding(lightmap, "secondary")
                missing_preview_role_uses += int(primary["present"] and not primary["previewAvailable"])
                missing_preview_role_uses += int(secondary["present"] and not secondary["previewAvailable"])
                specialization = {
                    "format": FORMAT,
                    "previewOnly": True,
                    "retailMaterialIndex": source_material_index,
                    "retailMaterialName": retail_name,
                    "variantMaterialName": variant_name,
                    "lightmapIndex": manifest_lm,
                    "lightmapTexCoord": texcoord,
                    "primary": primary,
                    "secondary": secondary,
                    "surfaceOwnership": "GfxSurface.lightmapIndex + canonical surfaceBindings exact join",
                    "canonicalRecipeIdentity": (
                        "generatedShaderRecipeV1.material remains retailMaterialName; preview variant name is not retail identity"
                    ),
                }
                specialization["bindingSha256"] = _jhash(specialization)
                vt6[BINDING_KEY] = specialization
                variant_index = len(materials)
                materials.append(variant)
                variant_by_key[key] = variant_index
                variant_rows.append({
                    "materialIndex": variant_index,
                    **specialization,
                })
            primitive["material"] = variant_index
            pt6 = primitive.setdefault("extras", {}).setdefault("T6", {})
            pt6["lightmapPreviewMaterialIndex"] = variant_index
            pt6["retailMaterialIndex"] = source_material_index
            redirected += 1

    missing_surface_bindings = sorted(set(surface_bindings) - seen_surfaces)
    if missing_surface_bindings:
        raise LightmapMaterialSpecializeError(
            f"{len(missing_surface_bindings)} canonical surface bindings did not match world primitives; "
            f"first={missing_surface_bindings[0]}"
        )

    stats = {
        "sourceMaterialCount": source_material_count,
        "finalMaterialCount": len(materials),
        "specializedMaterialCount": len(variant_rows),
        "redirectedLightmappedPrimitiveCount": redirected,
        "noLightmapPrimitiveCount": no_lightmap,
        "worldSurfacePrimitiveCount": len(seen_surfaces),
        "missingPresentPreviewRoleUseCount": missing_preview_role_uses,
        "binByteIdentical": True,
    }
    contract = {
        "format": FORMAT,
        "sourcePreviewFormat": PREVIEW_FORMAT,
        "stats": stats,
        "variants": variant_rows,
        "policy": (
            "preview-only material shell specialization by exact retail material/lightmap/UV ownership; "
            "canonical recipe/material identity and all BIN bytes remain unchanged"
        ),
    }
    contract["contractSha256"] = _jhash(contract)
    root_t6[ROOT_KEY] = contract
    return out, raw, stats
