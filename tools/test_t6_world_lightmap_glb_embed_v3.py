#!/usr/bin/env python3
"""Regression for nullable T6 world-lightmap GLB archival embedding v3."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from t6_world_lightmap_glb_embed_v1 import LightmapGlbEmbedError
from t6_world_lightmap_glb_embed_v3 import (
    embed_lightmap_dds,
    validate_identity_disk_bijection,
    validate_lightmap_archive,
)
from t6_world_lightmap_manifest_v3 import build_manifest


def _world() -> dict:
    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": "mp_nullable_test",
        "groups": [{"groupIndex": 0, "uvCount": 2}],
        "surfaces": [
            {"index": 0, "groupIndex": 0, "lightmapIndex": 0},
            {"index": 1, "groupIndex": 0, "lightmapIndex": 1},
            {"index": 2, "groupIndex": 0, "lightmapIndex": 2},
            {"index": 3, "groupIndex": 0, "lightmapIndex": 3},
        ],
    }


def _catalog() -> dict:
    return {
        "format": "t6-gfxworld-lightmap-catalog-v1",
        "map": "mp_nullable_test",
        "lightmapCount": 4,
        "lightmaps": [
            {
                "index": 0,
                "primaryImage": "*lm0_primary",
                "secondaryImage": "lm0_secondary",
            },
            {
                "index": 1,
                "primaryImage": None,
                "secondaryImage": "*lm1_secondary",
                "source": {
                    "primaryPointer": {"kind": "null", "rawHex": "0x00000000"},
                    "secondaryPointer": {"kind": "following", "rawHex": "0xffffffff"},
                },
            },
            {
                "index": 2,
                "primaryImage": "lm2_primary",
                "secondaryImage": None,
            },
            {
                "index": 3,
                "primaryImage": None,
                "secondaryImage": None,
            },
        ],
    }


def _write_dds(root: Path, name: str, marker: int) -> None:
    (root / name).write_bytes(b"DDS " + bytes([marker]) * 28)


def main() -> int:
    manifest = build_manifest(_world(), _catalog())
    assert validate_identity_disk_bijection(manifest)

    base_raw = b"\x11\x22\x33\x44"
    base_gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(base_raw)}],
        "bufferViews": [],
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_dds(root, "_lm0_primary.dds", 1)
        _write_dds(root, "lm0_secondary.dds", 2)
        _write_dds(root, "_lm1_secondary.dds", 3)
        _write_dds(root, "lm2_primary.dds", 4)

        gltf, raw = embed_lightmap_dds(
            base_gltf,
            base_raw,
            manifest,
            dds_root=root,
        )
        assert validate_lightmap_archive(gltf, raw)
        archive = gltf["extras"]["T6"]["lightmapArchive"]
        assert archive["format"] == "t6-world-lightmap-glb-archive-v3"
        stats = archive["stats"]
        assert stats["lightmapCount"] == 4
        assert stats["declaredRoleCount"] == 8
        assert stats["presentDependencyUseCount"] == 4
        assert stats["absentRoleCount"] == 4
        assert stats["uniqueGfxImageCount"] == 4
        assert stats["embeddedGfxImageCount"] == 4
        assert stats["missingGfxImageCount"] == 0
        assert stats["accountedGfxImageCount"] == 4

        secondary_only = archive["lightmaps"][1]
        assert secondary_only["primary"]["present"] is False
        assert secondary_only["primary"]["gfxImageAsset"] is None
        assert secondary_only["primary"]["sourceTexture"] is None
        assert secondary_only["primary"]["embedded"] is False
        assert secondary_only["primary"]["codeTextureSource"] == 4
        assert secondary_only["primary"]["samplerAccessor"] == "lightmapSamplerPrimary"
        assert secondary_only["secondary"]["present"] is True
        assert secondary_only["secondary"]["gfxImageAsset"] == "*lm1_secondary"
        assert secondary_only["secondary"]["embedded"] is True

        neither = archive["lightmaps"][3]
        assert neither["primary"]["present"] is False
        assert neither["secondary"]["present"] is False

        gltf2, raw2 = embed_lightmap_dds(
            copy.deepcopy(base_gltf),
            base_raw,
            copy.deepcopy(manifest),
            dds_root=root,
        )
        assert raw2 == raw
        assert gltf2 == gltf

        (root / "_lm1_secondary.dds").unlink()
        try:
            embed_lightmap_dds(
                base_gltf,
                base_raw,
                manifest,
                dds_root=root,
                allow_missing=False,
            )
        except LightmapGlbEmbedError as exc:
            assert "_lm1_secondary.dds" in str(exc)
        else:
            raise AssertionError("missing present lightmap DDS did not fail closed")

        missing_gltf, missing_raw = embed_lightmap_dds(
            base_gltf,
            base_raw,
            manifest,
            dds_root=root,
            allow_missing=True,
        )
        assert validate_lightmap_archive(missing_gltf, missing_raw)
        missing_archive = missing_gltf["extras"]["T6"]["lightmapArchive"]
        assert missing_archive["stats"]["embeddedGfxImageCount"] == 3
        assert missing_archive["stats"]["missingGfxImageCount"] == 1
        assert missing_archive["stats"]["accountedGfxImageCount"] == 4
        assert len(missing_archive["missing"]) == 1
        assert missing_archive["missing"][0]["gfxImageAsset"] == "*lm1_secondary"

    malformed = copy.deepcopy(manifest)
    malformed["lightmaps"][1]["primaryPresent"] = False
    malformed["lightmaps"][1]["primaryOatImageAsset"] = "*invented_primary"
    malformed["lightmaps"][1]["primarySourceTexture"] = "_invented_primary.dds"
    try:
        validate_identity_disk_bijection(malformed)
    except LightmapGlbEmbedError as exc:
        assert "absent role carries image/disk identity" in str(exc)
    else:
        raise AssertionError("absent role was allowed to carry invented image identity")

    print("PASS t6_world_lightmap_glb_embed_v3 nullable-role regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
