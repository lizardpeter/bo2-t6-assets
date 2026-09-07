#!/usr/bin/env python3
"""Census Blender-lowering capability over exact T6 final-output symbolic DAGs.

Input is a `t6-generated-slot4-final-output-symbolic-v3` sidecar.  Only nodes
reachable from written o0 lanes are counted.  This answers a renderer-engineering
question without weakening the reversal: which exact SM4 expression operations
can the current Blender symbolic backend reproduce, and which require an exact
adapter/bake before final output can be connected?

No shader arithmetic is inferred or rewritten here.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

FORMAT = "t6-blender-symbolic-dag-capability-v1"
INPUT_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"

# Exact scalar operation coverage of t6_blender_symbolic_dag_nodes_v2.
SUPPORTED_OPS = {
    "add", "mul", "div", "min", "max", "lt", "ge", "eq", "ne",
    "neg", "abs", "sqrt", "rsq", "exp", "log", "frc", "rcp",
    "round_ni", "round_pi", "round_z", "saturate", "sin", "cos",
    "test_nonzero", "test_zero", "not_bool", "and_bool", "select",
}
# Known exact-semantics gaps kept fail-closed by the current backend.
UNSUPPORTED_OPS = {"round_ne", "and", "or"}


class DagCapabilityError(RuntimeError):
    pass


def _reachable(nodes: list[dict], roots: list[int]) -> set[int]:
    by_id = {int(row["id"]): row for row in nodes}
    seen: set[int] = set()
    stack = list(roots)
    while stack:
        node_id = int(stack.pop())
        if node_id in seen:
            continue
        row = by_id.get(node_id)
        if row is None:
            raise DagCapabilityError(f"DAG references missing node {node_id}")
        seen.add(node_id)
        stack.extend(int(value) for value in row.get("args", []))
    return seen


def _roots(shader: dict) -> list[int]:
    out = next((row for row in shader.get("outputs", []) if int(row.get("register", -1)) == 0), None)
    if not isinstance(out, dict):
        raise DagCapabilityError(f"shader {shader.get('sha256')} has no o0 output")
    roots = []
    for lane in out.get("lanes", []):
        if bool(lane.get("written")):
            node = lane.get("node")
            if node is None:
                raise DagCapabilityError("written o0 lane has no node")
            roots.append(int(node))
    if len(roots) < 3:
        raise DagCapabilityError("shader lacks complete o0.rgb roots")
    return roots


def census(doc: dict) -> dict:
    if doc.get("format") != INPUT_FORMAT:
        raise DagCapabilityError(f"unsupported symbolic input {doc.get('format')!r}")
    shaders = doc.get("shaders")
    if not isinstance(shaders, list) or not shaders:
        raise DagCapabilityError("symbolic input has no shader rows")

    global_kind = collections.Counter()
    global_ops = collections.Counter()
    global_resources = collections.Counter()
    global_sample_opcodes = collections.Counter()
    rows = []
    unsupported_shader_count = 0

    for shader in shaders:
        nodes = shader.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise DagCapabilityError(f"shader {shader.get('sha256')} has no nodes")
        reachable = _reachable(nodes, _roots(shader))
        by_id = {int(row["id"]): row for row in nodes}
        kind = collections.Counter()
        ops = collections.Counter()
        resources = collections.Counter()
        sample_opcodes = collections.Counter()
        unknown_kinds = set()
        unsupported_ops = set()
        unknown_ops = set()
        reachable_undefined = []

        for node_id in sorted(reachable):
            row = by_id[node_id]
            k = str(row.get("kind") or "")
            kind[k] += 1
            if k == "op":
                op = str(row.get("op") or "")
                ops[op] += 1
                if op in UNSUPPORTED_OPS:
                    unsupported_ops.add(op)
                elif op not in SUPPORTED_OPS:
                    unknown_ops.add(op)
            elif k == "textureSample":
                resources[str(row.get("resource") or "")] += 1
                sample_opcodes[str(row.get("opcode") or "")] += 1
            elif k == "undefined":
                reachable_undefined.append(node_id)
            elif k not in {"literal32", "symbol"}:
                unknown_kinds.add(k)

        blockers = []
        if reachable_undefined:
            blockers.append({"type": "reachableUndefined", "nodes": reachable_undefined})
        if unknown_kinds:
            blockers.append({"type": "unknownNodeKinds", "values": sorted(unknown_kinds)})
        if unsupported_ops:
            blockers.append({"type": "knownUnsupportedOps", "values": sorted(unsupported_ops)})
        if unknown_ops:
            blockers.append({"type": "unknownOps", "values": sorted(unknown_ops)})
        if blockers:
            unsupported_shader_count += 1

        global_kind.update(kind)
        global_ops.update(ops)
        global_resources.update(resources)
        global_sample_opcodes.update(sample_opcodes)
        rows.append({
            "sha256": shader.get("sha256"),
            "asset": shader.get("asset"),
            "techniqueSets": shader.get("techniqueSets", []),
            "reachableNodeCount": len(reachable),
            "kindCounts": dict(sorted(kind.items())),
            "opCounts": dict(sorted(ops.items())),
            "resourceSampleCounts": dict(sorted(resources.items())),
            "sampleOpcodeCounts": dict(sorted(sample_opcodes.items())),
            "arithmeticLowerableByV2": not blockers,
            "blockers": blockers,
        })

    return {
        "format": FORMAT,
        "inputFormat": INPUT_FORMAT,
        "proofBoundary": (
            "Reachability/capability census over exact serialized final-output DAG nodes only. "
            "No arithmetic/resource semantics are inferred; unsupported Blender operations remain fail-closed."
        ),
        "summary": {
            "shaderCount": len(rows),
            "arithmeticLowerableShaderCount": len(rows) - unsupported_shader_count,
            "arithmeticBlockedShaderCount": unsupported_shader_count,
            "allArithmeticLowerableByV2": unsupported_shader_count == 0,
            "reachableKindCounts": dict(sorted(global_kind.items())),
            "reachableOpCounts": dict(sorted(global_ops.items())),
            "reachableResourceSampleCounts": dict(sorted(global_resources.items())),
            "reachableSampleOpcodeCounts": dict(sorted(global_sample_opcodes.items())),
            "knownUnsupportedOpsPresent": sorted(set(global_ops) & UNSUPPORTED_OPS),
            "unknownOpsPresent": sorted(set(global_ops) - SUPPORTED_OPS - UNSUPPORTED_OPS),
        },
        "shaders": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("symbolic_v3", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = census(json.loads(a.symbolic_v3.read_text(encoding="utf-8")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
