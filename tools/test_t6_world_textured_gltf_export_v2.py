#!/usr/bin/env python3
"""Regression for portable all-dependency T6 textured world export v2."""
from __future__ import annotations

import tempfile
from pathlib import Path

from test_t6_world_gltf_export_v1 import _world
from t6_texture_stage_v1 import _encode_png_rgba
from t6_world_textured_gltf_export_v2 import export_textured


def _dependency(role: str, source: str, index: int) -> dict:
    return {
        "role": role,
        "semantic": role,
        "textureIndex": index,
        "sourceTextureIndex": index,
        "sourceTexture": source,
        "compositors": [],
    }


def main() -> int:
    world = _world()
    # _world() materials are synthetic/mat_a..d.
    a_color = _dependency("colorMap", "a_color.dds", 0)
    a_spec = _dependency("specularMap", "a_spec.dds", 1)
    b_color = _dependency("colorMap", "b_color.dds", 0)
    b_normal = _dependency("normalMap", "b_normal.dds", 1)

    manifest = {
        "format": "t6-material-texture-manifest-v1",
        "materials": [
            {
                "materialIndex": 0,
                "material": "synthetic/mat_a",
                "layered": False,
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": "synthetic/mat_a",
                        "textures": [a_color, a_spec],
                    }
                ],
                "standardPreview": {
                    "baseColorTexture": {
                        "role": "colorMap",
                        "semantic": "colorMap",
                        "textureIndex": 0,
                        "sourceTexture": "a_color.dds",
                    }
                },
                "standardPreviewBlocked": [
                    {"role": "specularMap", "texture": a_spec}
                ],
            },
            {
                "materialIndex": 1,
                "material": "synthetic/mat_b",
                "layered": True,
                "compoundIdentity": True,
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": "wpc/base",
                        "textures": [b_color, b_normal],
                    }
                ],
                "standardPreview": {},
                "standardPreviewBlocked": [
                    {"role": "colorMap", "texture": b_color},
                    {"role": "normalMap", "texture": b_normal},
                ],
            },
            {
                "materialIndex": 2,
                "material": "synthetic/mat_c",
                "layered": False,
                "layers": [{"layerIndex": 0, "layer": "synthetic/mat_c", "textures": []}],
                "standardPreview": {},
                "standardPreviewBlocked": [],
            },
            {
                "materialIndex": 3,
                "material": "synthetic/mat_d",
                "layered": False,
                "layers": [{"layerIndex": 0, "layer": "synthetic/mat_d", "textures": []}],
                "standardPreview": {},
                "standardPreviewBlocked": [],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        stage_entries = []
        for i, source in enumerate(
            ["a_color.dds", "a_spec.dds", "b_color.dds", "b_normal.dds"]
        ):
            rgba = bytes((20 + i, 40 + i, 60 + i, 255)) * 4
            png = _encode_png_rgba(2, 2, rgba)
            file_name = f"texture_{i}.png"
            (root / file_name).write_bytes(png)
            import hashlib

            stage_entries.append(
                {
                    "sourceTexture": source,
                    "png": {
                        "file": file_name,
                        "width": 2,
                        "height": 2,
                        "sha256": hashlib.sha256(png).hexdigest(),
                    },
                }
            )

        stage = {
            "format": "t6-texture-stage-manifest-v1",
            "source": {},
            "stats": {
                "referencedTextureCount": 4,
                "stagedTextureCount": 4,
                "missingTextureCount": 0,
                "unsupportedTextureCount": 0,
            },
            "textures": stage_entries,
        }

        gltf, raw = export_textured(
            world,
            manifest,
            stage,
            stage_root=root,
        )
        stats = gltf["extras"]["T6"]["exportStats"]
        assert stats["standardPreviewEmbeddedImageCount"] == 1
        assert stats["materialDependencySourceCount"] == 4
        assert stats["embeddedDependencyImageCount"] == 4
        assert stats["unboundEmbeddedDependencyImageCount"] == 3
        assert stats["missingDependencyTextureCount"] == 0
        assert stats["embeddedImageCount"] == 4
        assert len(gltf["images"]) == 4
        assert len(gltf["textures"]) == 4

        by_name = {material["name"]: material for material in gltf["materials"]}
        mat_a = by_name["synthetic/mat_a"]
        mat_b = by_name["synthetic/mat_b"]
        assert "baseColorTexture" in mat_a["pbrMetallicRoughness"]
        assert "normalTexture" not in mat_a

        # Layered material has all exact dependency images embedded but receives
        # no invented core-glTF color/normal binding.
        assert "baseColorTexture" not in mat_b["pbrMetallicRoughness"]
        assert "normalTexture" not in mat_b
        embedded = mat_b["extras"]["T6"]["embeddedDependencyTextures"]
        assert [item["sourceTexture"] for item in embedded] == [
            "b_color.dds",
            "b_normal.dds",
        ]
        assert all(0 <= item["gltfTextureIndex"] < 4 for item in embedded)
        assert mat_b["extras"]["T6"]["materialDependencyGraph"]["compoundIdentity"] is True

        # Tampering/removing an unbound dependency is still a strict failure.
        missing_stage = {
            **stage,
            "textures": [
                entry for entry in stage_entries if entry["sourceTexture"] != "b_normal.dds"
            ],
        }
        try:
            export_textured(world, manifest, missing_stage, stage_root=root)
        except Exception as exc:
            assert "dependency texture" in str(exc) or "was not staged" in str(exc)
        else:
            raise AssertionError("missing unbound dependency was not rejected")

        assert raw

    print("PASS t6_world_textured_gltf_export_v2 portable dependency regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
