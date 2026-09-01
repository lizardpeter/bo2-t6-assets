#!/usr/bin/env python3
"""Regression for semantic-aware layered BC5 DDS staging v2."""
from __future__ import annotations

import tempfile
from pathlib import Path

from test_t6_dds_texture_stage_v1 import _bc4, _dds_header
from t6_dds_texture_stage_v1 import DdsStageError
from t6_dds_texture_stage_v2 import stage_dds


def _material(index: int, name: str, role: str, source: str, *, preview: bool) -> dict:
    texture = {
        "role": role,
        "semantic": role,
        "textureIndex": 0,
        "sourceTexture": source,
        "compositors": [],
    }
    return {
        "materialIndex": index,
        "material": name,
        "layered": not preview,
        "layers": [{"layerIndex": 0, "layer": name, "textures": [texture]}],
        "standardPreview": (
            {"normalTexture": {"role": role, "textureIndex": 0, "sourceTexture": source}}
            if preview
            else {}
        ),
        "standardPreviewBlocked": [] if preview else [{"role": role, "texture": texture}],
    }


def main() -> int:
    bc5 = _dds_header(4, 4, fourcc=b"DX10", dx10=(83, 3, 1)) + _bc4(128) + _bc4(128)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "dds"
        source.mkdir()
        (source / "layered_normal.dds").write_bytes(bc5)

        # No standardPreview binding: exact normalMap role alone must still
        # reconstruct BC5 normal Z for a layered material dependency.
        manifest = {
            "format": "t6-material-texture-manifest-v1",
            "materials": [
                _material(
                    0,
                    "*22n_14(wpc/base:wpc/decal)",
                    "normalMap",
                    "layered_normal.dds",
                    preview=False,
                )
            ],
        }
        doc = stage_dds(
            manifest,
            texture_root=source,
            output_dir=root / "out",
        )
        assert doc["stats"]["referencedTextureCount"] == 1
        assert doc["stats"]["standardPreviewSourceCount"] == 0
        assert doc["stats"]["semanticNormalSourceCount"] == 1
        assert doc["stats"]["bc5NormalReconstructionCount"] == 1
        entry = doc["textures"][0]
        assert entry["dds"]["bc5NormalZReconstructed"] is True
        assert entry["dds"]["materialRoles"] == ["normalMap"]
        assert "all exact material dependency roles are normalMap" in entry["dds"][
            "normalInterpretationSource"
        ]

        # A BC5 source reused as normalMap and colorMap is ambiguous and must
        # fail closed rather than applying one interpretation to both uses.
        mixed = {
            "format": "t6-material-texture-manifest-v1",
            "materials": [
                _material(0, "normal", "normalMap", "layered_normal.dds", preview=False),
                _material(1, "color", "colorMap", "layered_normal.dds", preview=False),
            ],
        }
        try:
            stage_dds(mixed, texture_root=source, output_dir=root / "mixed")
        except DdsStageError as exc:
            assert "mixed normalMap and non-normal" in str(exc)
        else:
            raise AssertionError("mixed BC5 semantic use was not rejected")

    print("PASS t6_dds_texture_stage_v2 layered semantic regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
