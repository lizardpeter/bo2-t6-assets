#!/usr/bin/env python3
"""Synthetic all-format regression for one-command textured T6 world pipeline."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
from pathlib import Path

from test_t6_texture_stage_v1 import _tga_rgba
from test_t6_world_export_pipeline_v1 import _build_fixture, _parse_glb
from t6_world_textured_export_pipeline_v1 import run_textured_pipeline


def _write_material_texture_fixture(root: Path) -> tuple[Path, Path, int]:
    texture_root = root / "texture_source"
    texture_root.mkdir()
    mapping = root / "material_texture_mapping.csv"
    fields = [
        "material_index",
        "material",
        "layer_index",
        "layer",
        "role",
        "texture_index",
        "source_texture",
        "compositors",
    ]
    rows: list[dict] = []
    texture_index = 0
    for fmt in range(9):
        material = f"synthetic/world_material_{fmt}"
        color_name = f"world_material_{fmt}_c.tga"
        rows.append(
            {
                "material_index": fmt,
                "material": material,
                "layer_index": 0,
                "layer": material,
                "role": "colorMap",
                "texture_index": texture_index,
                "source_texture": color_name,
                "compositors": "",
            }
        )
        texture_index += 1
        (texture_root / color_name).write_bytes(
            _tga_rgba(
                2,
                2,
                [(20 + fmt, 40 + fmt, 60 + fmt, 255)] * 4,
                rle=bool(fmt & 1),
                origin_top=bool(fmt & 2),
                origin_right=bool(fmt & 4),
            )
        )

        if fmt % 2 == 0:
            normal_name = f"world_material_{fmt}_n.tga"
            rows.append(
                {
                    "material_index": fmt,
                    "material": material,
                    "layer_index": 0,
                    "layer": material,
                    "role": "normalMap",
                    "texture_index": texture_index,
                    "source_texture": normal_name,
                    "compositors": "",
                }
            )
            texture_index += 1
            (texture_root / normal_name).write_bytes(
                _tga_rgba(
                    2,
                    2,
                    [(128, 128, 255, 255)] * 4,
                    rle=not bool(fmt & 1),
                    origin_top=not bool(fmt & 2),
                    origin_right=not bool(fmt & 4),
                )
            )

    with mapping.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return mapping, texture_root, len(rows)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        fixture = _build_fixture(root)
        mapping, texture_root, texture_count = _write_material_texture_fixture(root)

        manifest = run_textured_pipeline(
            map_name="synthetic_world_all_formats_textured",
            surfaces_path=fixture["surfaces"],
            vd0_path=fixture["vd0"],
            vd1_path=fixture["vd1"],
            indices_path=fixture["indices"],
            materials_path=fixture["materials"],
            catalog_path=fixture["catalog"],
            prefix_path=fixture["prefix"],
            asset_pointer_array_virtual_base=fixture["assetPointerBase"],
            material_texture_mapping_path=mapping,
            texture_root=texture_root,
            output_dir=fixture["output"],
            write_gltf=True,
        )

        validation = manifest["validation"]
        assert validation["baseWorldPipeline"]["vertexAuditBadGroups"] == 0
        assert validation["baseWorldPipeline"]["observedWorldVertFormats"] == list(
            range(9)
        )
        assert validation["textureStageMissingCount"] == 0
        assert validation["textureStageUnsupportedCount"] == 0
        assert validation["materialManifestMatchedCount"] == 9
        assert validation["materialManifestUnmatchedCount"] == 0
        assert validation["missingPreviewTextureCount"] == 0
        assert validation["texturedGlbRegenerationByteIdentical"] is True
        assert validation["texturedGltfRegenerationByteIdentical"] is True

        material_stats = manifest["stats"]["materialTextures"]
        assert material_stats["materialCount"] == 9
        assert material_stats["textureDependencyCount"] == texture_count
        assert material_stats["standardPreviewBindingCount"] == texture_count

        stage_stats = manifest["stats"]["textureStage"]
        assert stage_stats["referencedTextureCount"] == texture_count
        assert stage_stats["stagedTextureCount"] == texture_count
        assert stage_stats["standardPreviewSourceCount"] == texture_count

        textured_stats = manifest["stats"]["texturedGltf"]
        assert textured_stats["groupCount"] == 9
        assert textured_stats["primitiveCount"] == 9
        assert textured_stats["materialCount"] == 9
        assert textured_stats["texturedMaterialCount"] == 9
        assert textured_stats["standardPreviewBindingCount"] == texture_count
        assert textured_stats["embeddedImageCount"] == texture_count

        for record in manifest["outputs"].values():
            path = Path(record["path"])
            payload = path.read_bytes()
            assert len(payload) == record["bytes"]
            assert hashlib.sha256(payload).hexdigest() == record["sha256"]

        textured_path = Path(manifest["outputs"]["texturedGlb"]["path"])
        document, raw = _parse_glb(textured_path)
        assert len(document["materials"]) == 9
        assert len(document["images"]) == texture_count
        assert len(document["textures"]) == texture_count

        for fmt, material in enumerate(document["materials"]):
            assert material["name"] == f"synthetic/world_material_{fmt}"
            assert "baseColorTexture" in material["pbrMetallicRoughness"]
            if fmt % 2 == 0:
                assert "normalTexture" in material
            else:
                assert "normalTexture" not in material
            graph = material["extras"]["T6"]["materialDependencyGraph"]
            assert graph["material"] == material["name"]
            assert graph["layered"] is False

        for image in document["images"]:
            view = document["bufferViews"][image["bufferView"]]
            start = int(view.get("byteOffset", 0))
            end = start + int(view["byteLength"])
            payload = raw[start:end]
            assert payload[:8] == b"\x89PNG\r\n\x1a\n"
            assert hashlib.sha256(payload).hexdigest() == image["extras"]["T6"][
                "pngSha256"
            ]

        base_glb = Path(
            manifest["inputs"]["baseWorldPipelineManifest"]["path"]
        ).parent / "synthetic_world_all_formats_textured.world.glb"
        assert base_glb.is_file()
        assert base_glb.read_bytes() != textured_path.read_bytes()

        print("PASS t6_world_textured_export_pipeline_v1 synthetic regression")
        print(json.dumps(validation, indent=2, sort_keys=True))
        print("texturedGlbSha256=" + manifest["outputs"]["texturedGlb"]["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
