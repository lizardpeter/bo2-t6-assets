#!/usr/bin/env python3
"""Derive retail T6 vd1 strides directly from a standalone map layout audit.

This is the bridge between the standalone patched-OAT map extractor and the
source-closed world-format registry. Unlike the older raw-census path, it does
not need Material/TechniqueSet pointer reconstruction or a per-zone asset-array
virtual base when the layout audit already contains strong group records.

Proof requirements are deliberately strict. A promotable record must contain:
- worldVertFormat 0..8;
- a positive independently serialized/derived vertexCount;
- vd1Offset or vertexDataOffset1;
- group/surface geometry context; and
- it must not live beneath a format/reference/enum table.

A raw allocation promotes a stride only when every retained member at that
vd1 offset agrees on exactly one format and one positive vertex count, and the
span to the next distinct offset divides that count exactly. Ambiguous offsets
remain blockers. The tool never infers field semantics from byte statistics.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


class LayoutCensusError(RuntimeError):
    pass


REFERENCE_TOKENS = {
    "formattable", "formats", "knownformats", "enum", "enums", "reference",
    "references", "worldvertexformats", "worldvertformats",
}
CONTEXT_KEYS = {
    "groupIndex", "surfaceIndex", "surfaceIndices", "surfaceCount", "vertexCount",
    "vd0Offset", "vertexDataOffset0", "vd1Offset", "vertexDataOffset1",
    "firstVertex", "firstIndex", "baseIndex", "triCount",
}


def _normalized_token(value: str) -> str:
    return value.lower().replace("_", "").replace("-", "")


def _reference_path(path: tuple[str, ...]) -> bool:
    return any(_normalized_token(part) in REFERENCE_TOKENS for part in path)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(node: dict, names: tuple[str, ...]) -> int | None:
    for name in names:
        if name in node:
            value = _int(node.get(name))
            if value is not None:
                return value
    return None


def _candidate_layouts(root: Path, map_name: str | None) -> list[Path]:
    if root.is_file():
        files = [root]
    elif root.is_dir():
        files = sorted(root.rglob("*.layout.json"))
    else:
        raise LayoutCensusError(f"layout input does not exist: {root}")
    if map_name:
        needle = map_name.lower()
        files = [p for p in files if needle in str(p).lower()]
    return files


def _candidate_vd1(root: Path, map_name: str | None) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise LayoutCensusError(f"vd1 input does not exist: {root}")
    rows = []
    for path in root.rglob("*.bin"):
        name = path.name.lower()
        if "vd1" not in name:
            continue
        if map_name and map_name.lower() not in str(path).lower():
            continue
        rows.append(path)
    return sorted(rows)


def extract_group_records(document: Any) -> tuple[list[dict], list[dict]]:
    candidates: list[dict] = []
    rejected: list[dict] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            if "worldVertFormat" in node:
                fmt = _int(node.get("worldVertFormat"))
                vc = _first_int(node, ("vertexCount", "derivedVertexCount", "groupVertexCount"))
                off1 = _first_int(node, ("vd1Offset", "vertexDataOffset1"))
                off0 = _first_int(node, ("vd0Offset", "vertexDataOffset0"))
                context = sorted(CONTEXT_KEYS.intersection(node.keys()))
                reason = None
                if _reference_path(path):
                    reason = "reference-table-path"
                elif fmt is None or not 0 <= fmt <= 8:
                    reason = "invalid-worldVertFormat"
                elif vc is None or vc <= 0:
                    reason = "missing-or-nonpositive-vertexCount"
                elif off1 is None or off1 < 0:
                    reason = "missing-or-negative-vd1Offset"
                elif not context:
                    reason = "no-serialized-geometry-context"

                row = {
                    "path": "$" + "".join(
                        part if part.startswith("[") else "." + part for part in path
                    ),
                    "worldVertFormat": fmt,
                    "vertexCount": vc,
                    "vd0Offset": off0 if off0 is not None else -1,
                    "vd1Offset": off1,
                    "contextKeys": context,
                }
                if reason is None:
                    candidates.append(row)
                else:
                    row["reason"] = reason
                    rejected.append(row)

            for key, value in node.items():
                walk(value, path + (str(key),))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + (f"[{index}]",))

    walk(document, ())

    # Nested audit structures may repeat the same group. Repetition is not new
    # evidence, so collapse exact binary-allocation identities.
    dedup: dict[tuple[int, int, int, int], dict] = {}
    for row in candidates:
        key = (
            int(row["vd0Offset"]), int(row["vd1Offset"]),
            int(row["vertexCount"]), int(row["worldVertFormat"]),
        )
        dedup.setdefault(key, row)
    return list(dedup.values()), rejected


def derive_allocations(records: list[dict], vd1: bytes) -> dict:
    by_offset: dict[int, list[dict]] = collections.defaultdict(list)
    blockers: list[dict] = []
    for row in records:
        offset = int(row["vd1Offset"])
        if offset >= len(vd1):
            blockers.append({
                "vd1Offset": offset,
                "reason": "vd1Offset outside raw buffer",
                "vd1Bytes": len(vd1),
                "record": row,
            })
            continue
        by_offset[offset].append(row)

    offsets = sorted(by_offset)
    allocations: list[dict] = []
    observed: dict[int, set[int]] = collections.defaultdict(set)

    for oi, offset in enumerate(offsets):
        next_offset = offsets[oi + 1] if oi + 1 < len(offsets) else len(vd1)
        span = next_offset - offset
        members = by_offset[offset]
        counts = sorted({int(row["vertexCount"]) for row in members if int(row["vertexCount"]) > 0})
        formats = sorted({int(row["worldVertFormat"]) for row in members})
        raw_stride = None
        status = "unambiguous"
        reason = None

        if span <= 0:
            reason = "nonpositive-raw-allocation-span"
        elif len(counts) != 1:
            reason = "shared-offset-has-multiple-vertex-counts"
        elif len(formats) != 1:
            reason = "shared-offset-has-multiple-world-formats"
        elif span % counts[0] != 0:
            reason = "raw-span-does-not-divide-vertex-count"
        else:
            raw_stride = span // counts[0]
            if raw_stride <= 0 or raw_stride % 4:
                reason = "raw-stride-is-not-positive-4-byte-multiple"
                raw_stride = None

        if reason is not None:
            status = "ambiguous-or-invalid"
            blockers.append({
                "vd1Offset": offset,
                "nextDistinctVd1Offset": next_offset,
                "rawSpanBytes": span,
                "memberVertexCounts": counts,
                "memberFormats": formats,
                "reason": reason,
            })
        else:
            observed[formats[0]].add(int(raw_stride))

        allocations.append({
            "vd1Offset": offset,
            "nextDistinctVd1Offset": next_offset,
            "rawSpanBytes": span,
            "memberCount": len(members),
            "memberVertexCounts": counts,
            "memberFormats": formats,
            "unambiguousRawStride": raw_stride,
            "status": status,
            "members": members,
        })

    return {
        "allocations": allocations,
        "blockers": blockers,
        "observedRawStrideByFormat": {
            str(fmt): sorted(strides) for fmt, strides in sorted(observed.items())
        },
    }


def census(*, map_name: str, layout_path: Path, vd1_path: Path) -> dict:
    document = json.loads(layout_path.read_text(encoding="utf-8"))
    vd1 = vd1_path.read_bytes()
    records, rejected = extract_group_records(document)
    if not records:
        raise LayoutCensusError(
            f"{layout_path}: no strong group records with format/count/vd1 offset"
        )
    derived = derive_allocations(records, vd1)

    summary = {}
    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        strides = derived["observedRawStrideByFormat"].get(str(fmt), [])
        expected = int(spec.vd1_stride)
        summary[str(fmt)] = {
            "format": fmt,
            "name": fmt_enum.name,
            "formulaHypothesisStride": expected,
            "unambiguousRawStridesObservedInThisFixture": strides,
            "formulaSupportedByThisFixture": expected in strides if strides else None,
            "formulaContradictedByThisFixture": bool(strides) and expected not in strides,
            "semanticFieldsHypothesis": list(spec.vd1_fields),
            "semanticFieldsProvenByThisTool": False,
        }

    return {
        "format": "t6-world-vd1-layout-census-v1",
        "map": map_name,
        "source": {"layout": str(layout_path), "vd1": str(vd1_path)},
        "vd1Bytes": len(vd1),
        "strongGroupRecordCount": len(records),
        "rejectedWorldFormatRecordCount": len(rejected),
        "rejectedWorldFormatRecords": rejected,
        **derived,
        "formatSummary": summary,
        "stats": {
            "allocationCount": len(derived["allocations"]),
            "unambiguousAllocationCount": sum(
                1 for row in derived["allocations"] if row["unambiguousRawStride"] is not None
            ),
            "blockedAllocationCount": len(derived["blockers"]),
            "observedFormatCount": len(derived["observedRawStrideByFormat"]),
        },
        "proofBoundary": (
            "retail raw allocation stride only; layout record supplies format/count/offset "
            "identity, exact vd1 bytes supply allocation span; field/shader semantics are not inferred"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--vd1", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--target-format", type=int, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.archive is not None:
        if args.layout is not None or args.vd1 is not None:
            raise LayoutCensusError("--archive cannot be combined with --layout/--vd1")
        layouts = _candidate_layouts(args.archive, args.map_name)
        vd1s = _candidate_vd1(args.archive, args.map_name)
        if len(layouts) != 1:
            raise LayoutCensusError(
                f"archive discovery requires exactly one {args.map_name} *.layout.json; found {len(layouts)}"
            )
        if len(vd1s) != 1:
            raise LayoutCensusError(
                f"archive discovery requires exactly one {args.map_name} vd1 *.bin; found {len(vd1s)}"
            )
        layout_path, vd1_path = layouts[0], vd1s[0]
    else:
        if args.layout is None or args.vd1 is None:
            raise LayoutCensusError("provide either --archive or both --layout and --vd1")
        layout_path, vd1_path = args.layout, args.vd1

    doc = census(map_name=args.map_name, layout_path=layout_path, vd1_path=vd1_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    targets = set(args.target_format or [4, 5, 7, 8])
    target_hits = sorted(
        fmt for fmt in targets if doc["observedRawStrideByFormat"].get(str(fmt))
    )
    print(json.dumps({"out": str(args.out), "targetHits": target_hits, **doc["stats"]}, indent=2))
    if doc["blockers"]:
        return 2
    return 0 if target_hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
