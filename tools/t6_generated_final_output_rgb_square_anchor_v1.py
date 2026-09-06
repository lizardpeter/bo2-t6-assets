#!/usr/bin/env python3
"""Anchor the proven generated RGB-square stage inside full slot-4 output DAGs.

Generated/layered T6 color is composed in the retail encoded texture domain and
then explicitly squared per RGB channel before downstream lighting.  This tool
locates that already-proven boundary inside
``t6-generated-slot4-final-output-symbolic-v3`` without assigning any later
lighting equation.

A candidate must:
- be a literal DAG ``mul(X, X)`` (same child node on both operands);
- be reachable from the matching o0 RGB lane;
- depend on at least one exact ``colorMapSampler[1..3]`` texture;
- depend on no non-generated-color texture resource;
- contain exactly one RGB color-sample channel matching the output channel;
  color-map alpha samples are allowed because exact layer-weight DAGs use them.

Strict mode requires exactly one candidate for x, y and z in every shader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3

FORMAT = "t6-generated-final-output-rgb-square-anchor-v1"
COLOR_RE = re.compile(r"^colorMapSampler([1-3])?$")
RGB = "xyz"


class GeneratedFinalOutputRgbSquareAnchorError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _o0(shader: dict) -> list[dict]:
    rows = [row for row in shader.get("outputs", []) if int(row.get("register", -1)) == 0]
    if len(rows) != 1:
        raise GeneratedFinalOutputRgbSquareAnchorError(
            f"shader {shader.get('sha256')}: expected one o0 row, found {len(rows)}"
        )
    lanes = rows[0].get("lanes")
    if not isinstance(lanes, list) or len(lanes) != 4:
        raise GeneratedFinalOutputRgbSquareAnchorError("o0 row does not contain xyzw lanes")
    return lanes


def _reachable(nodes: list[dict], root: int) -> set[int]:
    seen: set[int] = set()
    visiting: set[int] = set()

    def walk(node_id: int) -> None:
        if node_id in seen:
            return
        if node_id in visiting:
            raise GeneratedFinalOutputRgbSquareAnchorError(
                f"DAG cycle while walking output root at node {node_id}"
            )
        if node_id < 0 or node_id >= len(nodes):
            raise GeneratedFinalOutputRgbSquareAnchorError(
                f"DAG references invalid node {node_id}"
            )
        visiting.add(node_id)
        node = nodes[node_id]
        if int(node.get("id", node_id)) != node_id:
            raise GeneratedFinalOutputRgbSquareAnchorError(
                f"non-dense node id {node.get('id')!r} at index {node_id}"
            )
        for child in node.get("args", []):
            walk(int(child))
        visiting.remove(node_id)
        seen.add(node_id)

    walk(int(root))
    return seen


def _samples(nodes: list[dict], root: int) -> list[dict]:
    out = []
    for node_id in sorted(_reachable(nodes, root)):
        node = nodes[node_id]
        if node.get("kind") == "textureSample":
            out.append(node)
    return out


def _canon(nodes: list[dict], root: int) -> str:
    memo: dict[int, Any] = {}

    def build(node_id: int):
        if node_id in memo:
            return memo[node_id]
        node = nodes[node_id]
        record = {
            key: value
            for key, value in node.items()
            if key not in ("id", "args", "instructionDword")
        }
        record["args"] = [build(int(child)) for child in node.get("args", [])]
        memo[node_id] = record
        return record

    return _jhash(build(int(root)))


def _candidate(nodes: list[dict], node_id: int, channel: str) -> dict | None:
    node = nodes[node_id]
    if node.get("kind") != "op" or node.get("op") != "mul":
        return None
    args = [int(x) for x in node.get("args", [])]
    if len(args) != 2 or args[0] != args[1]:
        return None
    source = args[0]
    samples = _samples(nodes, source)
    if not samples:
        return None
    resources = sorted({str(sample.get("resource") or "") for sample in samples})
    if any(not COLOR_RE.fullmatch(resource) for resource in resources):
        return None
    rgb_channels = {
        str(sample.get("channel") or "")
        for sample in samples
        if str(sample.get("channel") or "") in RGB
    }
    if rgb_channels != {channel}:
        return None
    bad_channels = {
        str(sample.get("channel") or "")
        for sample in samples
        if str(sample.get("channel") or "") not in (channel, "w")
    }
    if bad_channels:
        return None
    return {
        "squareNode": node_id,
        "encodedRgbNode": source,
        "channel": channel,
        "resources": resources,
        "sampleCount": len(samples),
        "sampleChannels": sorted({str(sample.get("channel") or "") for sample in samples}),
        "encodedRgbSha256": _canon(nodes, source),
        "squareSha256": _canon(nodes, node_id),
    }


def build(final_output: dict, *, strict: bool = True) -> dict:
    if final_output.get("format") != symbolic_v3.FORMAT:
        raise GeneratedFinalOutputRgbSquareAnchorError(
            f"unsupported final-output format {final_output.get('format')!r}"
        )
    shaders = final_output.get("shaders")
    if not isinstance(shaders, list) or not shaders:
        raise GeneratedFinalOutputRgbSquareAnchorError("final-output manifest has no shaders")

    rows = []
    candidate_count = 0
    ambiguity_count = 0
    missing_count = 0
    anchored_count = 0
    for shader in shaders:
        sha = str(shader.get("sha256") or "")
        nodes = shader.get("nodes")
        if not isinstance(nodes, list):
            raise GeneratedFinalOutputRgbSquareAnchorError(f"shader {sha}: nodes missing")
        lanes = _o0(shader)
        anchors = []
        for lane_index, channel in enumerate(RGB):
            lane = lanes[lane_index]
            if lane.get("channel") != channel or not bool(lane.get("written")):
                raise GeneratedFinalOutputRgbSquareAnchorError(
                    f"shader {sha}: o0.{channel} is not a written matching lane"
                )
            root = int(lane["node"])
            reachable = _reachable(nodes, root)
            candidates = []
            for node_id in sorted(reachable):
                item = _candidate(nodes, node_id, channel)
                if item is not None:
                    candidates.append(item)
            candidate_count += len(candidates)
            if len(candidates) == 0:
                missing_count += 1
            elif len(candidates) > 1:
                ambiguity_count += 1
            else:
                anchored_count += 1
            anchors.append({
                "channel": channel,
                "outputRootNode": root,
                "candidateCount": len(candidates),
                "candidates": candidates,
                "anchored": len(candidates) == 1,
            })
        if strict and any(not row["anchored"] for row in anchors):
            bad = [
                {"channel": row["channel"], "candidateCount": row["candidateCount"]}
                for row in anchors if not row["anchored"]
            ]
            raise GeneratedFinalOutputRgbSquareAnchorError(
                f"shader {sha}: RGB-square anchor is not unique for every lane: {bad}"
            )
        rows.append({
            "sha256": sha,
            "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
            "anchors": anchors,
            "allRgbChannelsAnchored": all(row["anchored"] for row in anchors),
        })

    summary = {
        "shaderCount": len(rows),
        "rgbLaneCount": 3 * len(rows),
        "candidateCount": candidate_count,
        "anchoredRgbLaneCount": anchored_count,
        "missingRgbLaneCount": missing_count,
        "ambiguousRgbLaneCount": ambiguity_count,
        "fullyAnchoredShaderCount": sum(1 for row in rows if row["allRgbChannelsAnchored"]),
        "strict": bool(strict),
        "rowsSha256": _jhash(rows),
    }
    if strict and summary["fullyAnchoredShaderCount"] != len(rows):
        raise GeneratedFinalOutputRgbSquareAnchorError("strict RGB-square anchoring incomplete")
    return {
        "format": FORMAT,
        "sourceFormat": symbolic_v3.FORMAT,
        "shaders": rows,
        "summary": summary,
        "proofBoundary": (
            "Structural anchor of the already-proven explicit generated RGB square inside complete final-output DAGs. "
            "Each anchor is a reachable mul(X,X) whose texture ancestry is exclusively exact colorMapSampler* and whose "
            "RGB sampled lane matches the output channel; alpha samples are permitted only as blend-weight inputs. "
            "This identifies the encoded-color -> squared-color boundary, not any downstream lighting equation."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--relaxed", action="store_true")
    a = p.parse_args()
    source = json.loads(a.final_output.read_text(encoding="utf-8"))
    result = build(source, strict=not a.relaxed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
