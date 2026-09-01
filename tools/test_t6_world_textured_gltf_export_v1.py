#!/usr/bin/env python3
"""Synthetic end-to-end regression for source-closed textured T6 world GLB."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from test_t6_texture_stage_v1 import _tga_rgba
from test_t6_world_gltf_export_v1 import _world
from t6_texture_stage_v1 import stage
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes
from t6_world_textured_gltf_export_v1 import (
    TexturedExportError,
    export_textured,
    validate_textured,
)


def _material_manifest() -> dict:
    return {
        "format": "t6-material-texture-manifest-v1",
        "materials": [
            {
                "materialIndex": 0,
                "material": "synthetic/mat_a",
                "layered": False,
                "compositors": [],
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": "synthetic/mat_a",
                        "textures": [
                            {
                                "role": "colorMap",
                                "textureIndex": 100,
                                "sourceTexture": "a_c.tga",
                                "compositors": [],
                            },
                            {
                                "role": "normalMap",
                                "textureIndex": 101,
                                "sourceTexture": "a_n.tga",
                                "compositors": [],
                            },
                            {
                                "role": "specularMap",
                                "textureIndex": 102,
                                "sourceTexture": "a_s.tga",
                                "compositors": [],
                            },
                        ],
                    }
                ],
                "standardPreview": {
                    "baseColorTexture": {
                        "role": "colorMap",
                        "textureIndex": 100,
                        "sourceTexture": "a_c.tga",
                    },
                    "normalTexture": {
                        "role": "normalMap",
                        "textureIndex": 101,
                        "sourceTexture": "a_n.tga",
                    },
                },
                "standardPreviewBlocked": [
                    {
                        "role": "specularMap",
                        "reason": "source semantic retained; no core-glTF conversion policy",
                    }
                ],
            },
            {
                "materialIndex": 1,
                "material": "synthetic/mat_b",
                "layered": True,
                "compositors": ["BlendTextures"],
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": "base",
                        "textures": [
                            {
                                "role": "colorMap",
                                "textureIndex": 200,
                                "sourceTexture": "b_c.tga",
                                "compositors": ["BlendTextures"],
                            }
                        ],
                    },
                    {
                        "layerIndex": 1,
                        "layer": "snow",
                        "textures": [
                            {
                                "role": "colorOpacity",
                                "textureIndex": 201,
                                "sourceTexture": "snow_co.tga",
                                "compositors": ["BlendTextures"],
                            }
                        ],
                    },
                ],
                "standardPreview": {},
                "standardPreviewBlocked": [],
            },
            {
                "materialIndex": 2,
                "material": "synthetic/mat_c",
                "layered": False,
                "compositors": [],
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": "synthetic/mat_c",
                        "textures": [
                            {
                                "role": "colorMap",
                                "textureIndex": 300,
                                "sourceTexture": "c_c.tga",
                                "compositors": [],
                            }
                        ],
                    }
                ],
                "standardPreview": {
                    "baseColorTexture": {
                        "role": "colorMap",
                        "textureIndex": 300,
                        "sourceTexture": "c_c.tga",
                    }
                },
                "standardPreviewBlocked": [],
            },
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source"
        staged_dir = root / "staged"
        source.mkdir()

        pixels = {
            "a_c.tga": (200, 10, 20, 255),
            "a_n.tga": (128, 128, 255, 255),
            "a_s.tga": (80, 80, 80, 255),
            "b_c.tga": (20, 200, 10, 255),
            "snow_co.tga": (240, 240, 240, 128),
            "c_c.tga": (20, 10, 200, 255),
        }
        for index, (name, color) in enumerate(sorted(pixels.items())):
            (source / name).write_bytes(
                _tga_rgba(
                    2,
                    2,
                    [color] * 4,
                    rle=bool(index % 2),
                    origin_top=bool(index % 3),
                    origin_right=bool(index % 4 == 0),
                )
            )

        material_manifest = _material_manifest()
        material_raw = (
            json.dumps(material_manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        material_sha = hashlib.sha256(material_raw).hexdigest()

        stage_manifest = stage(
            material_manifest,
            texture_root=source,
            output_dir=staged_dir,
            material_manifest_name="synthetic.materials.json",
            material_manifest_sha256=material_sha,
        )
        assert stage_manifest["stats"]["stagedTextureCount"] == 6
        assert stage_manifest["stats"]["standardPreviewSourceCount"] == 3

        world = _world()
        gltf1, raw1 = export_textured(
            world,
            material_manifest,
            stage_manifest,
            stage_root=staged_dir,
            material_manifest_sha256=material_sha,
        )
        assert validate_textured(gltf1, raw1)

        stats = gltf1["extras"]["T6"]["exportStats"]
        assert stats["materialManifestMatchedCount"] == 3
        assert stats["materialManifestUnmatchedCount"] == 1
        assert stats["texturedMaterialCount"] == 2
        assert stats["standardPreviewBindingCount"] == 3
        assert stats["embeddedImageCount"] == 3
        assert stats["missingPreviewTextureCount"] == 0

        assert len(gltf1["images"]) == 3
        assert len(gltf1["textures"]) == 3
        image_names = [image["name"] for image in gltf1["images"]]
        assert image_names == ["a_c.tga", "a_n.tga", "c_c.tga"]
        assert "a_s.tga" not in image_names
        assert "b_c.tga" not in image_names
        assert "snow_co.tga" not in image_names

        by_name = {material["name"]: material for material in gltf1["materials"]}
        mat_a = by_name["synthetic/mat_a"]
        assert mat_a["pbrMetallicRoughness"]["baseColorTexture"] == {
            "index": 0,
            "texCoord": 0,
        }
        assert mat_a["normalTexture"] == {"index": 1, "texCoord": 0}
        assert (
            mat_a["extras"]["T6"]["materialDependencyGraph"]["layers"][0][
                "textures"
            ][2]["role"]
            == "specularMap"
        )

        mat_b = by_name["synthetic/mat_b"]
        assert "baseColorTexture" not in mat_b["pbrMetallicRoughness"]
        assert "normalTexture" not in mat_b
        assert mat_b["extras"]["T6"]["materialDependencyGraph"]["layered"] is True
        assert mat_b["extras"]["T6"]["materialDependencyGraph"]["compositors"] == [
            "BlendTextures"
        ]

        mat_c = by_name["synthetic/mat_c"]
        assert mat_c["pbrMetallicRoughness"]["baseColorTexture"] == {
            "index": 2,
            "texCoord": 0,
        }

        mat_d = by_name["synthetic/mat_d"]
        assert (
            mat_d["extras"]["T6"]["materialTextureJoin"]
            == "no exact manifest material-name match"
        )

        for image in gltf1["images"]:
            view = gltf1["bufferViews"][image["bufferView"]]
            start = int(view.get("byteOffset", 0))
            end = start + int(view["byteLength"])
            payload = raw1[start:end]
            assert payload[:8] == b"\x89PNG\r\n\x1a\n"
            assert hashlib.sha256(payload).hexdigest() == image["extras"]["T6"][
                "pngSha256"
            ]

        gltf2, raw2 = export_textured(
            copy.deepcopy(world),
            copy.deepcopy(material_manifest),
            copy.deepcopy(stage_manifest),
            stage_root=staged_dir,
            material_manifest_sha256=material_sha,
        )
        assert raw2 == raw1
        blob1 = glb_bytes(gltf1, raw1)
        blob2 = glb_bytes(gltf2, raw2)
        assert blob2 == blob1
        assert gltf_bytes(gltf2, raw2) == gltf_bytes(gltf1, raw1)

        try:
            export_textured(
                world,
                material_manifest,
                stage_manifest,
                stage_root=staged_dir,
                material_manifest_sha256="0" * 64,
            )
        except TexturedExportError:
            pass
        else:
            raise AssertionError("material/stage SHA mismatch was not rejected")

        first_png = staged_dir / stage_manifest["textures"][0]["png"]["file"]
        original = first_png.read_bytes()
        first_png.write_bytes(original + b"x")
        try:
            export_textured(
                world,
                material_manifest,
                stage_manifest,
                stage_root=staged_dir,
                material_manifest_sha256=material_sha,
            )
        except TexturedExportError:
            pass
        else:
            raise AssertionError("staged PNG hash tampering was not rejected")

        print("PASS t6_world_textured_gltf_export_v1 regression")
        print(json.dumps(stats, indent=2, sort_keys=True))
        print("glbSha256=" + hashlib.sha256(blob1).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
