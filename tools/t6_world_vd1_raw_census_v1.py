#!/usr/bin/env python3
"""Derive T6 GfxWorld secondary-vertex-stream layout from retail byte extents.

This tool is intentionally independent from the semantic `WORLD_VERTEX_FORMATS`
vd1 field/stride table. It answers the narrower retail-byte question first:

    for each serialized `vertexDataOffset1` allocation, what byte stride is
    implied by the next distinct offset and the independently-derived vertex
    count?

Only after deriving that raw stride does the report compare it with the current
formula hypothesis. A mismatch is evidence to investigate, not something this
tool repairs or coerces.

The report also computes per-4-byte-column statistics (half2 plausibility,
RGBA8 endpoint behavior, and PackedUnitVec length behavior) without assigning
UV/color/normal-transform semantics.

Inputs are the same exact GfxWorld/material provenance sidecars used by
`t6_world_vertex_audit_v2`, plus raw vd0/vd1. Material/TechniqueSet lookup is
used only to label each group with its T6 `worldVertFormat`; raw allocation
stride derivation does not use that format's expected vd1 stride.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import struct
from pathlib import Path

from t6_zone_core import (
    GFX_WORLD_VD0_STRIDE,
    MaterialWorldVertexFormat,
    WORLD_VERTEX_FORMATS,
    align_up,
    unpack_unit_vec_third_based,
)


class Vd1RawCensusError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _derive_vertex_count(vd0_span: int) -> tuple[int | None, list[int]]:
    if vd0_span < 0:
        return None, []
    center = vd0_span // GFX_WORLD_VD0_STRIDE
    candidates = [
        n
        for n in range(max(0, center - 2), center + 3)
        if align_up(GFX_WORLD_VD0_STRIDE * n, 16) == vd0_span
    ]
    return (candidates[0] if len(candidates) == 1 else None), candidates


def _half_pair_metrics(words: list[bytes]) -> dict:
    finite_pairs = 0
    abs_le_1 = 0
    abs_le_8 = 0
    zeros = 0
    xs: list[float] = []
    ys: list[float] = []
    for word in words:
        a, b = struct.unpack("<2e", word)
        if math.isfinite(a) and math.isfinite(b):
            finite_pairs += 1
            xs.append(float(a))
            ys.append(float(b))
            if abs(a) <= 1.0 and abs(b) <= 1.0:
                abs_le_1 += 1
            if abs(a) <= 8.0 and abs(b) <= 8.0:
                abs_le_8 += 1
        if word == b"\x00\x00\x00\x00":
            zeros += 1
    n = len(words)
    return {
        "finitePairCount": finite_pairs,
        "finitePairRate": finite_pairs / n if n else None,
        "absLe1PairRate": abs_le_1 / n if n else None,
        "absLe8PairRate": abs_le_8 / n if n else None,
        "zeroWordRate": zeros / n if n else None,
        "finiteMin": [min(xs), min(ys)] if xs else None,
        "finiteMax": [max(xs), max(ys)] if xs else None,
    }


def _rgba_metrics(words: list[bytes]) -> dict:
    n = len(words)
    alpha_endpoint = sum(1 for word in words if word[3] in (0, 255))
    all_endpoint = sum(1 for word in words if all(x in (0, 255) for x in word))
    channels = list(zip(*words)) if words else [(), (), (), ()]
    return {
        "alphaEndpointRate": alpha_endpoint / n if n else None,
        "allChannelsEndpointRate": all_endpoint / n if n else None,
        "channelMin": [min(c) for c in channels] if words else None,
        "channelMax": [max(c) for c in channels] if words else None,
    }


def _packed_unit_metrics(words: list[bytes]) -> dict:
    lengths: list[float] = []
    for word in words:
        packed = struct.unpack("<I", word)[0]
        x, y, z = unpack_unit_vec_third_based(packed)
        lengths.append(math.sqrt(x * x + y * y + z * z))
    n = len(lengths)
    near = sum(1 for length in lengths if abs(length - 1.0) <= 0.25)
    return {
        "unitLengthWithin0_25Rate": near / n if n else None,
        "lengthMin": min(lengths) if lengths else None,
        "lengthMax": max(lengths) if lengths else None,
        "lengthMean": sum(lengths) / n if n else None,
    }


def _column_metrics(raw: bytes, *, offset: int, stride: int, count: int) -> list[dict]:
    if stride <= 0 or stride % 4:
        return []
    columns: list[dict] = []
    for column in range(stride // 4):
        words = [
            raw[offset + vertex * stride + column * 4 : offset + vertex * stride + column * 4 + 4]
            for vertex in range(count)
        ]
        if any(len(word) != 4 for word in words):
            raise Vd1RawCensusError(
                f"column {column}: allocation extends beyond vd1 source buffer"
            )
        u32s = [struct.unpack("<I", word)[0] for word in words]
        columns.append(
            {
                "columnIndex": column,
                "byteOffsetWithinVertex": column * 4,
                "sampleHex": [word.hex() for word in words[:8]],
                "uniqueWordCount": len(set(u32s)),
                "zeroWordCount": sum(1 for value in u32s if value == 0),
                "ffffffffWordCount": sum(1 for value in u32s if value == 0xFFFFFFFF),
                "half2": _half_pair_metrics(words),
                "rgba8": _rgba_metrics(words),
                "packedUnitVec": _packed_unit_metrics(words),
                "semantic": "unassigned",
            }
        )
    return columns


def derive_allocations(group_records: list[dict], vd1: bytes) -> dict:
    """Derive raw vd1 allocations from already-resolved vertex groups.

    `group_records` rows require: vd0Offset, vd1Offset, vertexCount,
    worldVertFormat. Multiple vd0 groups may share one vd1 offset; those remain
    explicit and are not silently assigned to one owner.
    """
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
            by_offset[offset], key=lambda row: (int(row["vd0Offset"]), int(row["worldVertFormat"]))
        )
        member_candidates: list[dict] = []
        exact_strides: set[int] = set()
        for row in members:
            vc = int(row["vertexCount"])
            exact = vc > 0 and span % vc == 0
            stride = span // vc if exact else None
            if stride is not None:
                exact_strides.add(stride)
                observed_by_format[int(row["worldVertFormat"])].add(stride)
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
        if len(exact_strides) == 1:
            candidate = next(iter(exact_strides))
            counts = {int(row["vertexCount"]) for row in members if int(row["vertexCount"]) > 0}
            # Shared offsets with different counts remain ambiguous even if an
            # accidental span division yields the same integer stride.
            if len(counts) == 1:
                unambiguous_stride = candidate
                unambiguous_count = next(iter(counts))

        columns = []
        if unambiguous_stride is not None and unambiguous_stride > 0:
            used = unambiguous_stride * int(unambiguous_count)
            if used == span:
                columns = _column_metrics(
                    vd1,
                    offset=offset,
                    stride=unambiguous_stride,
                    count=int(unambiguous_count),
                )

        allocations.append(
            {
                "vd1Offset": offset,
                "nextDistinctVd1Offset": next_offset,
                "rawSpanBytes": span,
                "memberCount": len(members),
                "memberCandidates": member_candidates,
                "exactRawStrideCandidates": sorted(exact_strides),
                "unambiguousRawStride": unambiguous_stride,
                "unambiguousVertexCount": unambiguous_count,
                "columnStats": columns,
                "status": (
                    "unambiguous"
                    if unambiguous_stride is not None
                    else "shared-or-nondivisible-offset; semantic ownership unresolved"
                ),
            }
        )

    return {
        "allocations": allocations,
        "observedRawStrideCandidatesByFormat": {
            str(fmt): sorted(strides) for fmt, strides in sorted(observed_by_format.items())
        },
    }


def census(
    *,
    map_name: str,
    surfaces_path: Path,
    vd0_path: Path,
    vd1_path: Path,
    materials_path: Path,
    catalog_path: Path,
    prefix_path: Path,
    asset_pointer_array_virtual_base: int,
) -> dict:
    surfaces = _load_json(surfaces_path)["surfaces"]
    vd0 = vd0_path.read_bytes()
    vd1 = vd1_path.read_bytes()
    materials = _load_json(materials_path)["materials"]
    catalog = _load_json(catalog_path)["materials"]
    prefix = _load_json(prefix_path)["walkedAssets"]

    mat_by_ptr = {int(m["surfacePointerHex"], 16): m for m in catalog}
    mat_detail_by_name = {str(m["name"]): m for m in materials}

    def technique_asset_index(material_name: str) -> int:
        m = mat_detail_by_name[material_name]
        pointer = m["techniqueSet"]["pointer"]
        if pointer["kind"] != "offset" or int(pointer["block"]) != 5:
            raise Vd1RawCensusError(
                f"{material_name}: TechniqueSet pointer is not virtual offset block 5"
            )
        target = int(pointer["offset"])
        quotient, remainder = divmod(
            target - asset_pointer_array_virtual_base - 4, 8
        )
        if remainder or not (0 <= quotient < len(prefix)):
            raise Vd1RawCensusError(
                f"{material_name}: TechniqueSet pointer does not map to prefix asset array"
            )
        return quotient

    mat_fmt: dict[str, int] = {}
    for name in mat_detail_by_name:
        asset_index = technique_asset_index(name)
        asset = prefix[asset_index]
        if asset["type"] != "techniqueset":
            raise Vd1RawCensusError(
                f"{name}: prefix asset {asset_index} is {asset['type']}, not techniqueset"
            )
        fmt = int(asset["details"]["worldVertFormat"])
        try:
            MaterialWorldVertexFormat(fmt)
        except ValueError as exc:
            raise Vd1RawCensusError(f"{name}: invalid worldVertFormat {fmt}") from exc
        mat_fmt[name] = fmt

    grouped: dict[int, list[dict]] = collections.defaultdict(list)
    for surface in surfaces:
        grouped[int(surface["vertexDataOffset0"])].append(surface)
    offsets0 = sorted(grouped)

    groups: list[dict] = []
    blockers: list[dict] = []
    for gi, off0 in enumerate(offsets0):
        members = grouped[off0]
        next0 = offsets0[gi + 1] if gi + 1 < len(offsets0) else len(vd0)
        span0 = next0 - off0
        vc, vc_candidates = _derive_vertex_count(span0)
        if vc is None:
            blockers.append(
                {
                    "vd0Offset": off0,
                    "reason": "vd0 span does not uniquely determine vertex count",
                    "vd0SpanBytes": span0,
                    "vertexCountCandidates": vc_candidates,
                }
            )
            continue
        stored_counts = sorted(
            {int(s["vertexCount"]) for s in members if int(s["vertexCount"]) > 0}
        )
        if stored_counts and stored_counts != [vc]:
            blockers.append(
                {
                    "vd0Offset": off0,
                    "reason": "stored vertexCount disagrees with vd0 allocation span",
                    "derivedVertexCount": vc,
                    "storedCounts": stored_counts,
                }
            )
            continue

        fmts: set[int] = set()
        material_names: set[str] = set()
        unresolved = False
        for surface in members:
            raw_ptr = int(surface["materialPointerRaw"], 16)
            catalog_row = mat_by_ptr.get(raw_ptr)
            if catalog_row is None:
                blockers.append(
                    {
                        "vd0Offset": off0,
                        "surface": int(surface["index"]),
                        "reason": "unknown material pointer",
                        "materialPointerRaw": surface["materialPointerRaw"],
                    }
                )
                unresolved = True
                continue
            name = str(catalog_row["name"])
            material_names.add(name)
            if name not in mat_fmt:
                blockers.append(
                    {
                        "vd0Offset": off0,
                        "surface": int(surface["index"]),
                        "reason": "material missing TechniqueSet worldVertFormat",
                        "material": name,
                    }
                )
                unresolved = True
                continue
            fmts.add(mat_fmt[name])
        if unresolved:
            continue
        if len(fmts) != 1:
            blockers.append(
                {
                    "vd0Offset": off0,
                    "reason": "mixed worldVertFormat values within vd0 allocation",
                    "formats": sorted(fmts),
                }
            )
            continue
        off1s = sorted({int(s["vertexDataOffset1"]) for s in members})
        if len(off1s) != 1:
            blockers.append(
                {
                    "vd0Offset": off0,
                    "reason": "mixed vertexDataOffset1 values within vd0 allocation",
                    "offsets1": off1s,
                }
            )
            continue
        fmt = next(iter(fmts))
        groups.append(
            {
                "groupIndex": gi,
                "vd0Offset": off0,
                "vd0SpanBytes": span0,
                "vd1Offset": off1s[0],
                "vertexCount": vc,
                "worldVertFormat": fmt,
                "formatName": MaterialWorldVertexFormat(fmt).name,
                "surfaceIndices": [int(s["index"]) for s in members],
                "materials": sorted(material_names),
            }
        )

    raw_layout = derive_allocations(groups, vd1)
    format_summary: dict[str, dict] = {}
    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        observed = raw_layout["observedRawStrideCandidatesByFormat"].get(str(fmt), [])
        format_summary[str(fmt)] = {
            "format": fmt,
            "name": fmt_enum.name,
            "formulaHypothesisStride": int(spec.vd1_stride),
            "rawStrideCandidatesObservedInThisFixture": observed,
            "formulaSupportedByThisFixture": (
                int(spec.vd1_stride) in observed if observed else None
            ),
            "semanticFieldsHypothesis": list(spec.vd1_fields),
            "semanticFieldsProvenByThisTool": False,
        }

    return {
        "format": "t6-world-vd1-raw-census-v1",
        "map": map_name,
        "source": {
            "surfaces": str(surfaces_path),
            "vd0": str(vd0_path),
            "vd1": str(vd1_path),
            "materials": str(materials_path),
            "catalog": str(catalog_path),
            "prefix": str(prefix_path),
            "assetPointerArrayVirtualBase": asset_pointer_array_virtual_base,
        },
        "policy": {
            "vertexCount": "derived from serialized vd0 allocation extent, independent of vd1 formula",
            "vd1Stride": "derived from next distinct serialized vertexDataOffset1 divided by derived vertex count",
            "sharedOffsets": "kept ambiguous when member vertex counts differ",
            "formulaComparison": "current WORLD_VERTEX_FORMATS stride is reported only after raw derivation",
            "columnSemantics": "unassigned; statistics only",
            "retailProof": "requires retained retail source bytes; synthetic results do not promote format proof",
        },
        "stats": {
            "surfaceCount": len(surfaces),
            "resolvedVertexGroupCount": len(groups),
            "groupBlockerCount": len(blockers),
            "distinctVd1OffsetCount": len(raw_layout["allocations"]),
            "unambiguousVd1AllocationCount": sum(
                1 for row in raw_layout["allocations"] if row["unambiguousRawStride"] is not None
            ),
        },
        "formatSummary": format_summary,
        "groups": groups,
        **raw_layout,
        "blockers": blockers,
        "proofBoundary": (
            "raw serialized allocation stride may be promoted from retained retail bytes; "
            "UV/color/normal-transform meaning remains a separate semantic proof"
        ),
    }


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
