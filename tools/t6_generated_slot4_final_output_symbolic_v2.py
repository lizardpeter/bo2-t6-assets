#!/usr/bin/env python3
"""Generated slot-4 final-output symbolic DAG v2 hardening.

v1 established exact OAT slot-4 PS identity, RDEF register naming, complete
output retention and structured branch merges. v2 preserves that contract and
hardens two forensic boundaries:

1. ``sample_d*`` derivative operands are retained as full four-component source
   vectors instead of scalarizing each extra operand.
2. branch-merge ``undefined`` sentinels are permitted internally only when they
   are dead. Any undefined node reachable from a written output fails closed.

No final T6 lighting interpretation is introduced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import t6_generated_slot4_final_output_symbolic_v1 as v1

FORMAT = "t6-generated-slot4-final-output-symbolic-v2"
_BASE_SYMBOLIC = v1.symbolic


class GeneratedFinalOutputSymbolicV2Error(v1.GeneratedFinalOutputSymbolicError):
    pass


def _named_sample_nodes_v2(
    O,
    lanes,
    state,
    dag,
    blockers,
    at,
    op,
    textures,
    samplers,
):
    coords = v1.straight.source_nodes(O[1], list(range(4)), state, dag, blockers, at)
    resource_register = v1.straight.idx(O[2])
    sampler_register = v1.straight.idx(O[3])
    if resource_register is None or resource_register not in textures:
        raise GeneratedFinalOutputSymbolicV2Error(
            f"sample at DWORD {at}: texture register {resource_register!r} absent from RDEF"
        )
    if sampler_register is None or sampler_register not in samplers:
        raise GeneratedFinalOutputSymbolicV2Error(
            f"sample at DWORD {at}: sampler register {sampler_register!r} absent from RDEF"
        )

    extra = []
    extra_widths = []
    # SM4 sample_d carries derivative vectors; retaining only lane 0 would lose
    # exact sampling-state ancestry. Other sample-family extra operands in the
    # retained T6 path are scalar controls (LOD, bias, compare/reference).
    derivative = str(op).startswith("sample_d")
    for source in O[4:]:
        source_lanes = list(range(4)) if derivative else [0]
        values = v1.straight.source_nodes(source, source_lanes, state, dag, blockers, at)
        extra.extend(values)
        extra_widths.append(len(values))

    args = coords + extra
    channels = v1.straight.source_components(O[2], lanes)
    if any(channel is None for channel in channels):
        raise GeneratedFinalOutputSymbolicV2Error(
            f"sample at DWORD {at}: unresolved resource channel selection"
        )
    resource = textures[resource_register]
    sampler = samplers[sampler_register]
    values = [
        dag.add(
            "textureSample",
            resource=resource,
            channel=v1.COMP[int(channel)],
            textureRegister=resource_register,
            sampler=sampler,
            samplerRegister=sampler_register,
            opcode=op,
            instructionDword=at,
            args=args,
        )
        for channel in channels
    ]
    return values, {
        "atDword": at,
        "opcode": op,
        "resource": resource,
        "textureRegister": resource_register,
        "sampler": sampler,
        "samplerRegister": sampler_register,
        "channels": [v1.COMP[int(channel)] for channel in channels],
        "coordinateNodes": coords,
        "extraOperandNodes": extra,
        "extraOperandWidths": extra_widths,
        "derivativeOperandsFullWidth": derivative,
    }


def _undefined_reachable(result: dict) -> list[dict]:
    nodes = result.get("nodes")
    outputs = result.get("outputs")
    if not isinstance(nodes, list) or not isinstance(outputs, list):
        raise GeneratedFinalOutputSymbolicV2Error("v1 symbolic result lacks nodes/outputs")

    cache: dict[int, frozenset[int]] = {}

    def walk(node_id: int) -> set[int]:
        if node_id in cache:
            return set(cache[node_id])
        if node_id < 0 or node_id >= len(nodes):
            raise GeneratedFinalOutputSymbolicV2Error(
                f"output DAG references invalid node {node_id}"
            )
        node = nodes[node_id]
        found = {node_id} if node.get("kind") == "undefined" else set()
        for child in node.get("args", []):
            found.update(walk(int(child)))
        cache[node_id] = frozenset(found)
        return found

    failures = []
    for output in outputs:
        register = int(output["register"])
        for lane in output.get("lanes", []):
            if not bool(lane.get("written")):
                continue
            node_id = int(lane["node"])
            undefined = sorted(walk(node_id))
            if undefined:
                failures.append({
                    "output": f"o{register}.{lane['channel']}",
                    "rootNode": node_id,
                    "undefinedNodes": undefined,
                })
    return failures


def symbolic(blob: bytes) -> dict:
    old = v1._named_sample_nodes
    v1._named_sample_nodes = _named_sample_nodes_v2
    try:
        result = _BASE_SYMBOLIC(blob)
    finally:
        v1._named_sample_nodes = old
    failures = _undefined_reachable(result)
    if failures:
        raise GeneratedFinalOutputSymbolicV2Error(
            f"branch-created undefined state reaches written output: {failures[:4]}"
        )
    result["undefinedOutputReachabilityFailureCount"] = 0
    result["sampleDerivativeOperandPolicy"] = (
        "sample_d* extra operands retain four source components; other sample-family extras remain scalar"
    )
    return result


def build(recipe_manifest: dict, *, oat_root: Path, strict_nuketown: bool = False) -> dict:
    old = v1.symbolic
    v1.symbolic = symbolic
    try:
        result = v1.build(
            recipe_manifest,
            oat_root=oat_root,
            strict_nuketown=strict_nuketown,
        )
    finally:
        v1.symbolic = old
    if result.get("format") != v1.FORMAT:
        raise GeneratedFinalOutputSymbolicV2Error(
            f"unexpected v1 result format {result.get('format')!r}"
        )
    result["format"] = FORMAT
    result.setdefault("summary", {})["undefinedOutputReachabilityFailureCount"] = 0
    result["summary"]["fullDerivativeSampleOperandRetention"] = True
    result["baseFormat"] = v1.FORMAT
    result["proofBoundary"] = (
        "v1 exact OAT/RDEF/full-output symbolic contract plus full sample_d derivative-vector retention and "
        "zero reachable undefined output state. Final physical T6 lighting interpretation and semantic subgraph "
        "matching remain separate proofs."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strict-nuketown", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.recipes.read_text(encoding="utf-8"))
    result = build(
        manifest,
        oat_root=args.oat_root,
        strict_nuketown=args.strict_nuketown,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
