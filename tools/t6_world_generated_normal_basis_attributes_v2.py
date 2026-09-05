#!/usr/bin/env python3
"""Generated normal basis attributes v2: preserve vertex-stage binormal topology.

v1 exposes exact NORMAL, TANGENT.xyz and TANGENT.w without BIN mutation.  Retail
paired VS proof establishes the Y basis as:

    B_vertex = cross(N_vertex, T_vertex) * TANGENT0.w

That expression is evaluated before raster interpolation.  Recomputing the cross
from interpolated N/T in a fragment/material shader is not algebraically
identical, so v2 derives one B vector per exported vertex and appends it as
`_T6_WORLD_BINORMAL`.

The derivation uses the already exported float32 NORMAL/TANGENT values and
float32-rounded scalar operations.  It preserves the proven vertex-stage
expression/interpolation topology, but does not claim bit-identical D3D11 MAD
rounding beyond the existing glTF float32 geometry contract.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from typing import Any

from t6_world_generated_normal_basis_attributes_v1 import (
    FORMAT as V1_FORMAT,
    GeneratedNormalBasisAttributeError,
    apply_contract as apply_v1,
)

FORMAT = "t6-generated-normal-basis-attributes-v2"
FLOAT = 5126
ARRAY_BUFFER = 34962


class GeneratedNormalBasisAttributeV2Error(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _cross_handed(n, t, h: float) -> tuple[float, float, float]:
    # Explicit float32 rounding at each scalar multiply/subtract and final sign
    # multiply. This matches the source equation/topology while keeping the
    # proof boundary honest about exact GPU MAD implementation details.
    cx = _f32(_f32(_f32(n[1]) * _f32(t[2])) - _f32(_f32(n[2]) * _f32(t[1])))
    cy = _f32(_f32(_f32(n[2]) * _f32(t[0])) - _f32(_f32(n[0]) * _f32(t[2])))
    cz = _f32(_f32(_f32(n[0]) * _f32(t[1])) - _f32(_f32(n[1]) * _f32(t[0])))
    hh = _f32(h)
    return _f32(cx * hh), _f32(cy * hh), _f32(cz * hh)


def _accessor_bytes(document: dict, raw: bytes, accessor_index: int, *, expected_type: str) -> tuple[dict, bytes, int]:
    try:
        accessor = document["accessors"][int(accessor_index)]
        view = document["bufferViews"][int(accessor["bufferView"])]
    except Exception as exc:
        raise GeneratedNormalBasisAttributeV2Error(f"invalid accessor {accessor_index}") from exc
    if int(accessor.get("componentType", -1)) != FLOAT or accessor.get("type") != expected_type:
        raise GeneratedNormalBasisAttributeV2Error(
            f"accessor {accessor_index} is not FLOAT {expected_type}"
        )
    if int(accessor.get("byteOffset", 0)) != 0 or view.get("byteStride") is not None:
        raise GeneratedNormalBasisAttributeV2Error(
            f"source accessor {accessor_index} must be tightly packed with zero byteOffset"
        )
    count = int(accessor.get("count", -1))
    width = {"VEC3": 12, "VEC4": 16}[expected_type]
    start = int(view.get("byteOffset", 0))
    length = int(view.get("byteLength", -1))
    if count <= 0 or length != count * width or start < 0 or start + length > len(raw):
        raise GeneratedNormalBasisAttributeV2Error(
            f"source accessor {accessor_index} payload range/length is invalid"
        )
    return accessor, raw[start:start + length], count


def _derive_binormal(document: dict, raw: bytes, normal_accessor: int, tangent_accessor: int) -> tuple[bytes, dict]:
    _, normal_bytes, normal_count = _accessor_bytes(
        document, raw, normal_accessor, expected_type="VEC3"
    )
    _, tangent_bytes, tangent_count = _accessor_bytes(
        document, raw, tangent_accessor, expected_type="VEC4"
    )
    if normal_count != tangent_count:
        raise GeneratedNormalBasisAttributeV2Error(
            f"NORMAL/TANGENT counts disagree {normal_count}/{tangent_count}"
        )
    out = bytearray()
    negative = positive = 0
    for index in range(normal_count):
        n = struct.unpack_from("<3f", normal_bytes, index * 12)
        t4 = struct.unpack_from("<4f", tangent_bytes, index * 16)
        if not all(math.isfinite(v) for v in (*n, *t4)):
            raise GeneratedNormalBasisAttributeV2Error(
                f"vertex {index}: non-finite normal/tangent basis"
            )
        h = float(t4[3])
        if abs(abs(h) - 1.0) > 1.0e-4:
            raise GeneratedNormalBasisAttributeV2Error(
                f"vertex {index}: tangent handedness {h} is not +/-1"
            )
        positive += int(h >= 0.0)
        negative += int(h < 0.0)
        b = _cross_handed(n, t4[:3], h)
        if not all(math.isfinite(v) for v in b):
            raise GeneratedNormalBasisAttributeV2Error(
                f"vertex {index}: derived binormal is non-finite"
            )
        out.extend(struct.pack("<3f", *b))
    payload = bytes(out)
    return payload, {
        "vertexCount": normal_count,
        "positiveHandednessCount": positive,
        "negativeHandednessCount": negative,
        "binormalPayloadSha256": hashlib.sha256(payload).hexdigest(),
    }


def _append_binormal(document: dict, raw: bytes, payload: bytes, *, source_normal: int, source_tangent: int, count: int):
    pad = (-len(raw)) & 3
    aligned = raw + b"\0" * pad
    offset = len(aligned)
    out_raw = aligned + payload
    views = document.setdefault("bufferViews", [])
    accessors = document.setdefault("accessors", [])
    view_index = len(views)
    views.append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "target": ARRAY_BUFFER,
        "name": "T6 vertex-stage world binormal",
        "extras": {"T6": {
            "sourceNormalAccessor": source_normal,
            "sourceTangentAccessor": source_tangent,
            "equation": "cross(N,T)*TANGENT.w per vertex",
        }},
    })
    accessor_index = len(accessors)
    accessors.append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": count,
        "type": "VEC3",
        "name": "_T6_WORLD_BINORMAL",
        "extras": {"T6": {
            "sourceNormalAccessor": source_normal,
            "sourceTangentAccessor": source_tangent,
            "interpolationPolicy": "derive at vertex then raster-interpolate",
        }},
    })
    document["buffers"][0]["byteLength"] = len(out_raw)
    return accessor_index, out_raw, pad


def apply_contract(document: dict, raw: bytes) -> tuple[dict, bytes, dict]:
    root = document.get("extras", {}).get("T6", {})
    v1_contract = root.get("generatedNormalBasisAttributes")
    if v1_contract is None:
        try:
            document, raw, _ = apply_v1(document, raw)
        except GeneratedNormalBasisAttributeError as exc:
            raise GeneratedNormalBasisAttributeV2Error(f"cannot establish v1 basis attributes: {exc}") from exc
        root = document["extras"]["T6"]
        v1_contract = root.get("generatedNormalBasisAttributes")
    if not isinstance(v1_contract, dict) or v1_contract.get("format") != V1_FORMAT:
        raise GeneratedNormalBasisAttributeV2Error(
            f"expected {V1_FORMAT}, got {getattr(v1_contract, 'get', lambda *_: None)('format')!r}"
        )
    if root.get("generatedNormalBasisAttributesV2") is not None:
        raise GeneratedNormalBasisAttributeV2Error("v2 binormal attributes already attached")

    source_raw_len = len(raw)
    source_raw_sha = hashlib.sha256(raw).hexdigest()
    cache: dict[tuple[int, int], int] = {}
    rows = []
    generated = 0
    total_binormal_vertices = 0
    total_padding = 0

    materials = document.get("materials", [])
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            try:
                material_name = str(materials[int(primitive["material"])].get("name") or "")
            except Exception as exc:
                raise GeneratedNormalBasisAttributeV2Error("invalid primitive material") from exc
            if not material_name.startswith("*"):
                continue
            generated += 1
            attrs = primitive.get("attributes")
            if not isinstance(attrs, dict):
                raise GeneratedNormalBasisAttributeV2Error(f"{material_name!r}: missing attributes")
            if "_T6_WORLD_BINORMAL" in attrs:
                raise GeneratedNormalBasisAttributeV2Error(
                    f"{material_name!r}: _T6_WORLD_BINORMAL already exists"
                )
            normal_accessor = int(attrs.get("NORMAL", -1))
            tangent_accessor = int(attrs.get("TANGENT", -1))
            if normal_accessor < 0 or tangent_accessor < 0:
                raise GeneratedNormalBasisAttributeV2Error(
                    f"{material_name!r}: standard NORMAL/TANGENT missing"
                )
            key = (normal_accessor, tangent_accessor)
            binormal_accessor = cache.get(key)
            if binormal_accessor is None:
                payload, meta = _derive_binormal(document, raw, normal_accessor, tangent_accessor)
                binormal_accessor, raw, padding = _append_binormal(
                    document,
                    raw,
                    payload,
                    source_normal=normal_accessor,
                    source_tangent=tangent_accessor,
                    count=int(meta["vertexCount"]),
                )
                cache[key] = binormal_accessor
                total_binormal_vertices += int(meta["vertexCount"])
                total_padding += padding
                rows.append({
                    "sourceNormalAccessor": normal_accessor,
                    "sourceTangentAccessor": tangent_accessor,
                    "binormalAccessor": binormal_accessor,
                    **meta,
                })
            attrs["_T6_WORLD_BINORMAL"] = binormal_accessor
            primitive.setdefault("extras", {}).setdefault("T6", {})[
                "generatedNormalBasisAttributesV2"
            ] = FORMAT

    if generated <= 0:
        raise GeneratedNormalBasisAttributeV2Error("world contains no generated primitives")
    stats = {
        "generatedPrimitiveCount": generated,
        "uniqueBasisSourcePairCount": len(cache),
        "derivedBinormalAccessorCount": len(cache),
        "derivedBinormalVertexCount": total_binormal_vertices,
        "alignmentPaddingBytes": total_padding,
        "sourceBinBytes": source_raw_len,
        "finalBinBytes": len(raw),
        "appendedBinBytes": len(raw) - source_raw_len,
        "sourceBinSha256": source_raw_sha,
    }
    contract = {
        "format": FORMAT,
        "stats": stats,
        "binormalDerivations": rows,
        "equation": "B_vertex = cross(N_vertex,T_vertex) * TANGENT.w",
        "interpolationTopology": "derive per vertex before raster interpolation",
        "proofBoundary": (
            "paired-VS exact cross/handedness equation applied to existing exported float32 basis values; preserves "
            "vertex-stage/interpolation topology, not a claim of bit-identical D3D11 MAD rounding"
        ),
    }
    contract["contractSha256"] = _jhash(contract)
    document.setdefault("extras", {}).setdefault("T6", {})[
        "generatedNormalBasisAttributesV2"
    ] = contract
    return document, raw, stats
