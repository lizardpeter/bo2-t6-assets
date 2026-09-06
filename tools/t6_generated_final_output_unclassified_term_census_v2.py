#!/usr/bin/env python3
"""Unclassified final-RGB term census v2: channel-agnostic structural groups.

v1 preserves exact occurrence rows but included the RGB lane in each structural
profile hash.  v2 deliberately keeps every v1 occurrence unchanged while
recomputing grouping fingerprints without lane/path/node identity, so the same
unknown equation shape independently emitted for R/G/B collapses into one group.

Operand order, sign, root operation, exact/deeper anchor tags, resources, and
ordered immediate-child profiles remain part of the fingerprint.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import t6_generated_final_output_unclassified_term_census_v1 as v1

FORMAT = "t6-generated-final-output-unclassified-term-census-v2"


class UnclassifiedTermCensusV2Error(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _child_shape(child: dict) -> dict:
    return {
        key: copy.deepcopy(child.get(key))
        for key in (
            "kind", "operation", "exactAnchorTags", "ancestryAnchorTags",
            "resources", "literal32Bits", "textureResource", "textureChannel",
        )
        if child.get(key) is not None
    }


def structural_profile(term: dict) -> dict:
    return {
        "sign": int(term.get("sign", 1)),
        "kind": term.get("kind"),
        "operation": term.get("operation"),
        "exactAnchorTags": copy.deepcopy(term.get("exactAnchorTags", [])),
        "ancestryAnchorTags": copy.deepcopy(term.get("ancestryAnchorTags", [])),
        "resources": copy.deepcopy(term.get("resources", [])),
        "immediateChildren": [
            _child_shape(child) for child in term.get("immediateChildren", [])
        ],
    }


def promote(base: dict) -> dict:
    if base.get("format") != v1.FORMAT:
        raise UnclassifiedTermCensusV2Error(
            f"unexpected v1 census format {base.get('format')!r}"
        )
    terms = copy.deepcopy(base.get("terms", []))
    groups = {}
    for term in terms:
        profile = structural_profile(term)
        signature = _jhash(profile)
        term["structuralProfileSha256V2"] = signature
        group = groups.get(signature)
        if group is None:
            groups[signature] = {
                "structuralProfileSha256": signature,
                "count": 1,
                "profile": profile,
                "representative": {
                    "sha256": term.get("sha256"),
                    "lane": term.get("lane"),
                    "path": term.get("path"),
                    "node": term.get("node"),
                },
                "observedLanes": [term.get("lane")],
            }
        else:
            group["count"] += 1
            lane = term.get("lane")
            if lane not in group["observedLanes"]:
                group["observedLanes"].append(lane)
    rows = sorted(
        groups.values(),
        key=lambda row: (-int(row["count"]), row["structuralProfileSha256"]),
    )
    for row in rows:
        row["observedLanes"] = sorted(str(x) for x in row["observedLanes"] if x is not None)

    summary = copy.deepcopy(base.get("summary", {}))
    summary["v1LaneSpecificStructuralSignatureCount"] = int(
        summary.get("structuralSignatureCount", len(base.get("signatureGroups", [])))
    )
    summary["structuralSignatureCount"] = len(rows)
    summary["channelAgnosticGrouping"] = True

    out = copy.deepcopy(base)
    out["format"] = FORMAT
    out["sourceCensusFormat"] = v1.FORMAT
    out["terms"] = terms
    out["signatureGroups"] = rows
    out["summary"] = summary
    out["rowsSha256"] = _jhash(terms)
    out["signatureGroupsSha256"] = _jhash(rows)
    out["proofBoundary"] = (
        str(base.get("proofBoundary") or "")
        + " v2 changes grouping only: RGB lane/path/node identity is excluded from the structural fingerprint, "
          "while sign, operand order, anchors, resources, and child profiles remain exact."
    )
    return out


def build(coverage_doc: dict, final_doc: dict, square_doc: dict, dir_doc: dict, spec_doc: dict, refl_doc: dict) -> dict:
    return promote(v1.build(coverage_doc, final_doc, square_doc, dir_doc, spec_doc, refl_doc))


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--coverage',type=Path,required=True);p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--directional',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--reflection-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.coverage.read_text()),json.loads(a.final_output.read_text()),json.loads(a.rgb_square.read_text()),json.loads(a.directional.read_text()),json.loads(a.specular.read_text()),json.loads(a.reflection_index.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
