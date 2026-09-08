#!/usr/bin/env python3
"""Reusable T6 PC32 XModel block-5 VIRTUAL cursor replay primitives.

This module is extracted from the exact retained Nuketown cross-XModel resolver
`t6_nuketown_static_material_alias_resolve_v3.py` (14,662 bytes,
SHA-256 b33e28e355ee62e869a4a9c44b8a2740a87d5b66896fefab48e1e8656ac4fbad).

The important loader rule is that XBlock destination alignment advances the
VIRTUAL destination cursor only; it never pads the serialized source cursor.
These helpers therefore keep source ranges (already proven by the XModel
walker/normalizer) separate from destination allocation alignment.

This is proof infrastructure, not a name/order resolver.  A Material alias is
promotable only when an independently anchored VIRTUAL cursor places an exact
Material* slot at the packed target offset and the slot's retail Material
identity is itself source-derived.
"""
from __future__ import annotations

import struct
from typing import Any

FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
VIRTUAL_BLOCK = 5
BLOCK_SHIFT = 29
OFFSET_MASK = (1 << BLOCK_SHIFT) - 1
RETAINED_V3_SOURCE_SHA256 = "b33e28e355ee62e869a4a9c44b8a2740a87d5b66896fefab48e1e8656ac4fbad"


class VirtualCursorError(ValueError):
    pass


def align_up(value: int, alignment: int) -> int:
    if alignment <= 0 or alignment & (alignment - 1):
        raise VirtualCursorError(f"alignment must be a power of two: {alignment}")
    return (value + alignment - 1) & ~(alignment - 1)


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]


def decode_packed_pointer(raw: int) -> tuple[int, int]:
    if raw in (0, FOLLOW, INSERT):
        raise VirtualCursorError(f"not a packed pointer: 0x{raw:08X}")
    encoded = (raw - 1) & 0xFFFFFFFF
    return encoded >> BLOCK_SHIFT, encoded & OFFSET_MASK


def ptr(data: bytes, base: int, off: int) -> int:
    return u32(data, base + off)


def geometry_events(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Return exact source-ordered XSurface destination allocations."""
    out: list[dict[str, Any]] = []
    for surface in model.get("surfaces", []):
        si = int(surface["surfaceIndex"])
        for field, alignment in (
            ("vertsBlend", 2),
            ("tensionData", 4),
            ("vertices", 16),
            ("rigidList", 4),
        ):
            row = surface.get(field)
            if isinstance(row, dict) and isinstance(row.get("offset"), int) and isinstance(row.get("size"), int):
                out.append({
                    "sourceOffset": int(row["offset"]),
                    "size": int(row["size"]),
                    "alignment": alignment,
                    "label": f"surface[{si}].{field}",
                })
        for rigid_index, rigid in enumerate(surface.get("rigidEntries") or []):
            tree = rigid.get("collisionTree") or {}
            for field, alignment in (("fixed", 4), ("nodes", 16), ("leafs", 2)):
                row = tree.get(field)
                if isinstance(row, dict) and isinstance(row.get("offset"), int) and isinstance(row.get("size"), int):
                    out.append({
                        "sourceOffset": int(row["offset"]),
                        "size": int(row["size"]),
                        "alignment": alignment,
                        "label": f"surface[{si}].rigid[{rigid_index}].collisionTree.{field}",
                    })
        row = surface.get("triangles")
        if isinstance(row, dict) and isinstance(row.get("offset"), int) and isinstance(row.get("size"), int):
            out.append({
                "sourceOffset": int(row["offset"]),
                "size": int(row["size"]),
                "alignment": 16,
                "label": f"surface[{si}].triangles",
            })
    out.sort(key=lambda row: row["sourceOffset"])
    return out


def prefix_to_material_handles(data: bytes, model: dict[str, Any], start_virtual: int) -> int:
    """Replay a top-level XModel's VIRTUAL prefix and return Material* array base.

    `start_virtual` is the exact block-5 cursor at entry to this XModel.  The
    fixed XModel object itself is TEMP and therefore does not advance block 5.
    """
    base = int(model["xmodelRawStart"])
    virtual = int(start_virtual)

    name_raw = ptr(data, base, 0)
    if name_raw == FOLLOW:
        virtual += len(model["modelName"].encode("utf-8")) + 1
    elif name_raw not in (0, INSERT):
        raise VirtualCursorError(f"XAsset {model.get('xassetIndex')}: packed XModel.name is not propagatable")

    num_bones = int(model["numBones"])
    num_root_bones = int(model["numRootBones"])
    non_roots = num_bones - num_root_bones
    fields = (
        (8, 2, 2 * num_bones, "boneNames"),
        (12, 1, non_roots, "parentList"),
        (16, 2, 8 * non_roots, "quats"),
        (20, 4, 16 * non_roots, "trans"),
        (24, 1, num_bones, "partClassification"),
        (28, 4, 32 * num_bones, "baseMat"),
    )
    for field_off, alignment, size, _label in fields:
        raw = ptr(data, base, field_off)
        if raw == FOLLOW:
            virtual = align_up(virtual, alignment)
            virtual += size
        elif raw not in (0, INSERT):
            # Packed/reused prefix arrays allocate no new destination bytes.
            pass

    surfaces = model.get("surfaces") or []
    surfaces_raw = ptr(data, base, 32)
    if surfaces_raw == FOLLOW:
        virtual = align_up(virtual, 16)
        virtual += 80 * len(surfaces)
    elif surfaces_raw not in (0, INSERT):
        raise VirtualCursorError(f"XAsset {model.get('xassetIndex')}: packed whole-surface array is not propagatable")

    events = geometry_events(model)
    source_cursor = (
        int(model["surfacesFixed"]["offset"]) + int(model["surfacesFixed"]["size"])
        if events
        else int(model["geometrySerializedEnd"])
    )
    for event in events:
        if event["sourceOffset"] != source_cursor:
            raise VirtualCursorError(
                f"XAsset {model.get('xassetIndex')}: geometry source gap "
                f"{source_cursor}->{event['sourceOffset']} ({event['label']})"
            )
        virtual = align_up(virtual, int(event["alignment"]))
        virtual += int(event["size"])
        source_cursor += int(event["size"])
    if source_cursor != int(model["geometrySerializedEnd"]):
        raise VirtualCursorError(
            f"XAsset {model.get('xassetIndex')}: geometry end drift "
            f"{source_cursor}!={model['geometrySerializedEnd']}"
        )
    return align_up(virtual, 4)


def simple_tail_end(data: bytes, model: dict[str, Any], material_base: int) -> tuple[int | None, dict[str, Any] | None]:
    """Replay the post-geometry XModel tail or return a fail-closed blocker."""
    base = int(model["xmodelRawStart"])
    source = int(model["geometrySerializedEnd"])
    virtual = int(material_base)
    materials = model.get("materials") or []

    if ptr(data, base, 36) != FOLLOW:
        return None, {"kind": "materialHandles-not-inline-array", "raw": ptr(data, base, 36)}
    virtual = align_up(virtual, 4)
    if virtual != material_base:
        return None, {"kind": "materialHandles-base-not-align4", "base": material_base}

    for index, handle in enumerate(materials):
        raw = u32(data, source + 4 * index)
        if raw in (FOLLOW, INSERT) or handle.get("inline"):
            return None, {
                "kind": "inline-material-tail",
                "surfaceIndex": index,
                "material": handle.get("name"),
                "raw": raw,
            }
    virtual += 4 * len(materials)
    source += 4 * len(materials)

    collision_ptr = ptr(data, base, 152)
    collision_count = i32(data, base + 156)
    if collision_ptr == FOLLOW:
        virtual = align_up(virtual, 4)
        fixed = source
        virtual += collision_count * 44
        source += collision_count * 44
        for index in range(collision_count):
            tris_ptr = u32(data, fixed + 44 * index)
            tri_count = i32(data, fixed + 44 * index + 4)
            if tris_ptr == FOLLOW:
                virtual = align_up(virtual, 4)
                virtual += tri_count * 48
                source += tri_count * 48
            elif tris_ptr == INSERT:
                return None, {"kind": "insert-colltris", "index": index}
    elif collision_ptr == INSERT:
        return None, {"kind": "insert-collSurfs"}

    bone_info_ptr = ptr(data, base, 164)
    if bone_info_ptr == FOLLOW:
        virtual = align_up(virtual, 4)
        virtual += int(model["numBones"]) * 44
        source += int(model["numBones"]) * 44
    elif bone_info_ptr == INSERT:
        return None, {"kind": "insert-boneInfo"}

    himip_ptr = ptr(data, base, 200)
    if himip_ptr == FOLLOW:
        virtual = align_up(virtual, 4)
        virtual += len(materials) * 4
        source += len(materials) * 4
    elif himip_ptr == INSERT:
        return None, {"kind": "insert-himip"}

    phys_ptr = ptr(data, base, 216)
    if phys_ptr in (FOLLOW, INSERT):
        return None, {"kind": "inline-physPreset", "raw": phys_ptr}

    collmap_count = data[base + 220]
    collmap_ptr = ptr(data, base, 224)
    if collmap_count and collmap_ptr in (FOLLOW, INSERT):
        return None, {"kind": "inline-collmaps", "count": collmap_count, "raw": collmap_ptr}

    constraints_ptr = ptr(data, base, 228)
    if constraints_ptr in (FOLLOW, INSERT):
        return None, {"kind": "inline-physConstraints", "raw": constraints_ptr}

    if source != int(model["xmodelRawEnd"]):
        return None, {
            "kind": "source-tail-end-drift",
            "predicted": source,
            "expected": int(model["xmodelRawEnd"]),
        }
    return virtual, None


def material_slot_offset(material_base: int, surface_index: int) -> int:
    if surface_index < 0:
        raise VirtualCursorError("surface index must be non-negative")
    return int(material_base) + 4 * int(surface_index)


def packed_virtual_key(raw_or_handle: int | dict[str, Any]) -> tuple[int, int] | None:
    """Normalize raw or walker-form packed pointers to `(block, offset)`."""
    if isinstance(raw_or_handle, int):
        if raw_or_handle in (0, FOLLOW, INSERT):
            return None
        return decode_packed_pointer(raw_or_handle)
    handle = raw_or_handle.get("pointer") if isinstance(raw_or_handle.get("pointer"), dict) else raw_or_handle
    kind = handle.get("kind")
    if kind in ("offset", "packed") and handle.get("block") is not None and handle.get("offset") is not None:
        return int(handle["block"]), int(handle["offset"])
    raw = handle.get("raw")
    if isinstance(raw, int) and raw not in (0, FOLLOW, INSERT):
        return decode_packed_pointer(raw)
    return None


if __name__ == "__main__":
    # Tiny deterministic self-test; retail authority always comes from callers.
    assert align_up(5, 4) == 8
    assert decode_packed_pointer(0xA10257ED) == (5, 16930796)
    assert material_slot_offset(16930792, 1) == 16930796
    print("t6_xmodel_virtual_cursor_v1: self-test PASS")
