#!/usr/bin/env python3
"""Anchor the exact reconstructed layered normal inside final-output lighting DAGs.

Consumes:
- full generated slot-4 final-output symbolic v3;
- exact CSO ISGN/OSGN sidecar v1;
- semantic directional-lightmap anchor v2.

For every shader whose generated TechniqueSet contains a secondary normal layer,
exactly one directional equation must use:

  raw.xyz = TEXCOORD1.xyz
          + layeredX * TEXCOORD3.xyz
          + layeredY * TEXCOORD2.xyz
  N.xyz   = raw.xyz * rsq(dot(raw.xyz, raw.xyz))

The same layeredX and layeredY DAG roots must be shared by all three raw-vector
components.  This is the universal retained layered-normal reconstruction proof
joined directly to the final-output directional dot; no physical meaning is
assigned to other directional equations in the shader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import t6_generated_final_output_directional_lightmap_anchor_v2 as directional
import t6_generated_final_output_io_signature_v1 as io_signature
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3
from t6_generated_world_shader_semantics_v1 import parse_generated_layer_tokens

FORMAT = "t6-generated-final-output-layered-normal-anchor-v1"
INPUT_RE = re.compile(r"^v(\d+)\.([xyzw])$")


class GeneratedFinalOutputLayeredNormalAnchorError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _node(nodes: list[dict], node_id: int) -> dict:
    if node_id < 0 or node_id >= len(nodes):
        raise GeneratedFinalOutputLayeredNormalAnchorError(f"invalid DAG node {node_id}")
    node = nodes[node_id]
    if int(node.get("id", node_id)) != node_id:
        raise GeneratedFinalOutputLayeredNormalAnchorError(
            f"non-dense node identity {node.get('id')!r} at {node_id}"
        )
    return node


def _flatten_add(nodes: list[dict], root: int) -> list[int]:
    node = _node(nodes, root)
    if node.get("kind") == "op" and node.get("op") == "add":
        args = [int(x) for x in node.get("args", [])]
        if len(args) == 2:
            return _flatten_add(nodes, args[0]) + _flatten_add(nodes, args[1])
    return [root]


def _input_semantic(nodes: list[dict], node_id: int, register_map: dict[int, str], semantic: str, lane: str) -> bool:
    node = _node(nodes, node_id)
    if node.get("kind") != "symbol":
        return False
    match = INPUT_RE.fullmatch(str(node.get("name") or ""))
    if not match or match.group(2) != lane:
        return False
    return register_map.get(int(match.group(1))) == semantic


def _mul_scalar_basis(nodes: list[dict], node_id: int, register_map: dict[int, str], semantic: str, lane: str) -> int | None:
    node = _node(nodes, node_id)
    if node.get("kind") != "op" or node.get("op") != "mul":
        return None
    args = [int(x) for x in node.get("args", [])]
    if len(args) != 2:
        return None
    for basis_pos in (0, 1):
        basis = args[basis_pos]
        if _input_semantic(nodes, basis, register_map, semantic, lane):
            return args[1 - basis_pos]
    return None


def _raw_component(nodes: list[dict], root: int, register_map: dict[int, str], lane: str) -> tuple[int, int] | None:
    terms = _flatten_add(nodes, root)
    if len(terms) != 3:
        return None
    base = [term for term in terms if _input_semantic(nodes, term, register_map, "TEXCOORD1", lane)]
    if len(base) != 1:
        return None
    x_terms = []
    y_terms = []
    for term in terms:
        if term == base[0]:
            continue
        x = _mul_scalar_basis(nodes, term, register_map, "TEXCOORD3", lane)
        y = _mul_scalar_basis(nodes, term, register_map, "TEXCOORD2", lane)
        if x is not None:
            x_terms.append(x)
        elif y is not None:
            y_terms.append(y)
        else:
            return None
    if len(x_terms) != 1 or len(y_terms) != 1:
        return None
    return x_terms[0], y_terms[0]


def _mul_pair(nodes: list[dict], node_id: int) -> tuple[int, int] | None:
    node = _node(nodes, node_id)
    if node.get("kind") != "op" or node.get("op") != "mul":
        return None
    args = [int(x) for x in node.get("args", [])]
    return (args[0], args[1]) if len(args) == 2 else None


def _normal_match(nodes: list[dict], normal_nodes: dict[str, int], register_map: dict[int, str]) -> dict | None:
    if set(normal_nodes) != set("xyz"):
        return None
    raw_nodes = {}
    rsq_nodes = set()
    for lane in "xyz":
        root = int(normal_nodes[lane])
        pair = _mul_pair(nodes, root)
        if pair is None:
            return None
        candidates = []
        for raw, inv in (pair, (pair[1], pair[0])):
            inv_node = _node(nodes, inv)
            if inv_node.get("kind") == "op" and inv_node.get("op") == "rsq":
                args = [int(x) for x in inv_node.get("args", [])]
                if len(args) == 1:
                    candidates.append((raw, inv, args[0]))
        if len(candidates) != 1:
            return None
        raw, rsq, dot = candidates[0]
        raw_nodes[lane] = raw
        rsq_nodes.add((rsq, dot))
    if len(rsq_nodes) != 1:
        return None
    rsq_node, dot_node = next(iter(rsq_nodes))

    layered_x = set(); layered_y = set()
    for lane in "xyz":
        result = _raw_component(nodes, raw_nodes[lane], register_map, lane)
        if result is None:
            return None
        layered_x.add(result[0]); layered_y.add(result[1])
    if len(layered_x) != 1 or len(layered_y) != 1:
        return None
    layered_x_node = next(iter(layered_x)); layered_y_node = next(iter(layered_y))

    dot_terms = _flatten_add(nodes, dot_node)
    if len(dot_terms) != 3:
        return None
    expected_squares = {raw_nodes[lane] for lane in "xyz"}
    observed_squares = set()
    for term in dot_terms:
        pair = _mul_pair(nodes, term)
        if pair is None or pair[0] != pair[1]:
            return None
        observed_squares.add(pair[0])
    if observed_squares != expected_squares:
        return None

    return {
        "normalNodes": {lane: int(normal_nodes[lane]) for lane in "xyz"},
        "rawNormalNodes": raw_nodes,
        "layeredNormalXNode": layered_x_node,
        "layeredNormalYNode": layered_y_node,
        "dotNode": dot_node,
        "rsqNode": rsq_node,
        "normalVectorSha256": _jhash({lane: int(normal_nodes[lane]) for lane in "xyz"}),
        "rawVectorNodeSha256": _jhash(raw_nodes),
        "basis": {
            "baseNormal": "TEXCOORD1.xyz",
            "layeredXBasis": "TEXCOORD3.xyz",
            "layeredYBasis": "TEXCOORD2.xyz",
        },
    }


def _layered_normal_target(technique_sets: list[str]) -> bool:
    values = set()
    for technique in technique_sets:
        tokens = parse_generated_layer_tokens(technique)
        values.add(any(token.has_normal for token in tokens))
    if len(values) > 1:
        raise GeneratedFinalOutputLayeredNormalAnchorError(
            f"TechniqueSets disagree on layered-normal target state: {technique_sets}"
        )
    return next(iter(values)) if values else False


def build(final_output: dict, io_doc: dict, directional_doc: dict, *, strict: bool = True) -> dict:
    if final_output.get("format") != symbolic_v3.FORMAT:
        raise GeneratedFinalOutputLayeredNormalAnchorError("unsupported final-output format")
    if io_doc.get("format") != io_signature.FORMAT:
        raise GeneratedFinalOutputLayeredNormalAnchorError("unsupported I/O-signature format")
    if directional_doc.get("format") != directional.FORMAT:
        raise GeneratedFinalOutputLayeredNormalAnchorError("unsupported directional-anchor format")

    shaders = {str(row["sha256"]): row for row in final_output.get("shaders", [])}
    io_rows = {str(row["sha256"]): row for row in io_doc.get("shaders", [])}
    dir_rows = {str(row["sha256"]): row for row in directional_doc.get("shaders", [])}
    if set(shaders) != set(io_rows) or set(shaders) != set(dir_rows):
        raise GeneratedFinalOutputLayeredNormalAnchorError("shader sets disagree across final-output/signature/directional inputs")

    rows = []
    target_count = anchored_target_count = matched_equations = 0
    missing = ambiguous = incidental = 0
    for sha in sorted(shaders):
        shader = shaders[sha]
        techniques = sorted(str(x) for x in shader.get("techniqueSets", []))
        target = _layered_normal_target(techniques)
        target_count += int(target)
        sig = io_rows[sha]["inputSignature"]
        register_map = {int(k): str(v) for k, v in sig.get("registerMap", {}).items()}
        required_semantics = {"TEXCOORD1", "TEXCOORD2", "TEXCOORD3"}
        if target and not required_semantics.issubset(set(register_map.values())):
            raise GeneratedFinalOutputLayeredNormalAnchorError(
                f"shader {sha}: layered-normal target lacks required ISGN semantics {sorted(required_semantics - set(register_map.values()))}"
            )
        matches = []
        for equation_index, equation in enumerate(dir_rows[sha].get("equations", [])):
            match = _normal_match(shader["nodes"], equation.get("normalNodes", {}), register_map)
            if match is not None:
                matches.append({"directionalEquationIndex": equation_index, **match})
        matched_equations += len(matches)
        if target:
            if len(matches) == 0: missing += 1
            elif len(matches) > 1: ambiguous += 1
            else: anchored_target_count += 1
            if strict and len(matches) != 1:
                raise GeneratedFinalOutputLayeredNormalAnchorError(
                    f"shader {sha}: layered-normal target has {len(matches)} matching directional equations, expected exactly 1"
                )
        elif matches:
            incidental += 1
        rows.append({
            "sha256": sha,
            "techniqueSets": techniques,
            "layeredNormalTarget": target,
            "matchCount": len(matches),
            "matches": matches,
            "anchored": target and len(matches) == 1,
        })

    return {
        "format": FORMAT,
        "sourceFinalOutputFormat": symbolic_v3.FORMAT,
        "sourceIoSignatureFormat": io_signature.FORMAT,
        "sourceDirectionalFormat": directional.FORMAT,
        "shaders": rows,
        "summary": {
            "shaderCount": len(rows),
            "layeredNormalTargetShaderCount": target_count,
            "anchoredLayeredNormalShaderCount": anchored_target_count,
            "matchedDirectionalEquationCount": matched_equations,
            "missingTargetShaderCount": missing,
            "ambiguousTargetShaderCount": ambiguous,
            "incidentalNonTargetMatchShaderCount": incidental,
            "strict": bool(strict),
            "rowsSha256": _jhash(rows),
        },
        "retainedProof": {
            "source": "manifests/render/T6_RETAIL_LAYERED_NORMAL_RECONSTRUCTION_V1.json",
            "retainedShaderCount": 107,
            "rawVectorConstructionFailureCount": 0,
            "normalizationFailureCount": 0,
            "signedSecondaryChannelDecodeFailureCount": 0,
            "basis": {
                "baseNormal": "TEXCOORD1.xyz",
                "layeredXBasis": "TEXCOORD3.xyz",
                "layeredYBasis": "TEXCOORD2.xyz",
            },
        },
        "proofBoundary": (
            "Exact ISGN-semantic structural join of the retained universal layered-normal reconstruction to one "
            "directional-lightmap N counterpart per generated TechniqueSet that declares a secondary normal layer. "
            "Requires shared layered X/Y roots, exact TEXCOORD1/3/2 basis, and raw*rsq(dot(raw,raw)) normalization. "
            "Other directional equations and non-layered-normal shader paths are not physically relabeled."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--io-signatures", type=Path, required=True)
    p.add_argument("--directional", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--relaxed", action="store_true")
    a = p.parse_args()
    result = build(
        json.loads(a.final_output.read_text(encoding="utf-8")),
        json.loads(a.io_signatures.read_text(encoding="utf-8")),
        json.loads(a.directional.read_text(encoding="utf-8")),
        strict=not a.relaxed,
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
