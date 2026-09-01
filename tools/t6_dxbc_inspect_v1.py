#!/usr/bin/env python3
"""Deterministic fail-closed DXBC/RDEF inspector for retail T6 DX11 shaders.

This is intentionally an inspection/provenance stage, not an instruction
semantic decoder. It validates the DXBC container, hashes every chunk, decodes
the SHDR/SHEX program header, and extracts the RDEF bound-resource table using
the same documented structures used by pinned OpenAssetTools.

The output is designed to answer exact questions such as:
- is this retained .cso byte-for-byte a valid DXBC container?
- which shader model/program type is it?
- which RDEF texture/sampler resources exist and at which bind points?
- do `lightmapSamplerPrimary` / `lightmapSamplerSecondary` occur in reflection?

Instruction swizzles and the primary/secondary combine equation remain outside
this tool's proof scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


class DxbcInspectError(RuntimeError):
    pass


INPUT_TYPES = {
    0: "CBUFFER",
    1: "TBUFFER",
    2: "TEXTURE",
    3: "SAMPLER",
    4: "UAV_RWTYPED",
    5: "STRUCTURED",
    6: "UAV_RWSTRUCTURED",
    7: "BYTEADDRESS",
    8: "UAV_RWBYTEADDRESS",
    9: "UAV_APPEND_STRUCTURED",
    10: "UAV_CONSUME_STRUCTURED",
    11: "UAV_RWSTRUCTURED_WITH_COUNTER",
}
RETURN_TYPES = {
    1: "UNORM",
    2: "SNORM",
    3: "SINT",
    4: "UINT",
    5: "FLOAT",
    6: "MIXED",
    7: "DOUBLE",
    8: "CONTINUED",
}
DIMENSIONS = {
    0: "UNKNOWN",
    1: "BUFFER",
    2: "TEXTURE1D",
    3: "TEXTURE1DARRAY",
    4: "TEXTURE2D",
    5: "TEXTURE2DARRAY",
    6: "TEXTURE2DMS",
    7: "TEXTURE2DMSARRAY",
    8: "TEXTURE3D",
    9: "TEXTURECUBE",
    10: "TEXTURECUBEARRAY",
    11: "BUFFEREX",
}
PROGRAM_TYPES = {
    0: "pixel",
    1: "vertex",
    2: "geometry",
    3: "hull",
    4: "domain",
    5: "compute",
}
LIGHTMAP_NAMES = {"lightmapSamplerPrimary", "lightmapSamplerSecondary"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise DxbcInspectError(f"{label}: u32 outside byte range at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _cstr(data: bytes, offset: int, label: str) -> str:
    if offset < 0 or offset >= len(data):
        raise DxbcInspectError(f"{label}: string offset outside chunk: {offset}")
    end = data.find(b"\0", offset)
    if end < 0:
        raise DxbcInspectError(f"{label}: unterminated string")
    try:
        return data[offset:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DxbcInspectError(f"{label}: non-UTF8 reflection string") from exc


def _fourcc(raw: bytes) -> str:
    if len(raw) != 4:
        raise DxbcInspectError("invalid fourcc length")
    return raw.decode("latin-1")


def _parse_program_chunk(tag: str, payload: bytes) -> dict:
    if len(payload) < 8 or len(payload) % 4:
        raise DxbcInspectError(f"{tag}: malformed shader-program chunk length {len(payload)}")
    version = _u32(payload, 0, f"{tag} version")
    declared_dwords = _u32(payload, 4, f"{tag} length")
    major = (version >> 4) & 0xF
    minor = version & 0xF
    program_type = (version >> 16) & 0xFFFF
    if declared_dwords * 4 > len(payload):
        raise DxbcInspectError(
            f"{tag}: declared program length {declared_dwords * 4} exceeds chunk {len(payload)}"
        )
    return {
        "tag": tag,
        "shaderModel": f"{major}.{minor}",
        "major": major,
        "minor": minor,
        "programType": PROGRAM_TYPES.get(program_type, f"unknown:{program_type}"),
        "programTypeValue": program_type,
        "declaredProgramDwords": declared_dwords,
        "declaredProgramBytes": declared_dwords * 4,
    }


def _parse_rdef(payload: bytes) -> dict:
    if len(payload) < 28:
        raise DxbcInspectError("RDEF chunk shorter than 28-byte header")
    (
        cb_count,
        cb_offset,
        resource_count,
        resource_offset,
    ) = struct.unpack_from("<IIII", payload, 0)
    minor = payload[16]
    major = payload[17]
    shader_type = struct.unpack_from("<H", payload, 18)[0]
    flags = _u32(payload, 20, "RDEF flags")
    creator_offset = _u32(payload, 24, "RDEF creator")
    creator = _cstr(payload, creator_offset, "RDEF creator")

    entry_size = 40 if (major, minor) >= (5, 1) else 32
    if resource_offset + resource_count * entry_size > len(payload):
        raise DxbcInspectError(
            "RDEF bound-resource table exceeds chunk: "
            f"offset={resource_offset} count={resource_count} entry={entry_size} chunk={len(payload)}"
        )

    resources: list[dict] = []
    for index in range(resource_count):
        off = resource_offset + index * entry_size
        (
            name_offset,
            input_type,
            return_type,
            dimension,
            num_samples,
            bind_point,
            bind_count,
            resource_flags,
        ) = struct.unpack_from("<IIIIIIII", payload, off)
        item = {
            "index": index,
            "name": _cstr(payload, name_offset, f"RDEF resource {index} name"),
            "inputType": INPUT_TYPES.get(input_type, f"unknown:{input_type}"),
            "inputTypeValue": input_type,
            "returnType": RETURN_TYPES.get(return_type, f"unknown:{return_type}"),
            "returnTypeValue": return_type,
            "dimension": DIMENSIONS.get(dimension, f"unknown:{dimension}"),
            "dimensionValue": dimension,
            "numSamples": num_samples,
            "bindPoint": bind_point,
            "bindCount": bind_count,
            "flags": resource_flags,
        }
        if entry_size == 40:
            item["space"] = _u32(payload, off + 32, f"RDEF resource {index} space")
            item["id"] = _u32(payload, off + 36, f"RDEF resource {index} id")
        resources.append(item)

    lightmap_resources = [x for x in resources if x["name"] in LIGHTMAP_NAMES]
    return {
        "shaderModel": f"{major}.{minor}",
        "major": major,
        "minor": minor,
        "shaderTypeValue": shader_type,
        "flags": flags,
        "creator": creator,
        "constantBufferCount": cb_count,
        "constantBufferOffset": cb_offset,
        "boundResourceCount": resource_count,
        "boundResourceOffset": resource_offset,
        "boundResourceEntrySize": entry_size,
        "boundResources": resources,
        "lightmapResources": lightmap_resources,
    }


def inspect_dxbc(data: bytes, *, name: str | None = None) -> dict:
    if len(data) < 32:
        raise DxbcInspectError(f"DXBC container too short: {len(data)}")
    if data[:4] != b"DXBC":
        raise DxbcInspectError("missing DXBC magic")
    unknown_one = _u32(data, 20, "DXBC header unknown/version")
    total_size = _u32(data, 24, "DXBC total size")
    chunk_count = _u32(data, 28, "DXBC chunk count")
    if total_size != len(data):
        raise DxbcInspectError(
            f"DXBC total size mismatch: header={total_size} actual={len(data)}"
        )
    table_end = 32 + chunk_count * 4
    if table_end > len(data):
        raise DxbcInspectError("DXBC chunk-offset table exceeds container")

    offsets = [_u32(data, 32 + i * 4, f"DXBC chunk offset {i}") for i in range(chunk_count)]
    if len(offsets) != len(set(offsets)):
        raise DxbcInspectError("DXBC chunk table contains duplicate offsets")

    chunks: list[dict] = []
    occupied: list[tuple[int, int, int]] = []
    program = None
    rdef = None
    for index, offset in enumerate(offsets):
        if offset < table_end or offset + 8 > len(data):
            raise DxbcInspectError(f"DXBC chunk {index} offset outside payload: {offset}")
        tag = _fourcc(data[offset:offset + 4])
        size = _u32(data, offset + 4, f"DXBC chunk {index} size")
        end = offset + 8 + size
        if end > len(data):
            raise DxbcInspectError(
                f"DXBC chunk {index} {tag!r} exceeds container: end={end} size={len(data)}"
            )
        for old_start, old_end, old_index in occupied:
            if not (end <= old_start or offset >= old_end):
                raise DxbcInspectError(
                    f"DXBC chunk {index} overlaps chunk {old_index}"
                )
        occupied.append((offset, end, index))
        payload = data[offset + 8:end]
        chunk = {
            "index": index,
            "tag": tag,
            "offset": offset,
            "payloadOffset": offset + 8,
            "payloadBytes": size,
            "totalBytes": size + 8,
            "payloadSha256": _sha256(payload),
        }
        chunks.append(chunk)
        if tag in ("SHDR", "SHEX"):
            if program is not None:
                raise DxbcInspectError("DXBC contains multiple SHDR/SHEX program chunks")
            program = _parse_program_chunk(tag, payload)
        elif tag == "RDEF":
            if rdef is not None:
                raise DxbcInspectError("DXBC contains multiple RDEF chunks")
            rdef = _parse_rdef(payload)

    if program is None:
        raise DxbcInspectError("DXBC has no SHDR/SHEX program chunk")
    if rdef is None:
        raise DxbcInspectError("DXBC has no RDEF reflection chunk")
    if program["shaderModel"] != rdef["shaderModel"]:
        raise DxbcInspectError(
            f"shader model disagreement: program={program['shaderModel']} RDEF={rdef['shaderModel']}"
        )

    return {
        "format": "t6-dxbc-inspection-v1",
        "name": name,
        "bytes": len(data),
        "sha256": _sha256(data),
        "checksumHex": data[4:20].hex(),
        "headerWord20": unknown_one,
        "totalSize": total_size,
        "chunkCount": chunk_count,
        "chunks": chunks,
        "program": program,
        "reflection": rdef,
        "lightmap": {
            "resourceCount": len(rdef["lightmapResources"]),
            "resources": rdef["lightmapResources"],
            "hasPrimary": any(x["name"] == "lightmapSamplerPrimary" for x in rdef["lightmapResources"]),
            "hasSecondary": any(x["name"] == "lightmapSamplerSecondary" for x in rdef["lightmapResources"]),
        },
        "policy": {
            "container": "strict DXBC bounds/overlap/size validation",
            "reflection": "RDEF bound-resource table only; no shader instruction semantics inferred",
            "combineEquation": "not decoded",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("shader_cso", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    data = args.shader_cso.read_bytes()
    doc = inspect_dxbc(data, name=args.shader_cso.name)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
