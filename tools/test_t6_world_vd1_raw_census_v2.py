#!/usr/bin/env python3
"""Regression for raw T6 world vd1 allocation/stride census v2."""
from __future__ import annotations

import struct

from t6_world_vd1_raw_census_v2 import derive_allocations


def _row(off0: int, off1: int, vc: int, fmt: int, surface: int) -> dict:
    return {
        "vd0Offset": off0,
        "vd1Offset": off1,
        "vertexCount": vc,
        "worldVertFormat": fmt,
        "surfaceIndices": [surface],
        "materials": [f"m{fmt}_{surface}"],
    }


def _word(a: float, b: float) -> bytes:
    return struct.pack("<2e", a, b)


def main() -> int:
    # Allocation map:
    #   0..24    shared by vc=2/fmt4 and vc=3/fmt0 -> ambiguous, do not promote
    #   24..72   vc=3/fmt5 => raw stride 16 (matches formula)
    #   72..96   vc=2/fmt7 => raw stride 12 (deliberate formula contradiction)
    #   96..136  vc=2/fmt8 => raw stride 20 (proves census can observe 20 if bytes do)
    groups = [
        _row(0, 0, 2, 4, 0),
        _row(80, 0, 3, 0, 1),
        _row(192, 24, 3, 5, 2),
        _row(304, 72, 2, 7, 3),
        _row(384, 96, 2, 8, 4),
    ]

    raw = bytearray(136)
    # Fill the unambiguous allocations with deterministic 4-byte columns.
    for vertex in range(3):
        for column in range(4):
            start = 24 + vertex * 16 + column * 4
            raw[start : start + 4] = _word(0.1 * (vertex + 1), 0.2 * (column + 1))
    for vertex in range(2):
        for column in range(3):
            start = 72 + vertex * 12 + column * 4
            raw[start : start + 4] = bytes((10 + vertex, 20 + column, 30, 255))
    for vertex in range(2):
        for column in range(5):
            start = 96 + vertex * 20 + column * 4
            raw[start : start + 4] = _word(0.25 * (vertex + 1), 0.125 * (column + 1))

    doc = derive_allocations(groups, bytes(raw))
    allocations = doc["allocations"]
    assert len(allocations) == 4

    shared = allocations[0]
    assert shared["vd1Offset"] == 0
    assert shared["rawSpanBytes"] == 24
    assert shared["memberVertexCounts"] == [2, 3]
    assert shared["exactRawStrideCandidates"] == [8, 12]
    assert shared["unambiguousRawStride"] is None
    assert shared["columnStats"] == []
    assert "0" not in doc["observedRawStrideByFormat"]
    assert "4" not in doc["observedRawStrideByFormat"]

    fmt5 = allocations[1]
    assert fmt5["unambiguousRawStride"] == 16
    assert fmt5["unambiguousVertexCount"] == 3
    assert len(fmt5["columnStats"]) == 4
    assert fmt5["memberCandidates"][0]["formulaHypothesisStride"] == 16
    assert fmt5["memberCandidates"][0]["formulaMatchesRawCandidate"] is True

    fmt7 = allocations[2]
    assert fmt7["unambiguousRawStride"] == 12
    assert len(fmt7["columnStats"]) == 3
    assert fmt7["memberCandidates"][0]["formulaHypothesisStride"] == 16
    assert fmt7["memberCandidates"][0]["formulaMatchesRawCandidate"] is False

    fmt8 = allocations[3]
    assert fmt8["unambiguousRawStride"] == 20
    assert fmt8["unambiguousVertexCount"] == 2
    assert len(fmt8["columnStats"]) == 5
    assert fmt8["memberCandidates"][0]["formulaHypothesisStride"] == 20
    assert fmt8["memberCandidates"][0]["formulaMatchesRawCandidate"] is True
    assert all(column["semantic"] == "unassigned" for column in fmt8["columnStats"])

    assert doc["observedRawStrideByFormat"] == {
        "5": [16],
        "7": [12],
        "8": [20],
    }

    # Non-divisible final extent remains visible and is not promoted.
    broken = derive_allocations([_row(0, 0, 3, 5, 0)], b"\0" * 47)
    assert broken["allocations"][0]["unambiguousRawStride"] is None
    assert broken["observedRawStrideByFormat"] == {}

    print("PASS t6_world_vd1_raw_census_v2 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
