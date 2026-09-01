#!/usr/bin/env python3
"""Regression for source-closed T6 layered worldVertFormat selection."""
from __future__ import annotations

from t6_layered_world_format_v1 import (
    LayeredWorldFormatError,
    format_for_counts,
    predict_from_name,
)
from t6_zone_core import MaterialWorldVertexFormat


def main() -> int:
    expected = {
        (2, 0): MaterialWorldVertexFormat.TEX_2_NRM_1,
        (2, 1): MaterialWorldVertexFormat.TEX_2_NRM_1,
        (2, 2): MaterialWorldVertexFormat.TEX_2_NRM_2,
        (3, 0): MaterialWorldVertexFormat.TEX_3_NRM_1,
        (3, 1): MaterialWorldVertexFormat.TEX_3_NRM_1,
        (3, 2): MaterialWorldVertexFormat.TEX_3_NRM_2,
        (3, 3): MaterialWorldVertexFormat.TEX_3_NRM_3,
        (4, 0): MaterialWorldVertexFormat.TEX_4_NRM_1,
        (4, 1): MaterialWorldVertexFormat.TEX_4_NRM_1,
        (4, 2): MaterialWorldVertexFormat.TEX_4_NRM_2,
        (4, 3): MaterialWorldVertexFormat.TEX_4_NRM_3,
    }
    for counts, fmt in expected.items():
        assert format_for_counts(*counts) == fmt, (counts, fmt)

    assert predict_from_name("*22n_14(wpc/base:wpc/decal)")["worldVertFormat"] == 1
    assert predict_from_name("*65n_82n(wpc/a:wpc/b)")["worldVertFormat"] == 2
    assert predict_from_name("*1n_2n_3(wpc/a:wpc/b:wpc/c)")["worldVertFormat"] == 4
    assert predict_from_name("*1n_2n_3n(wpc/a:wpc/b:wpc/c)")["worldVertFormat"] == 5
    assert predict_from_name("*1n_2n_3_4(wpc/a:wpc/b:wpc/c:wpc/d)")["worldVertFormat"] == 7
    assert predict_from_name("*1n_2n_3n_4(wpc/a:wpc/b:wpc/c:wpc/d)")["worldVertFormat"] == 8

    for bad in ((1, 0), (5, 1), (2, 3), (3, -1)):
        try:
            format_for_counts(*bad)
        except LayeredWorldFormatError:
            pass
        else:
            raise AssertionError(f"invalid counts were accepted: {bad}")

    print("PASS t6_layered_world_format_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
