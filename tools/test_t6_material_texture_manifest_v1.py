#!/usr/bin/env python3
"""Regression for t6_material_texture_manifest_v1."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from t6_material_texture_manifest_v1 import normalize_mapping_csv


def _write_csv(path: Path, rows: list[dict], *, with_optional_index: bool = False) -> None:
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
    if with_optional_index:
        fields.insert(0, "index")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row_index, source in enumerate(rows):
            row = dict(source)
            if with_optional_index:
                row["index"] = row_index
            writer.writerow(row)


def main() -> int:
    rows = [
        # Simple material: exactly the two core-preview semantics we allow.
        {"material_index": 1, "material": "simple", "layer_index": 0, "layer": "simple", "role": "colorMap", "texture_index": 100, "source_texture": "simple_c.tga", "compositors": ""},
        {"material_index": 1, "material": "simple", "layer_index": 0, "layer": "simple", "role": "normalMap", "texture_index": 101, "source_texture": "simple_n.tga", "compositors": ""},
        {"material_index": 1, "material": "simple", "layer_index": 0, "layer": "simple", "role": "specularMap", "texture_index": 102, "source_texture": "simple_s.tga", "compositors": ""},
        # Packed role must remain metadata-only.
        {"material_index": 2, "material": "packed", "layer_index": 0, "layer": "packed", "role": "colorGloss", "texture_index": 200, "source_texture": "packed_cg.tga", "compositors": ""},
        # Layered material: even base color/normal are not silently bound. The
        # pipe-delimited compositor expression must stay opaque/exact.
        {"material_index": 3, "material": "layered", "layer_index": 0, "layer": "base", "role": "colorMap", "texture_index": 300, "source_texture": "base_c.tga", "compositors": "ao_decal_ramp|BlendTextures"},
        {"material_index": 3, "material": "layered", "layer_index": 0, "layer": "base", "role": "normalMap", "texture_index": 301, "source_texture": "base_n.tga", "compositors": "ao_decal_ramp|BlendTextures"},
        {"material_index": 3, "material": "layered", "layer_index": 1, "layer": "snow", "role": "colorOpacity", "texture_index": 302, "source_texture": "snow_co.tga", "compositors": "ao_decal_ramp|BlendTextures"},
        # Multiple exact colorMap candidates are deliberately ambiguous.
        {"material_index": 4, "material": "ambiguous", "layer_index": 0, "layer": "ambiguous", "role": "colorMap", "texture_index": 400, "source_texture": "a_c.tga", "compositors": ""},
        {"material_index": 4, "material": "ambiguous", "layer_index": 0, "layer": "ambiguous", "role": "colorMap", "texture_index": 401, "source_texture": "b_c.tga", "compositors": ""},
        # Exact duplicate row should be coalesced, not counted twice.
        {"material_index": 4, "material": "ambiguous", "layer_index": 0, "layer": "ambiguous", "role": "colorMap", "texture_index": 401, "source_texture": "b_c.tga", "compositors": ""},
    ]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mapping = root / "mapping.csv"
        mapping_with_index = root / "mapping_with_index.csv"
        textures = root / "textures"
        textures.mkdir()
        # Primary regression matches the actual retained Frost CSV header.
        _write_csv(mapping, rows)
        # Derivative/viewer tables that prepend an index remain accepted.
        _write_csv(mapping_with_index, rows, with_optional_index=True)
        (textures / "simple_c.tga").write_bytes(b"color")
        (textures / "simple_n.tga").write_bytes(b"normal")
        # specular intentionally missing to exercise exact file-resolution status.

        doc = normalize_mapping_csv(mapping, texture_root=textures)
        stats = doc["stats"]
        assert doc["source"]["optionalIndexColumnPresent"] is False
        assert doc["source"]["columns"] == [
            "material_index",
            "material",
            "layer_index",
            "layer",
            "role",
            "texture_index",
            "source_texture",
            "compositors",
        ]
        assert stats["materialCount"] == 4
        assert stats["layeredMaterialCount"] == 1
        assert stats["compositorMaterialCount"] == 1
        assert stats["textureDependencyCount"] == 9
        assert stats["roleCounts"] == {
            "colorGloss": 1,
            "colorMap": 4,
            "colorOpacity": 1,
            "normalMap": 2,
            "specularMap": 1,
        }
        assert stats["compositorUseCounts"] == {
            "ao_decal_ramp|BlendTextures": 3
        }
        assert stats["standardPreviewBindingCount"] == 2
        assert stats["ambiguousStandardPreviewBindings"] == 1
        assert stats["duplicateIdenticalRows"] == 1
        assert stats["exactTextureFilesFound"] == 2
        assert stats["exactTextureFilesMissing"] == 7

        by_name = {material["material"]: material for material in doc["materials"]}
        simple = by_name["simple"]
        assert simple["standardPreview"] == {
            "baseColorTexture": {"role": "colorMap", "textureIndex": 100, "sourceTexture": "simple_c.tga"},
            "normalTexture": {"role": "normalMap", "textureIndex": 101, "sourceTexture": "simple_n.tga"},
        }
        assert any(
            item["role"] == "specularMap"
            and "no core-glTF conversion policy" in item["reason"]
            for item in simple["standardPreviewBlocked"]
        )

        packed = by_name["packed"]
        assert packed["standardPreview"] == {}
        assert packed["standardPreviewBlocked"][0]["role"] == "colorGloss"

        layered = by_name["layered"]
        assert layered["layered"] is True
        assert layered["compositors"] == ["ao_decal_ramp|BlendTextures"]
        assert layered["standardPreview"] == {}
        assert len(layered["layers"]) == 2
        assert all(
            item["reason"] == "layered/composited material requires explicit bake/shader policy"
            for item in layered["standardPreviewBlocked"]
            if item["role"] in ("colorMap", "normalMap")
        )

        ambiguous = by_name["ambiguous"]
        assert ambiguous["standardPreview"] == {}
        assert any(
            item["reason"] == "multiple exact candidates for one standard binding"
            for item in ambiguous["standardPreviewBlocked"]
        )

        # Normalized output is deterministic for identical bytes/files.
        doc2 = normalize_mapping_csv(mapping, texture_root=textures)
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        # Optional index column changes source provenance only, not normalized
        # material semantics or counts.
        with_index = normalize_mapping_csv(
            mapping_with_index,
            texture_root=textures,
        )
        assert with_index["source"]["optionalIndexColumnPresent"] is True
        assert with_index["stats"] == doc["stats"]
        assert with_index["materials"] == doc["materials"]

        print("PASS t6_material_texture_manifest_v1 regression")
        print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
