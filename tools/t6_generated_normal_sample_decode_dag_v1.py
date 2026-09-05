#!/usr/bin/env python3
"""Extract exact T6 generated normal-map sample -> decoded XY DAGs.

The layered-normal proofs already identify the exact decoded/current X/Y roots
for every normal-bearing generated layer.  This module isolates the sample-only
subtree that feeds those roots and serializes it before any per-vertex 2x2
normalTransform is applied.

No ``2*RG-1`` assumption is encoded here.  The exact compiled arithmetic is
retained as a forensic DAG.  Extraction requires:

* exactly one normalMapSamplerN resource for the layer;
* X decode ancestry reaching only sampler channel x, Y only channel y;
* the selected decode subtree to have no vertex-input or cbuffer dependency;
* for matrix2x2 layers, the matrix-dot itself is excluded by its input deps and
  the maximal sample-only ancestor is selected uniquely.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from t6_generated_height_weight_dag_v1 import _forensic_subgraph, validate_forensic_dag


FORMAT = "t6-generated-normal-sample-decode-dag-v1"
SET_FORMAT = "t6-generated-normal-sample-decode-dag-set-v1"


class GeneratedNormalDecodeDagError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _load_default_modules():
    import t6_retail_layered_lmap_compositor_v1 as comp
    import t6_retail_layered_normal_reconstruction_v1 as normal
    import t6_retail_special_shdr_opcode_census_v1 as opcode
    import t6_retail_special_shdr_operand_census_v1 as operand
    import t6_dxbc_inspect_v1 as inspect
    return comp, normal, opcode, operand, inspect


def _descendants(d, root: int) -> set[int]:
    out: set[int] = set()
    def visit(node_id: int) -> None:
        if node_id in out:
            return
        if not 0 <= node_id < len(d.n):
            raise GeneratedNormalDecodeDagError(f"DAG node {node_id} outside table")
        out.add(node_id)
        for child in d.n[node_id].get("args", []):
            if not isinstance(child, int):
                raise GeneratedNormalDecodeDagError(
                    f"DAG node {node_id} has non-integer child {child!r}"
                )
            visit(child)
    visit(int(root))
    return out


def _leaf_inventory(dag: dict) -> dict[str, list]:
    inventory = {"sample": [], "input": [], "cb": [], "lit": []}
    for node in dag.get("nodes", []):
        kind = str(node.get("kind") or "")
        if kind == "sample":
            inventory["sample"].append({
                "resource": node.get("resource"),
                "channel": node.get("channel"),
                "sampler": node.get("sampler"),
            })
        elif kind in ("input", "cb"):
            inventory[kind].append(str(node.get("name") or ""))
        elif kind == "lit":
            inventory["lit"].append(node.get("value"))
    for key in inventory:
        inventory[key] = sorted(
            inventory[key],
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
        )
    return inventory


def _maximal_decode_candidate(comp, normal, d, current_root: int, resource: str, channel: str) -> int:
    reachable = _descendants(d, current_root)
    candidates: list[int] = []
    for node_id in sorted(reachable):
        if comp.value_resources(d, node_id) != {resource}:
            continue
        if comp.input_deps(d, node_id):
            continue
        channels = normal.sample_channels(comp, d, node_id, resource)
        if channels != {channel}:
            continue
        candidates.append(node_id)
    if not candidates:
        raise GeneratedNormalDecodeDagError(
            f"normal decode root {current_root}: no sample-only {resource}.{channel} candidate"
        )

    descendants = {candidate: _descendants(d, candidate) for candidate in candidates}
    maximal = [
        candidate for candidate in candidates
        if not any(
            candidate != other and candidate in descendants[other]
            for other in candidates
        )
    ]
    if len(maximal) != 1:
        raise GeneratedNormalDecodeDagError(
            f"normal decode root {current_root}: maximal {resource}.{channel} candidates {maximal}"
        )
    return maximal[0]


def _normal_weight_roots(comp, d, technique_set: str) -> list[int]:
    candidates = comp.sequence(d, comp.mode_sig(technique_set), "x")
    if not candidates:
        raise GeneratedNormalDecodeDagError(
            f"{technique_set!r}: no exact RGB compositor sequence"
        )
    return list(min(candidates, key=lambda item: item[0])[1])


def extract_normal_decode_dags(
    shader_bytes: bytes,
    technique_set: str,
    *,
    modules=None,
) -> dict:
    if not shader_bytes or shader_bytes[:4] != b"DXBC":
        raise GeneratedNormalDecodeDagError("normal decode extraction requires DXBC bytes")
    comp, normal, opcode, operand, inspect = modules or _load_default_modules()
    d = comp.symbolic(shader_bytes, opcode, operand, inspect)
    weights = _normal_weight_roots(comp, d, technique_set)

    rows = []
    for layer, operation, flags in comp.specs(technique_set):
        if "n" not in flags:
            continue
        layer = int(layer)
        if layer <= 0 or layer - 1 >= len(weights):
            raise GeneratedNormalDecodeDagError(
                f"{technique_set!r}: normal layer {layer} has no aligned RGB weight root"
            )
        resource = f"normalMapSampler{layer}"
        current = normal.current_pair(comp, d, layer, weights[layer - 1])
        if not isinstance(current, list) or len(current) != 2:
            raise GeneratedNormalDecodeDagError(
                f"{technique_set!r} layer {layer}: current normal pair is not XY"
            )
        kinds = {str(d.n[int(node)]["kind"]) for node in current}
        if kinds == {"dot"}:
            transform_mode = "transform2x2"
        elif kinds == {"add"}:
            transform_mode = "direct"
        else:
            raise GeneratedNormalDecodeDagError(
                f"{technique_set!r} layer {layer}: unsupported current normal pair kinds {sorted(kinds)}"
            )

        components = []
        for component_index, channel in enumerate(("x", "y")):
            current_root = int(current[component_index])
            decode_root = _maximal_decode_candidate(
                comp, normal, d, current_root, resource, channel
            )
            dag = _forensic_subgraph(d, decode_root)
            validate_forensic_dag(dag)
            leaves = _leaf_inventory(dag)
            if leaves["input"] or leaves["cb"]:
                raise GeneratedNormalDecodeDagError(
                    f"{technique_set!r} layer {layer} {channel}: decoded normal subtree unexpectedly "
                    f"depends on inputs={leaves['input']} cb={leaves['cb']}"
                )
            samples = {
                (str(item["resource"]), str(item["channel"]))
                for item in leaves["sample"]
            }
            if samples != {(resource, channel)}:
                raise GeneratedNormalDecodeDagError(
                    f"{technique_set!r} layer {layer} {channel}: sample leaves {sorted(samples)} != "
                    f"{[(resource, channel)]}"
                )
            components.append({
                "component": channel,
                "currentNormalRoot": current_root,
                "decodeRoot": decode_root,
                "forensicDag": dag,
                "forensicDagSha256": dag["forensicDagSha256"],
                "leafInventory": leaves,
            })

        rows.append({
            "layerIndex": layer,
            "operation": operation,
            "flags": sorted(str(flag) for flag in flags),
            "normalResource": resource,
            "sampleChannels": ["x", "y"],
            "transformMode": transform_mode,
            "components": components,
            "decodePairSha256": _jhash([
                component["forensicDagSha256"] for component in components
            ]),
        })

    result = {
        "format": SET_FORMAT,
        "techniqueSet": technique_set,
        "pixelShaderSha256": hashlib.sha256(shader_bytes).hexdigest(),
        "normalLayerCount": len(rows),
        "layers": rows,
        "decodePairSetSha256": _jhash([row["decodePairSha256"] for row in rows]),
        "allDecodeLeavesSampleOnly": True,
        "proof": (
            "exact slot-4 current normal XY roots; maximal sample-only normalMapSamplerN.x/y subtrees "
            "serialized before any matrix2x2 vertex-input transform; no hard-coded RG decode equation"
        ),
    }
    return result


def evaluate_decode_component(dag: dict, sample_value: float) -> float:
    """Small reference evaluator for sample/literal arithmetic decode DAGs.

    This intentionally supports the scalar arithmetic forms expected in decode
    subgraphs and rejects vertex/cbuffer/dot dependencies.
    """
    validate_forensic_dag(dag)
    values: list[float] = []
    for node in dag["nodes"]:
        kind = str(node["kind"])
        args = [values[int(index)] for index in node.get("args", [])]
        if kind == "sample":
            value = float(sample_value)
        elif kind == "lit":
            value = float(node["value"])
        elif kind == "add" and len(args) == 2:
            value = args[0] + args[1]
        elif kind == "mul" and len(args) == 2:
            value = args[0] * args[1]
        elif kind == "div" and len(args) == 2:
            value = args[0] / args[1]
        elif kind == "neg" and len(args) == 1:
            value = -args[0]
        elif kind in ("sat", "saturate") and len(args) == 1:
            value = min(1.0, max(0.0, args[0]))
        elif kind == "min" and len(args) == 2:
            value = min(args)
        elif kind == "max" and len(args) == 2:
            value = max(args)
        else:
            raise GeneratedNormalDecodeDagError(
                f"unsupported normal decode DAG node {kind!r} with {len(args)} args"
            )
        values.append(float(value))
    return values[int(dag["root"])]
