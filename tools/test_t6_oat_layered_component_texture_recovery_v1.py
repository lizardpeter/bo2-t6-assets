#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_layered_component_texture_recovery_v1 as recover


def _write(root: Path, identity: str, textures: list[dict]) -> None:
    path = root / f"{identity}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "_game": "t6",
                "_type": "material",
                "_version": 1,
                "techniqueSet": "test",
                "textures": textures,
            }
        ),
        encoding="utf-8",
    )


def _tex(name: str, semantic: str) -> dict:
    return {
        "name": semantic,
        "semantic": semantic,
        "image": name,
        "samplerState": 0,
    }


def _catalog(names: list[str]) -> dict:
    return {
        "format": "t6-world-surface-material-catalog-source-v3-legacy-index-v1",
        "map": "synthetic",
        "materials": [{"index": i, "name": name} for i, name in enumerate(names)],
    }


def main() -> int:
    known = [_tex("known_c", "colorMap")]
    missing_normal = [
        _tex("missing_n", "normalMap"),
        _tex("missing_c", "colorMap"),
    ]
    missing_color = [_tex("overlay_c", "colorMap")]

    g1 = "*1_2n(wpc/known:wpc/missing_normal)"
    g2 = "*2n_3_3(wpc/missing_normal:wpc/missing_color:wpc/missing_color)"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root, "wpc/known", known)
        _write(root, "generated/_1_2n", known + missing_normal)
        _write(
            root,
            "generated/_2n_3_3",
            missing_normal + missing_color + missing_color,
        )
        doc = recover.build_recovery(
            material_root=root,
            catalog_doc=_catalog([g1, g2]),
            targets=["wpc/missing_normal", "wpc/missing_color"],
        )
        s = doc["summary"]
        assert s == {
            "targetCount": 2,
            "recoveredTargetCount": 2,
            "standaloneMissingComponentCount": 2,
            "generatedCatalogMaterialCount": 2,
            "allGeneratedExactReconstructionCount": 2,
            "targetBearingGeneratedMaterialCount": 2,
            "targetGeneratedLayerOccurrenceCount": 4,
        }, s
        rows = {row["identity"]: row for row in doc["components"]}
        normal = rows["wpc/missing_normal"]
        assert normal["bspMaterialIndex"] == 2
        assert normal["expectedNormalMap"] is True
        assert normal["textures"] == missing_normal
        assert normal["generatedMaterialCount"] == 2
        assert len(normal["recoveryEvidence"]) == 2

        color = rows["wpc/missing_color"]
        assert color["bspMaterialIndex"] == 3
        assert color["expectedNormalMap"] is False
        assert color["textures"] == missing_color
        assert color["generatedMaterialCount"] == 1
        assert color["generatedLayerOccurrenceCount"] == 2
        assert color["recoveryEvidence"][0]["unknownLayerMultiplicity"] == 2

        _write(root, "wpc/missing_color", missing_color)
        try:
            recover.build_recovery(
                material_root=root,
                catalog_doc=_catalog([g1, g2]),
                targets=["wpc/missing_normal", "wpc/missing_color"],
            )
        except recover.RecoveryError as exc:
            assert "unexpectedly have standalone" in str(exc)
        else:
            raise AssertionError("standalone target was not rejected")

    print(
        "PASS: exact layered component texture recovery is iterative, "
        "repeated-layer aware, cross-occurrence validated, and fail-closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
