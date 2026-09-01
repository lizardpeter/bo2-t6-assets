#!/usr/bin/env python3
"""Regression for direct OAT T6 material -> texture manifest conversion."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from t6_oat_material_manifest_v1 import OatMaterialManifestError, build_manifest


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _material(textures: list[dict]) -> dict:
    return {
        "$schema": "http://openassettools.dev/schema/material.v1.json",
        "_game": "t6",
        "_type": "material",
        "_version": 1,
        "techniqueSet": "wpc_lit_sm_r0c0n0s0_test",
        "cameraRegion": "litOpaque",
        "stateFlags": 121,
        "surfaceFlags": 16,
        "surfaceTypeBits": 4096,
        "contents": 1,
        "textures": textures,
    }


def _tex(image: str, semantic: str, *, name: str | None = None) -> dict:
    return {
        "image": image,
        "name": name or semantic,
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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mats = root / "materials"
        _write(
            mats / "wpc" / "simple.json",
            _material(
                [
                    _tex("simple_s", "specularMap"),
                    _tex("simple_n", "normalMap"),
                    _tex("~-gsimple_c", "colorMap"),
                ]
            ),
        )
        _write(
            mats / "wpc" / "ambiguous.json",
            _material([_tex("a_c", "colorMap"), _tex("b_c", "colorMap")]),
        )
        _write(
            mats / "wpc" / "name_only.json",
            _material(
                [{**_tex("name_only_c", ""), "name": "colorMap", "semantic": ""}]
            ),
        )
        _write(
            mats / "not_t6.json",
            {"_game": "t5", "_type": "material", "textures": []},
        )

        catalog = {
            "materials": [
                {"index": 0, "name": "wpc/simple", "surfacePointerHex": "0x1"},
                {"index": 1, "name": "wpc/ambiguous", "surfacePointerHex": "0x2"},
                {"index": 2, "name": "wpc/name_only", "surfacePointerHex": "0x3"},
            ]
        }
        doc = build_manifest(
            material_root=mats,
            catalog_doc=catalog,
            source_texture_extension=".dds",
        )
        assert doc["stats"]["materialCount"] == 3
        assert doc["stats"]["missingMaterialCount"] == 0
        assert doc["stats"]["textureDependencyCount"] == 6
        assert doc["stats"]["standardPreviewBindingCount"] == 2
        assert doc["stats"]["ambiguousStandardPreviewBindings"] == 1
        assert doc["stats"]["skippedNonT6MaterialJsonCount"] == 1
        assert doc["stats"]["roleCounts"] == {
            "colorMap": 4,
            "normalMap": 1,
            "specularMap": 1,
        }

        by_name = {material["material"]: material for material in doc["materials"]}
        simple = by_name["wpc/simple"]
        assert (
            simple["standardPreview"]["baseColorTexture"]["sourceTexture"]
            == "~-gsimple_c.dds"
        )
        assert (
            simple["standardPreview"]["normalTexture"]["sourceTexture"]
            == "simple_n.dds"
        )
        assert (
            simple["standardPreview"]["normalTexture"]["samplerState"]["filter"]
            == "aniso4x"
        )
        assert any(
            item["role"] == "specularMap"
            for item in simple["standardPreviewBlocked"]
        )

        ambiguous = by_name["wpc/ambiguous"]
        assert ambiguous["standardPreview"] == {}
        assert len(ambiguous["standardPreviewBlocked"]) == 2
        assert all(
            "multiple exact OAT semantic candidates" in item["reason"]
            for item in ambiguous["standardPreviewBlocked"]
        )

        # A name-only label is retained as provenance, but semantic-free input
        # is not promoted into a preview binding.
        name_only = by_name["wpc/name_only"]
        assert name_only["standardPreview"] == {}
        assert name_only["layers"][0]["textures"][0]["role"] == "colorMap"
        assert name_only["layers"][0]["textures"][0]["semantic"] is None

        doc2 = build_manifest(
            material_root=mats,
            catalog_doc=copy.deepcopy(catalog),
            source_texture_extension=".dds",
        )
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        missing_catalog = {
            "materials": catalog["materials"]
            + [{"index": 3, "name": "wpc/missing", "surfacePointerHex": "0x4"}]
        }
        try:
            build_manifest(
                material_root=mats,
                catalog_doc=missing_catalog,
                source_texture_extension=".dds",
            )
        except OatMaterialManifestError:
            pass
        else:
            raise AssertionError("strict missing OAT material was not rejected")

        allowed = build_manifest(
            material_root=mats,
            catalog_doc=missing_catalog,
            source_texture_extension=".dds",
            allow_missing_materials=True,
        )
        assert allowed["stats"]["missingMaterialCount"] == 1
        assert allowed["missingMaterials"][0]["material"] == "wpc/missing"

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

    print("PASS t6_oat_material_manifest_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
