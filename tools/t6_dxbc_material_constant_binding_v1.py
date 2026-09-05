#!/usr/bin/env python3
"""Bind T6 DXBC cbuffer scalar leaves to exact MaterialConstantDef literals.

Exact chain:

  DXBC RDEF cbuffer bind point + variable byte range
    -> OAT .tech shader-variable assignment
    -> material.<fullConstantName>
    -> T6 R_HashString(fullConstantName, seed=0)
    -> serialized MaterialConstantDef hash + 12-byte fragment + float4 literal

This exists primarily to close generated vN height DAG leaves such as
``cb1[59].x`` without hard-coded values.  It is generic for scalar cbN[R].xyzw
leaves whose shader variable is backed by an OAT material constant assignment.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Iterable

from t6_dxbc_inspect_v1 import inspect_dxbc


FORMAT = "t6-dxbc-material-constant-binding-v1"
CB_LEAF_RE = re.compile(r"^cb(\d+)\[(\d+)\]\.([xyzw])$")
MATERIAL_ASSIGN_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*material\.([A-Za-z_][A-Za-z0-9_]*)\s*;\s*(?://.*)?$"
)
COMPONENT_INDEX = {"x": 0, "y": 1, "z": 2, "w": 3}


class MaterialConstantBindingError(RuntimeError):
    pass


def t6_r_hash_string(text: str, seed: int = 0) -> int:
    """Pinned T6 Common::R_HashString: DJB2-XOR no-case with explicit seed."""
    value = seed & 0xFFFFFFFF
    for byte in text.encode("utf-8"):
        value = (((value << 5) + value) ^ (byte | 0x20)) & 0xFFFFFFFF
    return value


def _u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise MaterialConstantBindingError(f"{label}: u32 outside RDEF at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _cstr(data: bytes, offset: int, label: str) -> str:
    if offset < 0 or offset >= len(data):
        raise MaterialConstantBindingError(f"{label}: string offset outside RDEF: {offset}")
    end = data.find(b"\0", offset)
    if end < 0:
        raise MaterialConstantBindingError(f"{label}: unterminated RDEF string")
    try:
        return data[offset:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MaterialConstantBindingError(f"{label}: non-UTF8 RDEF string") from exc


def parse_rdef_constant_buffers(dxbc: bytes) -> dict:
    """Parse the documented RDEF constant-buffer/variable records fail-closed."""
    inspected = inspect_dxbc(dxbc)
    rdef_chunks = [chunk for chunk in inspected["chunks"] if chunk["tag"] == "RDEF"]
    if len(rdef_chunks) != 1:
        raise MaterialConstantBindingError(f"expected exactly one RDEF chunk, got {len(rdef_chunks)}")
    chunk = rdef_chunks[0]
    start = int(chunk["payloadOffset"])
    size = int(chunk["payloadBytes"])
    payload = dxbc[start:start + size]
    if len(payload) != size:
        raise MaterialConstantBindingError("RDEF payload truncated")

    cb_count = _u32(payload, 0, "RDEF cbuffer count")
    cb_offset = _u32(payload, 4, "RDEF cbuffer offset")
    major = int(inspected["reflection"]["major"])
    minor = int(inspected["reflection"]["minor"])
    cbuffer_entry_size = 24
    variable_entry_size = 40 if (major, minor) >= (5, 0) else 24
    if cb_offset + cb_count * cbuffer_entry_size > len(payload):
        raise MaterialConstantBindingError("RDEF cbuffer table exceeds chunk")

    # RDEF represents constant buffers both in its cbuffer metadata table and in
    # the bound-resource table. Join by exact reflected name to recover b#.
    bound_by_name: dict[str, dict] = {}
    for resource in inspected["reflection"]["boundResources"]:
        if resource["inputType"] != "CBUFFER":
            continue
        name = str(resource["name"])
        if name in bound_by_name:
            raise MaterialConstantBindingError(f"duplicate CBUFFER bound resource {name!r}")
        if int(resource["bindCount"]) != 1:
            raise MaterialConstantBindingError(
                f"CBUFFER {name!r} has bindCount {resource['bindCount']}, expected 1"
            )
        bound_by_name[name] = resource

    buffers: list[dict] = []
    seen_bind_points: set[int] = set()
    for index in range(cb_count):
        off = cb_offset + index * cbuffer_entry_size
        name_offset, variable_count, variables_offset, buffer_size, buffer_type, flags = struct.unpack_from(
            "<IIIIII", payload, off
        )
        name = _cstr(payload, name_offset, f"RDEF cbuffer {index} name")
        bound = bound_by_name.get(name)
        if bound is None:
            raise MaterialConstantBindingError(
                f"RDEF cbuffer metadata {name!r} has no exact bound-resource CBUFFER entry"
            )
        bind_point = int(bound["bindPoint"])
        if bind_point in seen_bind_points:
            raise MaterialConstantBindingError(f"multiple RDEF cbuffers bind to b{bind_point}")
        seen_bind_points.add(bind_point)
        if buffer_size % 16:
            raise MaterialConstantBindingError(
                f"RDEF cbuffer {name!r} size {buffer_size} is not 16-byte aligned"
            )
        if variables_offset + variable_count * variable_entry_size > len(payload):
            raise MaterialConstantBindingError(
                f"RDEF cbuffer {name!r} variable table exceeds chunk"
            )

        variables: list[dict] = []
        occupied: list[tuple[int, int, str]] = []
        for variable_index in range(variable_count):
            voff = variables_offset + variable_index * variable_entry_size
            name_ptr, start_offset, variable_size, variable_flags, type_offset, default_offset = struct.unpack_from(
                "<IIIIII", payload, voff
            )
            variable_name = _cstr(payload, name_ptr, f"RDEF {name} variable {variable_index} name")
            end_offset = start_offset + variable_size
            if variable_size <= 0 or end_offset > buffer_size:
                raise MaterialConstantBindingError(
                    f"RDEF {name}.{variable_name} byte range {start_offset}..{end_offset} outside buffer {buffer_size}"
                )
            for old_start, old_end, old_name in occupied:
                if not (end_offset <= old_start or start_offset >= old_end):
                    raise MaterialConstantBindingError(
                        f"RDEF cbuffer {name!r} variables {old_name!r}/{variable_name!r} overlap"
                    )
            occupied.append((start_offset, end_offset, variable_name))
            variable = {
                "index": variable_index,
                "name": variable_name,
                "startOffset": start_offset,
                "size": variable_size,
                "endOffset": end_offset,
                "flags": variable_flags,
                "typeOffset": type_offset,
                "defaultValueOffset": default_offset,
            }
            if variable_entry_size == 40:
                (
                    variable["startTexture"],
                    variable["textureSize"],
                    variable["startSampler"],
                    variable["samplerSize"],
                ) = struct.unpack_from("<IIII", payload, voff + 24)
            variables.append(variable)
        buffers.append({
            "index": index,
            "name": name,
            "bindPoint": bind_point,
            "size": buffer_size,
            "type": buffer_type,
            "flags": flags,
            "variableCount": variable_count,
            "variables": variables,
        })

    return {
        "format": "t6-dxbc-rdef-cbuffers-v1",
        "dxbcSha256": hashlib.sha256(dxbc).hexdigest(),
        "shaderModel": inspected["program"]["shaderModel"],
        "constantBufferCount": len(buffers),
        "constantBuffers": sorted(buffers, key=lambda item: item["bindPoint"]),
    }


def parse_material_assignments(technique_text: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for line in technique_text.splitlines():
        match = MATERIAL_ASSIGN_RE.match(line)
        if not match:
            continue
        shader_name, material_name = match.groups()
        old = assignments.get(shader_name)
        if old is not None and old != material_name:
            raise MaterialConstantBindingError(
                f"shader variable {shader_name!r} has conflicting material assignments {old!r}/{material_name!r}"
            )
        assignments[shader_name] = material_name
    return assignments


def _find_rdef_variable(rdef: dict, bind_point: int, byte_offset: int) -> tuple[dict, dict]:
    buffers = [b for b in rdef["constantBuffers"] if int(b["bindPoint"]) == bind_point]
    if len(buffers) != 1:
        raise MaterialConstantBindingError(
            f"DXBC has {len(buffers)} constant buffers at b{bind_point}, expected exactly one"
        )
    buffer = buffers[0]
    variables = [
        variable for variable in buffer["variables"]
        if int(variable["startOffset"]) <= byte_offset < int(variable["endOffset"])
    ]
    if len(variables) != 1:
        raise MaterialConstantBindingError(
            f"b{bind_point} byte {byte_offset} maps to {len(variables)} RDEF variables"
        )
    return buffer, variables[0]


def _constant_by_full_name(constants: list[dict], full_name: str) -> dict:
    expected_hash = t6_r_hash_string(full_name, 0)
    candidates = [item for item in constants if int(item["nameHash"]) == expected_hash]
    if len(candidates) != 1:
        raise MaterialConstantBindingError(
            f"material constant {full_name!r} hash 0x{expected_hash:08x} matched {len(candidates)} serialized constants"
        )
    constant = candidates[0]
    expected_fragment = full_name[:12]
    if str(constant.get("nameFragment") or "") != expected_fragment:
        raise MaterialConstantBindingError(
            f"material constant {full_name!r} hash matched but fragment {constant.get('nameFragment')!r} "
            f"!= {expected_fragment!r}"
        )
    literal = constant.get("literal")
    if not isinstance(literal, list) or len(literal) != 4:
        raise MaterialConstantBindingError(f"material constant {full_name!r} is not a float4 literal")
    return constant


def bind_cb_leaf(
    leaf: str,
    *,
    rdef: dict,
    assignments: dict[str, str],
    material_constants: list[dict],
) -> dict:
    match = CB_LEAF_RE.match(leaf)
    if not match:
        raise MaterialConstantBindingError(f"unsupported cbuffer scalar leaf {leaf!r}")
    bind_point = int(match.group(1))
    register = int(match.group(2))
    component = match.group(3)
    component_index = COMPONENT_INDEX[component]
    byte_offset = register * 16 + component_index * 4
    buffer, variable = _find_rdef_variable(rdef, bind_point, byte_offset)

    shader_variable = str(variable["name"])
    material_name = assignments.get(shader_variable)
    if material_name is None:
        raise MaterialConstantBindingError(
            f"RDEF variable {shader_variable!r} covering {leaf} has no material.* assignment in .tech"
        )
    constant = _constant_by_full_name(material_constants, material_name)

    relative = byte_offset - int(variable["startOffset"])
    if relative % 4:
        raise MaterialConstantBindingError(
            f"{leaf}: byte offset is not a scalar-float boundary within {shader_variable!r}"
        )
    literal_component = relative // 4
    if not 0 <= literal_component < 4:
        raise MaterialConstantBindingError(
            f"{leaf}: {shader_variable!r} component offset {literal_component} cannot map to MaterialConstantDef float4"
        )

    return {
        "leaf": leaf,
        "cbuffer": {
            "name": buffer["name"],
            "bindPoint": bind_point,
            "register": register,
            "registerComponent": component,
            "byteOffset": byte_offset,
        },
        "shaderVariable": {
            "name": shader_variable,
            "startOffset": variable["startOffset"],
            "size": variable["size"],
            "relativeByteOffset": relative,
        },
        "materialConstant": {
            "name": material_name,
            "nameHash": constant["nameHash"],
            "nameHashHex": constant.get("nameHashHex", f"0x{int(constant['nameHash']):08x}"),
            "nameFragment": constant["nameFragment"],
            "literal": list(constant["literal"]),
            "literalComponent": literal_component,
            "value": float(constant["literal"][literal_component]),
            "serializedSha256": constant.get("serializedSha256"),
        },
        "proof": (
            "DXBC RDEF byte-range -> exact OAT .tech material assignment -> T6 zero-seed "
            "R_HashString -> exact serialized MaterialConstantDef"
        ),
    }


def bind_cb_leaves(
    leaves: Iterable[str],
    *,
    dxbc: bytes,
    technique_text: str,
    material_constants: list[dict],
) -> dict:
    unique = sorted(set(map(str, leaves)))
    rdef = parse_rdef_constant_buffers(dxbc)
    assignments = parse_material_assignments(technique_text)
    rows = [
        bind_cb_leaf(
            leaf,
            rdef=rdef,
            assignments=assignments,
            material_constants=material_constants,
        )
        for leaf in unique
    ]
    return {
        "format": FORMAT,
        "dxbcSha256": hashlib.sha256(dxbc).hexdigest(),
        "leafCount": len(rows),
        "bindings": rows,
        "allLeavesExact": True,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--shader", type=Path, required=True)
    parser.add_argument("--technique", type=Path, required=True)
    parser.add_argument("--material-constants", type=Path, required=True)
    parser.add_argument("--leaf", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    constants_doc = json.loads(args.material_constants.read_text(encoding="utf-8"))
    constants = constants_doc.get("constants", constants_doc)
    if not isinstance(constants, list):
        raise MaterialConstantBindingError("material-constants input must be a list or contain a constants list")
    result = bind_cb_leaves(
        args.leaf,
        dxbc=args.shader.read_bytes(),
        technique_text=args.technique.read_text(encoding="utf-8"),
        material_constants=constants,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "leafCount": result["leafCount"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
