#!/usr/bin/env python3
"""Close the exact T6 native shadowoverlay pixel-shader equation.

Inputs are deliberately separated:

* the exact retail DXBC pixel shader, whose container/RDEF data is parsed here;
* a textual disassembly of that exact DXBC produced by an independently pinned
  disassembler.

Authority is emitted only if the retained shader SHA, Shader Model, RDEF
resource bindings, reflected `filterTap` constant-buffer location, and complete
executable instruction sequence all match the expected native
`pimp_shader_trivial_3981dec1.hlsl` program.

This proves shader arithmetic only.  It does not identify which engine image is
assigned to `feedbackSampler` for any draw, nor the renderer-global Material
slot, draw scheduler, or render-target lifetime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

EXPECTED_SHA256 = "2ef171c239a7c98542a961252362761828747bd288ee21e3fde542d48aa5de0e"
EXPECTED_BYTES = 5600
EXPECTED_MODEL = (4, 0)
EXPECTED_FILTER_TAP_START = 1648
EXPECTED_FILTER_TAP_SIZE = 128

EXPECTED_RESOURCES = [
    ("colorMapSampler", 3, 0, 0, 0, 1),  # sampler s0
    ("colorMapSampler", 2, 5, 4, 0, 1),  # float Texture2D t0
    ("PerSceneConsts", 0, 0, 0, 0, 1),  # cbuffer b0
]

EXPECTED_INSTRUCTIONS = [
    "add r0.x, -cb0[103].w, cb0[103].z",
    "sample r1.xyzw, v1.xyxx, t0.xyzw, s0",
    "mad r0.x, r1.x, r0.x, cb0[103].w",
    "mul r0.y, r1.x, cb0[103].z",
    "eq r0.z, r1.x, 1.000000f",
    "div r0.x, r0.y, r0.x",
    "mad_sat r0.x, r0.x, cb0[103].x, cb0[103].y",
    "movc o0.xyz, r0.zzzz, (0, 0, 0.500000f, 0), r0.xxxx",
    "mov o0.w, 1.000000f",
    "ret",
]


class ProofError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstr(data: bytes, off: int, label: str) -> str:
    if off < 0 or off >= len(data):
        raise ProofError(f"{label}: string offset outside RDEF: {off}")
    end = data.find(b"\0", off)
    if end < 0:
        raise ProofError(f"{label}: unterminated string")
    return data[off:end].decode("utf-8", errors="strict")


def dxbc_chunks(data: bytes) -> dict[str, bytes]:
    if len(data) != EXPECTED_BYTES or sha256(data) != EXPECTED_SHA256:
        raise ProofError(
            f"pixel shader identity mismatch: bytes={len(data)} sha256={sha256(data)}"
        )
    if data[:4] != b"DXBC" or len(data) < 32:
        raise ProofError("pixel shader is not a valid DXBC container")
    total, count = struct.unpack_from("<II", data, 24)
    if total != len(data) or 32 + count * 4 > len(data):
        raise ProofError("DXBC header size/table mismatch")
    offsets = struct.unpack_from(f"<{count}I", data, 32)
    out: dict[str, bytes] = {}
    spans = []
    for i, off in enumerate(offsets):
        if off < 32 + count * 4 or off + 8 > len(data):
            raise ProofError(f"DXBC chunk {i}: invalid offset {off}")
        tag = data[off:off+4].decode("ascii", errors="strict")
        size = struct.unpack_from("<I", data, off + 4)[0]
        end = off + 8 + size
        if end > len(data):
            raise ProofError(f"DXBC chunk {tag}: exceeds container")
        if any(not (end <= a or off >= b) for a, b in spans):
            raise ProofError(f"DXBC chunk {tag}: overlaps another chunk")
        spans.append((off, end))
        if tag in out:
            raise ProofError(f"duplicate DXBC chunk {tag}")
        out[tag] = data[off+8:end]
    return out


def parse_program(payload: bytes) -> dict:
    if len(payload) < 8 or len(payload) % 4:
        raise ProofError("malformed SHDR payload")
    version, declared = struct.unpack_from("<II", payload, 0)
    major = (version >> 4) & 0xF
    minor = version & 0xF
    ptype = (version >> 16) & 0xFFFF
    if (major, minor) != EXPECTED_MODEL or ptype != 0:
        raise ProofError(f"unexpected shader model/type {(major, minor, ptype)}")
    if declared * 4 > len(payload):
        raise ProofError("SHDR declared size exceeds payload")
    return {
        "shaderModel": f"{major}.{minor}",
        "programType": "pixel",
        "declaredProgramDwords": declared,
        "declaredProgramBytes": declared * 4,
    }


def parse_rdef(payload: bytes) -> dict:
    if len(payload) < 28:
        raise ProofError("RDEF shorter than header")
    cb_count, cb_off, resource_count, resource_off = struct.unpack_from("<4I", payload, 0)
    minor = payload[16]
    major = payload[17]
    shader_type = struct.unpack_from("<H", payload, 18)[0]
    if (major, minor) != EXPECTED_MODEL or shader_type != 0xFFFF:
        raise ProofError(f"unexpected RDEF model/type {(major, minor, shader_type)}")

    if resource_off + resource_count * 32 > len(payload):
        raise ProofError("RDEF resource table outside chunk")
    resources = []
    compact = []
    for i in range(resource_count):
        vals = struct.unpack_from("<8I", payload, resource_off + i * 32)
        name_off, input_type, return_type, dimension, samples, bind_point, bind_count, flags = vals
        name = cstr(payload, name_off, f"resource {i}")
        resources.append({
            "index": i,
            "name": name,
            "inputTypeValue": input_type,
            "returnTypeValue": return_type,
            "dimensionValue": dimension,
            "numSamples": samples,
            "bindPoint": bind_point,
            "bindCount": bind_count,
            "flags": flags,
        })
        compact.append((name, input_type, return_type, dimension, bind_point, bind_count))
    if compact != EXPECTED_RESOURCES:
        raise ProofError(f"unexpected RDEF resources: {compact!r}")

    if cb_count != 1 or cb_off + 24 > len(payload):
        raise ProofError(f"unexpected constant-buffer count/table: {cb_count}")
    cb_name_off, var_count, var_off, cb_size, cb_flags, cb_type = struct.unpack_from("<6I", payload, cb_off)
    cb_name = cstr(payload, cb_name_off, "constant buffer")
    if cb_name != "PerSceneConsts":
        raise ProofError(f"unexpected constant-buffer name {cb_name!r}")
    if var_off + var_count * 24 > len(payload):
        raise ProofError("RDEF variable table outside chunk")

    variables = []
    for i in range(var_count):
        name_off, start, size, flags, type_off, default_off = struct.unpack_from(
            "<6I", payload, var_off + i * 24
        )
        name = cstr(payload, name_off, f"constant variable {i}")
        variables.append({
            "index": i,
            "name": name,
            "startOffset": start,
            "bytes": size,
            "flags": flags,
            "typeOffset": type_off,
            "defaultValueOffset": default_off,
        })
    matches = [
        v for v in variables
        if v["name"] == "filterTap"
        and v["startOffset"] == EXPECTED_FILTER_TAP_START
        and v["bytes"] == EXPECTED_FILTER_TAP_SIZE
    ]
    if len(matches) != 1:
        raise ProofError(
            f"filterTap reflection mismatch: "
            f"{[(v['name'], v['startOffset'], v['bytes']) for v in variables if v['name']=='filterTap']}"
        )
    if EXPECTED_FILTER_TAP_START // 16 != 103:
        raise ProofError("internal filterTap register assertion failed")

    return {
        "shaderModel": f"{major}.{minor}",
        "boundResources": resources,
        "constantBuffer": {
            "name": cb_name,
            "bytes": cb_size,
            "variableCount": var_count,
        },
        "filterTap": {
            **matches[0],
            "firstFloat4Register": EXPECTED_FILTER_TAP_START // 16,
            "float4Count": EXPECTED_FILTER_TAP_SIZE // 16,
        },
    }


def parse_disassembly(text: str) -> dict:
    model = None
    declarations = []
    instructions = []
    for raw in text.splitlines():
        s = raw.strip()
        m = re.fullmatch(r"ps_(\d+)_(\d+) \((\d+) tok\):", s)
        if m:
            model = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            continue
        m = re.fullmatch(r"(\d+):\s+(.+)", s)
        if not m:
            continue
        idx = int(m.group(1))
        op = m.group(2).strip()
        if op.startswith("dcl_"):
            declarations.append({"index": idx, "instruction": op})
        else:
            instructions.append({"index": idx, "instruction": op})
    if model is None or model[:2] != EXPECTED_MODEL:
        raise ProofError(f"disassembly shader model mismatch: {model}")
    actual = [row["instruction"] for row in instructions]
    if actual != EXPECTED_INSTRUCTIONS:
        raise ProofError(f"pixel instruction sequence mismatch: {actual!r}")
    return {
        "shaderModel": f"{model[0]}.{model[1]}",
        "tokenCount": model[2],
        "declarations": declarations,
        "instructions": instructions,
    }


def build(cso: Path, disasm: Path) -> dict:
    data = cso.read_bytes()
    chunks = dxbc_chunks(data)
    if "SHDR" not in chunks or "RDEF" not in chunks:
        raise ProofError("required RDEF/SHDR chunks missing")
    program = parse_program(chunks["SHDR"])
    reflection = parse_rdef(chunks["RDEF"])
    assembly = parse_disassembly(disasm.read_text(encoding="utf-8", errors="strict"))
    if program["shaderModel"] != reflection["shaderModel"] or program["shaderModel"] != assembly["shaderModel"]:
        raise ProofError("shader model disagreement across SHDR/RDEF/disassembly")

    return {
        "format": "t6-shadowoverlay-shader-semantics-v1",
        "source": {
            "shader": "pimp_shader_trivial_3981dec1.hlsl",
            "bytes": len(data),
            "sha256": sha256(data),
            "nativeTechnique": "pimp_technique_trivial_7bf1260",
            "nativeTechniqueArgument": "colorMapSampler = sampler.feedbackSampler",
        },
        "program": program,
        "reflection": reflection,
        "disassembly": assembly,
        "equation": {
            "sample": "s = texture2D(t0, uv).r",
            "filterTap0": "f = cb0[103] = filterTap[0]",
            "denominator": "d = f.w + s * (f.z - f.w)",
            "projectiveRemap": "u = (s * f.z) / d",
            "scaledClamped": "v = saturate(u * f.x + f.y)",
            "rgb": "s == 1.0 ? (0.0, 0.0, 0.5) : (v, v, v)",
            "alpha": "1.0",
        },
        "summary": {
            "authoritativeShaderArithmetic": True,
            "textureRegister": 0,
            "samplerRegister": 0,
            "constantBufferRegister": 0,
            "filterTap0Register": 103,
            "sampledChannel": "red/x",
            "sampleInstructionCount": 1,
            "outputAlphaConstant": 1.0,
            "exactOneSentinelRgb": [0.0, 0.0, 0.5],
        },
        "proofBoundary": (
            "Authoritative only for the arithmetic of the exact SHA-pinned native T6 shadowoverlay pixel shader. "
            "RDEF proves colorMapSampler at t0/s0 and filterTap beginning at cb0[103]; the independently produced "
            "disassembly proves the exact instruction sequence and equation. The serialized Technique separately binds "
            "colorMapSampler to sampler.feedbackSampler. This document does not identify the runtime image assigned to "
            "feedbackSampler, the producer of filterTap[0], renderer-global Material storage, draw scheduling, or a "
            "high-level shadow-overlay consumer path."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pixel-cso", type=Path, required=True)
    p.add_argument("--disasm", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.pixel_cso.resolve(), a.disasm.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
