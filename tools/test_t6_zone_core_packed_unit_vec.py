#!/usr/bin/env python3
"""Regression for T6 PackedUnitVec third-based pack/unpack semantics."""
from __future__ import annotations

import math
import struct

from t6_zone_core import (
    decode_world_vd0_vertex,
    pack_unit_vec_third_based,
    unpack_unit_vec_third_based,
)


def _length(v: tuple[float, float, float] | list[float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


def _normalized(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = _length(v)
    return tuple(float(x) / n for x in v)


def main() -> int:
    exact = [
        ((1.0, 0.0, 0.0), 0x000001FF),
        ((-1.0, 0.0, 0.0), 0x00000201),
        ((0.0, 1.0, 0.0), 0x0007FC00),
        ((0.0, 0.0, 1.0), 0x1FF00000),
    ]
    for vector, packed in exact:
        actual = pack_unit_vec_third_based(vector)
        assert actual == packed, (vector, hex(actual), hex(packed))
        decoded = unpack_unit_vec_third_based(actual)
        assert decoded == vector, (vector, decoded)

    fixtures = [
        _normalized((1.0, 1.0, 1.0)),
        _normalized((-0.4, 0.3, 0.8660254)),
        _normalized((0.123, -0.975, 0.184)),
        _normalized((-0.7071, 0.0, 0.7071)),
    ]
    worst_length_error = 0.0
    worst_direction_error = 0.0
    for vector in fixtures:
        decoded = unpack_unit_vec_third_based(pack_unit_vec_third_based(vector))
        length_error = abs(_length(decoded) - 1.0)
        dot = sum(a * b for a, b in zip(vector, decoded))
        direction_error = abs(dot - 1.0)
        worst_length_error = max(worst_length_error, length_error)
        worst_direction_error = max(worst_direction_error, direction_error)
        assert length_error < 0.002, (vector, decoded, length_error)
        assert direction_error < 0.002, (vector, decoded, direction_error)

    normal = pack_unit_vec_third_based((0.0, 0.0, 1.0))
    tangent = pack_unit_vec_third_based((1.0, 0.0, 0.0))
    row = bytearray(36)
    struct.pack_into("<3f", row, 0, 1.0, 2.0, 3.0)
    struct.pack_into("<f", row, 12, -1.0)
    row[16:20] = bytes((10, 20, 30, 255))
    struct.pack_into("<2e", row, 20, 0.25, 0.75)
    struct.pack_into("<I", row, 24, normal)
    struct.pack_into("<I", row, 28, tangent)
    struct.pack_into("<HH", row, 32, 0, 65535)
    decoded = decode_world_vd0_vertex(bytes(row))
    assert decoded["normal"] == [0.0, 0.0, 1.0]
    assert decoded["tangent"] == [1.0, 0.0, 0.0]
    assert decoded["normalPacked"] == normal
    assert decoded["tangentPacked"] == tangent
    assert decoded["lightmapUV"] == [0.0, 1.0]

    print("PASS T6 PackedUnitVec third-based regression")
    print(f"worstLengthError={worst_length_error:.9g}")
    print(f"worstDirectionError={worst_direction_error:.9g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
