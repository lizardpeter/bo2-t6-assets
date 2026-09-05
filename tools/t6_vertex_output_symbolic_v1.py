#!/usr/bin/env python3
"""Straight-line T6 SM4 vertex-shader output DAG reconstruction.

This is a deliberately small sibling of ``t6_retail_special_shdr_symbolic_v1``.
That proven engine only returns outputs with lightmap dependencies because it was
built for a pixel-lightmap census. Here we retain every VS output component so
physical interpolator equations can be compared algebraically.

The parser reuses the existing opcode/operand decoders and symbolic leaf helpers.
It rejects control flow and unsupported opcodes rather than approximating them.
"""
from __future__ import annotations

import hashlib
import json
import struct
from typing import Any

import t6_retail_special_shdr_symbolic_v1 as shared


COMP = "xyzw"


class VertexSymbolicError(RuntimeError):
    pass


def symbolic_vertex(blob: bytes, operand, opcode) -> dict:
    payload = opcode.shdr_payload(blob)
    words = struct.unpack("<%dI" % (len(payload) // 4), payload)
    if len(words) < 2 or int(words[1]) != len(words):
        raise VertexSymbolicError("invalid SM4 program length")
    i = 2
    state = {}
    dag = shared.Dag()
    blockers = []
    while i < words[1]:
        ins = operand.parse_instruction(words, i, opcode.OPCODES)
        op = ins["opcode"]
        ops = ins["operands"]
        sat = bool(words[i] & 0x2000)
        if op.startswith("dcl_") or op == "ret":
            i += ins["lengthDwords"]
            continue
        if op in ("if", "else", "endif", "loop", "endloop", "break", "breakc", "continue", "continuec"):
            raise VertexSymbolicError(f"control-flow opcode {op!r} at {i}")
        if op == "discard":
            raise VertexSymbolicError(f"unexpected vertex discard at {i}")
        if op == "sincos":
            for dest, which in zip(ops[:2], ("sin", "cos")):
                lanes = shared.dest_lanes(dest)
                vals = shared.op1(
                    dag,
                    which,
                    shared.source_nodes(ops[2], lanes, state, dag, blockers, i),
                )
                reg = shared.idx(dest)
                for lane, value in zip(lanes, vals):
                    state[(dest["type"], reg, lane)] = value
            i += ins["lengthDwords"]
            continue

        if not ops:
            raise VertexSymbolicError(f"opcode {op!r} at {i} has no operands")
        dest = ops[0]
        lanes = shared.dest_lanes(dest)
        reg = shared.idx(dest)
        count = len(lanes)
        vals = None

        if op.startswith("sample"):
            raise VertexSymbolicError(f"vertex texture sample {op!r} at {i} is outside v1 proof scope")
        if op in ("dp2", "dp3", "dp4"):
            width = int(op[-1])
            a = shared.source_nodes(ops[1], list(range(width)), state, dag, blockers, i)
            b = shared.source_nodes(ops[2], list(range(width)), state, dag, blockers, i)
            products = [dag.add("op", op="mul", args=[x, y]) for x, y in zip(a, b)]
            value = products[0]
            for child in products[1:]:
                value = dag.add("op", op="add", args=[value, child])
            vals = [value] * count
        else:
            src = [
                shared.source_nodes(q, lanes, state, dag, blockers, i)
                for q in ops[1:]
            ]
            if op == "mov":
                vals = src[0]
            elif op in ("add", "mul", "div", "min", "max", "lt", "ge", "and", "or"):
                vals = shared.op2(dag, op, src[0], src[1])
            elif op == "mad":
                vals = [
                    dag.add("op", op="add", args=[dag.add("op", op="mul", args=[a, b]), c])
                    for a, b, c in zip(*src)
                ]
            elif op in ("sqrt", "rsq", "exp", "log", "frc", "round_ni"):
                vals = shared.op1(dag, op, src[0])
            elif op == "movc":
                vals = [
                    dag.add("op", op="select", args=[cond, yes, no])
                    for cond, yes, no in zip(*src)
                ]
            else:
                raise VertexSymbolicError(f"unsupported straight-line VS opcode {op!r} at {i}")

        if blockers:
            raise VertexSymbolicError(f"symbolic read-before-write/blocker at {i}: {blockers[0]}")
        if sat:
            vals = [dag.add("op", op="saturate", args=[v]) for v in vals]
        for lane, value in zip(lanes, vals):
            state[(dest["type"], reg, lane)] = value
        i += ins["lengthDwords"]

    outputs = {
        (int(reg), int(lane)): node
        for (typ, reg, lane), node in state.items()
        if typ == "output"
    }
    if not outputs:
        raise VertexSymbolicError("vertex shader symbolic pass produced no output components")
    return {"dag": dag, "outputs": outputs, "nodeCount": len(dag.nodes)}


def _canon_node(dag, node_id: int, memo: dict[int, Any]) -> Any:
    if node_id in memo:
        return memo[node_id]
    node = dag.nodes[node_id]
    kind = node["kind"]
    if kind in ("symbol", "literal32", "undefined"):
        out = {k: node[k] for k in node if k not in ("id",)}
    elif kind == "op":
        op = str(node["op"])
        args = [_canon_node(dag, int(child), memo) for child in node.get("args", [])]
        if op in ("add", "mul", "min", "max", "and", "or"):
            flat = []
            for arg in args:
                if isinstance(arg, dict) and arg.get("kind") == "op" and arg.get("op") == op:
                    flat.extend(arg["args"])
                else:
                    flat.append(arg)
            args = sorted(
                flat,
                key=lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")),
            )
        out = {"kind": "op", "op": op, "args": args}
    else:
        out = {k: node[k] for k in node if k != "id"}
        if "args" in out:
            out["args"] = [_canon_node(dag, int(child), memo) for child in node["args"]]
    memo[node_id] = out
    return out


def canonical(dag, node_id: int) -> Any:
    return _canon_node(dag, int(node_id), {})


def canonical_sha256(dag, node_id: int) -> str:
    return hashlib.sha256(
        json.dumps(canonical(dag, node_id), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _neg(dag, node: int) -> int:
    return dag.add("op", op="neg", args=[node])


def _mul(dag, a: int, b: int) -> int:
    return dag.add("op", op="mul", args=[a, b])


def _sub(dag, a: int, b: int) -> int:
    return dag.add("op", op="add", args=[a, _neg(dag, b)])


def cross_times_handedness(dag, n: tuple[int, int, int], t: tuple[int, int, int], handedness: int) -> tuple[int, int, int]:
    nx, ny, nz = n
    tx, ty, tz = t
    cross = (
        _sub(dag, _mul(dag, ny, tz), _mul(dag, nz, ty)),
        _sub(dag, _mul(dag, nz, tx), _mul(dag, nx, tz)),
        _sub(dag, _mul(dag, nx, ty), _mul(dag, ny, tx)),
    )
    return tuple(_mul(dag, value, handedness) for value in cross)


def classify_cross_handedness(
    dag,
    *,
    normal: tuple[int, int, int],
    tangent: tuple[int, int, int],
    handedness: int,
    candidate: tuple[int, int, int],
) -> dict:
    expected_nt = cross_times_handedness(dag, normal, tangent, handedness)
    expected_tn = cross_times_handedness(dag, tangent, normal, handedness)
    candidate_hashes = [canonical_sha256(dag, node) for node in candidate]
    nt_hashes = [canonical_sha256(dag, node) for node in expected_nt]
    tn_hashes = [canonical_sha256(dag, node) for node in expected_tn]
    matches = []
    if candidate_hashes == nt_hashes:
        matches.append("cross(normal,tangent)*handedness")
    if candidate_hashes == tn_hashes:
        matches.append("cross(tangent,normal)*handedness")
    return {
        "candidateComponentSha256": candidate_hashes,
        "normalTangentExpectedSha256": nt_hashes,
        "tangentNormalExpectedSha256": tn_hashes,
        "matches": matches,
        "uniqueMatch": matches[0] if len(matches) == 1 else None,
    }
