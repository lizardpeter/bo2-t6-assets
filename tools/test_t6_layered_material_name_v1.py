#!/usr/bin/env python3
"""Regression for t6_layered_material_name_v1."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from t6_layered_material_name_v1 import (
    LayeredMaterialError,
    build_fixture_census,
    parse_layered_material_name,
)


def _assert_raises(fn, contains: str) -> None:
    try:
        fn()
    except LayeredMaterialError as exc:
        assert contains in str(exc), (contains, str(exc))
    else:
        raise AssertionError(f"expected LayeredMaterialError containing {contains!r}")


def _write_mapping(path: Path) -> None:
    fields = ["materialIndex", "materialName", "textureCount"]
    rows = [
        {"materialIndex": 0, "materialName": "wpc/base_normal", "textureCount": 3},
        {"materialIndex": 1, "materialName": "wpc/decal", "textureCount": 2},
        {"materialIndex": 2, "materialName": "wpc/grunge", "textureCount": 1},
        {
            "materialIndex": 3,
            "materialName": "*22n_14(wpc/base_normal:wpc/decal)",
            "textureCount": 5,
        },
        {
            "materialIndex": 4,
            "materialName": "*22n_14_127(wpc/base_normal:wpc/decal:wpc/grunge)",
            "textureCount": 6,
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_proof(path: Path) -> None:
    doc = {
        "format": "t6-world-vertex-proof-v1",
        "map": "synthetic_layered",
        "badGroupCount": 0,
        "groups": [
            {
                "groupIndex": 0,
                "worldVertFormat": 1,
                "materials": ["*22n_14(wpc/base_normal:wpc/decal)"],
            },
            {
                "groupIndex": 1,
                "worldVertFormat": 3,
                "materials": ["*22n_14_127(wpc/base_normal:wpc/decal:wpc/grunge)"],
            },
        ],
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    two = parse_layered_material_name(
        "*22n_14(wpc/hjk_interior_plastic_tile:wpc/pb_decal_wall_fillet_2_blend)"
    )
    assert two["layerCount"] == 2
    assert two["expectedNormalMapLayerCount"] == 1
    assert two["layers"] == [
        {
            "layerIndex": 0,
            "token": "22n",
            "bspMaterialIndex": 22,
            "marker": "n",
            "expectedNormalMap": True,
            "explicitNoNormalMarker": False,
            "componentMaterial": "wpc/hjk_interior_plastic_tile",
        },
        {
            "layerIndex": 1,
            "token": "14",
            "bspMaterialIndex": 14,
            "marker": None,
            "expectedNormalMap": False,
            "explicitNoNormalMarker": False,
            "componentMaterial": "wpc/pb_decal_wall_fillet_2_blend",
        },
    ]

    three = parse_layered_material_name(
        "*360n_9_127(wpc/nt_2020_wallpaper_04:wpc/ao_decal_ramp:wpc/decal_grunge_lightstain_04)"
    )
    assert [layer["bspMaterialIndex"] for layer in three["layers"]] == [360, 9, 127]
    assert [layer["expectedNormalMap"] for layer in three["layers"]] == [True, False, False]

    four = parse_layered_material_name(
        "*1n_2_3n_4(wpc/a:wpc/b:wpc/c:wpc/d)"
    )
    assert four["layerCount"] == 4
    assert four["expectedNormalMapLayerCount"] == 2

    old_x = parse_layered_material_name("*7x_8n(wpc/a:wpc/b)")
    assert old_x["layers"][0]["explicitNoNormalMarker"] is True
    assert old_x["layers"][0]["expectedNormalMap"] is False
    assert old_x["layers"][1]["expectedNormalMap"] is True

    _assert_raises(
        lambda: parse_layered_material_name("*22n_14(wpc/only_one)"),
        "token/component count mismatch",
    )
    _assert_raises(
        lambda: parse_layered_material_name("*1_2_3_4_5(wpc/a:wpc/b:wpc/c:wpc/d:wpc/e)"),
        "outside 1..4",
    )
    _assert_raises(
        lambda: parse_layered_material_name("*22q_14(wpc/a:wpc/b)"),
        "invalid layer token",
    )
    _assert_raises(
        lambda: parse_layered_material_name("not_layered"),
        "not a supported layered material identity",
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mapping = root / "mapping.csv"
        proof = root / "proof.json"
        _write_mapping(mapping)
        _write_proof(proof)
        census = build_fixture_census(mapping, proof)
        stats = census["stats"]
        assert stats["uniqueMaterialCount"] == 5
        assert stats["ordinaryMaterialCount"] == 3
        assert stats["compoundMaterialCount"] == 2
        assert stats["layerCountHistogram"] == {"2": 1, "3": 1}
        assert stats["expectedNormalMapLayerCountHistogram"] == {"1": 2}
        assert stats["observedWorldVertFormatCompoundCounts"] == {"1": 1, "3": 1}
        assert stats["exactGeneratedTextureCountSumProofs"] == 2
        assert stats["pendingGeneratedTextureCountSums"] == 0
        assert stats["generatedTextureCountSumFailures"] == 0
        assert stats["worldLayoutFailures"] == 0
        assert census["retailFindings"]["tokenComponentBijection"] is True
        assert census["tokenToComponent"] == {
            "9": "wpc/ao_decal_ramp",
            "14": "wpc/decal",
            "22n": "wpc/base_normal",
            "127": "wpc/grunge",
        }

    print("PASS t6_layered_material_name_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
