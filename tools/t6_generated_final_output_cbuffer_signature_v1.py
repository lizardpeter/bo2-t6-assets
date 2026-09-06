#!/usr/bin/env python3
"""Resolve generated final-output cbuffer symbols through exact DXBC RDEF metadata.

The full slot-4 symbolic DAG intentionally preserves constant-buffer reads as
opaque symbols such as ``cb1[59].x``.  This sidecar resolves every such symbol
against the exact OAT slot-4 CSO used by that shader:

    cb bind point/register/component
      -> byte offset
      -> exact RDEF cbuffer
      -> exact RDEF variable byte range
      -> relative scalar offset inside that variable.

For each TechniqueSet sharing the exact shader, the exact `.tech` assignment for
the reflected variable is also retained when present. The complete right-hand
expression is preserved verbatim; only its syntactic source prefix is classified
as `material`, `code`, or `other`.

Names are metadata identities only. This tool does not infer physical meaning
from names and does not recover material-specific literal values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from t6_dxbc_material_constant_binding_v1 import parse_rdef_constant_buffers
from t6_oat_slot_shader_resolver_v1 import resolve_slot_shader

FORMAT = "t6-generated-final-output-cbuffer-signature-v1"
FINAL_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
CB_RE = re.compile(r"^cb(\d+)\[(\d+)\]\.([xyzw])$")
ASSIGN_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+?)\s*;\s*(?://.*)?$"
)
COMPONENT_INDEX = {"x": 0, "y": 1, "z": 2, "w": 3}


class FinalOutputCbufferSignatureError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def parse_tech_assignments(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        match = ASSIGN_RE.match(line)
        if not match:
            continue
        lhs, rhs = match.groups()
        rhs = rhs.strip()
        old = out.get(lhs)
        if old is not None and old != rhs:
            raise FinalOutputCbufferSignatureError(
                f"Technique variable {lhs!r} has conflicting assignments {old!r}/{rhs!r}"
            )
        out[lhs] = rhs
    return out


def _source_identity(expression: str | None) -> dict:
    if expression is None:
        return {"sourceClass": "unassigned", "sourceExpression": None, "sourceName": None}
    expression = str(expression).strip()
    for prefix in ("material", "code"):
        token = prefix + "."
        if expression.startswith(token) and len(expression) > len(token):
            return {
                "sourceClass": prefix,
                "sourceExpression": expression,
                "sourceName": expression[len(token):],
            }
    return {
        "sourceClass": "other",
        "sourceExpression": expression,
        "sourceName": None,
    }


def _rdef_lookup(rdef: dict, bind_point: int, byte_offset: int) -> tuple[dict, dict]:
    buffers = [
        row for row in rdef.get("constantBuffers", [])
        if int(row.get("bindPoint", -1)) == bind_point
    ]
    if len(buffers) != 1:
        raise FinalOutputCbufferSignatureError(
            f"RDEF b{bind_point} buffer count {len(buffers)}, expected 1"
        )
    buffer = buffers[0]
    variables = [
        row for row in buffer.get("variables", [])
        if int(row.get("startOffset", -1)) <= byte_offset < int(row.get("endOffset", -1))
    ]
    if len(variables) != 1:
        raise FinalOutputCbufferSignatureError(
            f"RDEF {buffer.get('name')!r} byte {byte_offset} variable count {len(variables)}, expected 1"
        )
    return buffer, variables[0]


def map_symbol(symbol: str, rdef: dict, assignments_by_technique: dict[str, dict[str, str]]) -> dict:
    match = CB_RE.fullmatch(str(symbol))
    if not match:
        raise FinalOutputCbufferSignatureError(f"unsupported cbuffer symbol {symbol!r}")
    bind_point = int(match.group(1))
    register = int(match.group(2))
    component = match.group(3)
    component_index = COMPONENT_INDEX[component]
    byte_offset = register * 16 + component_index * 4
    buffer, variable = _rdef_lookup(rdef, bind_point, byte_offset)
    relative = byte_offset - int(variable["startOffset"])
    if relative < 0 or relative % 4:
        raise FinalOutputCbufferSignatureError(
            f"{symbol}: invalid scalar-relative byte offset {relative} in {variable.get('name')!r}"
        )

    assignments = []
    for technique, mapping in sorted(assignments_by_technique.items()):
        identity = _source_identity(mapping.get(str(variable["name"])))
        assignments.append({"techniqueSet": technique, **identity})

    return {
        "symbol": symbol,
        "bindPoint": bind_point,
        "register": register,
        "registerComponent": component,
        "registerComponentIndex": component_index,
        "byteOffset": byte_offset,
        "buffer": {
            "name": buffer.get("name"),
            "size": int(buffer.get("size", 0)),
            "type": buffer.get("type"),
            "flags": buffer.get("flags"),
        },
        "variable": {
            "name": variable.get("name"),
            "startOffset": int(variable.get("startOffset", 0)),
            "size": int(variable.get("size", 0)),
            "endOffset": int(variable.get("endOffset", 0)),
            "flags": variable.get("flags"),
            "typeOffset": variable.get("typeOffset"),
            "relativeByteOffset": relative,
            "relativeScalarIndex": relative // 4,
        },
        "techniqueAssignments": assignments,
    }


def _resolve_shader(oat_root: Path, shader_row: dict) -> tuple[bytes, dict, dict[str, dict[str, str]], list[dict]]:
    sha = str(shader_row.get("sha256") or "")
    techniques = sorted(set(str(x) for x in shader_row.get("techniqueSets", []) if str(x)))
    if not techniques:
        raise FinalOutputCbufferSignatureError(f"shader {sha}: no TechniqueSets")
    chosen_bytes = None
    chosen_rdef = None
    assignments = {}
    proof_rows = []
    for technique in techniques:
        resolved = resolve_slot_shader(Path(oat_root), technique, slot_index=4)
        shaders = resolved.get("pixelShaders", [])
        if len(shaders) != 1:
            raise FinalOutputCbufferSignatureError(
                f"{technique!r}: slot 4 shader count {len(shaders)}"
            )
        ps = shaders[0]
        if str(ps.get("sha256") or "") != sha:
            raise FinalOutputCbufferSignatureError(
                f"{technique!r}: OAT pixel shader {ps.get('sha256')!r} != final-output shader {sha!r}"
            )
        shader_path = Path(oat_root) / str(ps["relativeFile"])
        technique_path = Path(oat_root) / str(resolved["techniqueFile"])
        blob = shader_path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != sha:
            raise FinalOutputCbufferSignatureError(
                f"{technique!r}: shader file bytes changed after OAT resolution"
            )
        rdef = parse_rdef_constant_buffers(blob)
        if str(rdef.get("dxbcSha256") or "") != sha:
            raise FinalOutputCbufferSignatureError(
                f"{technique!r}: RDEF parser shader identity mismatch"
            )
        if chosen_bytes is None:
            chosen_bytes = blob
            chosen_rdef = rdef
        elif blob != chosen_bytes or rdef != chosen_rdef:
            raise FinalOutputCbufferSignatureError(
                f"shader {sha}: TechniqueSets resolve non-identical CSO/RDEF payloads"
            )
        text = technique_path.read_text(encoding="utf-8", errors="strict")
        assignments[technique] = parse_tech_assignments(text)
        proof_rows.append({
            "techniqueSet": technique,
            "techniqueAsset": resolved.get("techniqueAsset"),
            "techniqueFile": resolved.get("techniqueFile"),
            "pixelShaderAsset": ps.get("asset"),
            "pixelShaderFile": ps.get("relativeFile"),
            "pixelShaderSha256": sha,
        })
    assert chosen_bytes is not None and chosen_rdef is not None
    return chosen_bytes, chosen_rdef, assignments, proof_rows


def build(final_output: dict, oat_root: Path) -> dict:
    if final_output.get("format") != FINAL_FORMAT:
        raise FinalOutputCbufferSignatureError(
            f"unexpected final-output format {final_output.get('format')!r}"
        )
    rows = []
    source_classes = Counter()
    total_symbols = total_nodes = 0
    unique_variables = set()
    for shader in final_output.get("shaders", []):
        sha = str(shader.get("sha256") or "")
        _blob, rdef, assignments, proof = _resolve_shader(Path(oat_root), shader)
        symbols: dict[str, list[int]] = {}
        for node in shader.get("nodes", []):
            if node.get("kind") != "symbol":
                continue
            name = str(node.get("name") or "")
            if not CB_RE.fullmatch(name):
                continue
            symbols.setdefault(name, []).append(int(node["id"]))
        mapped = []
        for symbol in sorted(symbols):
            item = map_symbol(symbol, rdef, assignments)
            item["nodeIds"] = sorted(symbols[symbol])
            item["nodeCount"] = len(item["nodeIds"])
            mapped.append(item)
            total_symbols += 1
            total_nodes += item["nodeCount"]
            unique_variables.add((item["buffer"]["name"], item["variable"]["name"]))
            for assignment in item["techniqueAssignments"]:
                source_classes[assignment["sourceClass"]] += 1
        rows.append({
            "sha256": sha,
            "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
            "rdef": {
                "format": rdef.get("format"),
                "shaderModel": rdef.get("shaderModel"),
                "constantBufferCount": rdef.get("constantBufferCount"),
                "constantBuffers": rdef.get("constantBuffers"),
            },
            "oatProof": proof,
            "usedCbufferSymbolCount": len(mapped),
            "usedCbufferNodeCount": sum(item["nodeCount"] for item in mapped),
            "usedCbufferSymbols": mapped,
        })
    summary = {
        "shaderCount": len(rows),
        "usedCbufferSymbolCount": total_symbols,
        "usedCbufferNodeCount": total_nodes,
        "uniqueReflectedVariableCount": len(unique_variables),
        "techniqueAssignmentSourceClassCounts": dict(sorted(source_classes.items())),
    }
    return {
        "format": FORMAT,
        "shaders": rows,
        "summary": summary,
        "rowsSha256": _jhash(rows),
        "proofBoundary": (
            "Exact final-output cbN[R].component symbol -> byte offset -> RDEF cbuffer/variable byte range join "
            "on the same exact OAT slot-4 CSO SHA. Exact .tech right-hand assignments are retained when present. "
            "Names/source prefixes are identities only; no physical meaning or material-specific literal value is inferred."
        ),
    }


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--oat-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),a.oat_root);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
