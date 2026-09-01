#!/usr/bin/env python3
"""Regression for component-resolved OAT T6 layered materials."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from t6_oat_material_manifest_v2 import OatMaterialManifestError, build_manifest


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tex(image: str, semantic: str) -> dict:
    return {
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


def _material(textures: list[dict], technique: str) -> dict:
    return {
        "$schema": "http://openassettools.dev/schema/material.v1.json",
        "_game": "t6",
        "_type": "material",
        "_version": 1,
        "techniqueSet": technique,
        "cameraRegion": "litOpaque",
        "stateFlags": 121,
        "surfaceFlags": 16,
        "surfaceTypeBits": 4096,
        "contents": 1,
        "textures": textures,
    }


def _expect_error(fn, text: str) -> None:
    try:
        fn()
    except OatMaterialManifestError as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError(f"expected OatMaterialManifestError containing {text!r}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mats = root / "materials"

        # Layer 0 has a real normal map and therefore must be marked `n`.
        _write(
            mats / "wpc" / "base.json",
            _material(
                [
                    _tex("base_s", "specularMap"),
                    _tex("base_n", "normalMap"),
                    _tex("base_c", "colorMap"),
                ],
                "base_tech",
            ),
        )
        # Layer 1 has no normal map and is intentionally unmarked.
        _write(
            mats / "wpc" / "decal.json",
            _material([_tex("decal_c", "colorMap")], "decal_tech"),
        )
        _write(
            mats / "wpc" / "ordinary.json",
            _material([_tex("ordinary_c", "colorMap")], "ordinary_tech"),
        )
        # Identity normal is not a real normal map in Material_HasNormalMap.
        _write(
            mats / "wpc" / "identity_normal.json",
            _material(
                [
                    _tex("$identitynormalmap", "normalMap"),
                    _tex("identity_c", "colorMap"),
                ],
                "identity_tech",
            ),
        )

        compound = "*22n_14(wpc/base:wpc/decal)"
        catalog = {
            "materials": [
                {"index": 0, "name": compound, "surfacePointerHex": "0x100"},
                {"index": 1, "name": "wpc/ordinary", "surfacePointerHex": "0x101"},
            ]
        }
        doc = build_manifest(
            material_root=mats,
            catalog_doc=catalog,
            source_texture_extension=".dds",
        )
        stats = doc["stats"]
        assert stats["materialCount"] == 2
        assert stats["missingMaterialCount"] == 0
        assert stats["compoundMaterialCount"] == 1
        assert stats["reconstructedCompoundMaterialCount"] == 1
        assert stats["exactGeneratedCompoundJsonCount"] == 0
        assert stats["compoundLayerNormalValidationCount"] == 2
        assert stats["textureDependencyCount"] == 5
        assert stats["roleCounts"] == {
            "colorMap": 3,
            "normalMap": 1,
            "specularMap": 1,
        }
        # Only the ordinary material contributes a standard preview binding.
        assert stats["standardPreviewBindingCount"] == 1

        by_name = {item["material"]: item for item in doc["materials"]}
        layered = by_name[compound]
        assert layered["layered"] is True
        assert layered["compoundIdentity"] is True
        assert layered["standardPreview"] == {}
        assert layered["sourceOatMaterial"] is None
        assert len(layered["sourceOatComponents"]) == 2
        assert [layer["layer"] for layer in layered["layers"]] == [
            "wpc/base",
            "wpc/decal",
        ]
        assert [layer["bspMaterialIndex"] for layer in layered["layers"]] == [22, 14]
        assert [layer["expectedNormalMap"] for layer in layered["layers"]] == [True, False]

        # Source-closed Material_CreateLayered order: all layer-0 texture entries,
        # then all layer-1 entries. Generated texture indices must be dense.
        generated_indices = [
            texture["textureIndex"]
            for layer in layered["layers"]
            for texture in layer["textures"]
        ]
        assert generated_indices == [0, 1, 2, 3]
        assert [
            texture["imageAsset"]
            for layer in layered["layers"]
            for texture in layer["textures"]
        ] == ["base_s", "base_n", "base_c", "decal_c"]
        assert layered["reconstruction"]["textureCount"] == 4
        assert len(layered["standardPreviewBlocked"]) == 4
        assert all(
            "layered Material_CreateLayered dependency retained" in blocked["reason"]
            for blocked in layered["standardPreviewBlocked"]
        )

        # Deterministic output for identical component bytes and catalog.
        doc2 = build_manifest(
            material_root=mats,
            catalog_doc=copy.deepcopy(catalog),
            source_texture_extension=".dds",
        )
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        # `n` on a component lacking a real normal map must fail.
        _expect_error(
            lambda: build_manifest(
                material_root=mats,
                catalog_doc={
                    "materials": [
                        {
                            "index": 0,
                            "name": "*14n_22(wpc/decal:wpc/base)",
                            "surfacePointerHex": "0x200",
                        }
                    ]
                },
                source_texture_extension=".dds",
            ),
            "expects real normal map=True",
        )

        # Conversely an unmarked component with a real normal map must fail.
        _expect_error(
            lambda: build_manifest(
                material_root=mats,
                catalog_doc={
                    "materials": [
                        {
                            "index": 0,
                            "name": "*22_14(wpc/base:wpc/decal)",
                            "surfacePointerHex": "0x201",
                        }
                    ]
                },
                source_texture_extension=".dds",
            ),
            "expects real normal map=False",
        )

        # `$identitynormalmap` is explicitly not a real normal map.
        identity_ok = build_manifest(
            material_root=mats,
            catalog_doc={
                "materials": [
                    {
                        "index": 0,
                        "name": "*7_14(wpc/identity_normal:wpc/decal)",
                        "surfacePointerHex": "0x202",
                    }
                ]
            },
            source_texture_extension=".dds",
        )
        identity_layer = identity_ok["materials"][0]["layers"][0]
        assert identity_layer["expectedNormalMap"] is False
        assert identity_layer["textures"][0]["imageAsset"] == "$identitynormalmap"

        _expect_error(
            lambda: build_manifest(
                material_root=mats,
                catalog_doc={
                    "materials": [
                        {
                            "index": 0,
                            "name": "*7n_14(wpc/identity_normal:wpc/decal)",
                            "surfacePointerHex": "0x203",
                        }
                    ]
                },
                source_texture_extension=".dds",
            ),
            "expects real normal map=True",
        )

        # Missing component is a strict failure, but remains explicit when the
        # caller opts into incomplete material coverage.
        missing_catalog = {
            "materials": [
                {
                    "index": 0,
                    "name": "*22n_99(wpc/base:wpc/missing)",
                    "surfacePointerHex": "0x204",
                }
            ]
        }
        _expect_error(
            lambda: build_manifest(
                material_root=mats,
                catalog_doc=missing_catalog,
                source_texture_extension=".dds",
            ),
            "missing exact OAT component material",
        )
        allowed = build_manifest(
            material_root=mats,
            catalog_doc=missing_catalog,
            source_texture_extension=".dds",
            allow_missing_materials=True,
        )
        assert allowed["stats"]["missingMaterialCount"] == 1
        assert allowed["stats"]["materialCount"] == 0
        assert "missing exact OAT component material" in allowed["missingMaterials"][0]["reason"]

    print("PASS t6_oat_material_manifest_v2 layered regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
