#!/usr/bin/env python3
"""Classify exact syntactic top-level generated o0.rgb terms by proven families.

This consumes the v36 topology plus already-proven direct-term sidecars and asks
one deliberately strict question: is each syntactic top-level ADD/NEG leaf itself
an exact known term node?

Recognized exact families:
- direct_squared_rgb_times_directional:
    leaf node == v35 literal two-input MUL(squareRgb, directionalRgb)
- direct_specular_times_reflection:
    leaf node == v34 literal two-input MUL(completedSpecular, reflectionSample)
- standalone_squared_rgb:
    leaf node == exact v26 squareRgb root
- standalone_directional_rgb:
    leaf node == exact v28 directional RGB root
- standalone_completed_specular:
    leaf node == exact v30 completed specular root
- standalone_reflection_sample:
    leaf node == exact v33 reflection sample node

A leaf that merely *contains* one or more anchors but has additional unproved
operations remains unclassified. ADD association is preserved from v36 and no
floating-point algebraic normalization is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FORMAT = "t6-generated-final-output-rgb-term-coverage-v1"
TOPOLOGY_FORMAT = "t6-generated-final-output-rgb-topology-v1"
PRODUCT_FORMAT = "t6-generated-final-output-diffuse-directional-product-probe-v1"
SR_FORMAT = "t6-generated-final-output-specular-reflection-join-v1"
FINAL_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
SQUARE_FORMAT = "t6-generated-final-output-rgb-square-anchor-v1"
DIR_FORMAT = "t6-generated-final-output-directional-lightmap-anchor-v2"
SPEC_FORMAT = "t6-generated-final-output-specular-state-anchor-v1"
REFL_FORMAT = "t6-generated-final-output-reflection-sample-index-v1"
RGB = "xyz"


class FinalRgbTermCoverageError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _shader_rows(doc: dict, *, field: str = "sha256") -> dict[str, dict]:
    out = {}
    for row in doc.get("shaders", []):
        key = str(row.get(field) or "")
        if not key or key in out:
            raise FinalRgbTermCoverageError(f"invalid/duplicate shader key {key!r}")
        out[key] = row
    return out


def _material_rows(doc: dict) -> dict[str, dict]:
    out = {}
    for row in doc.get("materials", []):
        material = str(row.get("material") or "")
        if not material or material in out:
            raise FinalRgbTermCoverageError(f"invalid/duplicate material {material!r}")
        out[material] = row
    return out


def _square_nodes(square_doc: dict) -> dict[str, dict[str, int]]:
    out = {}
    for sha, row in _shader_rows(square_doc).items():
        channels = {}
        for anchor in row.get("anchors", []):
            ch = str(anchor.get("channel") or "")
            if ch in RGB and bool(anchor.get("anchored")) and int(anchor.get("candidateCount", 0)) == 1:
                channels[ch] = int(anchor["candidates"][0]["squareNode"])
        if set(channels) != set(RGB):
            raise FinalRgbTermCoverageError(f"shader {sha}: incomplete square RGB roots")
        out[sha] = channels
    return out


def _directional_nodes(dir_doc: dict) -> dict[str, dict[str, set[int]]]:
    out = {}
    for sha, row in _shader_rows(dir_doc).items():
        channels = {ch: set() for ch in RGB}
        for eq in row.get("equations", []):
            rgb = eq.get("rgbNodes", {})
            if set(rgb) != set(RGB):
                raise FinalRgbTermCoverageError(f"shader {sha}: incomplete directional RGB roots")
            for ch in RGB:
                channels[ch].add(int(rgb[ch]))
        out[sha] = channels
    return out


def _specular_nodes(spec_doc: dict) -> dict[str, set[int]]:
    by_shader: dict[str, set[int]] = defaultdict(set)
    roots_by_shader: dict[str, dict[str, int]] = {}
    for row in spec_doc.get("materials", []):
        sha = str(row.get("shaderSha256") or "")
        roots = {ch: int(row.get("finalStateNodes", {}).get(ch, -1)) for ch in "xyzw"}
        old = roots_by_shader.get(sha)
        if old is not None and old != roots:
            raise FinalRgbTermCoverageError(f"shader {sha}: materials disagree on completed specular roots")
        roots_by_shader[sha] = roots
        by_shader[sha].update(roots.values())
    return dict(by_shader)


def _reflection_nodes(refl_doc: dict) -> dict[str, set[int]]:
    out = {}
    for sha, row in _shader_rows(refl_doc, field="shaderSha256").items():
        ids = set()
        for sample in row.get("samples", []):
            ids.update(int(x) for x in sample.get("sampleNodeIds", []))
        out[sha] = ids
    return out


def _diffuse_directional_products(product_doc: dict) -> dict[str, dict[str, set[int]]]:
    out = {}
    for sha, row in _shader_rows(product_doc).items():
        channels = {ch: set() for ch in RGB}
        for eq in row.get("equations", []):
            for ch, lane in eq.get("channels", {}).items():
                if ch not in RGB:
                    continue
                node = lane.get("directProductNode")
                if bool(lane.get("directProduct")) and node is not None:
                    channels[ch].add(int(node))
        out[sha] = channels
    return out


def _specular_reflection_products(sr_doc: dict) -> dict[str, dict[str, set[int]]]:
    # Several materials can share one exact shader. Require their direct-product
    # node sets to agree before promoting a shader-level exact term family.
    observed: dict[str, list[dict[str, set[int]]]] = defaultdict(list)
    for row in sr_doc.get("materials", []):
        sha = str(row.get("shaderSha256") or "")
        channels = {ch: set() for ch in RGB}
        for spec_ch, relations in row.get("channels", {}).items():
            for rel in relations:
                if not bool(rel.get("directSpecularTimesReflectionSample")):
                    continue
                site = int(rel["mixingSiteNode"])
                for out_ch in rel.get("outputLanes", []):
                    if out_ch in RGB:
                        channels[out_ch].add(site)
        observed[sha].append(channels)
    out = {}
    for sha, rows in observed.items():
        first = rows[0]
        if any(row != first for row in rows[1:]):
            raise FinalRgbTermCoverageError(
                f"shader {sha}: materials disagree on direct specular/reflection product nodes"
            )
        out[sha] = first
    return out


def _classify_leaf(
    *,
    sha: str,
    channel: str,
    node: int,
    dd_products,
    sr_products,
    square_nodes,
    dir_nodes,
    spec_nodes,
    refl_nodes,
) -> tuple[str, dict]:
    matches = []
    if node in dd_products.get(sha, {}).get(channel, set()):
        matches.append("direct_squared_rgb_times_directional")
    if node in sr_products.get(sha, {}).get(channel, set()):
        matches.append("direct_specular_times_reflection")
    if node == square_nodes.get(sha, {}).get(channel):
        matches.append("standalone_squared_rgb")
    if node in dir_nodes.get(sha, {}).get(channel, set()):
        matches.append("standalone_directional_rgb")
    if node in spec_nodes.get(sha, set()):
        matches.append("standalone_completed_specular")
    if node in refl_nodes.get(sha, set()):
        matches.append("standalone_reflection_sample")

    if len(matches) > 1:
        raise FinalRgbTermCoverageError(
            f"shader {sha} o0.{channel} leaf node {node}: overlaps exact term families {matches}"
        )
    if matches:
        return matches[0], {"exactNodeIdentity": True}
    return "unclassified", {"exactNodeIdentity": False}


def build(
    topology_doc: dict,
    product_doc: dict,
    sr_doc: dict,
    final_doc: dict,
    square_doc: dict,
    dir_doc: dict,
    spec_doc: dict,
    refl_doc: dict,
    *,
    strict: bool = False,
) -> dict:
    expected = (
        (topology_doc, TOPOLOGY_FORMAT, "topology"),
        (product_doc, PRODUCT_FORMAT, "diffuse-directional product"),
        (sr_doc, SR_FORMAT, "specular-reflection join"),
        (final_doc, FINAL_FORMAT, "final-output"),
        (square_doc, SQUARE_FORMAT, "square"),
        (dir_doc, DIR_FORMAT, "directional"),
        (spec_doc, SPEC_FORMAT, "specular"),
        (refl_doc, REFL_FORMAT, "reflection"),
    )
    for doc, fmt, label in expected:
        if doc.get("format") != fmt:
            raise FinalRgbTermCoverageError(
                f"unexpected {label} format {doc.get('format')!r}"
            )

    topology = _shader_rows(topology_doc)
    final = _shader_rows(final_doc)
    if set(topology) != set(final):
        raise FinalRgbTermCoverageError("topology/final shader sets disagree")
    dd_products = _diffuse_directional_products(product_doc)
    sr_products = _specular_reflection_products(sr_doc)
    square_nodes = _square_nodes(square_doc)
    dir_nodes = _directional_nodes(dir_doc)
    spec_nodes = _specular_nodes(spec_doc)
    refl_nodes = _reflection_nodes(refl_doc)

    rows = []
    family_counts = Counter()
    total = covered = unclassified = fully_covered_lanes = fully_covered_shaders = 0
    for sha in sorted(topology):
        source = topology[sha]
        lanes_out = {}
        shader_full = True
        for ch in RGB:
            lane = source.get("lanes", {}).get(ch)
            if not isinstance(lane, dict):
                raise FinalRgbTermCoverageError(f"shader {sha}: topology lacks o0.{ch}")
            leaves = []
            lane_full = True
            for leaf in lane.get("leaves", []):
                node = int(leaf["node"])
                family, proof = _classify_leaf(
                    sha=sha, channel=ch, node=node,
                    dd_products=dd_products, sr_products=sr_products,
                    square_nodes=square_nodes, dir_nodes=dir_nodes,
                    spec_nodes=spec_nodes, refl_nodes=refl_nodes,
                )
                total += 1
                family_counts[family] += 1
                is_covered = family != "unclassified"
                covered += int(is_covered)
                unclassified += int(not is_covered)
                lane_full = lane_full and is_covered
                leaves.append({
                    "path": leaf.get("path"),
                    "sign": int(leaf.get("sign", 1)),
                    "node": node,
                    "family": family,
                    "covered": is_covered,
                    "proof": proof,
                    "topologyAnchorTags": leaf.get("anchorTags", []),
                    "topologyResources": leaf.get("resources", []),
                })
            fully_covered_lanes += int(lane_full)
            shader_full = shader_full and lane_full
            lanes_out[ch] = {
                "leafCount": len(leaves),
                "coveredLeafCount": sum(1 for leaf in leaves if leaf["covered"]),
                "unclassifiedLeafCount": sum(1 for leaf in leaves if not leaf["covered"]),
                "fullyCovered": lane_full,
                "leaves": leaves,
            }
        fully_covered_shaders += int(shader_full)
        if strict and not shader_full:
            first = next(
                (ch for ch in RGB if not lanes_out[ch]["fullyCovered"]), "?"
            )
            raise FinalRgbTermCoverageError(
                f"shader {sha}: strict final RGB term coverage incomplete; first lane o0.{first}"
            )
        rows.append({
            "sha256": sha,
            "techniqueSets": source.get("techniqueSets", []),
            "lanes": lanes_out,
            "fullyCovered": shader_full,
        })

    summary = {
        "shaderCount": len(rows),
        "rgbLaneCount": 3 * len(rows),
        "syntacticLeafCount": total,
        "coveredLeafCount": covered,
        "unclassifiedLeafCount": unclassified,
        "fullyCoveredRgbLaneCount": fully_covered_lanes,
        "fullyCoveredShaderCount": fully_covered_shaders,
        "termFamilyCounts": dict(sorted(family_counts.items())),
        "strict": bool(strict),
    }
    return {
        "format": FORMAT,
        "shaders": rows,
        "summary": summary,
        "rowsSha256": _jhash(rows),
        "proofBoundary": (
            "Exact syntactic top-level o0.rgb leaf coverage. A leaf is covered only when its node identity equals "
            "a previously proven direct product or standalone anchor root. Deeper anchor ancestry does not count. "
            "ADD association/sign from v36 is preserved and no floating-point algebraic normalization is performed."
        ),
    }


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--topology',type=Path,required=True);p.add_argument('--diffuse-directional',type=Path,required=True);p.add_argument('--specular-reflection',type=Path,required=True);p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--directional',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--reflection-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--strict',action='store_true');a=p.parse_args();d=build(json.loads(a.topology.read_text()),json.loads(a.diffuse_directional.read_text()),json.loads(a.specular_reflection.read_text()),json.loads(a.final_output.read_text()),json.loads(a.rgb_square.read_text()),json.loads(a.directional.read_text()),json.loads(a.specular.read_text()),json.loads(a.reflection_index.read_text()),strict=a.strict);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
