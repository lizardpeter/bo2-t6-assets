#!/usr/bin/env python3
"""Read exact retained MaterialShaderArgument rows for Nuketown multiply decals.

This proof walks the SHA-pinned expanded mp_nuketown_2020 FastFile directly. It
selects the exact wpc_unlitdecalblend_multiply_35079164 TechniqueSet and its
physically inline unlit slot-2 pass. The emissive slot-3 Technique is retained as
its exact packed pointer provenance and is not deserialized by resemblance.

Shader byte identity remains a separate already-green OAT/VS proof. This file
proves the retail map ownership and exact serialized unlit MaterialShaderArgument
rows without inventing packed-pointer aliases or runtime constant values.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-multiply-decal-retail-args-v1"
MAP = "mp_nuketown_2020"
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
WORLD_START = 63_150_420
TECH_Q0 = 565
TECH_Q1 = 623
TECHNIQUE_SET = "wpc_unlitdecalblend_multiply_35079164"
UNLIT_SLOT = 2
EMISSIVE_SLOT = 3
PINNED_VS_SHA256 = "c3bd9eb7d12a444c63867be2e466ac00c495a5a7f64a8b2c9f73e2558a5e12e0"
PINNED_PS_SHA256 = "e9820077a4df69228fd1626997270d7b31337f82eab6c26c1a14a33257424a0b"
CODE_VERTEX_CONST = 3


class ProofError(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def parse_arg_rows(data: bytes, start: int, count: int, blocks, prod):
    if start + 12 * count > len(data):
        raise ProofError("MaterialShaderArgument table exceeds expanded FastFile")
    rows = []
    literals = []
    for i in range(count):
        typ, loc, size, buf, raw = struct.unpack_from("<HHHHI", data, start + i * 12)
        if typ >= 8:
            raise ProofError(f"argument {i} has invalid type {typ}")
        code_index = raw & 0xFFFF if typ in (3, 5) else None
        first_row = (raw >> 16) & 0xFF if typ in (3, 5) else None
        row_count = (raw >> 24) & 0xFF if typ in (3, 5) else None
        rows.append(
            {
                "index": i,
                "type": typ,
                "locationOffset": loc,
                "size": size,
                "buffer": buf,
                "rawValue": raw,
                "rawValueHex": f"0x{raw:08X}",
                "codeIndex": code_index,
                "codeIndexHex": f"0x{code_index:02X}" if code_index is not None else None,
                "firstRow": first_row,
                "rowCount": row_count,
            }
        )
        literals.append((typ, raw))
    cursor = start + 12 * count
    for typ, raw in literals:
        if typ not in (1, 7):
            continue
        kind = prod.ff_dec(raw, blocks)[0]
        if kind in ("following", "insert"):
            cursor += 16
            if cursor > len(data):
                raise ProofError("inline literal exceeds expanded FastFile")
        elif kind not in ("packed", "null"):
            raise ProofError(f"invalid literal pointer kind {kind}")
    return cursor, rows


def shader_reference(pass_row: dict[str, Any], stage: str, expected_sha: str) -> dict[str, Any]:
    child = pass_row["children"][stage]
    kind = str(child.get("kind"))
    if kind not in ("following", "insert", "packed"):
        raise ProofError(f"selected {stage} has unsupported pointer kind {kind!r}")
    out = {
        "pointerRaw": child.get("raw"),
        "pointerKind": kind,
        "block": child.get("block"),
        "offset": child.get("offset"),
    }
    inline = child.get("inline")
    if inline is not None:
        program = inline.get("program") or {}
        if not program.get("direct"):
            raise ProofError(f"selected inline {stage} is not a direct program")
        got = str(program.get("sha256") or "")
        if got != expected_sha:
            raise ProofError(f"selected inline {stage} SHA {got} != pinned {expected_sha}")
        out["inline"] = {
            "name": inline.get("name"),
            "sha256": got,
            "sourceStart": program.get("start"),
            "byteCount": program.get("bytes"),
        }
    return out


def plain_pointer(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": int(ref["slot"]),
        "pointerRaw": ref.get("raw"),
        "pointerKind": ref.get("kind"),
        "block": ref.get("block"),
        "offset": ref.get("offset"),
    }


def build(expanded: Path, producer: Path) -> dict[str, Any]:
    data = expanded.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != EXPANDED_SHA256:
        raise ProofError(f"expanded source SHA {got} != pinned {EXPANDED_SHA256}")

    prod = load_module(producer, "t6_multiply_decal_retail_prod")
    blocks = prod.ff_front(data)
    candidates = prod.ff_scan_tech(data, blocks, WORLD_START)
    required = TECH_Q1 - TECH_Q0 + 1
    if len(candidates) < required:
        raise ProofError(f"TechniqueSet candidate count {len(candidates)} < required {required}")
    retained = candidates[-required:]
    hits = [(i, row) for i, row in enumerate(retained) if row["name"] == TECHNIQUE_SET]
    if len(hits) != 1:
        raise ProofError(f"TechniqueSet {TECHNIQUE_SET!r} occurrence count {len(hits)}")
    ordinal, row = hits[0]
    next_start = retained[ordinal + 1]["fixedStart"] if ordinal + 1 < len(retained) else WORLD_START

    groups: list[list[dict[str, Any]]] = []
    original = prod.ff_parse_args
    try:
        def capture(dd, p, n, bb):
            q, args = parse_arg_rows(dd, p, n, bb, prod)
            groups.append(args)
            return q
        prod.ff_parse_args = capture
        technique_set = prod.ff_parse_techset(data, row, next_start, blocks)
    finally:
        prod.ff_parse_args = original

    argument_groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    gi = 0
    for ref in technique_set["techniqueRefs"]:
        inline = ref.get("inlineTechnique")
        if not inline:
            continue
        slot = int(ref["slot"])
        for pass_row in inline["passes"]:
            child = pass_row["children"]["args"]
            if child["kind"] in ("following", "insert"):
                if gi >= len(groups):
                    raise ProofError("captured argument table underflow")
                argument_groups[(slot, int(pass_row["passIndex"]))] = groups[gi]
                gi += 1
            elif int(pass_row["argCount"]) != 0:
                raise ProofError(
                    f"slot {slot} pass {pass_row['passIndex']} has non-direct nonzero argument table"
                )
    if gi != len(groups):
        raise ProofError(f"captured argument table overflow: consumed {gi} / {len(groups)}")

    unlit_refs = [r for r in technique_set["techniqueRefs"] if int(r["slot"]) == UNLIT_SLOT]
    if len(unlit_refs) != 1 or not unlit_refs[0].get("inlineTechnique"):
        raise ProofError("unlit slot 2 is not one exact inline Technique")
    unlit_technique = unlit_refs[0]["inlineTechnique"]
    if len(unlit_technique["passes"]) != 1:
        raise ProofError(f"unlit slot has {len(unlit_technique['passes'])} passes, expected one")
    pass_row = unlit_technique["passes"][0]
    args = argument_groups.get((UNLIT_SLOT, int(pass_row["passIndex"])))
    if args is None:
        raise ProofError("unlit exact pass has no direct captured argument table")
    if len(args) != int(pass_row["argCount"]):
        raise ProofError(f"unlit argument count mismatch {len(args)} != {pass_row['argCount']}")
    code_vs = [a for a in args if a["type"] == CODE_VERTEX_CONST]
    if not code_vs:
        raise ProofError("selected exact unlit pass has no code vertex constants")

    emissive_refs = [r for r in technique_set["techniqueRefs"] if int(r["slot"]) == EMISSIVE_SLOT]
    if len(emissive_refs) != 1:
        raise ProofError(f"emissive slot 3 occurrence count {len(emissive_refs)}")
    if emissive_refs[0].get("kind") != "packed" or emissive_refs[0].get("inlineTechnique") is not None:
        raise ProofError("emissive slot 3 is not the exact packed Technique reference observed in retail Nuketown")

    unlit = {
        "slot": UNLIT_SLOT,
        "technique": unlit_technique.get("name"),
        "passIndex": int(pass_row["passIndex"]),
        "argCount": int(pass_row["argCount"]),
        "vertexShaderReference": shader_reference(pass_row, "vertexShader", PINNED_VS_SHA256),
        "pixelShaderReference": shader_reference(pass_row, "pixelShader", PINNED_PS_SHA256),
        "arguments": args,
        "codeVertexConstants": code_vs,
    }

    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_multiply_decal_retail_args_v1.py",
        "map": MAP,
        "source": {
            "file": str(expanded),
            "sha256": EXPANDED_SHA256,
            "bytes": len(data),
        },
        "techniqueSet": TECHNIQUE_SET,
        "techniqueSetXassetIndex": TECH_Q0 + ordinal,
        "worldVertFormat": technique_set["worldVertFormat"],
        "separateShaderIdentityProof": {
            "vertexShaderSha256": PINNED_VS_SHA256,
            "pixelShaderSha256": PINNED_PS_SHA256,
            "note": "Exact shader bytes/DAG are pinned by the separate OAT/VS symbolic proof; packed map references are not aliased to bytes here.",
        },
        "unlit": unlit,
        "emissiveTechniqueReference": plain_pointer(emissive_refs[0]),
        "summary": {
            "argumentCount": len(args),
            "codeVertexConstantCount": len(code_vs),
            "codeVertexConstantIndices": [a["codeIndex"] for a in code_vs],
            "codeVertexConstantRowsSha256": digest(code_vs),
            "allArgumentRowsSha256": digest(args),
            "unlitVertexShaderPointerKind": unlit["vertexShaderReference"]["pointerKind"],
            "unlitPixelShaderPointerKind": unlit["pixelShaderReference"]["pointerKind"],
            "emissiveTechniquePointerKind": emissive_refs[0]["kind"],
        },
        "proofBoundary": (
            "Direct retained-byte proof from the SHA-pinned expanded mp_nuketown_2020 FastFile. "
            "The exact multiply-decal TechniqueSet is selected by serialized name. Slot 2 must contain one physically inline unlit Technique/pass and its MaterialShaderArgument rows are decoded directly from 12-byte retail records. Slot 3 is required to remain the exact packed emissive Technique reference and is not deserialized by resemblance. Inline shader payloads are SHA-checked when physically present; packed shader references remain opaque and shader-byte identity is supplied only by the separate already-pinned OAT/VS proof. Type 3 is the serialized code-vertex-constant class and its codeIndex/firstRow/rowCount fields are reported exactly. No semantic runtime value is inferred here."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument(
        "--producer",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord5_producer_v1.py"),
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = build(a.expanded, a.producer)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print("CODE VERTEX CONSTANT ROWS")
    for row in result["unlit"]["codeVertexConstants"]:
        print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
