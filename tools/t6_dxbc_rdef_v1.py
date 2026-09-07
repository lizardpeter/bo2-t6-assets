#!/usr/bin/env python3
"""Extract exact T6 DXBC resource/constant-buffer ABI from the RDEF chunk.

Optionally merge SPIRV-Cross JSON reflection and GLSL produced from a validated
DXBC->SPIR-V translation.  This closes symbolic HLSL resource names to original
D3D registers and, when reflection is supplied, to the translated Vulkan
set/binding without guessing shader semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-dxbc-rdef-abi-v1"
RESOURCE_TYPES = {
    0: "cbuffer",
    1: "tbuffer",
    2: "texture",
    3: "sampler",
    4: "uav-rwtyped",
    5: "structured",
    6: "uav-rwstructured",
    7: "byte-address",
    8: "uav-rwbyte-address",
    9: "uav-append-structured",
    10: "uav-consume-structured",
    11: "uav-rwstructured-counter",
}
REGISTER_CLASS = {0: "b", 1: "t", 2: "t", 3: "s"}
DIMENSIONS = {
    0: "unknown",
    1: "buffer",
    2: "texture1d",
    3: "texture1darray",
    4: "texture2d",
    5: "texture2darray",
    6: "texture2dms",
    7: "texture2dmsarray",
    8: "texture3d",
    9: "texturecube",
    10: "texturecubearray",
    11: "bufferex",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstr(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        raise ValueError(f"RDEF string offset {offset} is outside payload")
    end = blob.find(b"\0", offset)
    if end < 0:
        raise ValueError(f"RDEF string at offset {offset} is not NUL terminated")
    return blob[offset:end].decode("utf-8", errors="strict")


def dxbc_chunks(data: bytes) -> list[dict[str, Any]]:
    if len(data) < 32 or data[:4] != b"DXBC":
        raise ValueError("input is not a DXBC container")
    one, total, count = struct.unpack_from("<III", data, 20)
    if one != 1 or total != len(data):
        raise ValueError(f"invalid DXBC header one={one} total={total} actual={len(data)}")
    if 32 + count * 4 > len(data):
        raise ValueError("DXBC chunk offset array exceeds file")
    offsets = struct.unpack_from("<" + "I" * count, data, 32)
    rows = []
    for offset in offsets:
        if offset + 8 > len(data):
            raise ValueError(f"DXBC chunk header at {offset} exceeds file")
        fourcc = data[offset : offset + 4].decode("ascii", errors="strict")
        size = struct.unpack_from("<I", data, offset + 4)[0]
        end = offset + 8 + size
        if end > len(data):
            raise ValueError(f"DXBC chunk {fourcc} at {offset} exceeds file")
        rows.append({"fourcc": fourcc, "offset": offset, "size": size, "payload": data[offset + 8 : end]})
    return rows


def parse_rdef(data: bytes) -> dict[str, Any]:
    chunks = dxbc_chunks(data)
    matches = [row for row in chunks if row["fourcc"] == "RDEF"]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one RDEF chunk, got {len(matches)}")
    blob = matches[0]["payload"]
    if len(blob) < 28:
        raise ValueError("RDEF payload is too short")
    cb_count, cb_offset, res_count, res_offset, target, flags, creator_offset = struct.unpack_from("<7I", blob, 0)

    resources = []
    for i in range(res_count):
        off = res_offset + i * 32
        if off + 32 > len(blob):
            raise ValueError("RDEF resource table exceeds payload")
        name_offset, kind, return_type, dimension, samples, bind_point, bind_count, rflags = struct.unpack_from("<8I", blob, off)
        register_class = REGISTER_CLASS.get(kind)
        resources.append(
            {
                "name": cstr(blob, name_offset),
                "resourceTypeCode": kind,
                "resourceType": RESOURCE_TYPES.get(kind, f"unknown-{kind}"),
                "registerClass": register_class,
                "registerIndex": bind_point,
                "register": f"{register_class}{bind_point}" if register_class else None,
                "bindCount": bind_count,
                "returnTypeCode": return_type,
                "dimensionCode": dimension,
                "dimension": DIMENSIONS.get(dimension, f"unknown-{dimension}"),
                "sampleCount": samples,
                "flags": rflags,
            }
        )

    constant_buffers = []
    for cb_index in range(cb_count):
        off = cb_offset + cb_index * 24
        if off + 24 > len(blob):
            raise ValueError("RDEF constant-buffer table exceeds payload")
        name_offset, var_count, var_offset, byte_size, cb_flags, cb_type = struct.unpack_from("<6I", blob, off)
        variables = []
        for vi in range(var_count):
            voff = var_offset + vi * 24
            if voff + 24 > len(blob):
                raise ValueError("RDEF variable table exceeds payload")
            var_name, start, size, vflags, type_offset, default_offset = struct.unpack_from("<6I", blob, voff)
            variables.append(
                {
                    "name": cstr(blob, var_name),
                    "startOffset": start,
                    "size": size,
                    "flags": vflags,
                    "typeOffset": type_offset,
                    "defaultValueOffset": default_offset,
                }
            )
        constant_buffers.append(
            {
                "name": cstr(blob, name_offset),
                "size": byte_size,
                "flags": cb_flags,
                "typeCode": cb_type,
                "variables": variables,
            }
        )

    # Attach original b-registers to cbuffer definitions from the resource table.
    by_name = {cb["name"]: cb for cb in constant_buffers}
    for resource in resources:
        if resource["resourceType"] == "cbuffer" and resource["name"] in by_name:
            cb = by_name[resource["name"]]
            cb["registerClass"] = "b"
            cb["registerIndex"] = resource["registerIndex"]
            cb["register"] = resource["register"]

    return {
        "creator": cstr(blob, creator_offset),
        "targetToken": f"0x{target:08X}",
        "flags": flags,
        "resources": resources,
        "constantBuffers": constant_buffers,
        "chunks": [{k: v for k, v in row.items() if k != "payload"} for row in chunks],
    }


def merge_spirv_reflection(rdef: dict[str, Any], reflection: dict[str, Any], glsl: str) -> dict[str, Any]:
    translated: dict[str, dict[str, Any]] = {}
    for key in ("separate_images", "separate_samplers"):
        for row in reflection.get(key, []):
            name = row.get("name")
            if isinstance(name, str):
                translated[name] = {
                    "set": row.get("set"),
                    "binding": row.get("binding"),
                    "type": row.get("type"),
                }

    # SPIRV-Cross keeps original D3D cbuffer register in the GLSL instance name,
    # e.g. `} cb0_0;` or `} cb3_0;`, while the reflected block itself is named
    # cb57_struct/cb11_struct after dead-range trimming.  Pair declaration order
    # with reflection UBO order and fail closed on mismatch.
    glsl_cb_regs = [int(x) for x in re.findall(r"}\s+cb(\d+)_0\s*;", glsl)]
    ubos = reflection.get("ubos", [])
    if len(glsl_cb_regs) != len(ubos):
        raise ValueError(
            f"GLSL cbuffer instance count {len(glsl_cb_regs)} != reflected UBO count {len(ubos)}"
        )
    for reg, ubo in zip(glsl_cb_regs, ubos):
        translated[f"b{reg}"] = {
            "set": ubo.get("set"),
            "binding": ubo.get("binding"),
            "type": "uniform-buffer",
            "translatedBlockName": ubo.get("name"),
            "translatedBlockSize": ubo.get("block_size"),
        }

    for resource in rdef["resources"]:
        register = resource.get("register")
        if register in translated:
            resource["translatedSpirv"] = translated[register]

    used_constants = []
    cb_by_register = {
        cb.get("register"): cb
        for cb in rdef["constantBuffers"]
        if cb.get("register") is not None
    }
    for reg_text, slot_text in re.findall(r"cb(\d+)_0\._m0\[(\d+)u\]", glsl):
        register = f"b{int(reg_text)}"
        slot = int(slot_text)
        byte_offset = slot * 16
        cb = cb_by_register.get(register)
        if cb is None:
            raise ValueError(f"translated GLSL uses {register} but RDEF has no such cbuffer")
        owners = [
            v
            for v in cb["variables"]
            if v["startOffset"] <= byte_offset < v["startOffset"] + v["size"]
        ]
        if len(owners) != 1:
            raise ValueError(
                f"{register} vec4 slot {slot} byte {byte_offset} maps to {len(owners)} RDEF variables"
            )
        variable = owners[0]
        used_constants.append(
            {
                "constantBuffer": cb["name"],
                "register": register,
                "vec4Slot": slot,
                "byteOffset": byte_offset,
                "variable": variable["name"],
                "variableStartOffset": variable["startOffset"],
                "variableSize": variable["size"],
                "byteOffsetWithinVariable": byte_offset - variable["startOffset"],
            }
        )
    # Deduplicate while preserving sorted deterministic output.
    unique = {
        (r["register"], r["vec4Slot"], r["variable"]): r for r in used_constants
    }
    rdef["translatedSpirv"] = {
        "entryPoints": reflection.get("entryPoints", []),
        "inputs": reflection.get("inputs", []),
        "outputs": reflection.get("outputs", []),
        "usedConstants": [unique[k] for k in sorted(unique)],
    }
    return rdef


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxbc", type=Path)
    parser.add_argument("--spirv-reflection", type=Path)
    parser.add_argument("--glsl", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    data = args.dxbc.read_bytes()
    parsed = parse_rdef(data)
    if (args.spirv_reflection is None) != (args.glsl is None):
        raise SystemExit("--spirv-reflection and --glsl must be supplied together")
    if args.spirv_reflection is not None:
        parsed = merge_spirv_reflection(
            parsed,
            json.loads(args.spirv_reflection.read_text(encoding="utf-8")),
            args.glsl.read_text(encoding="utf-8"),
        )

    out = {
        "format": FORMAT,
        "proofBoundary": (
            "Direct DXBC RDEF metadata, optionally joined to SPIRV-Cross reflection/GLSL "
            "by preserved D3D register identity. No resource-role or shader-equation inference."
        ),
        "source": {
            "path": args.dxbc.name,
            "bytes": len(data),
            "sha256": sha256(data),
        },
        **parsed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
