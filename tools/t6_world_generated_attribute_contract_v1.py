#!/usr/bin/env python3
"""Normalize legacy T6 world glTF attributes into the renderer contract used by v31+.

The production world exporter predates several later source-closed semantics. Its
binary accessors are still correct, but primitive semantic names/layout are not:

* native UVs occupy TEXCOORD_0..N and lightmap follows dynamically;
* generated-material packed COLOR is exposed as COLOR_0;
* normal-transform words remain raw stored-order UBYTE4 values.

This postpass fixes those semantics without rebuilding geometry:

    TEXCOORD_0 = material UV0
    TEXCOORD_1 = lightmap UV
    TEXCOORD_2/3/4 = material UV1/2/3
    generated '*' COLOR_0 -> _T6_LAYER_WEIGHTS

For normal transforms, the source bytes really must change. Stored T6 order is
[m00,m11,m01,m10], while the pixel shader consumes logical
[m00,m01,m10,m11]. We therefore append a reordered normalized-UBYTE VEC4
accessor, bind it as _T6_NORMAL_TRANSFORM_N, and preserve the original accessor
as _T6_NORMAL_TRANSFORM_N_RAW.

All original accessors/bufferViews and existing raw bytes remain immutable. Only
new logical normal-transform accessors are appended. Ordinary material COLOR_0
is retained; only generated-material color controls are retyped.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


FORMAT = "t6-world-generated-attribute-contract-v1"
ARRAY_BUFFER = 34962
UNSIGNED_BYTE = 5121


class GeneratedAttributeContractError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _align4(raw: bytes) -> bytes:
    pad = (-len(raw)) & 3
    return raw + b"\0" * pad


def _material_name(document: dict, primitive: dict) -> str:
    try:
        index = int(primitive["material"])
        material = document["materials"][index]
    except Exception as exc:
        raise GeneratedAttributeContractError("primitive has invalid material reference") from exc
    name = str(material.get("name") or "")
    if not name:
        raise GeneratedAttributeContractError(f"material {index} has empty name")
    return name


def _buffer_view_bytes(document: dict, raw: bytes, accessor_index: int) -> tuple[dict, bytes]:
    try:
        accessor = document["accessors"][accessor_index]
        view = document["bufferViews"][int(accessor["bufferView"])]
    except Exception as exc:
        raise GeneratedAttributeContractError(f"invalid accessor {accessor_index}") from exc
    if int(view.get("buffer", 0)) != 0:
        raise GeneratedAttributeContractError(
            f"accessor {accessor_index}: only buffer 0 is supported"
        )
    if int(accessor.get("byteOffset", 0)) != 0:
        raise GeneratedAttributeContractError(
            f"accessor {accessor_index}: nonzero accessor byteOffset is not supported"
        )
    if view.get("byteStride") is not None:
        raise GeneratedAttributeContractError(
            f"accessor {accessor_index}: interleaved bufferView is not supported"
        )
    start = int(view.get("byteOffset", 0))
    length = int(view["byteLength"])
    end = start + length
    if start < 0 or end > len(raw):
        raise GeneratedAttributeContractError(
            f"accessor {accessor_index}: bufferView range {start}:{end} outside {len(raw)}"
        )
    return accessor, raw[start:end]


def _append_logical_normal_transform(
    document: dict,
    raw: bytes,
    source_accessor_index: int,
    *,
    semantic: str,
) -> tuple[int, bytes, dict]:
    source, payload = _buffer_view_bytes(document, raw, source_accessor_index)
    if int(source.get("componentType", -1)) != UNSIGNED_BYTE:
        raise GeneratedAttributeContractError(
            f"{semantic}: source accessor is not UNSIGNED_BYTE"
        )
    if source.get("type") != "VEC4":
        raise GeneratedAttributeContractError(f"{semantic}: source accessor is not VEC4")
    count = int(source.get("count", -1))
    if count <= 0 or len(payload) != count * 4:
        raise GeneratedAttributeContractError(
            f"{semantic}: source payload {len(payload)} bytes != {count}*4"
        )
    if bool(source.get("normalized", False)):
        raise GeneratedAttributeContractError(
            f"{semantic}: legacy raw source accessor is unexpectedly already normalized"
        )

    logical = bytearray(len(payload))
    for offset in range(0, len(payload), 4):
        m00, m11, m01, m10 = payload[offset:offset + 4]
        logical[offset:offset + 4] = bytes((m00, m01, m10, m11))

    aligned = _align4(raw)
    byte_offset = len(aligned)
    out_raw = aligned + bytes(logical)
    view_index = len(document.setdefault("bufferViews", []))
    document["bufferViews"].append({
        "buffer": 0,
        "byteOffset": byte_offset,
        "byteLength": len(logical),
        "target": ARRAY_BUFFER,
        "name": f"{semantic}:logical_unorm8",
        "extras": {
            "T6": {
                "sourceAccessor": source_accessor_index,
                "storedByteOrder": ["m00", "m11", "m01", "m10"],
                "logicalByteOrder": ["m00", "m01", "m10", "m11"],
            }
        },
    })
    accessor_index = len(document.setdefault("accessors", []))
    document["accessors"].append({
        "bufferView": view_index,
        "componentType": UNSIGNED_BYTE,
        "count": count,
        "type": "VEC4",
        "normalized": True,
        "name": f"{semantic}:logical_unorm8",
        "extras": {
            "T6": {
                "sourceAccessor": source_accessor_index,
                "decode": "logical UNORM8 component * 2 - 1 in shader",
            }
        },
    })
    return accessor_index, out_raw, {
        "sourceAccessor": source_accessor_index,
        "logicalAccessor": accessor_index,
        "count": count,
        "sourcePayloadSha256": hashlib.sha256(payload).hexdigest(),
        "logicalPayloadSha256": hashlib.sha256(logical).hexdigest(),
    }


def _fixed_texcoord_attributes(mesh: dict, attributes: dict) -> tuple[dict[str, int], dict]:
    t6 = mesh.get("extras", {}).get("T6", {})
    mapping = t6.get("texCoordMapping")
    if not isinstance(mapping, dict) or not mapping:
        raise GeneratedAttributeContractError(
            f"mesh {mesh.get('name')!r} lacks legacy texCoordMapping provenance"
        )

    by_source: dict[str, str] = {}
    for semantic, source in mapping.items():
        semantic = str(semantic)
        source = str(source)
        if not semantic.startswith("TEXCOORD_") or semantic not in attributes:
            raise GeneratedAttributeContractError(
                f"mesh {mesh.get('name')!r}: mapping {semantic!r}->{source!r} has no primitive accessor"
            )
        if source in by_source:
            raise GeneratedAttributeContractError(
                f"mesh {mesh.get('name')!r}: duplicate texcoord source {source!r}"
            )
        by_source[source] = semantic

    if "uv0" not in by_source or "lightmapUV" not in by_source:
        raise GeneratedAttributeContractError(
            f"mesh {mesh.get('name')!r}: texCoordMapping lacks uv0/lightmapUV"
        )

    new: dict[str, int] = {
        "TEXCOORD_0": int(attributes[by_source["uv0"]]),
        "TEXCOORD_1": int(attributes[by_source["lightmapUV"]]),
    }
    uv_count = int(t6.get("uvCount", 1))
    if not 1 <= uv_count <= 4:
        raise GeneratedAttributeContractError(
            f"mesh {mesh.get('name')!r}: invalid uvCount {uv_count}"
        )
    for native_index in range(1, uv_count):
        source_name = f"uv{native_index}"
        old_semantic = by_source.get(source_name)
        if old_semantic is None:
            raise GeneratedAttributeContractError(
                f"mesh {mesh.get('name')!r}: missing native {source_name} mapping"
            )
        new[f"TEXCOORD_{native_index + 1}"] = int(attributes[old_semantic])

    expected_keys = {f"TEXCOORD_{i}" for i in range(uv_count + 1)}
    if set(new) != expected_keys:
        raise GeneratedAttributeContractError(
            f"mesh {mesh.get('name')!r}: normalized TEXCOORD keys are not consecutive"
        )
    return new, {
        "legacy": dict(sorted((str(k), str(v)) for k, v in mapping.items())),
        "normalized": {
            "TEXCOORD_0": "materialUV0",
            "TEXCOORD_1": "lightmapUV",
            **{
                f"TEXCOORD_{i + 1}": f"materialUV{i}"
                for i in range(1, uv_count)
            },
        },
    }


def normalize_generated_attributes(document: dict, raw: bytes) -> tuple[dict, bytes, dict]:
    existing = document.get("extras", {}).get("T6", {}).get("generatedAttributeContract")
    if existing is not None:
        if existing.get("format") != FORMAT:
            raise GeneratedAttributeContractError(
                f"document already has incompatible generated attribute contract {existing.get('format')!r}"
            )
        raise GeneratedAttributeContractError("document is already normalized by this contract")

    materials = document.get("materials")
    meshes = document.get("meshes")
    if not isinstance(materials, list) or not isinstance(meshes, list):
        raise GeneratedAttributeContractError("glTF lacks materials/meshes lists")

    original_accessor_count = len(document.get("accessors", []))
    original_view_count = len(document.get("bufferViews", []))
    original_raw_bytes = len(raw)
    original_raw_sha = hashlib.sha256(raw).hexdigest()
    transform_cache: dict[tuple[str, int], int] = {}
    transform_rows: list[dict] = []
    generated_primitives = ordinary_primitives = 0
    generated_color_retypes = 0
    texcoord_primitive_count = 0
    normal_transform_primitive_bindings = 0
    uv_contracts: dict[str, dict] = {}

    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives")
        if not isinstance(primitives, list) or not primitives:
            raise GeneratedAttributeContractError(f"mesh {mesh_index} has no primitives")
        mesh_uv_contract = None

        for primitive_index, primitive in enumerate(primitives):
            attrs = primitive.get("attributes")
            if not isinstance(attrs, dict):
                raise GeneratedAttributeContractError(
                    f"mesh {mesh_index} primitive {primitive_index} lacks attributes"
                )
            fixed_uvs, uv_contract = _fixed_texcoord_attributes(mesh, attrs)
            if mesh_uv_contract is None:
                mesh_uv_contract = uv_contract
            elif mesh_uv_contract != uv_contract:
                raise GeneratedAttributeContractError(
                    f"mesh {mesh_index}: primitive UV provenance disagrees within shared group"
                )

            non_texcoord = {
                key: value for key, value in attrs.items()
                if not str(key).startswith("TEXCOORD_")
            }
            non_texcoord.update(fixed_uvs)
            attrs = non_texcoord
            texcoord_primitive_count += 1

            material_name = _material_name(document, primitive)
            generated = material_name.startswith("*")
            if generated:
                generated_primitives += 1
                if "_T6_LAYER_WEIGHTS" in attrs:
                    raise GeneratedAttributeContractError(
                        f"{material_name!r}: generated primitive is ambiguously already layer-normalized"
                    )
                if "COLOR_0" not in attrs:
                    raise GeneratedAttributeContractError(
                        f"{material_name!r}: generated primitive lacks legacy COLOR_0 layer controls"
                    )
                attrs["_T6_LAYER_WEIGHTS"] = attrs.pop("COLOR_0")
                generated_color_retypes += 1
            else:
                ordinary_primitives += 1

            for transform_index in (0, 1):
                semantic = f"_T6_NORMAL_TRANSFORM_{transform_index}"
                source_accessor = attrs.get(semantic)
                if source_accessor is None:
                    continue
                source_accessor = int(source_accessor)
                cache_key = (semantic, source_accessor)
                logical_accessor = transform_cache.get(cache_key)
                if logical_accessor is None:
                    logical_accessor, raw, row = _append_logical_normal_transform(
                        document,
                        raw,
                        source_accessor,
                        semantic=semantic,
                    )
                    transform_cache[cache_key] = logical_accessor
                    transform_rows.append({"semantic": semantic, **row})
                attrs[f"{semantic}_RAW"] = source_accessor
                attrs[semantic] = logical_accessor
                normal_transform_primitive_bindings += 1

            primitive["attributes"] = dict(sorted(attrs.items()))
            t6p = primitive.setdefault("extras", {}).setdefault("T6", {})
            t6p["normalizedAttributeContract"] = FORMAT
            t6p["generatedLayerWeights"] = (
                "_T6_LAYER_WEIGHTS" if generated else None
            )

        if mesh_uv_contract is None:
            raise GeneratedAttributeContractError(f"mesh {mesh_index}: no UV contract produced")
        uv_contracts[str(mesh_index)] = mesh_uv_contract
        t6m = mesh.setdefault("extras", {}).setdefault("T6", {})
        t6m["legacyTexCoordMapping"] = mesh_uv_contract["legacy"]
        t6m["texCoordMapping"] = mesh_uv_contract["normalized"]
        t6m["lightmapTexCoord"] = 1
        t6m["generatedAttributeContract"] = FORMAT

    if generated_primitives == 0:
        raise GeneratedAttributeContractError("world contains no generated-material primitives")
    if generated_color_retypes != generated_primitives:
        raise GeneratedAttributeContractError(
            "not every generated primitive was retyped to _T6_LAYER_WEIGHTS"
        )

    buffers = document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise GeneratedAttributeContractError("expected exactly one glTF buffer")
    buffers[0]["byteLength"] = len(raw)

    stats = {
        "meshCount": len(meshes),
        "primitiveCount": generated_primitives + ordinary_primitives,
        "generatedPrimitiveCount": generated_primitives,
        "ordinaryPrimitiveCount": ordinary_primitives,
        "generatedColorRetypeCount": generated_color_retypes,
        "texcoordNormalizedPrimitiveCount": texcoord_primitive_count,
        "logicalNormalTransformAccessorCount": len(transform_rows),
        "normalTransformPrimitiveBindingCount": normal_transform_primitive_bindings,
        "originalAccessorCount": original_accessor_count,
        "finalAccessorCount": len(document.get("accessors", [])),
        "originalBufferViewCount": original_view_count,
        "finalBufferViewCount": len(document.get("bufferViews", [])),
        "originalRawBytes": original_raw_bytes,
        "finalRawBytes": len(raw),
    }
    contract = {
        "format": FORMAT,
        "stats": stats,
        "normalTransformConversions": transform_rows,
        "uvContracts": uv_contracts,
        "policies": {
            "texcoords": "fixed renderer contract: materialUV0, lightmapUV, materialUV1/2/3",
            "generatedColor": "generated '*' COLOR_0 is T6 layer control and is exposed only as _T6_LAYER_WEIGHTS",
            "ordinaryColor": "ordinary material COLOR_0 remains unchanged",
            "normalTransform": (
                "raw stored-order accessor preserved as *_RAW; logical reordered accessor is normalized UBYTE4 "
                "and shader decodes component*2-1"
            ),
            "geometry": "existing geometry/index/UV/color accessors are referenced only; no original payload rewritten",
        },
        "sourceRawSha256": original_raw_sha,
    }
    contract["contractSha256"] = _jhash({
        "format": FORMAT,
        "stats": stats,
        "normalTransformConversions": transform_rows,
        "uvContracts": uv_contracts,
    })
    root = document.setdefault("extras", {}).setdefault("T6", {})
    root["generatedAttributeContract"] = contract
    return document, raw, stats
