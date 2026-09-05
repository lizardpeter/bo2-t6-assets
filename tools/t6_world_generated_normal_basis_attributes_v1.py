#!/usr/bin/env python3
"""Expose exact T6 generated-normal basis data as Blender-readable attributes.

The production glTF already stores source-exact decoded world NORMAL and TANGENT
(VEC4, with retail binormal sign in w).  Blender may recompute tangents and its
Tangent shader node does not expose the imported w component.  This postpass
therefore aliases the existing bytes for generated primitives as:

    _T6_WORLD_NORMAL          FLOAT VEC3 (same accessor as NORMAL)
    _T6_WORLD_TANGENT         FLOAT VEC3 (strided view of TANGENT.xyz)
    _T6_TANGENT_HANDEDNESS    FLOAT SCALAR (strided view of TANGENT.w)

No buffer bytes are appended or rewritten.  The tangent aliases use a second
bufferView over the exact original tangent payload with byteStride=16.  This is
renderer metadata only and preserves the complete v18 artifact byte-for-byte in
its BIN chunk.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

FORMAT = "t6-generated-normal-basis-attributes-v1"
SOURCE_ATTRIBUTE_FORMAT = "t6-world-generated-attribute-contract-v1"
FLOAT = 5126
ARRAY_BUFFER = 34962


class GeneratedNormalBasisAttributeError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _generated_material(document: dict, primitive: dict) -> str | None:
    try:
        index = int(primitive["material"])
        material = document["materials"][index]
    except Exception as exc:
        raise GeneratedNormalBasisAttributeError("primitive has invalid material reference") from exc
    name = str(material.get("name") or "")
    if not name:
        raise GeneratedNormalBasisAttributeError(f"material {index} has empty name")
    return name if name.startswith("*") else None


def _accessor(document: dict, index: int, label: str) -> tuple[dict, dict]:
    try:
        accessor = document["accessors"][int(index)]
        view = document["bufferViews"][int(accessor["bufferView"])]
    except Exception as exc:
        raise GeneratedNormalBasisAttributeError(f"{label}: invalid accessor {index}") from exc
    if int(view.get("buffer", 0)) != 0:
        raise GeneratedNormalBasisAttributeError(f"{label}: accessor is not in buffer 0")
    return accessor, view


def _validate_normal(document: dict, accessor_index: int) -> None:
    accessor, view = _accessor(document, accessor_index, "NORMAL")
    if int(accessor.get("componentType", -1)) != FLOAT or accessor.get("type") != "VEC3":
        raise GeneratedNormalBasisAttributeError("NORMAL is not FLOAT VEC3")
    if bool(accessor.get("normalized", False)):
        raise GeneratedNormalBasisAttributeError("NORMAL FLOAT accessor is unexpectedly normalized")
    if int(accessor.get("byteOffset", 0)) != 0:
        raise GeneratedNormalBasisAttributeError("NORMAL accessor has unsupported nonzero byteOffset")
    if view.get("byteStride") not in (None, 12):
        raise GeneratedNormalBasisAttributeError("NORMAL accessor has unexpected byteStride")
    count = int(accessor.get("count", -1))
    if count <= 0 or int(view.get("byteLength", -1)) < count * 12:
        raise GeneratedNormalBasisAttributeError("NORMAL payload is shorter than its accessor")


def _validate_tangent(document: dict, accessor_index: int) -> tuple[dict, dict, int]:
    accessor, view = _accessor(document, accessor_index, "TANGENT")
    if int(accessor.get("componentType", -1)) != FLOAT or accessor.get("type") != "VEC4":
        raise GeneratedNormalBasisAttributeError("TANGENT is not FLOAT VEC4")
    if bool(accessor.get("normalized", False)):
        raise GeneratedNormalBasisAttributeError("TANGENT FLOAT accessor is unexpectedly normalized")
    if int(accessor.get("byteOffset", 0)) != 0:
        raise GeneratedNormalBasisAttributeError("TANGENT accessor has unsupported nonzero byteOffset")
    if view.get("byteStride") not in (None, 16):
        raise GeneratedNormalBasisAttributeError("TANGENT accessor has unexpected byteStride")
    count = int(accessor.get("count", -1))
    if count <= 0 or int(view.get("byteLength", -1)) != count * 16:
        raise GeneratedNormalBasisAttributeError(
            f"TANGENT payload length {view.get('byteLength')} != {count}*16"
        )
    return accessor, view, count


def _make_tangent_aliases(document: dict, source_accessor: int) -> tuple[int, int, dict]:
    accessor, source_view, count = _validate_tangent(document, source_accessor)
    views = document.setdefault("bufferViews", [])
    accessors = document.setdefault("accessors", [])
    view_index = len(views)
    alias_view = {
        "buffer": 0,
        "byteOffset": int(source_view.get("byteOffset", 0)),
        "byteLength": int(source_view["byteLength"]),
        "byteStride": 16,
        "target": int(source_view.get("target", ARRAY_BUFFER)),
        "name": f"T6 exact tangent basis alias of accessor {source_accessor}",
        "extras": {"T6": {
            "sourceAccessor": int(source_accessor),
            "sourceBufferView": int(accessor["bufferView"]),
            "policy": "metadata alias only; no BIN bytes copied",
        }},
    }
    views.append(alias_view)

    tangent_index = len(accessors)
    accessors.append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": count,
        "type": "VEC3",
        "byteOffset": 0,
        "name": "_T6_WORLD_TANGENT",
        "extras": {"T6": {"sourceAccessor": int(source_accessor), "components": "xyz"}},
    })
    handedness_index = len(accessors)
    accessors.append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": count,
        "type": "SCALAR",
        "byteOffset": 12,
        "name": "_T6_TANGENT_HANDEDNESS",
        "extras": {"T6": {"sourceAccessor": int(source_accessor), "component": "w"}},
    })
    return tangent_index, handedness_index, {
        "sourceAccessor": int(source_accessor),
        "sourceBufferView": int(accessor["bufferView"]),
        "aliasBufferView": view_index,
        "tangentAccessor": tangent_index,
        "handednessAccessor": handedness_index,
        "vertexCount": count,
    }


def apply_contract(document: dict, raw: bytes) -> tuple[dict, bytes, dict]:
    root_t6 = document.get("extras", {}).get("T6", {})
    source = root_t6.get("generatedAttributeContract")
    if not isinstance(source, dict) or source.get("format") != SOURCE_ATTRIBUTE_FORMAT:
        raise GeneratedNormalBasisAttributeError(
            f"input lacks authoritative {SOURCE_ATTRIBUTE_FORMAT}"
        )
    if root_t6.get("generatedNormalBasisAttributes") is not None:
        raise GeneratedNormalBasisAttributeError("generated normal basis attributes already attached")
    if len(document.get("buffers", [])) != 1 or int(document["buffers"][0].get("byteLength", -1)) != len(raw):
        raise GeneratedNormalBasisAttributeError("single-buffer logical byteLength disagrees with BIN payload")

    original_raw_sha = hashlib.sha256(raw).hexdigest()
    original_accessor_count = len(document.get("accessors", []))
    original_view_count = len(document.get("bufferViews", []))
    tangent_cache: dict[int, tuple[int, int]] = {}
    alias_rows: list[dict] = []
    generated_primitives = 0

    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        primitives = mesh.get("primitives")
        if not isinstance(primitives, list):
            raise GeneratedNormalBasisAttributeError(f"mesh {mesh_index} has invalid primitives")
        for primitive_index, primitive in enumerate(primitives):
            material = _generated_material(document, primitive)
            if material is None:
                continue
            generated_primitives += 1
            attrs = primitive.get("attributes")
            if not isinstance(attrs, dict):
                raise GeneratedNormalBasisAttributeError(
                    f"{material!r}: primitive lacks attributes"
                )
            for semantic in ("_T6_WORLD_NORMAL", "_T6_WORLD_TANGENT", "_T6_TANGENT_HANDEDNESS"):
                if semantic in attrs:
                    raise GeneratedNormalBasisAttributeError(
                        f"{material!r}: {semantic} already exists; refusing ambiguous overwrite"
                    )
            if "NORMAL" not in attrs or "TANGENT" not in attrs:
                raise GeneratedNormalBasisAttributeError(
                    f"{material!r}: generated primitive lacks standard NORMAL/TANGENT"
                )
            normal_accessor = int(attrs["NORMAL"])
            tangent_accessor = int(attrs["TANGENT"])
            _validate_normal(document, normal_accessor)
            normal_count = int(document["accessors"][normal_accessor]["count"])
            tangent_meta = tangent_cache.get(tangent_accessor)
            if tangent_meta is None:
                tangent_alias, handedness_alias, row = _make_tangent_aliases(document, tangent_accessor)
                tangent_cache[tangent_accessor] = (tangent_alias, handedness_alias)
                alias_rows.append(row)
            else:
                tangent_alias, handedness_alias = tangent_meta
            if int(document["accessors"][tangent_alias]["count"]) != normal_count:
                raise GeneratedNormalBasisAttributeError(
                    f"{material!r}: NORMAL/TANGENT vertex counts disagree"
                )
            attrs["_T6_WORLD_NORMAL"] = normal_accessor
            attrs["_T6_WORLD_TANGENT"] = tangent_alias
            attrs["_T6_TANGENT_HANDEDNESS"] = handedness_alias
            primitive.setdefault("extras", {}).setdefault("T6", {})[
                "generatedNormalBasisAttributes"
            ] = FORMAT

    if generated_primitives <= 0:
        raise GeneratedNormalBasisAttributeError("world contains no generated primitives")
    if hashlib.sha256(raw).hexdigest() != original_raw_sha:
        raise GeneratedNormalBasisAttributeError("normal basis aliasing changed BIN bytes")

    stats = {
        "generatedPrimitiveCount": generated_primitives,
        "uniqueTangentSourceAccessorCount": len(tangent_cache),
        "tangentAliasAccessorCount": len(tangent_cache),
        "handednessAliasAccessorCount": len(tangent_cache),
        "originalAccessorCount": original_accessor_count,
        "finalAccessorCount": len(document.get("accessors", [])),
        "originalBufferViewCount": original_view_count,
        "finalBufferViewCount": len(document.get("bufferViews", [])),
        "binBytes": len(raw),
        "binSha256": original_raw_sha,
        "binByteIdentical": True,
    }
    contract = {
        "format": FORMAT,
        "stats": stats,
        "tangentAliases": alias_rows,
        "attributes": {
            "_T6_WORLD_NORMAL": "exact existing standard NORMAL accessor; glTF-space vector",
            "_T6_WORLD_TANGENT": "exact existing standard TANGENT.xyz via strided metadata alias",
            "_T6_TANGENT_HANDEDNESS": "exact existing standard TANGENT.w via strided metadata alias",
        },
        "rendererPolicy": (
            "consume exact custom attributes rather than Blender/realtime-engine tangent recomputation; "
            "transform vector attributes from mesh/object space to the renderer world space before N/T/B reconstruction"
        ),
        "sourceGeneratedAttributeContract": SOURCE_ATTRIBUTE_FORMAT,
    }
    contract["contractSha256"] = _jhash({
        "format": FORMAT,
        "stats": stats,
        "tangentAliases": alias_rows,
        "attributes": contract["attributes"],
    })
    document.setdefault("extras", {}).setdefault("T6", {})[
        "generatedNormalBasisAttributes"
    ] = contract
    return document, raw, stats
