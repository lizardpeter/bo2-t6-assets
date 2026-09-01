#!/usr/bin/env python3
"""Regression for exact T6 GfxImage identity -> OAT DDS filename mapping."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from t6_oat_material_manifest_v2 import OatMaterialManifestError
from t6_oat_material_manifest_v3 import build_manifest


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _material(image: str, semantic: str) -> dict:
    return {
        "$schema": "http://openassettools.dev/schema/material.v1.json",
        "_game": "t6",
        "_type": "material",
        "_version": 1,
        "techniqueSet": "wpc_lit_sm_r0c0_test",
        "cameraRegion": "litOpaque",
        "textures": [
            {
                "image": image,
                "name": semantic,
                "semantic": semantic,
                "isMatureContent": False,
                "samplerState": {
                    "clampU": False,
                    "clampV": False,
                    "clampW": False,
                    "filter": "aniso4x",
                    "mipMap": "linear",
                },
            }
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mats = root / "materials"
        _write(mats / "wpc" / "star.json", _material("*generated_color", "colorMap"))
        _write(mats / "wpc" / "plain.json", _material("plain_normal", "normalMap"))

        catalog = {
            "materials": [
                {"index": 0, "name": "wpc/star", "surfacePointerHex": "0x1"},
                {"index": 1, "name": "wpc/plain", "surfacePointerHex": "0x2"},
            ]
        }
        doc = build_manifest(
            material_root=mats,
            catalog_doc=catalog,
            source_texture_extension=".dds",
        )

        assert doc["format"] == "t6-material-texture-manifest-v1"
        assert doc["source"]["producer"] == "t6_oat_material_manifest_v3.py"
        assert doc["stats"]["oatImageMappedDependencyCount"] == 2
        assert doc["stats"]["oatImageFilenameChangedDependencyCount"] == 1

        by_name = {entry["material"]: entry for entry in doc["materials"]}
        star = by_name["wpc/star"]
        dep = star["layers"][0]["textures"][0]
        assert dep["imageAsset"] == "*generated_color"
        assert dep["sourceOatImageAsset"] == "*generated_color"
        assert dep["sourceTexture"] == "_generated_color.dds"
        assert dep["sourceOatImagePath"] == "images/_generated_color.dds"
        assert star["standardPreview"]["baseColorTexture"]["sourceTexture"] == "_generated_color.dds"
        assert star["standardPreview"]["baseColorTexture"]["sourceOatImagePath"] == "images/_generated_color.dds"

        plain = by_name["wpc/plain"]
        plain_dep = plain["layers"][0]["textures"][0]
        assert plain_dep["imageAsset"] == "plain_normal"
        assert plain_dep["sourceTexture"] == "plain_normal.dds"
        assert plain_dep["sourceOatImagePath"] == "images/plain_normal.dds"
        assert plain["standardPreview"]["normalTexture"]["sourceTexture"] == "plain_normal.dds"

        doc2 = build_manifest(
            material_root=mats,
            catalog_doc=copy.deepcopy(catalog),
            source_texture_extension=".dds",
        )
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        try:
            build_manifest(
                material_root=mats,
                catalog_doc=catalog,
                source_texture_extension="dds",
            )
        except OatMaterialManifestError:
            pass
        else:
            raise AssertionError("extension without dot was not rejected")

        bad = root / "bad_materials"
        _write(bad / "wpc" / "nested.json", _material("folder/image", "colorMap"))
        try:
            build_manifest(
                material_root=bad,
                catalog_doc={"materials": [{"index": 0, "name": "wpc/nested"}]},
                source_texture_extension=".dds",
            )
        except OatMaterialManifestError:
            pass
        else:
            raise AssertionError("nested image path was not rejected by flat staging policy")

    print("PASS t6_oat_material_manifest_v3 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
