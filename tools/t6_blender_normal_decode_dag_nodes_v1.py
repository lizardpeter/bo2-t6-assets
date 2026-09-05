#!/usr/bin/env python3
"""Compile exact T6 normal sample decode forensic DAGs to Blender Math nodes.

Recovery v9 stores sample-only scalar DAGs for base and secondary normal X/Y.
This adapter deliberately reuses the already-tested generic scalar operations of
the vN Blender DAG compiler.  A normal component DAG is accepted only when it
contains no vertex/cbuffer leaves and every sample leaf is the one exact
`normalMapSampler[ N ].{x|y}` bound by its recipe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import t6_blender_height_dag_nodes_v1 as scalar
from t6_generated_height_weight_dag_v1 import validate_forensic_dag


class BlenderNormalDecodeDagError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalDecodePlan:
    layer_index: int
    component: str
    resource: str
    dag: dict
    forensic_sha256: str


def prepare_component(component_row: dict, *, layer_index: int, resource: str, component: str) -> NormalDecodePlan:
    if component not in ("x", "y"):
        raise BlenderNormalDecodeDagError(f"unsupported normal component {component!r}")
    if str(component_row.get("component") or "") != component:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index}: component row {component_row.get('component')!r} != {component!r}"
        )
    dag = component_row.get("forensicDag")
    if not isinstance(dag, dict):
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index} {component}: missing forensic normal decode DAG"
        )
    try:
        validate_forensic_dag(dag)
    except Exception as exc:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index} {component}: invalid forensic DAG: {exc}"
        ) from exc
    expected_sha = str(component_row.get("forensicDagSha256") or "")
    actual_sha = str(dag.get("forensicDagSha256") or "")
    if not expected_sha or expected_sha != actual_sha:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index} {component}: component/DAG forensic SHA disagrees"
        )

    samples = set()
    inputs = []
    constants = []
    for node in dag.get("nodes", []):
        kind = str(node.get("kind") or "")
        if kind == "sample":
            samples.add((str(node.get("resource") or ""), str(node.get("channel") or "")))
        elif kind == "input":
            inputs.append(str(node.get("name") or ""))
        elif kind == "cb":
            constants.append(str(node.get("name") or ""))
    if inputs or constants:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index} {component}: normal decode DAG has non-sample leaves inputs={inputs} cb={constants}"
        )
    expected_sample = {(resource, component)}
    if samples != expected_sample:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index} {component}: sample leaves {sorted(samples)} != {sorted(expected_sample)}"
        )
    return NormalDecodePlan(
        layer_index=int(layer_index),
        component=component,
        resource=resource,
        dag=dag,
        forensic_sha256=actual_sha,
    )


def compile_component(nodes, links, plan: NormalDecodePlan, *, sample_socket: Any):
    # HeightDagPlan is only a scalar-DAG carrier here.  Because the validated
    # normal DAG contains no input/cbuffer nodes, vertex_socket/constant maps are
    # unreachable by construction.
    scalar_plan = scalar.HeightDagPlan(
        layer_index=plan.layer_index,
        dag=plan.dag,
        vertex_leaf_names=(),
        sample_leaves=((plan.resource, plan.component),),
        constant_values={},
        forensic_sha256=plan.forensic_sha256,
        raw_vertex_component="",
    )
    try:
        return scalar.compile_height_dag(
            nodes,
            links,
            scalar_plan,
            vertex_socket=None,
            sample_sockets={(plan.resource, plan.component): sample_socket},
        )
    except scalar.BlenderHeightDagError as exc:
        raise BlenderNormalDecodeDagError(
            f"layer {plan.layer_index} {plan.component}: Blender normal decode compilation failed: {exc}"
        ) from exc


def prepare_pair(payload: dict, *, layer_index: int, expected_resource: str) -> tuple[NormalDecodePlan, NormalDecodePlan]:
    components = payload.get("components")
    if not isinstance(components, list) or len(components) != 2:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index}: normal decode does not contain exactly two components"
        )
    by_component = {str(row.get("component") or ""): row for row in components}
    if set(by_component) != {"x", "y"}:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index}: normal decode components are {sorted(by_component)}, expected x/y"
        )
    resource = str(payload.get("normalResource") or expected_resource)
    if resource != expected_resource:
        raise BlenderNormalDecodeDagError(
            f"layer {layer_index}: normal resource {resource!r} != exact recipe {expected_resource!r}"
        )
    return (
        prepare_component(by_component["x"], layer_index=layer_index, resource=resource, component="x"),
        prepare_component(by_component["y"], layer_index=layer_index, resource=resource, component="y"),
    )
