#!/usr/bin/env python3
"""Build the authoritative T6 world-vertex export eligibility registry.

The T6 format family (0..8) is source-closed, but formula knowledge is not the
same thing as retail byte validation. This registry deliberately separates:

1. source-closed binary family/layout knowledge;
2. direct retail observation of a format;
3. independent raw vd1 allocation-stride evidence; and
4. final decoder/export eligibility.

Existing direct byte proofs (for example the Nuketown census) remain valid.
Previously-unproven formats can be promoted only when a supported raw census
contains an unambiguous raw stride equal to the source-closed family stride and
no clean fixture reports a contradictory stride.

Accepted raw evidence formats:
- t6-world-vd1-raw-census-v2 (full material/prefix reconstruction path)
- t6-world-vd1-layout-census-v1 (standalone layout + exact vd1 bridge path)

This makes format promotion data-driven: adding a clean retail fixture can
enable a format without weakening the decoder or hand-editing a pending list.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from t6_zone_core import WORLD_VERTEX_FORMATS


class WorldVertexFormatRegistryError(RuntimeError):
    pass


RAW_CENSUS_FORMATS = {
    "t6-world-vd1-raw-census-v2",
    "t6-world-vd1-layout-census-v1",
}


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WorldVertexFormatRegistryError(f"{path}: top level must be an object")
    return value


def _validate_baseline(census: dict) -> None:
    if census.get("format") != "t6-world-vertex-format-census-v1":
        raise WorldVertexFormatRegistryError(
            f"unsupported baseline census {census.get('format')!r}"
        )
    formats = census.get("formats")
    if not isinstance(formats, dict):
        raise WorldVertexFormatRegistryError("baseline census has no formats object")
    if set(formats) != {str(i) for i in range(9)}:
        raise WorldVertexFormatRegistryError(
            f"baseline census format keys must be exactly 0..8, got {sorted(formats)}"
        )

    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        row = formats[str(fmt)]
        expected = {
            "name": fmt_enum.name,
            "uvCount": int(spec.uv_count),
            "normalCount": int(spec.normal_count),
            "vd1Stride": int(spec.vd1_stride),
            "vd1Fields": list(spec.vd1_fields),
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise WorldVertexFormatRegistryError(
                    f"baseline format {fmt} {key}={row.get(key)!r} != source-closed {value!r}"
                )


def _validate_raw_census(report: dict, source: str) -> None:
    fmt = report.get("format")
    if fmt not in RAW_CENSUS_FORMATS:
        raise WorldVertexFormatRegistryError(
            f"{source}: unsupported raw census {fmt!r}; expected one of {sorted(RAW_CENSUS_FORMATS)}"
        )
    observed = report.get("observedRawStrideByFormat")
    if not isinstance(observed, dict):
        raise WorldVertexFormatRegistryError(
            f"{source}: raw census lacks observedRawStrideByFormat"
        )
    blockers = report.get("blockers", [])
    if blockers is None:
        blockers = []
    if not isinstance(blockers, list):
        raise WorldVertexFormatRegistryError(f"{source}: blockers must be a list")


def _fixture_name(report: dict, fallback: str) -> str:
    for key in ("map", "mapName", "worldName", "zone"):
        value = report.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def build_registry(
    baseline_census: dict,
    raw_censuses: list[tuple[str, dict]],
) -> dict:
    _validate_baseline(baseline_census)
    for source, report in raw_censuses:
        _validate_raw_census(report, source)

    baseline_formats = baseline_census["formats"]
    rows: dict[str, dict[str, Any]] = {}

    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        baseline = baseline_formats[str(fmt)]
        expected_stride = int(spec.vd1_stride)

        direct_maps = sorted({str(v) for v in baseline.get("maps", []) if str(v)})
        baseline_proven = bool(baseline.get("retailByteProven"))
        raw_rows: list[dict] = []
        observed_strides: set[int] = set()
        raw_blocked_sources: list[str] = []

        for source, report in raw_censuses:
            values = report.get("observedRawStrideByFormat", {}).get(str(fmt), [])
            if not isinstance(values, list):
                raise WorldVertexFormatRegistryError(
                    f"{source}: format {fmt} observed stride entry must be a list"
                )
            strides = sorted({int(v) for v in values})
            if not strides:
                continue
            blockers = list(report.get("blockers") or [])
            fixture = _fixture_name(report, source)
            raw_rows.append(
                {
                    "fixture": fixture,
                    "source": source,
                    "censusFormat": report.get("format"),
                    "observedRawStrides": strides,
                    "blockerCount": len(blockers),
                    "clean": len(blockers) == 0,
                }
            )
            if blockers:
                raw_blocked_sources.append(source)
                continue
            observed_strides.update(strides)

        contradictory = sorted(s for s in observed_strides if s != expected_stride)
        matching_stride_observed = expected_stride in observed_strides
        raw_stride_proven = matching_stride_observed and not contradictory

        # A prior direct retail proof remains sufficient, but any clean new
        # contradictory raw allocation is a hard stop rather than being ignored.
        retail_byte_proven = (baseline_proven or raw_stride_proven) and not contradictory
        export_enabled = retail_byte_proven and not contradictory

        proof_kinds: list[str] = []
        if baseline_proven:
            proof_kinds.append("direct-retail-vertex-proof")
        if raw_stride_proven:
            proof_kinds.append("unambiguous-retail-vd1-allocation-stride")

        maps = set(direct_maps)
        for raw in raw_rows:
            if raw["clean"] and expected_stride in raw["observedRawStrides"]:
                maps.add(str(raw["fixture"]))

        rows[str(fmt)] = {
            "format": fmt,
            "name": fmt_enum.name,
            "sourceClosedFamily": {
                "uvCount": int(spec.uv_count),
                "normalCount": int(spec.normal_count),
                "vd1Stride": expected_stride,
                "vd1Fields": list(spec.vd1_fields),
                "layoutRule": (
                    "vd0 owns uv0 + first normal/tangent basis; vd1 appends "
                    "4-byte half2 UV lanes then 4-byte packed normal-transform lanes"
                ),
            },
            "baselineDirectRetailProof": baseline_proven,
            "baselineMaps": direct_maps,
            "rawAllocationEvidence": raw_rows,
            "cleanObservedRawStrides": sorted(observed_strides),
            "matchingExpectedRawStrideObserved": matching_stride_observed,
            "rawStrideRetailProven": raw_stride_proven,
            "contradictoryRawStrides": contradictory,
            "rawEvidenceWithBlockers": sorted(set(raw_blocked_sources)),
            "retailByteProven": retail_byte_proven,
            "exportEnabled": export_enabled,
            "proofKinds": proof_kinds,
            "retailProofMaps": sorted(maps),
            "status": (
                "contradicted"
                if contradictory
                else "export-enabled"
                if export_enabled
                else "pending-retail-byte-proof"
            ),
        }

    enabled = [i for i in range(9) if rows[str(i)]["exportEnabled"]]
    pending = [i for i in range(9) if not rows[str(i)]["exportEnabled"]]
    contradicted = [i for i in range(9) if rows[str(i)]["contradictoryRawStrides"]]

    return {
        "format": "t6-world-vertex-format-registry-v1",
        "sourceClosedFormatCount": 9,
        "formats": rows,
        "coverage": {
            "exportEnabledCount": len(enabled),
            "exportEnabledFormats": enabled,
            "pendingCount": len(pending),
            "pendingFormats": pending,
            "contradictedCount": len(contradicted),
            "contradictedFormats": contradicted,
            "allFormatsExportEnabled": len(enabled) == 9,
        },
        "inputs": {
            "baselineFormat": baseline_census.get("format"),
            "baselineMapCount": len(baseline_census.get("maps", [])),
            "rawCensusCount": len(raw_censuses),
            "rawCensusSources": [source for source, _ in raw_censuses],
            "acceptedRawCensusFormats": sorted(RAW_CENSUS_FORMATS),
        },
        "policy": {
            "formulaAloneCannotEnableExport": True,
            "ambiguousRawAllocationCannotPromote": True,
            "rawCensusWithBlockersCannotPromote": True,
            "cleanContradictoryStrideDisablesFormat": True,
            "directExistingRetailProofRemainsValid": True,
            "pendingFormatPromotionRequiresExpectedUnambiguousRawStride": True,
        },
        "proofBoundary": (
            "exportEnabled certifies the serialized world-vertex binary layout needed "
            "for normalized geometry export. Packed normalTransformN words remain raw "
            "unless/until their downstream shader-space meaning is independently closed; "
            "this registry does not invent that renderer semantic."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--raw-census", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    baseline = _load(args.baseline)
    raw = [(str(path), _load(path)) for path in args.raw_census]
    registry = build_registry(baseline, raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.out), **registry["coverage"]}, indent=2))
    if registry["coverage"]["contradictedCount"]:
        return 3
    return 0 if registry["coverage"]["allFormatsExportEnabled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
