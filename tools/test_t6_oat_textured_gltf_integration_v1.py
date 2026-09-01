#!/usr/bin/env python3
"""Direct OAT T6 Material JSON + DDS -> textured world GLB regression."""
from __future__ import annotations

import hashlib
import json
import struct
import tempfile
from pathlib import Path

from test_t6_dds_texture_stage_v1 import _bc4, _dds_header
from test_t6_world_gltf_export_v1 import _world
from t6_dds_texture_stage_v1 import stage_dds
from t6_oat_material_manifest_v1 import build_manifest
from t6_world_gltf_export_v1 import glb_bytes
from t6_world_textured_gltf_export_v1 import export_textured, validate_textured


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _material(textures: list[dict]) -> dict:
    return {
        "$schema": "http://openassettools.dev/schema/material.v1.json",
        "_game": "t6",
        "_type": "material",
        "_version": 1,
        "techniqueSet": "wpc_lit_test",
        "cameraRegion": "litOpaque",
        "textures": textures,
    }


def _texture(image: str, semantic: str) -> dict:
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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        materials = root / "materials"
        dds = root / "dds"
        staged = root / "staged"
        dds.mkdir()

        _write(
            materials / "synthetic" / "mat_a.json",
            _material(
                [
                    _texture("a_n", "normalMap"),
                    _texture("a_c", "colorMap"),
                    _texture("a_s", "specularMap"),
                ]
            ),
        )
        _write(
            materials / "synthetic" / "mat_b.json",
            _material([_texture("b_c", "colorMap")]),
        )
        _write(
            materials / "synthetic" / "mat_c.json",
            _material([_texture("c_c", "colorMap")]),
        )
        catalog = {
            "materials": [
                {
                    "index": 0,
                    "name": "synthetic/mat_a",
                    "surfacePointerHex": "0x10000000",
                },
                {
                    "index": 1,
                    "name": "synthetic/mat_b",
                    "surfacePointerHex": "0x10000001",
                },
                {
                    "index": 2,
                    "name": "synthetic/mat_c",
                    "surfacePointerHex": "0x10000002",
                },
            ]
        }
        manifest = build_manifest(
            material_root=materials,
            catalog_doc=catalog,
            source_texture_extension=".dds",
        )
        assert manifest["stats"]["standardPreviewBindingCount"] == 4

        red = _dds_header(4, 4, fourcc=b"DXT1") + struct.pack(
            "<HHI", 0xF800, 0, 0
        )
        green = _dds_header(4, 4, fourcc=b"DXT1") + struct.pack(
            "<HHI", 0x07E0, 0, 0
        )
        blue = _dds_header(4, 4, fourcc=b"DXT1") + struct.pack(
            "<HHI", 0x001F, 0, 0
        )
        grey = _dds_header(4, 4, fourcc=b"DXT1") + struct.pack(
            "<HHI", 0x8410, 0, 0
        )
        normal = (
            _dds_header(4, 4, fourcc=b"DX10", dx10=(83, 3, 1))
            + _bc4(128)
            + _bc4(128)
        )
        for name, payload in {
            "a_c.dds": red,
            "a_n.dds": normal,
            "a_s.dds": grey,
            "b_c.dds": green,
            "c_c.dds": blue,
        }.items():
            (dds / name).write_bytes(payload)

        material_raw = (
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        material_sha = hashlib.sha256(material_raw).hexdigest()
        stage = stage_dds(
            manifest,
            texture_root=dds,
            output_dir=staged,
            material_manifest_name="m.json",
            material_manifest_sha256=material_sha,
        )
        assert stage["stats"]["stagedTextureCount"] == 5
        assert stage["stats"]["bc5NormalReconstructionCount"] == 1

        gltf, raw = export_textured(
            _world(),
            manifest,
            stage,
            stage_root=staged,
            material_manifest_sha256=material_sha,
        )
        assert validate_textured(gltf, raw)
        stats = gltf["extras"]["T6"]["exportStats"]
        assert stats["materialManifestMatchedCount"] == 3
        assert stats["materialManifestUnmatchedCount"] == 1
        assert stats["texturedMaterialCount"] == 3
        assert stats["standardPreviewBindingCount"] == 4
        assert stats["embeddedImageCount"] == 4  # Specular is staged, not bound.

        by_name = {material["name"]: material for material in gltf["materials"]}
        assert "normalTexture" in by_name["synthetic/mat_a"]
        graph = by_name["synthetic/mat_a"]["extras"]["T6"][
            "materialDependencyGraph"
        ]
        assert graph["sourceOatMaterial"]["techniqueSet"] == "wpc_lit_test"
        assert any(
            texture["role"] == "specularMap"
            for texture in graph["layers"][0]["textures"]
        )

        blob = glb_bytes(gltf, raw)
        print("PASS t6_oat_textured_gltf_integration_v1 regression")
        print("glbSha256=" + hashlib.sha256(blob).hexdigest())
        print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
