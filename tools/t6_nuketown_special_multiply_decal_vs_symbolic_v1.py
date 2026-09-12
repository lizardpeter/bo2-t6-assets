#!/usr/bin/env python3
"""Close the exact VS producer for Nuketown's zero-runtime multiply decals.

The three retained wpc multiply-decal Materials share one exact unlit/emissive
VS/PS pair.  Their pixel shader is already fully reconstructed and its only
remaining non-texture leaf of interest is input register v2.z, which multiplies
sample alpha.  This tool reads the exact native-OAT-selected VS/PS bytes from
the retained special census, SHA-verifies both payloads, reconstructs every VS
output lane with the existing straight-line SM4 symbolic executor, and joins
PS v2 to the matching VS OSGN semantic.  No value is guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-multiply-decal-vs-symbolic-v1"
TECHNIQUE_SET = "wpc_unlitdecalblend_multiply_35079164"
VS_SHA256 = "c3bd9eb7d12a444c63867be2e466ac00c495a5a7f64a8b2c9f73e2558a5e12e0"
PS_SHA256 = "e9820077a4df69228fd1626997270d7b31337f82eab6c26c1a14a33257424a0b"


class MultiplyDecalVsError(RuntimeError):
    pass


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def dxbc_chunks(blob: bytes):
    if len(blob) < 32 or blob[:4] != b"DXBC":
        raise MultiplyDecalVsError("payload is not DXBC")
    chunk_count = struct.unpack_from("<I", blob, 28)[0]
    table_end = 32 + 4 * chunk_count
    if table_end > len(blob):
        raise MultiplyDecalVsError("DXBC chunk table is truncated")
    for offset in struct.unpack_from("<" + "I" * chunk_count, blob, 32):
        if offset + 8 > len(blob):
            raise MultiplyDecalVsError("DXBC chunk header is truncated")
        size = struct.unpack_from("<I", blob, offset + 4)[0]
        end = offset + 8 + size
        if end > len(blob):
            raise MultiplyDecalVsError("DXBC chunk payload is truncated")
        yield blob[offset : offset + 4], blob[offset + 8 : end]


def signature(blob: bytes, tag: bytes) -> list[dict[str, Any]]:
    rows = []
    for chunk_tag, raw in dxbc_chunks(blob):
        if chunk_tag != tag:
            continue
        if len(raw) < 8:
            raise MultiplyDecalVsError(f"{tag!r} chunk is truncated")
        count = struct.unpack_from("<I", raw, 0)[0]
        for index in range(count):
            offset = 8 + 24 * index
            if offset + 24 > len(raw):
                raise MultiplyDecalVsError(f"{tag!r} row {index} is truncated")
            name_offset, semantic_index, system_value, component_type, register, mask_word = struct.unpack_from(
                "<6I", raw, offset
            )
            if name_offset >= len(raw):
                raise MultiplyDecalVsError(f"{tag!r} row {index} has invalid semantic offset")
            end = raw.find(b"\0", name_offset)
            if end < 0:
                raise MultiplyDecalVsError(f"{tag!r} row {index} semantic is unterminated")
            semantic = raw[name_offset:end].decode("ascii")
            mask = mask_word & 0xFF
            read_write_mask = (mask_word >> 8) & 0xFF
            rows.append(
                {
                    "semantic": semantic,
                    "semanticIndex": semantic_index,
                    "systemValue": system_value,
                    "componentType": component_type,
                    "register": register,
                    "mask": mask,
                    "readWriteMask": read_write_mask,
                }
            )
        return rows
    raise MultiplyDecalVsError(f"DXBC has no {tag.decode('ascii')} signature")


def selected_group(census: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    groups = {
        str(row.get("groupKey")): row
        for row in census.get("shaderGroups", [])
        if isinstance(row, dict) and row.get("groupKey")
    }
    matches = []
    for material in census.get("materials", []):
        if not isinstance(material, dict) or material.get("techniqueSet") != TECHNIQUE_SET:
            continue
        for program in material.get("programs", []):
            if not isinstance(program, dict) or program.get("techniqueType") not in ("unlit", "emissive"):
                continue
            key = str(program.get("groupKey") or "")
            group = groups.get(key)
            if group is None:
                raise MultiplyDecalVsError(f"missing exact shader group {key!r}")
            matches.append((group, Path(str(program.get("techniqueOwner") or ""))))
    if not matches:
        raise MultiplyDecalVsError(f"no exact {TECHNIQUE_SET!r} unlit/emissive group")

    stage_identity = set()
    for group, owner in matches:
        if not str(owner):
            raise MultiplyDecalVsError("exact multiply-decal group has no technique owner")
        stages = []
        for pass_row in group.get("passes", []):
            for stage in pass_row.get("stages", []):
                if stage.get("kind") in ("vertexShader", "pixelShader"):
                    stages.append((stage.get("kind"), stage.get("sha256"), stage.get("relativeFile")))
        stage_identity.add(tuple(stages))
    if len(stage_identity) != 1:
        raise MultiplyDecalVsError("unlit/emissive multiply-decal groups disagree on exact stage identity")
    return matches[0]


def exact_stage(group: dict[str, Any], owner: Path, kind: str, expected_sha: str) -> tuple[bytes, dict[str, Any]]:
    rows = [
        stage
        for pass_row in group.get("passes", [])
        for stage in pass_row.get("stages", [])
        if stage.get("kind") == kind
    ]
    if len(rows) != 1:
        raise MultiplyDecalVsError(f"multiply-decal group has {len(rows)} {kind} rows, expected one")
    stage = rows[0]
    recorded_sha = str(stage.get("sha256") or "").lower()
    if recorded_sha != expected_sha:
        raise MultiplyDecalVsError(f"{kind} census SHA {recorded_sha} != pinned {expected_sha}")
    relative = str(stage.get("relativeFile") or "")
    if not relative:
        raise MultiplyDecalVsError(f"{kind} has no exact relative file")
    path = owner / relative
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha:
        raise MultiplyDecalVsError(f"{path}: SHA-256 {actual} != pinned {expected_sha}")
    return raw, stage


def build(
    census_path: Path,
    full_symbolic_tool: Path,
    base_symbolic_tool: Path,
    operand_tool: Path,
    opcode_tool: Path,
) -> dict[str, Any]:
    census = json.loads(census_path.read_text(encoding="utf-8"))
    if census.get("format") != "t6-nuketown-special-material-census-v1":
        raise MultiplyDecalVsError(f"unexpected special census format {census.get('format')!r}")
    group, owner = selected_group(census)
    vs_raw, vs_stage = exact_stage(group, owner, "vertexShader", VS_SHA256)
    ps_raw, ps_stage = exact_stage(group, owner, "pixelShader", PS_SHA256)

    full = load(full_symbolic_tool, "special_full_symbolic")
    base = load(base_symbolic_tool, "special_symbolic_base")
    operand = load(operand_tool, "special_operand")
    opcode = load(opcode_tool, "special_opcode")
    symbolic = full.symbolic_full({"data": vs_raw}, operand, opcode, base)
    if symbolic["hasControlFlow"]:
        raise MultiplyDecalVsError("exact multiply-decal VS unexpectedly contains control flow")
    if symbolic["blockers"]:
        raise MultiplyDecalVsError(f"exact multiply-decal VS symbolic blockers: {symbolic['blockers'][:4]}")
    if symbolic["sideEffects"]:
        raise MultiplyDecalVsError(f"exact multiply-decal VS side effects: {symbolic['sideEffects'][:4]}")
    if symbolic["samples"]:
        raise MultiplyDecalVsError("exact multiply-decal VS unexpectedly samples a texture")

    vs_isgn = signature(vs_raw, b"ISGN")
    vs_osgn = signature(vs_raw, b"OSGN")
    ps_isgn = signature(ps_raw, b"ISGN")
    ps_v2 = [row for row in ps_isgn if row["register"] == 2]
    if len(ps_v2) != 1:
        raise MultiplyDecalVsError(f"pixel v2 signature has {len(ps_v2)} rows, expected one")
    target_semantic = (ps_v2[0]["semantic"], ps_v2[0]["semanticIndex"])
    vs_target = [
        row
        for row in vs_osgn
        if (row["semantic"], row["semanticIndex"]) == target_semantic
    ]
    if len(vs_target) != 1:
        raise MultiplyDecalVsError(
            f"VS output semantic {target_semantic!r} has {len(vs_target)} rows, expected one"
        )
    output_name = f"o{vs_target[0]['register']}.z"
    output_rows = [row for row in symbolic["outputs"] if row["output"] == output_name]
    if len(output_rows) != 1:
        raise MultiplyDecalVsError(f"symbolic VS output {output_name} has {len(output_rows)} rows, expected one")
    node_id = int(output_rows[0]["node"])
    if node_id < 0 or node_id >= len(symbolic["nodes"]):
        raise MultiplyDecalVsError(f"symbolic VS output {output_name} references invalid node {node_id}")

    compact = {
        "nodes": symbolic["nodes"],
        "outputs": symbolic["outputs"],
        "vsInputSignature": vs_isgn,
        "vsOutputSignature": vs_osgn,
        "psInputSignature": ps_isgn,
    }
    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_multiply_decal_vs_symbolic_v1.py",
        "map": "mp_nuketown_2020",
        "techniqueSet": TECHNIQUE_SET,
        "vertexShader": {
            "asset": vs_stage.get("asset"),
            "relativeFile": vs_stage.get("relativeFile"),
            "sha256": VS_SHA256,
            "byteCount": len(vs_raw),
        },
        "pixelShader": {
            "asset": ps_stage.get("asset"),
            "relativeFile": ps_stage.get("relativeFile"),
            "sha256": PS_SHA256,
            "byteCount": len(ps_raw),
        },
        "vsInputSignature": vs_isgn,
        "vsOutputSignature": vs_osgn,
        "psInputSignature": ps_isgn,
        "vsNodes": symbolic["nodes"],
        "vsOutputs": symbolic["outputs"],
        "pixelV2ZProducer": {
            "pixelInputRegister": 2,
            "semantic": ps_v2[0]["semantic"],
            "semanticIndex": ps_v2[0]["semanticIndex"],
            "vertexOutputRegister": vs_target[0]["register"],
            "vertexOutput": output_name,
            "node": node_id,
            "nodeRecord": symbolic["nodes"][node_id],
        },
        "dagSha256": digest(compact),
        "proofBoundary": (
            "Exact native-OAT-selected multiply-decal VS/PS bytes are SHA-256 verified before analysis. "
            "The VS is symbolically reconstructed from SM4 instructions with control flow, side effects, texture sampling, read-before-write and unsupported opcodes failing closed. "
            "Pixel v2.z is joined to the VS output only through matching DXBC ISGN/OSGN semantic identity. No default interpolant value or family-name heuristic is used."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument(
        "--full-symbolic-tool",
        type=Path,
        default=Path("tools/t6_nuketown_special_full_output_symbolic_v1.py"),
    )
    ap.add_argument(
        "--base-symbolic-tool",
        type=Path,
        default=Path("tools/t6_retail_special_shdr_symbolic_v1.py"),
    )
    ap.add_argument(
        "--operand-tool",
        type=Path,
        default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"),
    )
    ap.add_argument(
        "--opcode-tool",
        type=Path,
        default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"),
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(
        args.special_census,
        args.full_symbolic_tool,
        args.base_symbolic_tool,
        args.operand_tool,
        args.opcode_tool,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["pixelV2ZProducer"], indent=2, sort_keys=True))
    print(doc["dagSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
