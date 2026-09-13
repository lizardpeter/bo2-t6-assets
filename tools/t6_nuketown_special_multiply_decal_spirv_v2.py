#!/usr/bin/env python3
"""Translate and canonically rebind the exact Nuketown multiply-decal shaders.

V1 proves the SHA-pinned retail DXBC pair translates through vkd3d and exposes
exactly VS {cb0_0, cb3_0} and PS {s0, t0}. V2 additionally applies the renderer's
source-neutral T6 Vulkan descriptor ABI directly to SPIR-V Binding decorations:

  bN -> N, sN -> 16 + N, tN -> 32 + N

No executable instruction or type is rewritten. Both the raw and canonical
modules must pass spirv-val, and the canonical modules are disassembled again to
prove the final bindings that Rust-test will embed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import t6_nuketown_special_multiply_decal_spirv_v1 as v1

FORMAT = "t6-nuketown-special-multiply-decal-spirv-v2"
ABI = "t6-vulkan-descriptor-abi-v1"
EXPECTED_CANONICAL = {
    "vs": {"cb0_0": 0, "cb3_0": 3},
    "ps": {"s0": 16, "t0": 32},
}
EXPECTED_CANONICAL_SHA256 = {
    "vs": "0ec443fd60bcd78276bece81e956f767f28dd373160dfa60cae5842811abd05c",
    "ps": "eeb57084909474182be759b2342a86ea9089081a54fae2191ce18995dea8714e",
}

SPIRV_MAGIC = 0x07230203
OP_NAME = 5
OP_DECORATE = 71
DECORATION_BINDING = 33
DECORATION_DESCRIPTOR_SET = 34


class CanonicalSpirvError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_words(data: bytes) -> list[int]:
    if len(data) < 20 or len(data) % 4:
        raise CanonicalSpirvError(f"invalid SPIR-V byte length {len(data)}")
    words = list(struct.unpack(f"<{len(data)//4}I", data))
    if words[0] != SPIRV_MAGIC:
        raise CanonicalSpirvError("invalid SPIR-V magic")
    return words


def walk(words: list[int]):
    offset = 5
    while offset < len(words):
        header = words[offset]
        count = header >> 16
        opcode = header & 0xFFFF
        if count == 0 or offset + count > len(words):
            raise CanonicalSpirvError(f"malformed instruction at word {offset}")
        yield offset, opcode, words[offset + 1 : offset + count]
        offset += count


def spirv_string(words: list[int]) -> str:
    raw = b"".join(struct.pack("<I", word) for word in words)
    raw = raw.split(b"\0", 1)[0]
    return raw.decode("utf-8")


def canonical_binding(name: str) -> int:
    if name.startswith("cb"):
        suffix = name[2:]
        pieces = suffix.split("_")
        if len(pieces) != 2 or pieces[1] != "0" or not pieces[0].isdigit():
            raise CanonicalSpirvError(f"unsupported cbuffer descriptor name {name!r}")
        register = int(pieces[0])
        if register >= 16:
            raise CanonicalSpirvError(f"cbuffer register out of range: {name!r}")
        return register
    if name.startswith("s") and name[1:].isdigit():
        register = int(name[1:])
        if register < 16:
            return 16 + register
    if name.startswith("t") and name[1:].isdigit():
        register = int(name[1:])
        if register < 16:
            return 32 + register
    raise CanonicalSpirvError(f"unsupported translated descriptor name {name!r}")


def canonicalize(data: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    words = decode_words(data)
    names: dict[int, str] = {}
    sets: dict[int, int] = {}
    binding_words: dict[int, tuple[int, int]] = {}

    for offset, opcode, operands in walk(words):
        if opcode == OP_NAME and len(operands) >= 2:
            names[operands[0]] = spirv_string(operands[1:])
        elif opcode == OP_DECORATE and len(operands) >= 3:
            target, decoration, value = operands[0], operands[1], operands[2]
            if decoration == DECORATION_DESCRIPTOR_SET:
                if target in sets:
                    raise CanonicalSpirvError(f"duplicate DescriptorSet decoration on id {target}")
                sets[target] = value
            elif decoration == DECORATION_BINDING:
                if target in binding_words:
                    raise CanonicalSpirvError(f"duplicate Binding decoration on id {target}")
                binding_words[target] = (offset + 3, value)

    if not binding_words:
        raise CanonicalSpirvError("module has no bound descriptors")

    owners: dict[int, str] = {}
    report: list[dict[str, Any]] = []
    for target, (word_index, old_binding) in binding_words.items():
        name = names.get(target)
        if not name:
            raise CanonicalSpirvError(f"bound descriptor id {target} has no OpName")
        if sets.get(target) != 0:
            raise CanonicalSpirvError(
                f"descriptor {name!r} uses set {sets.get(target)!r}, expected set 0"
            )
        new_binding = canonical_binding(name)
        previous = owners.get(new_binding)
        if previous is not None:
            raise CanonicalSpirvError(
                f"canonical binding collision {new_binding}: {previous!r} vs {name!r}"
            )
        owners[new_binding] = name
        words[word_index] = new_binding
        report.append(
            {
                "name": name,
                "descriptorSet": 0,
                "oldBinding": old_binding,
                "binding": new_binding,
            }
        )

    report.sort(key=lambda row: (row["binding"], row["name"]))
    return struct.pack(f"<{len(words)}I", *words), report


def canonicalize_stage(stage: str, raw_path: Path) -> dict[str, Any]:
    raw = raw_path.read_bytes()
    canonical, patch_report = canonicalize(raw)
    out_path = raw_path.with_name(raw_path.name.replace(".raw.spv", ".canonical.spv"))
    out_path.write_bytes(canonical)
    v1.run("spirv-val", str(out_path))

    dis_rows = v1.descriptor_rows(v1.disassemble(out_path))
    actual = {row["name"]: row["binding"] for row in dis_rows}
    if actual != EXPECTED_CANONICAL[stage]:
        raise CanonicalSpirvError(
            f"{stage} canonical descriptor map {actual!r} != {EXPECTED_CANONICAL[stage]!r}"
        )
    digest = sha256(canonical)
    expected_digest = EXPECTED_CANONICAL_SHA256[stage]
    if digest != expected_digest:
        raise CanonicalSpirvError(
            f"{stage} canonical SPIR-V SHA {digest} != pinned {expected_digest}"
        )
    return {
        "sha256": digest,
        "bytes": len(canonical),
        "file": out_path.name,
        "descriptorAbi": ABI,
        "patches": patch_report,
        "descriptors": dis_rows,
    }


def build(census_path: Path, out_dir: Path) -> dict[str, Any]:
    # Re-run the independent v1 translation first; do not consume a cached raw
    # module whose DXBC provenance could have drifted.
    raw_doc = v1.build(census_path, out_dir)
    vs_path = out_dir / f"vs_{v1.VS_SHA256}.raw.spv"
    ps_path = out_dir / f"ps_{v1.PS_SHA256}.raw.spv"
    vs = canonicalize_stage("vs", vs_path)
    ps = canonicalize_stage("ps", ps_path)

    doc = {
        "format": FORMAT,
        "map": "mp_nuketown_2020",
        "techniqueSet": v1.TECHNIQUE_SET,
        "descriptorAbi": ABI,
        "rawProofSha256": raw_doc["proofSha256"],
        "vertexShader": {
            "dxbcSha256": v1.VS_SHA256,
            "rawSpirvSha256": raw_doc["vertexShader"]["rawSpirvSha256"],
            "canonical": vs,
        },
        "pixelShader": {
            "dxbcSha256": v1.PS_SHA256,
            "rawSpirvSha256": raw_doc["pixelShader"]["rawSpirvSha256"],
            "canonical": ps,
        },
        "proofBoundary": (
            "V1 exact retail DXBC provenance and raw vkd3d translation are re-run. V2 changes only "
            "set-0 SPIR-V Binding decoration literals according to the source-neutral T6 ABI "
            "bN->N,sN->16+N,tN->32+N. Both canonical modules pass spirv-val and their "
            "post-patch spirv-dis descriptor maps and SHA-256 identities are pinned. No shader "
            "arithmetic, control flow, types, interface locations, or constants are rewritten."
        ),
    }
    stable = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    doc["proofSha256"] = sha256(stable)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.special_census, args.out_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "vertexShader": doc["vertexShader"],
        "pixelShader": doc["pixelShader"],
        "proofSha256": doc["proofSha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
