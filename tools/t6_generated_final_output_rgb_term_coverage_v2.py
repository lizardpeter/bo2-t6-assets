#!/usr/bin/env python3
"""Final RGB syntactic term coverage v2: exact DAG-reference preflight.

v1 classifies top-level o0.rgb leaves only when the leaf node itself equals a
previously proven term/anchor node. v2 adds an independent trust-boundary pass:
every node referenced by every contributing sidecar must physically exist in the
same exact full-output shader DAG before v1 classification is allowed.

This prevents an integer copied between sidecars from being treated as an exact
node identity if the referenced node is absent from the authoritative DAG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import t6_generated_final_output_rgb_term_coverage_v1 as v1

FORMAT = "t6-generated-final-output-rgb-term-coverage-v2"


class FinalRgbTermCoverageV2Error(RuntimeError):
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
            raise FinalRgbTermCoverageV2Error(f"invalid/duplicate shader key {key!r}")
        out[key] = row
    return out


def _node_sets(final_doc: dict) -> dict[str, set[int]]:
    if final_doc.get("format") != v1.FINAL_FORMAT:
        raise FinalRgbTermCoverageV2Error(
            f"unexpected final-output format {final_doc.get('format')!r}"
        )
    out = {}
    for sha, shader in _shader_rows(final_doc).items():
        ids = set()
        for row in shader.get("nodes", []):
            node = int(row.get("id", -1))
            if node < 0 or node in ids:
                raise FinalRgbTermCoverageV2Error(
                    f"shader {sha}: invalid/duplicate authoritative DAG node {node}"
                )
            ids.add(node)
        if not ids:
            raise FinalRgbTermCoverageV2Error(f"shader {sha}: authoritative DAG has no nodes")
        out[sha] = ids
    return out


def _require(node_sets: dict[str, set[int]], sha: str, node: int, label: str) -> None:
    nodes = node_sets.get(sha)
    if nodes is None:
        raise FinalRgbTermCoverageV2Error(f"{label}: shader {sha} absent from authoritative DAG")
    if int(node) not in nodes:
        raise FinalRgbTermCoverageV2Error(
            f"{label}: shader {sha} references absent authoritative DAG node {int(node)}"
        )


def preflight(
    topology_doc: dict,
    product_doc: dict,
    sr_doc: dict,
    final_doc: dict,
    square_doc: dict,
    dir_doc: dict,
    spec_doc: dict,
    refl_doc: dict,
) -> dict:
    node_sets = _node_sets(final_doc)
    checks = 0

    # v36 syntactic leaf identities.
    for sha, row in _shader_rows(topology_doc).items():
        for ch, lane in row.get("lanes", {}).items():
            for leaf in lane.get("leaves", []):
                _require(node_sets, sha, int(leaf["node"]), f"topology o0.{ch} leaf")
                checks += 1
            root = lane.get("outputRootNode")
            if root is not None:
                _require(node_sets, sha, int(root), f"topology o0.{ch} root")
                checks += 1

    # v35 direct square*directional products and their operands.
    for sha, row in _shader_rows(product_doc).items():
        for eq in row.get("equations", []):
            for ch, lane in eq.get("channels", {}).items():
                for key in ("squareNode", "directionalRgbNode"):
                    if lane.get(key) is not None:
                        _require(node_sets, sha, int(lane[key]), f"v35 {ch} {key}")
                        checks += 1
                if lane.get("directProductNode") is not None:
                    _require(node_sets, sha, int(lane["directProductNode"]), f"v35 {ch} directProductNode")
                    checks += 1

    # v34 same-sample specular/reflection joins are material keyed.
    for row in sr_doc.get("materials", []):
        sha = str(row.get("shaderSha256") or "")
        for spec_ch, relations in row.get("channels", {}).items():
            for rel in relations:
                for key in ("specularRootNode", "mixingSiteNode", "reflectionSampleNode"):
                    if rel.get(key) is not None:
                        _require(node_sets, sha, int(rel[key]), f"v34 {spec_ch} {key}")
                        checks += 1

    # v26 exact square roots.
    for sha, row in _shader_rows(square_doc).items():
        for anchor in row.get("anchors", []):
            for candidate in anchor.get("candidates", []):
                for key in ("squareNode", "encodedRgbNode"):
                    if candidate.get(key) is not None:
                        _require(node_sets, sha, int(candidate[key]), f"v26 {key}")
                        checks += 1

    # v28 directional RGB and normal counterpart roots.
    for sha, row in _shader_rows(dir_doc).items():
        for eq in row.get("equations", []):
            for ch, node in eq.get("rgbNodes", {}).items():
                _require(node_sets, sha, int(node), f"v28 directional rgb {ch}")
                checks += 1
            for ch, node in eq.get("normalNodes", {}).items():
                _require(node_sets, sha, int(node), f"v28 directional normal {ch}")
                checks += 1

    # v30 completed specular roots.
    for row in spec_doc.get("materials", []):
        sha = str(row.get("shaderSha256") or "")
        for ch, node in row.get("finalStateNodes", {}).items():
            _require(node_sets, sha, int(node), f"v30 completed specular {ch}")
            checks += 1

    # v33 exact reflection sample nodes and operand nodes.
    for sha, row in _shader_rows(refl_doc, field="shaderSha256").items():
        for sample in row.get("samples", []):
            for key in ("sampleNodeIds", "coordinateNodes", "extraOperandNodes"):
                for node in sample.get(key, []):
                    _require(node_sets, sha, int(node), f"v33 reflection {key}")
                    checks += 1
            source = sample.get("classification", {}).get("sourceNode")
            if source is not None:
                _require(node_sets, sha, int(source), "v33 reflection affine sourceNode")
                checks += 1

    return {
        "authoritativeShaderCount": len(node_sets),
        "nodeReferenceCheckCount": checks,
        "allReferencedNodesExist": True,
    }


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
    proof = preflight(
        topology_doc, product_doc, sr_doc, final_doc,
        square_doc, dir_doc, spec_doc, refl_doc,
    )
    base = v1.build(
        topology_doc, product_doc, sr_doc, final_doc,
        square_doc, dir_doc, spec_doc, refl_doc,
        strict=strict,
    )
    if base.get("format") != v1.FORMAT:
        raise FinalRgbTermCoverageV2Error(
            f"unexpected v1 coverage result {base.get('format')!r}"
        )
    out = dict(base)
    out["format"] = FORMAT
    out["sourceCoverageFormat"] = v1.FORMAT
    out["authoritativeDagPreflight"] = proof
    out["proofBoundary"] = (
        str(base.get("proofBoundary") or "")
        + " v2 additionally requires every topology/anchor/product/specular/reflection node reference "
          "to exist in the authoritative full-output DAG for the same exact shader SHA."
    )
    out["documentSha256"] = _jhash({k: out[k] for k in sorted(out) if k != "documentSha256"})
    return out


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--topology',type=Path,required=True);p.add_argument('--diffuse-directional',type=Path,required=True);p.add_argument('--specular-reflection',type=Path,required=True);p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--directional',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--reflection-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--strict',action='store_true');a=p.parse_args();docs=[json.loads(x.read_text()) for x in (a.topology,a.diffuse_directional,a.specular_reflection,a.final_output,a.rgb_square,a.directional,a.specular,a.reflection_index)];d=build(*docs,strict=a.strict);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps({**d['summary'],**d['authoritativeDagPreflight']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
