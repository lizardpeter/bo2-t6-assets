#!/usr/bin/env python3
"""Unclassified final-RGB census v3: exact cbuffer-identity enrichment.

v2 groups still-unknown top-level o0.rgb terms by exact channel-agnostic
operation/resource/anchor shape. v3 preserves those v2 rows and grouping hashes,
then resolves every constant-buffer symbol in each unknown term's authoritative
DAG ancestry through the production v39 RDEF/.tech sidecar.

Each dependency retains both levels of identity:
- raw shader symbol/node: cbN[R].component and exact DAG node id;
- reflected identity: cbuffer name, variable byte range, relative scalar index,
  and exact `.tech` assignment expression/source class where present.

No meaning is inferred from names. A second cbuffer-enriched structural grouping
is emitted alongside the untouched v2 grouping so constant identity can split or
merge observed unknown shapes without destroying the earlier forensic evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import t6_generated_final_output_unclassified_term_census_v2 as v2

FORMAT = "t6-generated-final-output-unclassified-term-census-v3"
FINAL_FORMAT = "t6-generated-slot4-final-output-symbolic-v3"
CBUFFER_FORMAT = "t6-generated-final-output-cbuffer-signature-v1"


class UnclassifiedTermCensusV3Error(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _shader_rows(doc: dict, *, label: str) -> dict[str, dict]:
    out = {}
    for row in doc.get("shaders", []):
        sha = str(row.get("sha256") or "")
        if not sha or sha in out:
            raise UnclassifiedTermCensusV3Error(f"{label}: invalid/duplicate shader key {sha!r}")
        out[sha] = row
    return out


def _node_table(shader: dict) -> dict[int, dict]:
    out = {}
    for row in shader.get("nodes", []):
        node_id = int(row.get("id", -1))
        if node_id < 0 or node_id in out:
            raise UnclassifiedTermCensusV3Error(f"invalid/duplicate final DAG node {node_id}")
        out[node_id] = row
    return out


def _cbuffer_node_map(row: dict) -> dict[int, dict]:
    out = {}
    for item in row.get("usedCbufferSymbols", []):
        symbol = str(item.get("symbol") or "")
        if not symbol:
            raise UnclassifiedTermCensusV3Error("cbuffer sidecar contains empty symbol")
        identity = {
            "symbol": symbol,
            "bindPoint": int(item.get("bindPoint", -1)),
            "register": int(item.get("register", -1)),
            "registerComponent": item.get("registerComponent"),
            "registerComponentIndex": int(item.get("registerComponentIndex", -1)),
            "byteOffset": int(item.get("byteOffset", -1)),
            "buffer": copy.deepcopy(item.get("buffer")),
            "variable": copy.deepcopy(item.get("variable")),
            "techniqueAssignments": copy.deepcopy(item.get("techniqueAssignments", [])),
        }
        for node in item.get("nodeIds", []):
            node_id = int(node)
            old = out.get(node_id)
            if old is not None and old != identity:
                raise UnclassifiedTermCensusV3Error(
                    f"cbuffer node {node_id} maps to conflicting reflected identities"
                )
            out[node_id] = identity
    return out


def _reachable(nodes: dict[int, dict], root: int) -> set[int]:
    seen: set[int] = set()
    visiting: set[int] = set()
    def walk(node_id: int) -> None:
        if node_id in seen:
            return
        if node_id in visiting:
            raise UnclassifiedTermCensusV3Error(f"cycle at DAG node {node_id}")
        if node_id not in nodes:
            raise UnclassifiedTermCensusV3Error(f"DAG references missing node {node_id}")
        visiting.add(node_id)
        for child in nodes[node_id].get("args", []):
            walk(int(child))
        visiting.remove(node_id)
        seen.add(node_id)
    walk(int(root))
    return seen


def _dependency_rows(nodes: dict[int, dict], cbmap: dict[int, dict], root: int) -> list[dict]:
    out = []
    for node_id in sorted(_reachable(nodes, root)):
        row = nodes[node_id]
        if row.get("kind") != "symbol" or not str(row.get("name") or "").startswith("cb"):
            continue
        identity = cbmap.get(node_id)
        if identity is None:
            raise UnclassifiedTermCensusV3Error(
                f"final DAG cbuffer node {node_id} {row.get('name')!r} is absent from exact cbuffer sidecar"
            )
        if str(identity["symbol"]) != str(row.get("name") or ""):
            raise UnclassifiedTermCensusV3Error(
                f"final DAG cbuffer node {node_id} symbol {row.get('name')!r} != sidecar {identity['symbol']!r}"
            )
        out.append({"node": node_id, **copy.deepcopy(identity)})
    return out


def _assignment_shape(rows: list[dict]) -> list[dict]:
    out = []
    for item in rows:
        assignments = [
            {
                "sourceClass": row.get("sourceClass"),
                "sourceExpression": row.get("sourceExpression"),
                "sourceName": row.get("sourceName"),
            }
            for row in item.get("techniqueAssignments", [])
        ]
        # TechniqueSet names are shader ownership proof, but excluding them here
        # lets exact same variable/source identity group across equivalent rows.
        out.append({
            "symbol": item.get("symbol"),
            "bindPoint": item.get("bindPoint"),
            "register": item.get("register"),
            "registerComponent": item.get("registerComponent"),
            "byteOffset": item.get("byteOffset"),
            "bufferName": (item.get("buffer") or {}).get("name"),
            "variableName": (item.get("variable") or {}).get("name"),
            "variableStartOffset": (item.get("variable") or {}).get("startOffset"),
            "variableSize": (item.get("variable") or {}).get("size"),
            "relativeByteOffset": (item.get("variable") or {}).get("relativeByteOffset"),
            "relativeScalarIndex": (item.get("variable") or {}).get("relativeScalarIndex"),
            "assignments": assignments,
        })
    return out


def _child_shape(child: dict) -> dict:
    base = {
        key: copy.deepcopy(child.get(key))
        for key in (
            "kind", "operation", "exactAnchorTags", "ancestryAnchorTags",
            "resources", "literal32Bits", "textureResource", "textureChannel",
        )
        if child.get(key) is not None
    }
    deps = child.get("cbufferDependenciesV1", [])
    if deps:
        base["cbufferDependencies"] = _assignment_shape(deps)
    return base


def enriched_structural_profile(term: dict) -> dict:
    profile = v2.structural_profile(term)
    deps = term.get("cbufferDependenciesV1", [])
    if deps:
        profile["cbufferDependencies"] = _assignment_shape(deps)
    profile["immediateChildren"] = [_child_shape(child) for child in term.get("immediateChildren", [])]
    return profile


def promote(base_v2: dict, final_doc: dict, cbuffer_doc: dict) -> dict:
    if base_v2.get("format") != v2.FORMAT:
        raise UnclassifiedTermCensusV3Error(f"unexpected v2 census format {base_v2.get('format')!r}")
    if final_doc.get("format") != FINAL_FORMAT:
        raise UnclassifiedTermCensusV3Error(f"unexpected final-output format {final_doc.get('format')!r}")
    if cbuffer_doc.get("format") != CBUFFER_FORMAT:
        raise UnclassifiedTermCensusV3Error(f"unexpected cbuffer format {cbuffer_doc.get('format')!r}")

    final = _shader_rows(final_doc, label="final-output")
    cbrows = _shader_rows(cbuffer_doc, label="cbuffer")
    census_shaders = {str(term.get("sha256") or "") for term in base_v2.get("terms", [])}
    if not census_shaders.issubset(set(final)):
        raise UnclassifiedTermCensusV3Error("census references shader absent from final-output DAG")
    if set(final) != set(cbrows):
        raise UnclassifiedTermCensusV3Error("final-output/cbuffer shader sets disagree")

    nodes_by_shader = {sha: _node_table(row) for sha, row in final.items()}
    cbmap_by_shader = {sha: _cbuffer_node_map(row) for sha, row in cbrows.items()}

    terms = copy.deepcopy(base_v2.get("terms", []))
    total_deps = terms_with_deps = child_deps = 0
    source_classes = Counter()
    reflected_variables = set()
    groups = {}
    for term in terms:
        sha = str(term.get("sha256") or "")
        node_id = int(term.get("node", -1))
        nodes = nodes_by_shader[sha]
        if node_id not in nodes:
            raise UnclassifiedTermCensusV3Error(f"shader {sha}: census term node {node_id} absent from final DAG")
        cbmap = cbmap_by_shader[sha]
        deps = _dependency_rows(nodes, cbmap, node_id)
        term["cbufferDependenciesV1"] = deps
        term["cbufferDependencyCount"] = len(deps)
        total_deps += len(deps)
        terms_with_deps += int(bool(deps))
        for dep in deps:
            reflected_variables.add(((dep.get("buffer") or {}).get("name"), (dep.get("variable") or {}).get("name")))
            for assignment in dep.get("techniqueAssignments", []):
                source_classes[str(assignment.get("sourceClass") or "")] += 1

        dag_children = [int(x) for x in nodes[node_id].get("args", [])]
        children = term.get("immediateChildren", [])
        if len(children) != len(dag_children):
            raise UnclassifiedTermCensusV3Error(
                f"shader {sha} node {node_id}: census immediate-child count {len(children)} != DAG {len(dag_children)}"
            )
        for index, (child, child_id) in enumerate(zip(children, dag_children)):
            if int(child.get("node", child_id)) != child_id:
                # v1 child profiles retained node ids; if absent, exact operand
                # order from the authoritative DAG remains the join source.
                raise UnclassifiedTermCensusV3Error(
                    f"shader {sha} node {node_id}: child {index} identity disagrees with DAG"
                )
            cdeps = _dependency_rows(nodes, cbmap, child_id)
            child["cbufferDependenciesV1"] = cdeps
            child["cbufferDependencyCount"] = len(cdeps)
            child_deps += len(cdeps)

        profile = enriched_structural_profile(term)
        signature = _jhash(profile)
        term["cbufferEnrichedStructuralProfileSha256V3"] = signature
        group = groups.get(signature)
        if group is None:
            groups[signature] = {
                "cbufferEnrichedStructuralProfileSha256": signature,
                "count": 1,
                "profile": profile,
                "representative": {
                    "sha256": sha,
                    "lane": term.get("lane"),
                    "path": term.get("path"),
                    "node": node_id,
                },
                "observedLanes": [term.get("lane")],
            }
        else:
            group["count"] += 1
            lane = term.get("lane")
            if lane not in group["observedLanes"]:
                group["observedLanes"].append(lane)

    enriched_groups = sorted(groups.values(), key=lambda row: (-int(row["count"]), row["cbufferEnrichedStructuralProfileSha256"]))
    for row in enriched_groups:
        row["observedLanes"] = sorted(str(x) for x in row["observedLanes"] if x is not None)

    summary = copy.deepcopy(base_v2.get("summary", {}))
    summary.update({
        "cbufferEnrichmentApplied": True,
        "termWithCbufferDependencyCount": terms_with_deps,
        "termCbufferDependencyOccurrenceCount": total_deps,
        "immediateChildCbufferDependencyOccurrenceCount": child_deps,
        "uniqueReflectedCbufferVariableCount": len(reflected_variables),
        "cbufferAssignmentSourceClassCounts": dict(sorted(source_classes.items())),
        "v2StructuralSignatureCount": int(summary.get("structuralSignatureCount", len(base_v2.get("signatureGroups", [])))),
        "cbufferEnrichedStructuralSignatureCount": len(enriched_groups),
    })

    out = copy.deepcopy(base_v2)
    out["format"] = FORMAT
    out["sourceCensusFormat"] = v2.FORMAT
    out["sourceCbufferFormat"] = CBUFFER_FORMAT
    out["terms"] = terms
    out["cbufferEnrichedSignatureGroups"] = enriched_groups
    out["summary"] = summary
    out["rowsSha256V3"] = _jhash(terms)
    out["cbufferEnrichedSignatureGroupsSha256"] = _jhash(enriched_groups)
    out["proofBoundary"] = (
        str(base_v2.get("proofBoundary") or "")
        + " v3 retains v2 grouping unchanged and adds exact same-CSO RDEF cbuffer/variable identities plus exact .tech "
          "assignment expressions to every cbuffer dependency in each unknown term and immediate child. Names remain identities only."
    )
    return out


def build(base_v2: dict, final_doc: dict, cbuffer_doc: dict) -> dict:
    return promote(base_v2, final_doc, cbuffer_doc)


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--census-v2',type=Path,required=True);p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer-signature',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.census_v2.read_text()),json.loads(a.final_output.read_text()),json.loads(a.cbuffer_signature.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
