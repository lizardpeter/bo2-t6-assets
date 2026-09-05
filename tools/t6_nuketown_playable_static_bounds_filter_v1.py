#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside_playable_xy_bounds(row: dict, half_extent: float) -> bool:
    mins = row["mins"]
    maxs = row["maxs"]
    return (
        mins[0] >= -half_extent
        and maxs[0] <= half_extent
        and mins[1] >= -half_extent
        and maxs[1] <= half_extent
    )


def validate_row(row: dict) -> None:
    for key in ("origin", "mins", "maxs"):
        v = row[key]
        if len(v) != 3 or not all(math.isfinite(float(x)) for x in v):
            raise ValueError(f"row {row.get('index')}: invalid {key}: {v}")
    if any(float(row["mins"][i]) > float(row["maxs"][i]) for i in range(3)):
        raise ValueError(f"row {row.get('index')}: inverted bounds")
    scale = float(row["scale"])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError(f"row {row.get('index')}: invalid scale {scale}")


def bounds_of(rows: list[dict]) -> dict:
    return {
        "mins": [min(float(r["mins"][i]) for r in rows) for i in range(3)],
        "maxs": [max(float(r["maxs"][i]) for r in rows) for i in range(3)],
        "originMins": [min(float(r["origin"][i]) for r in rows) for i in range(3)],
        "originMaxs": [max(float(r["origin"][i]) for r in rows) for i in range(3)],
    }


def build(source: Path, selected_out: Path, manifest_out: Path, excluded_out: Path | None,
          half_extent: float, expected_source: int, expected_selected: int,
          expected_identity_count: int) -> dict:
    doc = json.loads(source.read_text())
    rows = doc["placements"]
    if len(rows) != expected_source or int(doc.get("count", len(rows))) != expected_source:
        raise ValueError(f"candidate source count {len(rows)} != {expected_source}")

    for row in rows:
        validate_row(row)

    identities = {r["model"] for r in rows}
    if len(identities) != expected_identity_count:
        raise ValueError(f"candidate identity count {len(identities)} != {expected_identity_count}")

    selected = [r for r in rows if inside_playable_xy_bounds(r, half_extent)]
    excluded = [r for r in rows if not inside_playable_xy_bounds(r, half_extent)]
    if len(selected) != expected_selected:
        raise ValueError(f"playable-bounds filter yielded {len(selected)}, expected {expected_selected}")
    if len(selected) + len(excluded) != expected_source:
        raise AssertionError("selection partition mismatch")

    selected_indices = [int(r["index"]) for r in selected]
    excluded_indices = [int(r["index"]) for r in excluded]
    if len(set(selected_indices)) != len(selected_indices) or len(set(excluded_indices)) != len(excluded_indices):
        raise ValueError("duplicate smodel indices")
    if set(selected_indices) & set(excluded_indices):
        raise AssertionError("selected/excluded overlap")

    selected_models = {r["model"] for r in selected}
    missing_models = sorted(identities - selected_models)
    excluded_model_counts = collections.Counter(r["model"] for r in excluded)

    selected_doc = {
        "format": "t6-nuketown-playable-static-bounds-filter-v1",
        "source": source.name,
        "sourceSha256": sha256_file(source),
        "halfExtentGameUnitsXY": half_extent,
        "count": len(selected),
        "placements": selected,
    }
    selected_out.write_text(json.dumps(selected_doc, separators=(",", ":")) + "\n")

    excluded_digest_input = ",".join(str(i) for i in excluded_indices).encode()
    selected_digest_input = ",".join(str(i) for i in selected_indices).encode()
    manifest = {
        "format": "t6-nuketown-playable-static-bounds-filter-proof-v1",
        "source": {
            "file": source.name,
            "sha256": sha256_file(source),
            "candidateCount": len(rows),
            "candidateIdentityCount": len(identities),
        },
        "rule": {
            "description": "Retain a candidate iff its authoritative GfxStaticModelInst AABB is fully contained in [-2500,+2500] on retail world X and Y. Z is not cropped.",
            "halfExtentGameUnitsXY": half_extent,
            "fields": ["mins[0]", "maxs[0]", "mins[1]", "maxs[1]"],
            "boundary": "inclusive",
        },
        "result": {
            "selectedCount": len(selected),
            "excludedCount": len(excluded),
            "selectedIdentityCount": len(selected_models),
            "uninstantiatedDefinitionIdentities": missing_models,
            "selectedBounds": bounds_of(selected),
            "selectedIndexListSha256": hashlib.sha256(selected_digest_input).hexdigest(),
            "excludedIndexListSha256": hashlib.sha256(excluded_digest_input).hexdigest(),
            "topExcludedModels": excluded_model_counts.most_common(40),
        },
        "output": {
            "file": selected_out.name,
            "bytes": selected_out.stat().st_size,
            "sha256": sha256_file(selected_out),
        },
        "proofBoundary": (
            "This proves a deterministic 2303-to-1943 spatial partition of the independently recovered retail GfxWorld static placements. "
            "The 297-XModel material proof is definition-level, so definitions may remain uninstantiated after this crop. "
            "This does not by itself prove that the lost historical exporter used the same source code; it proves the recovered rule reproduces the retained 1943 playable-static cardinality from authoritative retail bounds without model-name heuristics."
        ),
    }
    manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    if excluded_out is not None:
        excluded_out.write_text(json.dumps({
            "format": "t6-nuketown-playable-static-bounds-excluded-v1",
            "halfExtentGameUnitsXY": half_extent,
            "count": len(excluded),
            "placements": excluded,
        }, separators=(",", ":")) + "\n")

    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--selected-out", type=Path, required=True)
    ap.add_argument("--manifest-out", type=Path, required=True)
    ap.add_argument("--excluded-out", type=Path)
    ap.add_argument("--half-extent", type=float, default=2500.0)
    ap.add_argument("--expected-source", type=int, default=2303)
    ap.add_argument("--expected-selected", type=int, default=1943)
    ap.add_argument("--expected-identities", type=int, default=297)
    args = ap.parse_args()
    result = build(args.source, args.selected_out, args.manifest_out, args.excluded_out,
                   args.half_extent, args.expected_source, args.expected_selected,
                   args.expected_identities)
    print(json.dumps(result["result"], indent=2))


if __name__ == "__main__":
    main()
