#!/usr/bin/env python3
from __future__ import annotations

from math import isclose

from t6_directional_lightmap_semantics_v1 import (
    ALPHA_EPSILON,
    decode_direction,
    directional_factor,
    directional_lightmap_row_uvs,
    evaluate_directional_lightmap,
    normalize_lightmap_rgb,
    renderer_contract,
)


def _close(actual, expected, eps=1e-9):
    assert len(actual) == len(expected)
    assert all(isclose(float(a), float(b), abs_tol=eps) for a, b in zip(actual, expected)), (actual, expected)


def main() -> int:
    rows = directional_lightmap_row_uvs((0.25, 0.75))
    _close(rows.row0_uv, (0.25, 0.25))
    _close(rows.row1_uv, (0.25, 0.25 + 1.0 / 3.0))
    _close(rows.row2_uv, (0.25, 0.25 + 2.0 / 3.0))

    _close(decode_direction((1.0, 0.5, 0.0, 0.7)), (1.0, 0.0, -1.0))
    assert isclose(directional_factor((1.0, 0.5, 0.5, 1.0), (1.0, 0.0, 0.0)), 1.0)
    assert isclose(directional_factor((0.0, 0.5, 0.5, 1.0), (1.0, 0.0, 0.0)), 0.0)
    # Prove saturate, not direction normalization: decoded x=0.5 and N=(1,0,0)
    # yields exactly 0.5.
    assert isclose(directional_factor((0.75, 0.5, 0.5, 1.0), (1.0, 0.0, 0.0)), 0.5)

    row = normalize_lightmap_rgb((0.2, 0.4, 0.6, 0.5))
    _close(row, tuple(v / (0.5 + ALPHA_EPSILON) for v in (0.2, 0.4, 0.6)))

    row0 = (0.2, 0.1, 0.05, 0.5)
    row1 = (0.3, 0.6, 0.9, 0.25)
    row2 = (0.75, 0.5, 0.5, 1.0)  # direction=(0.5,0,0); factor=0.5
    got = evaluate_directional_lightmap(row0, row1, row2, (1.0, 0.0, 0.0))
    expected0 = [v / (0.5 + ALPHA_EPSILON) for v in row0[:3]]
    expected1 = [v / (0.25 + ALPHA_EPSILON) for v in row1[:3]]
    expected = [expected0[i] + expected1[i] * 0.5 for i in range(3)]
    _close(got, expected)

    contract = renderer_contract()
    assert contract["lightmapUvAttribute"] == "TEXCOORD_1"
    assert contract["verticalRows"] == 3
    assert contract["directionRenormalized"] is False

    print("PASS: T6 directional lightmap semantics v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
