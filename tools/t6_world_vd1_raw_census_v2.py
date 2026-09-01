#!/usr/bin/env python3
"""T6 world vd1 raw-layout census v2: count only unambiguous allocations as observed.

V1 intentionally exposed every raw span/member candidate, but its per-format
summary also included strides calculated from shared/ambiguous `vd1Offset`
buckets. V2 preserves the v1 report and column-statistics machinery while
promoting a stricter rule:

  a stride becomes `observedRawStrideByFormat` only when one serialized vd1
  allocation has a single independently-derived vertex count and therefore one
  unambiguous raw stride.

A shared offset with different vertex counts remains useful evidence in the
allocation record, but cannot promote any format's retail stride.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import t6_world_vd1_raw_census_v1 as v1
from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


Vd1RawCensusError = v1.Vd1RawCensusError


def derive_allocations(group_records: list[dict], vd1: bytes) -> dict:
    by_offset: dict[int, list[dict]] = collections.defaultdict(list)
    for row in group_records:
        by_offset[int(row["vd1Offset"])].append(row)
    offsets = sorted(x for x in by_offset if 0 <= x < len(vd1))

    allocations: list[dict] = []
    observed_by_format: dict[int, set[int]] = collections.defaultdict(set)
    for oi, offset in enumerate(offsets):
        next_offset = offsets[oi + 1] if oi + 1 < len(offsets) else len(vd1)
        span = next_offset - offset
        members = sorted(
            by_offset[offset],
            key=lambda row: (int(row["vd0Offset"]), int(row["worldVertFormat"])),
        )
        member_candidates: list[dict] = []
        exact_strides: set[int] = set()
        positive_counts: set[int] = set()
        for row in members:
            vc = int(row["vertexCount"])
            if vc > 0:
                positive_counts.add(vc)
            exact = vc > 0 and span % vc == 0
            stride = span // vc if exact else None
            if stride is not None:
                exact_strides.add(stride)
            fmt = int(row["worldVertFormat"])
            spec = WORLD_VERTEX_FORMATS[MaterialWorldVertexFormat(fmt)]
            member_candidates.append(
                {
                    "vd0Offset": int(row["vd0Offset"]),
                    "vertexCount": vc,
                    "worldVertFormat": fmt,
                    "formatName": MaterialWorldVertexFormat(fmt).name,
                    "rawSpanDividesVertexCount": exact,
                    "rawStrideCandidate": stride,
                    "formulaHypothesisStride": int(spec.vd1_stride),
                    "formulaMatchesRawCandidate": (
                        stride == int(spec.vd1_stride) if stride is not None else None
                    ),
                    "surfaceIndices": list(row.get("surfaceIndices", [])),
                    "materials": list(row.get("materials", [])),
                }
            )

        unambiguous_stride = None
        unambiguous_count = None
        if len(positive_counts) == 1 and len(exact_strides) == 1:
            unambiguous_count = next(iter(positive_counts))
            unambiguous_stride = next(iter(exact_strides))
            # Only this condition is allowed to promote an observed format stride.
            for row in members:
                observed_by_format[int(row["worldVertFormat"])].add(
                    int(unambiguous_stride)
                )

        columns = []
        if unambiguous_stride is not None and unambiguous_stride > 0:
            used = int(unambiguous_stride) * int(unambiguous_count)
            if used == span:
                columns = v1._column_metrics(
                    vd1,
                    offset=offset,
                    stride=int(unambiguous_stride),
                    count=int(unambiguous_count),
                )

        allocations.append(
            {
                "vd1Offset": offset,
                "nextDistinctVd1Offset": next_offset,
                "rawSpanBytes": span,
                "memberCount": len(members),
                "memberVertexCounts": sorted(positive_counts),
                "memberCandidates": member_candidates,
                "exactRawStrideCandidates": sorted(exact_strides),
                "unambiguousRawStride": unambiguous_stride,
                "unambiguousVertexCount": unambiguous_count,
                "columnStats": columns,
                "status": (
                    "unambiguous"
                    if unambiguous_stride is not None
                    else "shared-or-nondivisible-offset; no format stride promoted"
                ),
            }
        )

    return {
        "allocations": allocations,
        "observedRawStrideByFormat": {
            str(fmt): sorted(strides)
            for fmt, strides in sorted(observed_by_format.items())
        },
    }


def census(**kwargs) -> dict:
    base = v1.census(**kwargs)
    vd1_path = Path(kwargs["vd1_path"])
    raw_layout = derive_allocations(base["groups"], vd1_path.read_bytes())

    doc = dict(base)
    doc["format"] = "t6-world-vd1-raw-census-v2"
    doc["policy"] = dict(base["policy"])
    doc["policy"].update(
        {
            "observedFormatStride": (
                "promoted only from allocations with exactly one positive member vertex count "
                "and exactly one exact raw stride candidate"
            ),
            "ambiguousOffsetPromotion": "forbidden",
        }
    )
    doc.pop("allocations", None)
    doc.pop("observedRawStrideCandidatesByFormat", None)
    doc.update(raw_layout)

    format_summary: dict[str, dict] = {}
    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        observed = raw_layout["observedRawStrideByFormat"].get(str(fmt), [])
        format_summary[str(fmt)] = {
            "format": fmt,
            "name": fmt_enum.name,
            "formulaHypothesisStride": int(spec.vd1_stride),
            "unambiguousRawStridesObservedInThisFixture": observed,
            "formulaSupportedByThisFixture": (
                int(spec.vd1_stride) in observed if observed else None
            ),
            "formulaContradictedByThisFixture": (
                bool(observed) and int(spec.vd1_stride) not in observed
            ),
            "semanticFieldsHypothesis": list(spec.vd1_fields),
            "semanticFieldsProvenByThisTool": False,
        }
    doc["formatSummary"] = format_summary
    doc["stats"] = dict(base["stats"])
    doc["stats"]["distinctVd1OffsetCount"] = len(raw_layout["allocations"])
    doc["stats"]["unambiguousVd1AllocationCount"] = sum(
        1
        for row in raw_layout["allocations"]
        if row["unambiguousRawStride"] is not None
    )
    doc["stats"]["ambiguousVd1AllocationCount"] = sum(
        1
        for row in raw_layout["allocations"]
        if row["unambiguousRawStride"] is None
    )
    doc["proofBoundary"] = (
        "only unambiguous serialized allocation strides may become retail byte evidence; "
        "column semantics and logical worldVertFormat field meanings remain separate proofs"
    )
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--surfaces", type=Path, required=True)
    parser.add_argument("--vd0", type=Path, required=True)
    parser.add_argument("--vd1", type=Path, required=True)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument(
        "--asset-pointer-base", type=lambda value: int(value, 0), required=True
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    doc = census(
        map_name=args.map_name,
        surfaces_path=args.surfaces,
        vd0_path=args.vd0,
        vd1_path=args.vd1,
        materials_path=args.materials,
        catalog_path=args.catalog,
        prefix_path=args.prefix,
        asset_pointer_array_virtual_base=args.asset_pointer_base,
    )
    args.out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0 if not doc["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
