#!/usr/bin/env python3
"""Census exact structural shapes of still-unclassified generated o0.rgb terms.

Consumes the v37/v2 exact term-coverage sidecar plus the authoritative final DAG
and anchor sidecars. Only leaves explicitly classified ``unclassified`` are
examined.

For each remaining leaf this records:
- exact root kind/opcode/operation and original o0 lane/path/sign;
- exact texture-resource ancestry;
- exact anchor ancestry (square RGB, directional equation, completed specular,
  reflection sample);
- ordered immediate-child profiles, including whether each child *is itself* an
  exact anchor root versus merely contains an anchor deeper in its subtree;
- literal32 bits for immediate literal children.

No new semantic family is promoted. Repeated structures are grouped by a stable
profile SHA so the next matcher can target observed retail shapes rather than a
guessed lighting formula.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FORMAT = "t6-generated-final-output-unclassified-term-census-v1"
COVERAGE_FORMAT = "t6-generated-final-output-rgb-term-coverage-v2"
FINAL_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
SQUARE_FORMAT = "t6-generated-final-output-rgb-square-anchor-v1"
DIR_FORMAT = "t6-generated-final-output-directional-lightmap-anchor-v2"
SPEC_FORMAT = "t6-generated-final-output-specular-state-anchor-v1"
REFL_FORMAT = "t6-generated-final-output-reflection-sample-index-v1"
RGB = "xyz"


class UnclassifiedTermCensusError(RuntimeError):
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
            raise UnclassifiedTermCensusError(f"invalid/duplicate shader key {key!r}")
        out[key] = row
    return out


def _nodes(shader: dict) -> dict[int, dict]:
    out = {}
    for row in shader.get("nodes", []):
        node = int(row.get("id", -1))
        if node < 0 or node in out:
            raise UnclassifiedTermCensusError(f"invalid/duplicate DAG node {node}")
        out[node] = row
    return out


def _anc(nodes: dict[int, dict], root: int, memo: dict[int, set[int]]) -> set[int]:
    if root in memo:
        return memo[root]
    seen = set()
    def walk(node: int) -> None:
        if node in seen:
            return
        if node not in nodes:
            raise UnclassifiedTermCensusError(f"DAG references missing node {node}")
        seen.add(node)
        for child in nodes[node].get("args", []):
            walk(int(child))
    walk(root)
    memo[root] = seen
    return seen


def _resources(nodes: dict[int, dict], root: int, memo: dict[int, frozenset[str]]) -> set[str]:
    if root in memo:
        return set(memo[root])
    row = nodes[root]
    out = set()
    if row.get("kind") == "textureSample":
        resource = str(row.get("resource") or "")
        if resource:
            out.add(resource)
    for child in row.get("args", []):
        out.update(_resources(nodes, int(child), memo))
    memo[root] = frozenset(out)
    return out


def _square_roots(doc: dict) -> dict[str, dict[str, int]]:
    out = {}
    for sha, row in _shader_rows(doc).items():
        channels = {}
        for anchor in row.get("anchors", []):
            ch = str(anchor.get("channel") or "")
            if ch in RGB and bool(anchor.get("anchored")) and int(anchor.get("candidateCount", 0)) == 1:
                channels[ch] = int(anchor["candidates"][0]["squareNode"])
        out[sha] = channels
    return out


def _directional_roots(doc: dict) -> dict[str, dict[str, dict[int, int]]]:
    out = {}
    for sha, row in _shader_rows(doc).items():
        channels = {ch: {} for ch in RGB}
        for index, eq in enumerate(row.get("equations", [])):
            for ch, node in eq.get("rgbNodes", {}).items():
                if ch in RGB:
                    channels[ch][index] = int(node)
        out[sha] = channels
    return out


def _specular_roots(doc: dict) -> dict[str, dict[str, int]]:
    out = {}
    for row in doc.get("materials", []):
        sha = str(row.get("shaderSha256") or "")
        roots = {ch: int(row.get("finalStateNodes", {}).get(ch, -1)) for ch in "xyzw"}
        old = out.get(sha)
        if old is not None and old != roots:
            raise UnclassifiedTermCensusError(
                f"shader {sha}: materials disagree on completed specular roots"
            )
        out[sha] = roots
    return out


def _reflection_roots(doc: dict) -> dict[str, set[int]]:
    out = {}
    for sha, row in _shader_rows(doc, field="shaderSha256").items():
        roots = set()
        for sample in row.get("samples", []):
            roots.update(int(x) for x in sample.get("sampleNodeIds", []))
        out[sha] = roots
    return out


def _anchor_profile(
    sha: str,
    lane: str,
    node: int,
    ancestors: set[int],
    squares,
    directionals,
    speculars,
    reflections,
) -> tuple[list[str], list[str]]:
    exact = []
    ancestry = []
    square = squares.get(sha, {}).get(lane)
    if square is not None:
        if node == square:
            exact.append("squareRgb")
        if square in ancestors:
            ancestry.append("squareRgb")
    for index, root in sorted(directionals.get(sha, {}).get(lane, {}).items()):
        tag = f"directional:{index}"
        if node == root:
            exact.append(tag)
        if root in ancestors:
            ancestry.append(tag)
    for ch, root in sorted(speculars.get(sha, {}).items()):
        tag = f"specular:{ch}"
        if node == root:
            exact.append(tag)
        if root in ancestors:
            ancestry.append(tag)
    refl = reflections.get(sha, set())
    if node in refl:
        exact.append("reflectionProbe")
    if ancestors & refl:
        ancestry.append("reflectionProbe")
    return exact, ancestry


def _child_profile(
    sha: str,
    lane: str,
    nodes: dict[int, dict],
    child: int,
    amemo,
    rmemo,
    squares,
    directionals,
    speculars,
    reflections,
) -> dict:
    row = nodes[child]
    anc = _anc(nodes, child, amemo)
    exact, ancestry = _anchor_profile(
        sha, lane, child, anc,
        squares, directionals, speculars, reflections,
    )
    profile = {
        "node": child,
        "kind": row.get("kind"),
        "operation": row.get("op") if row.get("kind") == "op" else row.get("opcode") if row.get("kind") == "textureSample" else None,
        "exactAnchorTags": exact,
        "ancestryAnchorTags": ancestry,
        "resources": sorted(_resources(nodes, child, rmemo)),
    }
    if row.get("kind") == "literal32":
        profile["literal32Bits"] = str(row.get("bits") or "").lower()
    if row.get("kind") == "textureSample":
        profile["textureResource"] = str(row.get("resource") or "")
        profile["textureChannel"] = str(row.get("channel") or "")
    return profile


def _signature_profile(row: dict) -> dict:
    # Strip node/path identities while preserving exact ordered shape/anchors/resources.
    children = []
    for child in row["immediateChildren"]:
        children.append({
            key: child.get(key)
            for key in (
                "kind", "operation", "exactAnchorTags", "ancestryAnchorTags",
                "resources", "literal32Bits", "textureResource", "textureChannel",
            )
            if child.get(key) is not None
        })
    return {
        "lane": row["lane"],
        "sign": row["sign"],
        "kind": row["kind"],
        "operation": row["operation"],
        "exactAnchorTags": row["exactAnchorTags"],
        "ancestryAnchorTags": row["ancestryAnchorTags"],
        "resources": row["resources"],
        "immediateChildren": children,
    }


def build(coverage_doc: dict, final_doc: dict, square_doc: dict, dir_doc: dict, spec_doc: dict, refl_doc: dict) -> dict:
    for doc, fmt, label in (
        (coverage_doc, COVERAGE_FORMAT, "coverage"),
        (final_doc, FINAL_FORMAT, "final-output"),
        (square_doc, SQUARE_FORMAT, "square"),
        (dir_doc, DIR_FORMAT, "directional"),
        (spec_doc, SPEC_FORMAT, "specular"),
        (refl_doc, REFL_FORMAT, "reflection"),
    ):
        if doc.get("format") != fmt:
            raise UnclassifiedTermCensusError(
                f"unexpected {label} format {doc.get('format')!r}"
            )
    coverage = _shader_rows(coverage_doc)
    final = _shader_rows(final_doc)
    if set(coverage) != set(final):
        raise UnclassifiedTermCensusError("coverage/final shader sets disagree")
    squares = _square_roots(square_doc)
    directionals = _directional_roots(dir_doc)
    speculars = _specular_roots(spec_doc)
    reflections = _reflection_roots(refl_doc)

    rows = []
    operation_counts = Counter()
    anchor_counts = Counter()
    resource_signature_counts = Counter()
    groups: dict[str, dict] = {}
    observed_unclassified = 0
    for sha in sorted(coverage):
        shader = final[sha]
        nodes = _nodes(shader)
        amemo = {}; rmemo = {}
        for lane in RGB:
            c_lane = coverage[sha].get("lanes", {}).get(lane)
            if not isinstance(c_lane, dict):
                raise UnclassifiedTermCensusError(f"shader {sha}: coverage lacks lane {lane}")
            for leaf in c_lane.get("leaves", []):
                if str(leaf.get("family") or "") != "unclassified":
                    continue
                observed_unclassified += 1
                node = int(leaf["node"])
                if node not in nodes:
                    raise UnclassifiedTermCensusError(
                        f"shader {sha} lane {lane}: unclassified node {node} absent from final DAG"
                    )
                dag = nodes[node]
                anc = _anc(nodes, node, amemo)
                exact, ancestry = _anchor_profile(
                    sha, lane, node, anc,
                    squares, directionals, speculars, reflections,
                )
                children = [
                    _child_profile(
                        sha, lane, nodes, int(child), amemo, rmemo,
                        squares, directionals, speculars, reflections,
                    )
                    for child in dag.get("args", [])
                ]
                resources = sorted(_resources(nodes, node, rmemo))
                operation = dag.get("op") if dag.get("kind") == "op" else dag.get("opcode") if dag.get("kind") == "textureSample" else None
                row = {
                    "sha256": sha,
                    "techniqueSets": shader.get("techniqueSets", []),
                    "lane": lane,
                    "path": leaf.get("path"),
                    "sign": int(leaf.get("sign", 1)),
                    "node": node,
                    "kind": dag.get("kind"),
                    "operation": operation,
                    "exactAnchorTags": exact,
                    "ancestryAnchorTags": ancestry,
                    "resources": resources,
                    "immediateChildren": children,
                }
                profile = _signature_profile(row)
                signature = _jhash(profile)
                row["structuralProfileSha256"] = signature
                rows.append(row)
                operation_counts[f"{row['kind']}:{operation}"] += 1
                anchor_counts["+".join(ancestry) if ancestry else "none"] += 1
                resource_signature_counts["+".join(resources) if resources else "none"] += 1
                group = groups.get(signature)
                if group is None:
                    groups[signature] = {
                        "structuralProfileSha256": signature,
                        "count": 1,
                        "profile": profile,
                        "representative": {
                            "sha256": sha,
                            "lane": lane,
                            "path": leaf.get("path"),
                            "node": node,
                        },
                    }
                else:
                    group["count"] += 1

    expected_unclassified = int(coverage_doc.get("summary", {}).get("unclassifiedLeafCount", -1))
    if expected_unclassified != observed_unclassified:
        raise UnclassifiedTermCensusError(
            f"coverage summary unclassifiedLeafCount {expected_unclassified} != observed {observed_unclassified}"
        )
    signature_groups = sorted(groups.values(), key=lambda row: (-int(row["count"]), row["structuralProfileSha256"]))
    summary = {
        "shaderCount": len(coverage),
        "unclassifiedLeafCount": observed_unclassified,
        "structuralSignatureCount": len(signature_groups),
        "rootOperationCounts": dict(sorted(operation_counts.items())),
        "anchorAncestrySignatureCounts": dict(sorted(anchor_counts.items())),
        "resourceSignatureCounts": dict(sorted(resource_signature_counts.items())),
    }
    return {
        "format": FORMAT,
        "terms": rows,
        "signatureGroups": signature_groups,
        "summary": summary,
        "rowsSha256": _jhash(rows),
        "proofBoundary": (
            "Forensic census of only v37-unclassified exact top-level o0.rgb leaves. Root/child operation order, "
            "resource ancestry, exact-anchor identity, and deeper anchor ancestry are preserved. Structural grouping "
            "does not promote a semantic family or algebraically normalize the shader."
        ),
    }


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--coverage',type=Path,required=True);p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--directional',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--reflection-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.coverage.read_text()),json.loads(a.final_output.read_text()),json.loads(a.rgb_square.read_text()),json.loads(a.directional.read_text()),json.loads(a.specular.read_text()),json.loads(a.reflection_index.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
