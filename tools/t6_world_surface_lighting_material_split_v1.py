#!/usr/bin/env python3
"""Split shared glTF world materials by exact T6 surface lighting ownership.

T6 `GfxSurface` stores `lightmapIndex`, `reflectionProbeIndex` and
`primaryLightIndex` per surface, while a glTF/Blender material is normally shared
by every primitive that references it. A renderer-facing material graph cannot
bind the correct baked-light/probe resources if two surfaces share one source
material but use different lighting indices.

This transformer clones materials by the exact tuple:

    (sourceMaterialIndex, lightmapIndex, reflectionProbeIndex, primaryLightIndex)

and rewrites primitive material references only. Geometry buffers/accessors are
untouched. The original source material identity and index are retained in each
clone's `extras.T6.surfaceLightingSplitV1`, making the operation reversible.

No lightmap/reflection shader equation is inferred here.
"""
from __future__ import annotations

import copy


FORMAT = "t6-world-surface-lighting-material-split-v1"


class SurfaceLightingSplitError(RuntimeError):
    pass


def _surface_binding(primitive: dict, *, mesh_index: int, primitive_index: int) -> tuple[int, int, int]:
    t6 = primitive.get("extras", {}).get("T6")
    if not isinstance(t6, dict):
        raise SurfaceLightingSplitError(
            f"mesh {mesh_index} primitive {primitive_index} lacks extras.T6 surface provenance"
        )
    required = ("lightmapIndex", "reflectionProbeIndex", "primaryLightIndex")
    missing = [key for key in required if key not in t6]
    if missing:
        raise SurfaceLightingSplitError(
            f"mesh {mesh_index} primitive {primitive_index} lacks {missing}"
        )
    return tuple(int(t6[key]) for key in required)


def split_surface_lighting_materials(gltf: dict) -> dict:
    """Return a deep-copied glTF document with exact per-surface material clones."""
    out = copy.deepcopy(gltf)
    source_materials = list(out.get("materials", []))
    if not source_materials:
        raise SurfaceLightingSplitError("glTF contains no materials")

    original_count = len(source_materials)
    clones: list[dict] = []
    clone_index: dict[tuple[int, int, int, int], int] = {}
    source_use_counts: dict[int, int] = {}
    tuple_use_counts: dict[tuple[int, int, int, int], int] = {}

    for mesh_index, mesh in enumerate(out.get("meshes", [])):
        primitives = mesh.get("primitives")
        if not isinstance(primitives, list):
            raise SurfaceLightingSplitError(f"mesh {mesh_index} primitives is not a list")
        for primitive_index, primitive in enumerate(primitives):
            if "material" not in primitive:
                raise SurfaceLightingSplitError(
                    f"mesh {mesh_index} primitive {primitive_index} has no material"
                )
            source_index = int(primitive["material"])
            if source_index < 0 or source_index >= original_count:
                raise SurfaceLightingSplitError(
                    f"mesh {mesh_index} primitive {primitive_index} bad material {source_index}"
                )
            lightmap, reflection, primary = _surface_binding(
                primitive, mesh_index=mesh_index, primitive_index=primitive_index
            )
            key = (source_index, lightmap, reflection, primary)
            source_use_counts[source_index] = source_use_counts.get(source_index, 0) + 1
            tuple_use_counts[key] = tuple_use_counts.get(key, 0) + 1

            target = clone_index.get(key)
            if target is None:
                source = source_materials[source_index]
                clone = copy.deepcopy(source)
                source_name = str(source.get("name") or f"material_{source_index}")
                suffix = f"__T6_LM{lightmap}_RP{reflection}_PL{primary}"
                clone["name"] = source_name + suffix
                t6 = clone.setdefault("extras", {}).setdefault("T6", {})
                t6["surfaceLightingSplitV1"] = {
                    "format": FORMAT,
                    "sourceMaterialIndex": source_index,
                    "sourceMaterialName": source_name,
                    "lightmapIndex": lightmap,
                    "reflectionProbeIndex": reflection,
                    "primaryLightIndex": primary,
                    "joinPolicy": "exact primitive extras.T6 indices",
                }
                target = original_count + len(clones)
                clone_index[key] = target
                clones.append(clone)
            primitive["material"] = target

    # Keep originals as an immutable provenance prefix. This also means a later
    # inverse transform can restore primitive material indices without needing
    # an external file.
    out["materials"] = source_materials + clones
    root = out.setdefault("extras", {}).setdefault("T6", {})
    root["surfaceLightingMaterialSplit"] = {
        "format": FORMAT,
        "sourceMaterialPrefixCount": original_count,
        "cloneMaterialCount": len(clones),
        "primitiveCount": sum(tuple_use_counts.values()),
        "uniqueLightingTupleCount": len(clone_index),
        "sourceMaterialUseCount": len(source_use_counts),
        "sourceMaterialsRetainedAsPrefix": True,
        "geometryBuffersModified": False,
        "key": [
            "sourceMaterialIndex",
            "lightmapIndex",
            "reflectionProbeIndex",
            "primaryLightIndex",
        ],
    }
    validate_surface_lighting_split(out)
    return out


def validate_surface_lighting_split(gltf: dict) -> bool:
    root = gltf.get("extras", {}).get("T6", {}).get("surfaceLightingMaterialSplit")
    if not isinstance(root, dict) or root.get("format") != FORMAT:
        raise SurfaceLightingSplitError("missing/invalid surface-lighting split metadata")
    prefix = int(root["sourceMaterialPrefixCount"])
    materials = gltf.get("materials", [])
    if prefix < 1 or prefix > len(materials):
        raise SurfaceLightingSplitError("invalid source material prefix count")

    seen_keys: dict[tuple[int, int, int, int], int] = {}
    primitive_count = 0
    for mesh_index, mesh in enumerate(gltf.get("meshes", [])):
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            primitive_count += 1
            material_index = int(primitive.get("material", -1))
            if material_index < prefix or material_index >= len(materials):
                raise SurfaceLightingSplitError(
                    f"mesh {mesh_index} primitive {primitive_index} does not reference a split clone"
                )
            clone = materials[material_index]
            split = clone.get("extras", {}).get("T6", {}).get("surfaceLightingSplitV1")
            if not isinstance(split, dict) or split.get("format") != FORMAT:
                raise SurfaceLightingSplitError(f"material {material_index} lacks split provenance")
            source_index = int(split["sourceMaterialIndex"])
            if source_index < 0 or source_index >= prefix:
                raise SurfaceLightingSplitError(f"material {material_index} bad source index")
            surface_key = _surface_binding(
                primitive, mesh_index=mesh_index, primitive_index=primitive_index
            )
            clone_key = (
                source_index,
                int(split["lightmapIndex"]),
                int(split["reflectionProbeIndex"]),
                int(split["primaryLightIndex"]),
            )
            expected_key = (source_index, *surface_key)
            if clone_key != expected_key:
                raise SurfaceLightingSplitError(
                    f"mesh {mesh_index} primitive {primitive_index} lighting tuple mismatch"
                )
            prior = seen_keys.setdefault(clone_key, material_index)
            if prior != material_index:
                raise SurfaceLightingSplitError(f"lighting tuple duplicated across clones: {clone_key}")

    if primitive_count != int(root["primitiveCount"]):
        raise SurfaceLightingSplitError("split primitive count mismatch")
    if len(seen_keys) != int(root["uniqueLightingTupleCount"]):
        raise SurfaceLightingSplitError("split tuple count mismatch")
    if len(materials) - prefix != int(root["cloneMaterialCount"]):
        raise SurfaceLightingSplitError("split clone count mismatch")
    return True


def restore_source_material_indices(gltf: dict) -> dict:
    """Inverse the split and discard clone materials."""
    validate_surface_lighting_split(gltf)
    out = copy.deepcopy(gltf)
    root = out["extras"]["T6"]["surfaceLightingMaterialSplit"]
    prefix = int(root["sourceMaterialPrefixCount"])
    materials = out["materials"]
    for mesh in out.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            clone = materials[int(primitive["material"])]
            split = clone["extras"]["T6"]["surfaceLightingSplitV1"]
            primitive["material"] = int(split["sourceMaterialIndex"])
    out["materials"] = materials[:prefix]
    out["extras"]["T6"].pop("surfaceLightingMaterialSplit", None)
    return out
