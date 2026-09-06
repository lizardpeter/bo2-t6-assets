#!/usr/bin/env python3
"""Probe the explicit directional-secondary-lightmap equation inside full output DAGs.

The retained global DXBC proof establishes the exact T6 directional secondary
lightmap equation and records two compiler encodings: explicit and folded.  This
probe anchors only the explicit form inside
``t6-generated-slot4-final-output-symbolic-v3``.  Folded/unmatched shaders are
reported, never rewritten into an assumed equivalent form.

Explicit equation matched here:

  row0 = secondary(u, v/3)
  row1 = secondary(u, v/3 + 1/3)
  row2 = secondary(u, v/3 + 2/3)
  D    = 2*row2.rgb - 1
  F    = saturate(dot(D, N))
  Lrgb = row0.rgb/(row0.a+1e-6) + row1.rgb/(row1.a+1e-6)*F

Every matched Lrgb component must be an ancestor of the corresponding o0.rgb
lane.  N is intentionally preserved as the exact three counterpart DAG roots;
this tool does not assign additional physical meaning to it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3

FORMAT = "t6-generated-final-output-directional-lightmap-anchor-probe-v1"
RESOURCE = "lightmapSamplerSecondary"
EPS_BITS = "358637bd"
ONE_THIRD = struct.unpack("<f", struct.pack("<I", 0x3EAAAAAB))[0]
TWO_THIRDS = struct.unpack("<f", struct.pack("<I", 0x3F2AAAAB))[0]
TOL = 2.0e-6


class DirectionalLightmapAnchorProbeError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _node(nodes: list[dict], node_id: int) -> dict:
    if node_id < 0 or node_id >= len(nodes):
        raise DirectionalLightmapAnchorProbeError(f"invalid DAG node {node_id}")
    node = nodes[node_id]
    if int(node.get("id", node_id)) != node_id:
        raise DirectionalLightmapAnchorProbeError(
            f"non-dense DAG node identity at {node_id}: {node.get('id')!r}"
        )
    return node


def _literal(nodes: list[dict], node_id: int) -> float | None:
    node = _node(nodes, node_id)
    if node.get("kind") != "literal32":
        return None
    bits = str(node.get("bits") or "").lower()
    if len(bits) != 8:
        return None
    try:
        value = struct.unpack("<f", struct.pack("<I", int(bits, 16)))[0]
    except Exception:
        return None
    return float(value) if math.isfinite(value) else None


def _canon(nodes: list[dict], root: int) -> str:
    memo: dict[int, Any] = {}
    visiting: set[int] = set()
    def build(node_id: int):
        if node_id in memo:
            return memo[node_id]
        if node_id in visiting:
            raise DirectionalLightmapAnchorProbeError(f"cycle at DAG node {node_id}")
        visiting.add(node_id)
        node = _node(nodes, node_id)
        record = {
            key: value for key, value in node.items()
            if key not in ("id", "args", "instructionDword")
        }
        record["args"] = [build(int(x)) for x in node.get("args", [])]
        visiting.remove(node_id)
        memo[node_id] = record
        return record
    return _jhash(build(int(root)))


def _reachable(nodes: list[dict], root: int) -> set[int]:
    seen = set()
    visiting = set()
    def walk(node_id: int):
        if node_id in seen:
            return
        if node_id in visiting:
            raise DirectionalLightmapAnchorProbeError(f"cycle at DAG node {node_id}")
        visiting.add(node_id)
        for child in _node(nodes, node_id).get("args", []):
            walk(int(child))
        visiting.remove(node_id)
        seen.add(node_id)
    walk(int(root))
    return seen


def _affine(nodes: list[dict], root: int, memo=None):
    """Return (atomHash|None, scale, offset) for a single-atom affine expression."""
    memo = {} if memo is None else memo
    if root in memo:
        return memo[root]
    lit = _literal(nodes, root)
    if lit is not None:
        result = (None, 0.0, lit)
        memo[root] = result
        return result
    node = _node(nodes, root)
    if node.get("kind") != "op":
        result = (_canon(nodes, root), 1.0, 0.0)
        memo[root] = result
        return result
    op = node.get("op")
    args = [int(x) for x in node.get("args", [])]
    result = None
    if op == "neg" and len(args) == 1:
        a = _affine(nodes, args[0], memo)
        if a is not None:
            result = (a[0], -a[1], -a[2])
    elif op == "add" and len(args) == 2:
        a = _affine(nodes, args[0], memo); b = _affine(nodes, args[1], memo)
        if a is not None and b is not None:
            if a[0] is None:
                result = (b[0], b[1], a[2] + b[2])
            elif b[0] is None:
                result = (a[0], a[1], a[2] + b[2])
            elif a[0] == b[0]:
                result = (a[0], a[1] + b[1], a[2] + b[2])
    elif op == "mul" and len(args) == 2:
        a = _affine(nodes, args[0], memo); b = _affine(nodes, args[1], memo)
        if a is not None and b is not None:
            if a[0] is None:
                result = (b[0], a[2] * b[1], a[2] * b[2])
            elif b[0] is None:
                result = (a[0], b[2] * a[1], b[2] * a[2])
    elif op == "div" and len(args) == 2:
        a = _affine(nodes, args[0], memo); b = _affine(nodes, args[1], memo)
        if a is not None and b is not None and b[0] is None and abs(b[2]) > 1.0e-30:
            result = (a[0], a[1] / b[2], a[2] / b[2])
    memo[root] = result
    return result


def _close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= TOL


def _sample_groups(nodes: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for node in nodes:
        if node.get("kind") != "textureSample" or node.get("resource") != RESOURCE:
            continue
        args = [int(x) for x in node.get("args", [])]
        if len(args) < 2:
            continue
        key = (
            int(node.get("instructionDword", -1)),
            str(node.get("sampler") or ""),
            tuple(args),
        )
        row = grouped.setdefault(key, {
            "instructionDword": key[0],
            "sampler": key[1],
            "args": args,
            "channels": {},
        })
        channel = str(node.get("channel") or "")
        if channel in row["channels"]:
            raise DirectionalLightmapAnchorProbeError(
                f"duplicate {RESOURCE}.{channel} sample node at DWORD {key[0]}"
            )
        row["channels"][channel] = int(node["id"])
    return list(grouped.values())


def _row_triplets(nodes: list[dict]) -> list[dict]:
    groups = _sample_groups(nodes)
    candidates = []
    for row0 in groups:
        if not set("xyzw").issubset(row0["channels"]):
            continue
        u0 = _canon(nodes, row0["args"][0]); v0 = _affine(nodes, row0["args"][1])
        if v0 is None or v0[0] is None or not _close(v0[1], ONE_THIRD) or not _close(v0[2], 0.0):
            continue
        for row1 in groups:
            if row1 is row0 or not set("xyzw").issubset(row1["channels"]):
                continue
            if _canon(nodes, row1["args"][0]) != u0:
                continue
            v1 = _affine(nodes, row1["args"][1])
            if v1 is None or v1[0] != v0[0] or not _close(v1[1], ONE_THIRD) or not _close(v1[2], ONE_THIRD):
                continue
            for row2 in groups:
                if row2 is row0 or row2 is row1 or not set("xyz").issubset(row2["channels"]):
                    continue
                if _canon(nodes, row2["args"][0]) != u0:
                    continue
                v2 = _affine(nodes, row2["args"][1])
                if v2 is None or v2[0] != v0[0] or not _close(v2[1], ONE_THIRD) or not _close(v2[2], TWO_THIRDS):
                    continue
                candidates.append({"row0": row0, "row1": row1, "row2": row2, "vAtomSha256": v0[0], "uSha256": u0})
    # Instruction-order tuple makes duplicate coordinate-equivalent groups explicit.
    unique = {}
    for item in candidates:
        key = tuple(item[f"row{i}"]["instructionDword"] for i in range(3))
        unique[key] = item
    return [unique[key] for key in sorted(unique)]


def _is_literal_bits(nodes, node_id, bits: str) -> bool:
    node = _node(nodes, node_id)
    return node.get("kind") == "literal32" and str(node.get("bits") or "").lower() == bits.lower()


def _is_add_pair(nodes, node_id, a: int, b: int) -> bool:
    node = _node(nodes, node_id)
    if node.get("kind") != "op" or node.get("op") != "add":
        return False
    args = [int(x) for x in node.get("args", [])]
    return len(args) == 2 and ({args[0], args[1]} == {a, b})


def _denominator(nodes, sample_w: int) -> set[int]:
    out = set()
    for node in nodes:
        if node.get("kind") != "op" or node.get("op") != "add":
            continue
        args = [int(x) for x in node.get("args", [])]
        if len(args) != 2 or sample_w not in args:
            continue
        other = args[1] if args[0] == sample_w else args[0]
        if _is_literal_bits(nodes, other, EPS_BITS):
            out.add(int(node["id"]))
    return out


def _normalized(nodes, sample_rgb: int, sample_w: int) -> set[int]:
    denoms = _denominator(nodes, sample_w)
    out = set()
    for node in nodes:
        if node.get("kind") != "op":
            continue
        args = [int(x) for x in node.get("args", [])]
        if node.get("op") == "div" and len(args) == 2 and args[0] == sample_rgb and args[1] in denoms:
            out.add(int(node["id"]))
        elif node.get("op") == "mul" and len(args) == 2 and sample_rgb in args:
            other = args[1] if args[0] == sample_rgb else args[0]
            rcp = _node(nodes, other)
            if rcp.get("kind") == "op" and rcp.get("op") == "rcp":
                rargs = [int(x) for x in rcp.get("args", [])]
                if len(rargs) == 1 and rargs[0] in denoms:
                    out.add(int(node["id"]))
    return out


def _direction(nodes, sample: int) -> set[int]:
    out = set()
    two_nodes = {int(n["id"]) for n in nodes if _is_literal_bits(nodes, int(n["id"]), "40000000")}
    minus_one_nodes = {int(n["id"]) for n in nodes if _is_literal_bits(nodes, int(n["id"]), "bf800000")}
    muls = set()
    for node in nodes:
        if node.get("kind") != "op" or node.get("op") != "mul":
            continue
        args = [int(x) for x in node.get("args", [])]
        if len(args) == 2 and sample in args and any(x in two_nodes for x in args):
            muls.add(int(node["id"]))
    for node in nodes:
        if node.get("kind") != "op" or node.get("op") != "add":
            continue
        args = [int(x) for x in node.get("args", [])]
        if len(args) == 2 and any(x in muls for x in args) and any(x in minus_one_nodes for x in args):
            out.add(int(node["id"]))
    return out


def _flatten_add(nodes, root: int) -> list[int]:
    node = _node(nodes, root)
    if node.get("kind") == "op" and node.get("op") == "add":
        args = [int(x) for x in node.get("args", [])]
        if len(args) == 2:
            return _flatten_add(nodes, args[0]) + _flatten_add(nodes, args[1])
    return [root]


def _factor_candidates(nodes, directions: dict[str, set[int]]) -> list[dict]:
    direction_to_channel = {}
    for channel, ids in directions.items():
        for node_id in ids:
            direction_to_channel[node_id] = channel
    out = []
    for node in nodes:
        if node.get("kind") != "op" or node.get("op") != "saturate":
            continue
        args = [int(x) for x in node.get("args", [])]
        if len(args) != 1:
            continue
        terms = _flatten_add(nodes, args[0])
        if len(terms) != 3:
            continue
        normals = {}
        ok = True
        for term in terms:
            mul = _node(nodes, term)
            if mul.get("kind") != "op" or mul.get("op") != "mul":
                ok = False; break
            margs = [int(x) for x in mul.get("args", [])]
            if len(margs) != 2:
                ok = False; break
            hits = [x for x in margs if x in direction_to_channel]
            if len(hits) != 1:
                ok = False; break
            d = hits[0]; channel = direction_to_channel[d]
            other = margs[1] if margs[0] == d else margs[0]
            if channel in normals:
                ok = False; break
            normals[channel] = other
        if ok and set(normals) == set("xyz"):
            out.append({
                "factorNode": int(node["id"]),
                "dotNode": args[0],
                "normalNodes": {ch: normals[ch] for ch in "xyz"},
                "normalSha256": _jhash({ch: _canon(nodes, normals[ch]) for ch in "xyz"}),
            })
    return out


def _mul_pair(nodes, node_id: int, a: int, b: int) -> bool:
    node = _node(nodes, node_id)
    if node.get("kind") != "op" or node.get("op") != "mul":
        return False
    args = [int(x) for x in node.get("args", [])]
    return len(args) == 2 and ((args[0] == a and args[1] == b) or (args[0] == b and args[1] == a))


def _final_explicit(nodes, row0norm: int, row1norm: int, factor: int) -> set[int]:
    weighted = {
        int(node["id"]) for node in nodes
        if _mul_pair(nodes, int(node["id"]), row1norm, factor)
    }
    out = set()
    for node in nodes:
        if node.get("kind") != "op" or node.get("op") != "add":
            continue
        args = [int(x) for x in node.get("args", [])]
        if len(args) == 2 and row0norm in args and any(x in weighted for x in args):
            out.add(int(node["id"]))
    return out


def _o0_reachable(shader: dict, nodes: list[dict]) -> dict[str, set[int]]:
    rows = [x for x in shader.get("outputs", []) if int(x.get("register", -1)) == 0]
    if len(rows) != 1:
        raise DirectionalLightmapAnchorProbeError("shader does not have exactly one o0 row")
    lanes = rows[0].get("lanes", [])
    if len(lanes) != 4:
        raise DirectionalLightmapAnchorProbeError("o0 row does not contain xyzw")
    out = {}
    for lane, channel in zip(lanes[:3], "xyz"):
        if lane.get("channel") != channel or not bool(lane.get("written")):
            raise DirectionalLightmapAnchorProbeError(f"o0.{channel} is not written")
        out[channel] = _reachable(nodes, int(lane["node"]))
    return out


def _equations_for_triplet(shader: dict, nodes: list[dict], triplet: dict) -> list[dict]:
    row0 = triplet["row0"]; row1 = triplet["row1"]; row2 = triplet["row2"]
    row0norm = {}; row1norm = {}; directions = {}
    for ch in "xyz":
        a = _normalized(nodes, row0["channels"][ch], row0["channels"]["w"])
        b = _normalized(nodes, row1["channels"][ch], row1["channels"]["w"])
        d = _direction(nodes, row2["channels"][ch])
        if len(a) != 1 or len(b) != 1 or len(d) != 1:
            return []
        row0norm[ch] = next(iter(a)); row1norm[ch] = next(iter(b)); directions[ch] = d
    reachable = _o0_reachable(shader, nodes)
    equations = []
    for factor in _factor_candidates(nodes, directions):
        rgb_nodes = {}
        valid = True
        for ch in "xyz":
            finals = _final_explicit(nodes, row0norm[ch], row1norm[ch], factor["factorNode"])
            finals = {node_id for node_id in finals if node_id in reachable[ch]}
            if len(finals) != 1:
                valid = False; break
            rgb_nodes[ch] = next(iter(finals))
        if valid:
            equations.append({
                "encoding": "explicit",
                "factorNode": factor["factorNode"],
                "normalNodes": factor["normalNodes"],
                "normalSha256": factor["normalSha256"],
                "rgbNodes": rgb_nodes,
                "rgbSha256": _jhash({ch: _canon(nodes, rgb_nodes[ch]) for ch in "xyz"}),
                "row0NormalizedNodes": row0norm,
                "row1NormalizedNodes": row1norm,
                "directionNodes": {ch: next(iter(directions[ch])) for ch in "xyz"},
                "rowSampleDwords": [row0["instructionDword"], row1["instructionDword"], row2["instructionDword"]],
            })
    return equations


def build(final_output: dict) -> dict:
    if final_output.get("format") != symbolic_v3.FORMAT:
        raise DirectionalLightmapAnchorProbeError(
            f"unsupported final-output format {final_output.get('format')!r}"
        )
    shaders = final_output.get("shaders")
    if not isinstance(shaders, list) or not shaders:
        raise DirectionalLightmapAnchorProbeError("final-output manifest has no shaders")
    rows = []
    total_equations = 0
    zero = one = two_plus = 0
    triplet_count = 0
    for shader in shaders:
        nodes = shader.get("nodes")
        if not isinstance(nodes, list):
            raise DirectionalLightmapAnchorProbeError(
                f"shader {shader.get('sha256')}: nodes missing"
            )
        triplets = _row_triplets(nodes)
        triplet_count += len(triplets)
        equations = []
        for triplet in triplets:
            equations.extend(_equations_for_triplet(shader, nodes, triplet))
        # Exact node identities deduplicate equivalent discoveries.
        dedup = {}
        for eq in equations:
            key = (eq["factorNode"], tuple(eq["rgbNodes"][ch] for ch in "xyz"))
            dedup[key] = eq
        equations = [dedup[key] for key in sorted(dedup)]
        count = len(equations); total_equations += count
        if count == 0: zero += 1
        elif count == 1: one += 1
        else: two_plus += 1
        rows.append({
            "sha256": str(shader.get("sha256") or ""),
            "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
            "rowTripletCount": len(triplets),
            "explicitDirectionalEquationCount": count,
            "equations": equations,
        })
    return {
        "format": FORMAT,
        "sourceFormat": symbolic_v3.FORMAT,
        "shaders": rows,
        "summary": {
            "shaderCount": len(rows),
            "rowTripletCount": triplet_count,
            "explicitDirectionalEquationCount": total_equations,
            "zeroExplicitEquationShaderCount": zero,
            "oneExplicitEquationShaderCount": one,
            "twoOrMoreExplicitEquationShaderCount": two_plus,
            "rowsSha256": _jhash(rows),
        },
        "proofBoundary": (
            "Exact structural probe for the retained explicit directional-secondary-lightmap compiler encoding: "
            "three affine row coordinates, exact 1e-6 epsilon denominator, signed row2, saturated 3-term dot and final "
            "explicit RGB add/multiply form, with every matched RGB node required in corresponding o0 ancestry. "
            "Folded encoding is deliberately reported as unmatched; no algebraic rewrite or final lighting promotion occurs."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    source = json.loads(a.final_output.read_text(encoding="utf-8"))
    result = build(source)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
