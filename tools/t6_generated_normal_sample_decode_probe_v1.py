#!/usr/bin/env python3
"""Recover the exact affine XY decode applied to layered normal-map samples.

The existing retained layered-normal proof already identifies, per shader/layer,
the exact current normal XY pair immediately before the ordered normal recurrence.
This probe walks backward from that boundary to the largest subexpressions that
depend only on `normalMapSamplerN`, then solves each scalar as an affine function
of its exact X or Y sample:

    decoded = scale * sampledChannel + offset

No candidate scale/offset is hard-coded.  A uniform renderer decode is promoted
only if all retained normal-bearing shader/layer/channel observations resolve and
all independently produce the same affine pair.  Transformed layers are handled
before the 2x2 matrix dot by selecting the maximal resource-only descendants.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

import t6_dxbc_inspect_v1 as inspect
import t6_retail_layered_lmap_compositor_v1 as comp
import t6_retail_layered_normal_reconstruction_v1 as normal
import t6_retail_special_shader_payload_census_v1 as parser
import t6_retail_special_shdr_opcode_census_v1 as opcode
import t6_retail_special_shdr_operand_census_v1 as operand
import t6_retail_world_formats_45_proof_v1 as helper

FORMAT = "t6-generated-normal-sample-decode-probe-v1"


class NormalSampleDecodeProbeError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _f32_bits(value: float) -> str:
    return f"{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def _literal(dag, node_id: int) -> float | None:
    node = dag.n[node_id]
    if node.get("kind") != "lit":
        return None
    try:
        value = float(node["value"])
    except Exception:
        return None
    return value if math.isfinite(value) else None


def _sample_nodes(dag, root: int, resource: str, channel: str) -> list[int]:
    out: set[int] = set()
    seen: set[int] = set()
    def walk(node_id: int) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        node = dag.n[node_id]
        if (
            node.get("kind") == "sample"
            and str(node.get("resource") or "") == resource
            and str(node.get("channel") or "") == channel
        ):
            out.add(node_id)
        for child in node.get("args", []):
            walk(int(child))
    walk(root)
    return sorted(out)


def _affine(dag, root: int, sample_node: int, memo=None) -> tuple[float, float] | None:
    """Return (scale,offset) when root is affine in exactly one sample atom."""
    memo = {} if memo is None else memo
    key = (root, sample_node)
    if key in memo:
        return memo[key]
    if root == sample_node:
        memo[key] = (1.0, 0.0)
        return memo[key]
    node = dag.n[root]
    kind = str(node.get("kind") or "")
    lit = _literal(dag, root)
    if lit is not None:
        memo[key] = (0.0, lit)
        return memo[key]
    args = [int(value) for value in node.get("args", [])]
    result = None
    if kind == "neg" and len(args) == 1:
        q = _affine(dag, args[0], sample_node, memo)
        if q is not None:
            result = (-q[0], -q[1])
    elif kind == "add" and len(args) == 2:
        a = _affine(dag, args[0], sample_node, memo)
        b = _affine(dag, args[1], sample_node, memo)
        if a is not None and b is not None:
            result = (a[0] + b[0], a[1] + b[1])
    elif kind == "mul" and len(args) == 2:
        a = _affine(dag, args[0], sample_node, memo)
        b = _affine(dag, args[1], sample_node, memo)
        if a is not None and b is not None:
            # Product stays affine only when at least one operand is constant.
            if a[0] == 0.0:
                result = (a[1] * b[0], a[1] * b[1])
            elif b[0] == 0.0:
                result = (b[1] * a[0], b[1] * a[1])
    memo[key] = result
    return result


def _maximal_resource_only(comp_module, dag, root: int, resource: str) -> list[int]:
    cache: dict[int, set[str]] = {}
    def resources(node_id: int) -> set[str]:
        if node_id not in cache:
            cache[node_id] = set(comp_module.value_resources(dag, node_id))
        return cache[node_id]
    def walk(node_id: int) -> list[int]:
        rs = resources(node_id)
        if rs == {resource}:
            return [node_id]
        out: list[int] = []
        for child in dag.n[node_id].get("args", []):
            child = int(child)
            if resource in resources(child):
                out.extend(walk(child))
        return out
    return sorted(set(walk(root)))


def _decode_boundary(comp_module, dag, pair: list[int], resource: str) -> dict[str, int]:
    candidates: dict[str, set[int]] = {"x": set(), "y": set()}
    for root in pair:
        for node_id in _maximal_resource_only(comp_module, dag, int(root), resource):
            channels = normal.sample_channels(comp_module, dag, node_id, resource)
            if channels == {"x"}:
                candidates["x"].add(node_id)
            elif channels == {"y"}:
                candidates["y"].add(node_id)
    out: dict[str, int] = {}
    for channel in ("x", "y"):
        nodes = sorted(candidates[channel])
        # The same decoded scalar can feed both transformed dot outputs. Canonical
        # DAG interning generally collapses it; if several remain, require equal
        # canonical hashes and choose the lowest stable node id.
        if not nodes:
            raise NormalSampleDecodeProbeError(
                f"{resource}.{channel}: no resource-only decode boundary found"
            )
        hashes = {comp_module.canon_hash(dag, node_id) for node_id in nodes}
        if len(hashes) != 1:
            raise NormalSampleDecodeProbeError(
                f"{resource}.{channel}: ambiguous decode boundary nodes {nodes}"
            )
        out[channel] = nodes[0]
    return out


def _classify_scalar(dag, node_id: int, resource: str, channel: str) -> dict:
    samples = _sample_nodes(dag, node_id, resource, channel)
    if len(samples) != 1:
        raise NormalSampleDecodeProbeError(
            f"{resource}.{channel}: decode boundary contains {len(samples)} exact sample atoms"
        )
    sample_node = samples[0]
    affine = _affine(dag, node_id, sample_node)
    if affine is None:
        raise NormalSampleDecodeProbeError(
            f"{resource}.{channel}: decode boundary is not affine in its sampled channel"
        )
    scale, offset = affine
    if not math.isfinite(scale) or not math.isfinite(offset):
        raise NormalSampleDecodeProbeError(f"{resource}.{channel}: non-finite affine decode")
    return {
        "channel": channel,
        "boundaryNode": node_id,
        "sampleNode": sample_node,
        "boundarySha256": comp.canon_hash(dag, node_id),
        "scale": scale,
        "offset": offset,
        "scaleFloat32Bits": _f32_bits(scale),
        "offsetFloat32Bits": _f32_bits(offset),
    }


def build(root: Path) -> dict:
    _, unique = comp.collect(Path(root), parser, helper)
    rows = []
    observed: dict[tuple[str, str], int] = {}
    shader_count = layer_count = channel_count = 0

    for shader_sha, q in sorted(unique.items()):
        technique = str(q["techniqueSet"])
        specs = comp.specs(technique)
        normal_layers = [(layer, mode, flags) for layer, mode, flags in specs if "n" in flags]
        if not normal_layers:
            continue
        shader_count += 1
        dag = comp.symbolic(q["blob"], opcode, operand, inspect)
        sequence = comp.sequence(dag, comp.mode_sig(technique), "x")
        if not sequence:
            raise NormalSampleDecodeProbeError(f"{technique!r}: RGB compositor sequence unresolved")
        weights = sequence[0][1]
        shader_rows = []
        for layer, mode, flags in normal_layers:
            resource = f"normalMapSampler{layer}"
            try:
                pair = normal.current_pair(comp, dag, layer, weights[layer - 1])
                boundary = _decode_boundary(comp, dag, pair, resource)
                x = _classify_scalar(dag, boundary["x"], resource, "x")
                y = _classify_scalar(dag, boundary["y"], resource, "y")
            except Exception as exc:
                raise NormalSampleDecodeProbeError(
                    f"{technique!r} layer {layer}: normal sample decode proof failed: {exc}"
                ) from exc
            for item in (x, y):
                key = (item["scaleFloat32Bits"], item["offsetFloat32Bits"])
                observed[key] = observed.get(key, 0) + 1
                channel_count += 1
            shader_rows.append({
                "layerIndex": layer,
                "mode": mode,
                "flags": flags,
                "resource": resource,
                "currentPairSha256": _jhash([comp.canon_hash(dag, int(node)) for node in pair]),
                "decode": {"x": x, "y": y},
            })
            layer_count += 1
        rows.append({
            "sha256": shader_sha,
            "techniqueSet": technique,
            "worldVertFormat": int(q["format"]),
            "normalLayers": shader_rows,
        })

    distribution = [
        {
            "scaleFloat32Bits": scale,
            "offsetFloat32Bits": offset,
            "observationCount": count,
        }
        for (scale, offset), count in sorted(observed.items())
    ]
    uniform = len(distribution) == 1 and channel_count > 0
    uniform_decode = None
    if uniform:
        first = rows[0]["normalLayers"][0]["decode"]["x"]
        uniform_decode = {
            "scale": first["scale"],
            "offset": first["offset"],
            "scaleFloat32Bits": first["scaleFloat32Bits"],
            "offsetFloat32Bits": first["offsetFloat32Bits"],
            "equation": "decodedChannel = sampledChannel * scale + offset",
        }
    summary = {
        "shaderCount": shader_count,
        "normalLayerCount": layer_count,
        "channelDecodeObservationCount": channel_count,
        "affineDecodeFailureCount": 0,
        "uniqueAffineDecodeCount": len(distribution),
        "uniformAffineDecode": uniform,
        "rowsSha256": _jhash(rows),
    }
    return {
        "format": FORMAT,
        "producer": "tools/t6_generated_normal_sample_decode_probe_v1.py",
        "sourceSlot4ShaderSetSha256": "f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799",
        "summary": summary,
        "uniformDecode": uniform_decode,
        "decodeDistribution": distribution,
        "rows": rows,
        "proofBoundary": (
            "Direct retained symbolic-DXBC ancestry from each layered normal current-pair boundary back to the exact "
            "normalMapSamplerN X/Y sample atoms. Scale/offset are observed, not assumed; only a single affine pair across "
            "every retained normal channel is promoted as uniform. Texture storage/color-space staging remains separate."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("/mnt/data/t6_xanim_corpus"))
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    doc = build(a.root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print(json.dumps(doc["uniformDecode"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
