#!/usr/bin/env python3
"""Regression for hardened T6 lightmap GLB archive identity accounting v2."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from t6_world_lightmap_glb_embed_v1 import LightmapGlbEmbedError
from t6_world_lightmap_glb_embed_v2 import (
    embed_lightmap_dds,
    validate_identity_disk_bijection,
    validate_lightmap_archive,
)


def _gltf(raw: bytes) -> dict:
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "bufferViews": [],
        "extras": {"T6": {}},
    }


def _lightmap(index: int, pa: str, ps: str, sa: str, ss: str) -> dict:
    return {
        "index": index,
        "primaryImage": pa,
        "primaryOatImageAsset": pa,
        "primarySourceTexture": ps,
        "primaryOatImagePath": f"images/{ps}",
        "primaryCodeTextureSource": 4,
        "primarySamplerAccessor": "lightmapSamplerPrimary",
        "secondaryImage": sa,
        "secondaryOatImageAsset": sa,
        "secondarySourceTexture": ss,
        "secondaryOatImagePath": f"images/{ss}",
        "secondaryCodeTextureSource": 5,
        "secondarySamplerAccessor": "lightmapSamplerSecondary",
    }


def _manifest() -> dict:
    return {
        "format": "t6-world-lightmap-manifest-v2",
        "map": "mp_test",
        "t6CodeSamplerContract": {
            "primary": {"codeTextureSource": 4, "samplerAccessor": "lightmapSamplerPrimary"},
            "secondary": {"codeTextureSource": 5, "samplerAccessor": "lightmapSamplerSecondary"},
        },
        "lightmaps": [
            _lightmap(0, "*shared_primary", "_shared_primary.dds", "secondary0", "secondary0.dds"),
            _lightmap(1, "*shared_primary", "_shared_primary.dds", "secondary1", "secondary1.dds"),
        ],
        "surfaceBindings": [],
    }


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except LightmapGlbEmbedError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected LightmapGlbEmbedError containing {needle!r}")


def main() -> int:
    raw = b"WORLD"
    manifest = _manifest()
    assert validate_identity_disk_bijection(manifest)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # No DDS files: four dependency uses collapse to three unique missing assets.
        missing_doc, missing_raw = embed_lightmap_dds(
            _gltf(raw), raw, manifest, dds_root=root, allow_missing=True
        )
        archive = missing_doc["extras"]["T6"]["lightmapArchive"]
        assert archive["format"] == "t6-world-lightmap-glb-archive-v2"
        assert archive["stats"]["dependencyUseCount"] == 4
        assert archive["stats"]["uniqueGfxImageCount"] == 3
        assert archive["stats"]["embeddedGfxImageCount"] == 0
        assert archive["stats"]["missingGfxImageCount"] == 3
        assert archive["stats"]["accountedGfxImageCount"] == 3
        assert len(archive["missing"]) == 3
        assert sorted(item["gfxImageAsset"] for item in archive["missing"]) == [
            "*shared_primary",
            "secondary0",
            "secondary1",
        ]
        assert validate_lightmap_archive(missing_doc, missing_raw)

        # One shared DDS present: one embedded identity plus two unique missing identities.
        (root / "_shared_primary.dds").write_bytes(b"DDS " + b"PRIMARY")
        partial_doc, partial_raw = embed_lightmap_dds(
            _gltf(raw), raw, manifest, dds_root=root, allow_missing=True
        )
        partial = partial_doc["extras"]["T6"]["lightmapArchive"]
        assert partial["stats"]["embeddedGfxImageCount"] == 1
        assert partial["stats"]["missingGfxImageCount"] == 2
        assert partial["stats"]["accountedGfxImageCount"] == 3
        assert len(partial["missing"]) == 2
        assert validate_lightmap_archive(partial_doc, partial_raw)

        # Same T6 identity -> two disk basenames is rejected before file existence matters.
        split = copy.deepcopy(manifest)
        split["lightmaps"][1]["primarySourceTexture"] = "other_primary.dds"
        _expect_error(
            lambda: embed_lightmap_dds(
                _gltf(raw), raw, split, dds_root=root, allow_missing=True
            ),
            "maps to multiple disk sources",
        )

        # Two T6 identities -> one OAT basename is also rejected before I/O.
        collision = copy.deepcopy(manifest)
        collision["lightmaps"][1]["primaryImage"] = "_shared_primary"
        collision["lightmaps"][1]["primaryOatImageAsset"] = "_shared_primary"
        _expect_error(
            lambda: embed_lightmap_dds(
                _gltf(raw), raw, collision, dds_root=root, allow_missing=True
            ),
            "distinct T6 GfxImage identities share one lightmap disk source",
        )

        # Validator independently rejects duplicated missing-accounting records.
        corrupt = copy.deepcopy(missing_doc)
        corrupt_archive = corrupt["extras"]["T6"]["lightmapArchive"]
        corrupt_archive["missing"].append(copy.deepcopy(corrupt_archive["missing"][0]))
        corrupt_archive["stats"]["missingGfxImageCount"] += 1
        corrupt_archive["stats"]["accountedGfxImageCount"] += 1
        _expect_error(
            lambda: validate_lightmap_archive(corrupt, missing_raw),
            "not unique by GfxImage",
        )

    print("PASS t6_world_lightmap_glb_embed_v2 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
