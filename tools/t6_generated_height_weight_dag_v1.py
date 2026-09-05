#!/usr/bin/env python3
"""Extract and execute exact T6 generated-material vN scalar weight DAGs.

The retained layered compositor already source-closes vN as a shader-specific
straight-line SM4 scalar DAG.  This module turns the proven symbolic graph into
a renderer-neutral, forensic subgraph that preserves operation and argument
order.  It deliberately does NOT replace vN with a universal height formula.

The extraction path reuses the same direct-DXBC symbolic engine used by
`t6_retail_layered_lmap_compositor_v1.py` and its cross-pass proof.  The emitted
DAG can be attached to a canonical generated shader recipe and consumed by
Blender/Tour without re-disassembling the shader.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


FORMAT = "t6-generated-height-weight-dag-v1"


class GeneratedHeightDagError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _semantic_canon(d, node_id: int, memo: dict[int, dict] | None = None) -> dict:
    """Match the retained cross-pass semantic hash canonicalization exactly."""
    if memo is None:
        memo = {}
    if node_id in memo:
        return memo[node_id]
    node = d.n[node_id]
    kind = node["kind"]
    if kind == "sample":
        result = {
            "kind": "sample",
            "resource": node["resource"],
            "channel": node["channel"],
            "sampler": node["sampler"],
        }
    elif kind in ("input", "cb", "lit"):
        result = {
            "kind": kind,
            **{key: node[key] for key in ("name", "value") if key in node},
        }
    else:
        args = [_semantic_canon(d, int(child), memo) for child in node.get("args", [])]
        if kind == "mul":
            flat: list[dict] = []

            def flatten(item: dict) -> None:
                if isinstance(item, dict) and item.get("kind") == "mul":
                    for child in item["args"]:
                        flatten(child)
                else:
                    flat.append(item)

            for arg in args:
                flatten(arg)
            args = sorted(flat, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        elif kind in ("add", "min", "max"):
            args = sorted(args, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        result = {"kind": kind, "args": args}
    memo[node_id] = result
    return result


def _forensic_subgraph(d, root: int) -> dict:
    nodes = d.n
    if not isinstance(root, int) or not 0 <= root < len(nodes):
        raise GeneratedHeightDagError(f"invalid symbolic root {root}")
    seen: set[int] = set()
    order: list[int] = []

    def visit(node_id: int) -> None:
        if node_id in seen:
            return
        if not 0 <= node_id < len(nodes):
            raise GeneratedHeightDagError(f"DAG child {node_id} is outside symbolic node table")
        seen.add(node_id)
        node = nodes[node_id]
        for child in node.get("args", []):
            if not isinstance(child, int):
                raise GeneratedHeightDagError(
                    f"symbolic node {node_id} has non-integer child {child!r}"
                )
            visit(child)
        order.append(node_id)

    visit(root)
    remap = {old: new for new, old in enumerate(order)}
    out: list[dict] = []
    for old in order:
        raw = dict(nodes[old])
        raw.pop("id", None)
        if "args" in raw:
            raw["args"] = [remap[int(child)] for child in raw["args"]]
        raw["id"] = remap[old]
        out.append(raw)
    document = {
        "format": FORMAT,
        "root": remap[root],
        "nodes": out,
        "nodeCount": len(out),
        "ordering": "reachable child-before-parent; operation argument order preserved",
    }
    document["forensicDagSha256"] = _jhash({
        "format": FORMAT,
        "root": document["root"],
        "nodes": document["nodes"],
    })
    return document


def _load_default_modules():
    # Import lazily because the compositor proof is a compressed forensic module
    # and ordinary recipe consumers should not pay its import cost.
    import t6_retail_layered_lmap_compositor_v1 as compositor
    import t6_retail_special_shdr_opcode_census_v1 as opcode
    import t6_retail_special_shdr_operand_census_v1 as operand
    import t6_dxbc_inspect_v1 as inspect
    return compositor, opcode, operand, inspect


def extract_height_weight_dags(
    shader_bytes: bytes,
    technique_set: str,
    *,
    modules=None,
) -> dict:
    """Extract every vN height scalar from one exact slot-4 pixel shader."""
    if not shader_bytes or shader_bytes[:4] != b"DXBC":
        raise GeneratedHeightDagError("height DAG extraction requires a nonempty DXBC shader")
    compositor, opcode, operand, inspect = modules or _load_default_modules()
    d = compositor.symbolic(shader_bytes, opcode, operand, inspect)
    mode = compositor.mode_sig(technique_set)
    specs = compositor.specs(technique_set)
    solutions = []
    for channel in "xyz":
        candidates = compositor.sequence(d, mode, channel)
        if not candidates:
            raise GeneratedHeightDagError(
                f"{technique_set!r}: no exact RGB compositor recurrence for {channel}"
            )
        solutions.append(min(candidates, key=lambda item: item[0]))

    layers: list[dict] = []
    for step_index, (layer, operation, flags) in enumerate(specs):
        predicted = compositor.predict(operation, flags)
        roots = [int(solution[1][step_index]) for solution in solutions]
        semantic = [_semantic_canon(d, root) for root in roots]
        semantic_hashes = [_jhash(item) for item in semantic]
        if len(set(semantic_hashes)) != 1:
            raise GeneratedHeightDagError(
                f"{technique_set!r} layer {layer}: RGB scalar weight DAGs disagree"
            )
        actual = compositor.wclass(operation, flags, d, roots[0])
        if actual != predicted:
            raise GeneratedHeightDagError(
                f"{technique_set!r} layer {layer}: symbolic weight class {actual!r} "
                f"!= TechniqueSet-predicted {predicted!r}"
            )
        if predicted != "height":
            continue
        dag = _forensic_subgraph(d, roots[0])
        layers.append({
            "layerIndex": int(layer),
            "operation": str(operation),
            "flags": sorted(str(flag) for flag in flags),
            "weightClass": "height",
            "semanticWeightDagSha256": semantic_hashes[0],
            "forensicDag": dag,
        })

    result = {
        "format": "t6-generated-height-weight-dag-set-v1",
        "techniqueSet": technique_set,
        "pixelShaderSha256": hashlib.sha256(shader_bytes).hexdigest(),
        "layers": layers,
        "heightLayerCount": len(layers),
        "heightSemanticDagSetSha256": _jhash(
            [row["semanticWeightDagSha256"] for row in layers]
        ),
        "proof": (
            "Direct slot-4 retained-DXBC symbolic recurrence; forensic subgraph preserves "
            "operator/argument order and exact sample/input/constant leaves"
        ),
    }
    return result


def validate_forensic_dag(dag: dict) -> dict:
    if dag.get("format") != FORMAT:
        raise GeneratedHeightDagError(f"unsupported height DAG format {dag.get('format')!r}")
    nodes = dag.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise GeneratedHeightDagError("height DAG has no nodes")
    if int(dag.get("nodeCount", -1)) != len(nodes):
        raise GeneratedHeightDagError("height DAG nodeCount mismatch")
    root = int(dag.get("root", -1))
    if not 0 <= root < len(nodes):
        raise GeneratedHeightDagError("height DAG root out of range")
    for i, node in enumerate(nodes):
        if not isinstance(node, dict) or int(node.get("id", -1)) != i:
            raise GeneratedHeightDagError(f"height DAG node {i} has non-canonical id")
        for child in node.get("args", []):
            child = int(child)
            if not 0 <= child < i:
                raise GeneratedHeightDagError(
                    f"height DAG node {i} child {child} is not child-before-parent"
                )
    expected = _jhash({"format": FORMAT, "root": root, "nodes": nodes})
    if dag.get("forensicDagSha256") != expected:
        raise GeneratedHeightDagError("height DAG forensic SHA mismatch")
    return dag


def _leaf_value(node: dict, *, inputs: dict, constants: dict, samples: dict) -> float:
    kind = node["kind"]
    if kind == "input":
        name = str(node.get("name") or "")
        if name not in inputs:
            raise GeneratedHeightDagError(f"missing height DAG input {name!r}")
        return float(inputs[name])
    if kind == "cb":
        name = str(node.get("name") or "")
        if name not in constants:
            raise GeneratedHeightDagError(f"missing height DAG constant {name!r}")
        return float(constants[name])
    if kind == "lit":
        try:
            return float(node["value"])
        except Exception as exc:
            raise GeneratedHeightDagError(f"invalid height DAG literal {node.get('value')!r}") from exc
    if kind == "sample":
        resource = str(node.get("resource") or "")
        channel = str(node.get("channel") or "")
        value = samples.get(resource)
        if value is None:
            raise GeneratedHeightDagError(f"missing height DAG sample resource {resource!r}")
        if isinstance(value, dict):
            if channel not in value:
                raise GeneratedHeightDagError(
                    f"sample resource {resource!r} lacks channel {channel!r}"
                )
            return float(value[channel])
        sequence = list(value)
        index = "xyzw".find(channel)
        if index < 0 or index >= len(sequence):
            raise GeneratedHeightDagError(
                f"sample resource {resource!r} lacks channel {channel!r}"
            )
        return float(sequence[index])
    raise GeneratedHeightDagError(f"node kind {kind!r} is not a scalar leaf")


def evaluate_forensic_dag(
    dag: dict,
    *,
    inputs: dict[str, float],
    constants: dict[str, float],
    samples: dict[str, Any],
) -> float:
    """Reference scalar evaluator using SM4 exp2/log2 semantics."""
    validate_forensic_dag(dag)
    values: list[float] = []
    for node in dag["nodes"]:
        kind = node["kind"]
        args = [values[int(i)] for i in node.get("args", [])]
        if kind in ("input", "cb", "lit", "sample"):
            value = _leaf_value(node, inputs=inputs, constants=constants, samples=samples)
        elif kind == "add" and len(args) == 2:
            value = args[0] + args[1]
        elif kind == "mul" and len(args) == 2:
            value = args[0] * args[1]
        elif kind == "div" and len(args) == 2:
            value = args[0] / args[1]
        elif kind == "min" and len(args) == 2:
            value = min(args)
        elif kind == "max" and len(args) == 2:
            value = max(args)
        elif kind == "neg" and len(args) == 1:
            value = -args[0]
        elif kind in ("sat", "saturate") and len(args) == 1:
            value = min(1.0, max(0.0, args[0]))
        elif kind == "abs" and len(args) == 1:
            value = abs(args[0])
        elif kind == "exp" and len(args) == 1:
            value = 2.0 ** args[0]
        elif kind == "log" and len(args) == 1:
            value = math.log2(args[0])
        elif kind == "rcp" and len(args) == 1:
            value = 1.0 / args[0]
        elif kind == "sqrt" and len(args) == 1:
            value = math.sqrt(args[0])
        elif kind == "rsq" and len(args) == 1:
            value = 1.0 / math.sqrt(args[0])
        elif kind == "frc" and len(args) == 1:
            value = args[0] - math.floor(args[0])
        elif kind == "lt" and len(args) == 2:
            value = 1.0 if args[0] < args[1] else 0.0
        elif kind == "ge" and len(args) == 2:
            value = 1.0 if args[0] >= args[1] else 0.0
        elif kind == "eq" and len(args) == 2:
            value = 1.0 if args[0] == args[1] else 0.0
        elif kind == "ne" and len(args) == 2:
            value = 1.0 if args[0] != args[1] else 0.0
        elif kind == "select" and len(args) == 3:
            value = args[1] if args[0] != 0.0 else args[2]
        else:
            raise GeneratedHeightDagError(
                f"unsupported exact height DAG node {kind!r} with {len(args)} args"
            )
        values.append(float(value))
    return values[int(dag["root"])]
