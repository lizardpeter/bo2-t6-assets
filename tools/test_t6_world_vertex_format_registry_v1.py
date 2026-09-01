#!/usr/bin/env python3
"""Regression for retail-gated T6 world vertex format promotion."""
from __future__ import annotations

from t6_world_vertex_format_registry_v1 import build_registry
from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


BASE_PROVEN = {0, 1, 2, 3, 6}


def _baseline() -> dict:
    formats = {}
    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        formats[str(fmt)] = {
            "format": fmt,
            "name": fmt_enum.name,
            "uvCount": spec.uv_count,
            "normalCount": spec.normal_count,
            "vd1Stride": spec.vd1_stride,
            "vd1Fields": list(spec.vd1_fields),
            "retailByteProven": fmt in BASE_PROVEN,
            "maps": ["mp_nuketown_2020"] if fmt in BASE_PROVEN else [],
        }
    return {
        "format": "t6-world-vertex-format-census-v1",
        "formats": formats,
        "maps": [{"map": "mp_nuketown_2020"}],
    }


def _raw(map_name: str, observed: dict[str, list[int]], blockers=None) -> dict:
    return {
        "format": "t6-world-vd1-raw-census-v2",
        "map": map_name,
        "observedRawStrideByFormat": observed,
        "blockers": list(blockers or []),
    }


def main() -> int:
    # Baseline alone must reproduce the current 5/9 proof boundary.
    baseline = build_registry(_baseline(), [])
    assert baseline["coverage"]["exportEnabledFormats"] == [0, 1, 2, 3, 6]
    assert baseline["coverage"]["pendingFormats"] == [4, 5, 7, 8]
    assert baseline["coverage"]["allFormatsExportEnabled"] is False

    # Clean unambiguous exact strides promote pending formats.
    promoted = build_registry(
        _baseline(),
        [
            (
                "raid.raw.json",
                _raw("mp_raid", {"4": [12], "5": [16]}),
            ),
            (
                "slums.raw.json",
                _raw("mp_slums", {"7": [16], "8": [20]}),
            ),
        ],
    )
    assert promoted["coverage"]["exportEnabledFormats"] == list(range(9))
    assert promoted["coverage"]["pendingFormats"] == []
    assert promoted["coverage"]["allFormatsExportEnabled"] is True
    for fmt in (4, 5, 7, 8):
        row = promoted["formats"][str(fmt)]
        assert row["rawStrideRetailProven"] is True
        assert row["retailByteProven"] is True
        assert row["exportEnabled"] is True
        assert "unambiguous-retail-vd1-allocation-stride" in row["proofKinds"]

    # A blocked census is retained as evidence but cannot promote.
    blocked = build_registry(
        _baseline(),
        [
            (
                "blocked.raw.json",
                _raw("mp_blocked", {"4": [12]}, blockers=[{"reason": "fixture blocker"}]),
            )
        ],
    )
    assert blocked["formats"]["4"]["exportEnabled"] is False
    assert blocked["formats"]["4"]["rawEvidenceWithBlockers"] == ["blocked.raw.json"]

    # Any clean contradictory raw stride is a hard failure even for a format
    # that already had an older direct proof. Contradictions are never buried.
    contradicted = build_registry(
        _baseline(),
        [
            (
                "contradiction.raw.json",
                _raw("mp_contradiction", {"1": [8], "7": [20]}),
            )
        ],
    )
    assert contradicted["formats"]["1"]["baselineDirectRetailProof"] is True
    assert contradicted["formats"]["1"]["exportEnabled"] is False
    assert contradicted["formats"]["1"]["contradictoryRawStrides"] == [8]
    assert contradicted["formats"]["7"]["exportEnabled"] is False
    assert contradicted["formats"]["7"]["contradictoryRawStrides"] == [20]
    assert contradicted["coverage"]["contradictedFormats"] == [1, 7]

    # Source-closed table identity must match the canonical enum/spec exactly.
    assert promoted["formats"]["8"]["sourceClosedFamily"] == {
        "uvCount": 4,
        "normalCount": 3,
        "vd1Stride": 20,
        "vd1Fields": ["uv1", "uv2", "uv3", "normalTransform0", "normalTransform1"],
        "layoutRule": (
            "vd0 owns uv0 + first normal/tangent basis; vd1 appends "
            "4-byte half2 UV lanes then 4-byte packed normal-transform lanes"
        ),
    }

    print("PASS t6_world_vertex_format_registry_v1 retail promotion regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
