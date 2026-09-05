#!/usr/bin/env python3
"""Renderer-neutral bindings for exact T6 generated vN DAG leaves.

The symbolic DAG preserves raw shader leaves.  This module binds the nonconstant
leaves to the already source-closed portable map representation without asking a
renderer to infer semantics from names:

* each solved height step's unique raw vertex input -> that step's normalized
  `_T6_LAYER_WEIGHTS` component (L1=G, L2=B, L3=A);
* each exact sample resource in that solved step -> its exact OAT `.tech`
  `material.*` assignment and the step's exact generated layer `colorMap` role.

Material cbuffer leaves are bound separately, per Material, by
`t6_dxbc_material_constant_binding_v1.py`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from t6_dxbc_material_constant_binding_v1 import parse_material_assignments


FORMAT = "t6-generated-height-leaf-bindings-v1"
LAYER_COMPONENT = {1: "G", 2: "B", 3: "A"}


class GeneratedHeightLeafBindingError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _unique_nodes(dag: dict, kind: str, keys: tuple[str, ...]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for node in dag.get("nodes", []):
        if node.get("kind") != kind:
            continue
        signature = tuple(node.get(key) for key in keys)
        if any(value is None or value == "" for value in signature):
            raise GeneratedHeightLeafBindingError(
                f"{kind} DAG leaf is missing one of {keys}: {node!r}"
            )
        seen.setdefault(signature, {key: node.get(key) for key in keys})
    return [seen[key] for key in sorted(seen, key=lambda item: tuple(map(str, item)))]


def build_height_leaf_bindings(height_payload: dict, *, technique_text: str) -> dict:
    layers = height_payload.get("layers")
    if not isinstance(layers, list):
        raise GeneratedHeightLeafBindingError("height payload has no layers")
    assignments = parse_material_assignments(technique_text)
    out: list[dict] = []

    for height_layer in layers:
        layer = int(height_layer.get("layerIndex", -1))
        component = LAYER_COMPONENT.get(layer)
        if component is None:
            raise GeneratedHeightLeafBindingError(
                f"height layer {layer} has no normalized generated-layer component"
            )
        dag = height_layer.get("forensicDag")
        if not isinstance(dag, dict):
            raise GeneratedHeightLeafBindingError(f"height layer {layer} has no forensic DAG")

        inputs = _unique_nodes(dag, "input", ("name",))
        if len(inputs) != 1:
            raise GeneratedHeightLeafBindingError(
                f"height layer {layer} has {len(inputs)} unique raw vertex inputs; "
                "current exact normalized-layer binding requires exactly one"
            )
        raw_input = str(inputs[0]["name"])

        samples = _unique_nodes(dag, "sample", ("resource", "channel", "sampler"))
        if not samples:
            raise GeneratedHeightLeafBindingError(
                f"height layer {layer} has no exact layer-alpha sample dependency"
            )
        resources = sorted({str(item["resource"]) for item in samples})
        if len(resources) != 1:
            raise GeneratedHeightLeafBindingError(
                f"height layer {layer} samples {resources}; exact one-layer color binding is ambiguous"
            )
        if {str(item["channel"]) for item in samples} != {"w"}:
            raise GeneratedHeightLeafBindingError(
                f"height layer {layer} sample channels are not alpha-only: "
                f"{sorted({str(item['channel']) for item in samples})}"
            )
        resource = resources[0]
        material_argument = assignments.get(resource)
        if material_argument is None:
            raise GeneratedHeightLeafBindingError(
                f"height layer {layer} shader sample resource {resource!r} has no exact material.* assignment"
            )

        cb_leaves = _unique_nodes(dag, "cb", ("name",))
        out.append({
            "layerIndex": layer,
            "rawVertexInputs": [raw_input],
            "normalizedVertexWeight": {
                "attribute": "_T6_LAYER_WEIGHTS",
                "component": component,
                "layerIndex": layer,
                "proof": (
                    "raw input is a dependency of the compositor recurrence already solved as this exact layer; "
                    "portable world exporter stores that generated layer control in normalized layer component"
                ),
            },
            "sampleBindings": [{
                "resource": resource,
                "channel": "w",
                "samplers": sorted({str(item["sampler"]) for item in samples}),
                "materialArgument": material_argument,
                "portableDependency": {
                    "layerIndex": layer,
                    "role": "colorMap",
                },
                "proof": (
                    "exact sample resource from solved height recurrence plus exact OAT .tech material assignment; "
                    "layer/role comes from the solved compositor step, not resource-name suffix inference"
                ),
            }],
            "constantLeaves": sorted(str(item["name"]) for item in cb_leaves),
            "forensicDagSha256": dag.get("forensicDagSha256"),
        })

    result = {
        "format": FORMAT,
        "techniqueSet": height_payload.get("techniqueSet"),
        "pixelShaderSha256": height_payload.get("pixelShaderSha256"),
        "heightLayerCount": len(out),
        "layers": out,
        "allNonconstantLeavesExact": True,
    }
    result["bindingSetSha256"] = _jhash(result)
    return result
