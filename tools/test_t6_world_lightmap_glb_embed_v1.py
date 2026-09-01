#!/usr/bin/env python3
"""Regression for lossless renderer-neutral T6 lightmap DDS embedding."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from t6_world_lightmap_glb_embed_v1 import (
    LightmapGlbEmbedError,
    embed_lightmap_dds,
    validate_lightmap_archive,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gltf(raw: bytes) -> dict:
    # Keep representative core glTF image/texture/material state so the test can
    # prove archival lightmap embedding does not invent standard glTF bindings.
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(raw), "name": "geometry"}
        ],
        "images": [{"name": "existing material image", "uri": "existing.png"}],
        "textures": [{"source": 0}],
        "materials": [
            {
                "name": "existing material",
                "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}},
            }
        ],
        "extras": {"T6": {"existingProof": True}},
    }


def _lightmap(
    index: int,
    primary_asset: str,
    primary_source: str,
    secondary_asset: str,
    secondary_source: str,
) -> dict:
    return {
        "index": index,
        "primaryImage": primary_asset,
        "primaryOatImageAsset": primary_asset,
        "primarySourceTexture": primary_source,
        "primaryOatImagePath": f"images/{primary_source}",
        "primaryCodeTextureSource": 4,
        "primarySamplerAccessor": "lightmapSamplerPrimary",
        "secondaryImage": secondary_asset,
        "secondaryOatImageAsset": secondary_asset,
        "secondarySourceTexture": secondary_source,
        "secondaryOatImagePath": f"images/{secondary_source}",
        "secondaryCodeTextureSource": 5,
        "secondarySamplerAccessor": "lightmapSamplerSecondary",
    }


def _manifest() -> dict:
    return {
        "format": "t6-world-lightmap-manifest-v2",
        "map": "mp_test",
        "t6CodeSamplerContract": {
            "primary": {
                "codeTextureSource": 4,
                "samplerAccessor": "lightmapSamplerPrimary",
            },
            "secondary": {
                "codeTextureSource": 5,
                "samplerAccessor": "lightmapSamplerSecondary",
            },
        },
        "lightmaps": [
            _lightmap(0, "*lm_primary", "_lm_primary.dds", "lm_secondary0", "lm_secondary0.dds"),
            # Reuse the exact same primary GfxImage to prove payload deduplication.
            _lightmap(1, "*lm_primary", "_lm_primary.dds", "lm_secondary1", "lm_secondary1.dds"),
        ],
        "surfaceBindings": [
            {
                "surfaceIndex": 10,
                "groupIndex": 2,
                "lightmapIndex": 0,
                "hasLightmap": True,
                "lightmapTexCoord": 3,
                "primaryOatImageAsset": "*lm_primary",
                "secondaryOatImageAsset": "lm_secondary0",
            },
            {
                "surfaceIndex": 11,
                "groupIndex": 3,
                "lightmapIndex": 1,
                "hasLightmap": True,
                "lightmapTexCoord": 4,
                "primaryOatImageAsset": "*lm_primary",
                "secondaryOatImageAsset": "lm_secondary1",
            },
            {
                "surfaceIndex": 12,
                "groupIndex": 0,
                "lightmapIndex": 31,
                "hasLightmap": False,
                "lightmapTexCoord": 1,
            },
        ],
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
    geometry = b"GEOMETRY-RAW!"  # deliberately not 4-byte aligned
    source_gltf = _gltf(geometry)
    source_images = copy.deepcopy(source_gltf["images"])
    source_textures = copy.deepcopy(source_gltf["textures"])
    source_materials = copy.deepcopy(source_gltf["materials"])
    manifest = _manifest()

    payloads = {
        "_lm_primary.dds": b"DDS " + b"PRIMARY" * 5,
        "lm_secondary0.dds": b"DDS " + b"SECONDARY0" * 3,
        "lm_secondary1.dds": b"DDS " + b"SECONDARY1" * 4,
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name, payload in payloads.items():
            (root / name).write_bytes(payload)

        out1, raw1 = embed_lightmap_dds(
            source_gltf, geometry, manifest, dds_root=root
        )
        out2, raw2 = embed_lightmap_dds(
            copy.deepcopy(source_gltf), geometry, copy.deepcopy(manifest), dds_root=root
        )

        # Deterministic document and binary regeneration.
        assert raw1 == raw2
        assert json.dumps(out1, sort_keys=True, separators=(",", ":")) == json.dumps(
            out2, sort_keys=True, separators=(",", ":")
        )
        assert validate_lightmap_archive(out1, raw1)

        archive = out1["extras"]["T6"]["lightmapArchive"]
        assert archive["format"] == "t6-world-lightmap-glb-archive-v1"
        assert archive["map"] == "mp_test"
        assert archive["policy"]["standardGltfImagesCreated"] is False
        assert archive["policy"]["standardGltfTexturesCreated"] is False
        assert archive["policy"]["materialBindingsCreated"] is False
        assert archive["policy"]["shaderComposition"] == "not guessed"
        assert archive["codeSamplerContract"] == manifest["t6CodeSamplerContract"]
        assert archive["stats"] == {
            "lightmapCount": 2,
            "dependencyUseCount": 4,
            "uniqueGfxImageCount": 3,
            "embeddedGfxImageCount": 3,
            "missingGfxImageCount": 0,
            "surfaceBindingCount": 3,
        }
        assert archive["missing"] == []
        assert archive["surfaceBindings"] == manifest["surfaceBindings"]

        # Archival embedding must not create or modify standard renderer bindings.
        assert out1["images"] == source_images
        assert out1["textures"] == source_textures
        assert out1["materials"] == source_materials
        assert out1["extras"]["T6"]["existingProof"] is True

        lm0 = archive["lightmaps"][0]
        lm1 = archive["lightmaps"][1]
        assert lm0["primary"]["gfxImageAsset"] == "*lm_primary"
        assert lm0["primary"]["codeTextureSource"] == 4
        assert lm0["primary"]["samplerAccessor"] == "lightmapSamplerPrimary"
        assert lm0["secondary"]["codeTextureSource"] == 5
        assert lm0["secondary"]["samplerAccessor"] == "lightmapSamplerSecondary"
        # Exact asset reuse must reuse one bufferView, not duplicate bytes.
        assert lm0["primary"]["bufferView"] == lm1["primary"]["bufferView"]

        unique_views: dict[str, int] = {}
        for lightmap in archive["lightmaps"]:
            for role in ("primary", "secondary"):
                item = lightmap[role]
                view = out1["bufferViews"][item["bufferView"]]
                assert view["byteOffset"] % 4 == 0
                embedded = raw1[
                    int(view["byteOffset"]): int(view["byteOffset"]) + int(view["byteLength"])
                ]
                expected = payloads[item["sourceTexture"]]
                assert embedded == expected
                assert item["bytes"] == len(expected)
                assert item["sha256"] == _sha256(expected)
                prior = unique_views.setdefault(item["gfxImageAsset"], item["bufferView"])
                assert prior == item["bufferView"]

        assert out1["buffers"][0]["byteLength"] == len(raw1)
        assert len(raw1) > len(geometry) + sum(len(v) for v in payloads.values())

        # Missing exact DDS fails closed by default.
        missing_root = root / "missing"
        missing_root.mkdir()
        (missing_root / "_lm_primary.dds").write_bytes(payloads["_lm_primary.dds"])
        _expect_error(
            lambda: embed_lightmap_dds(
                source_gltf, geometry, manifest, dds_root=missing_root
            ),
            "missing exact lightmap DDS",
        )

        # Explicit allow-missing preserves the dependency graph and reports absence.
        partial, partial_raw = embed_lightmap_dds(
            source_gltf,
            geometry,
            manifest,
            dds_root=missing_root,
            allow_missing=True,
        )
        partial_archive = partial["extras"]["T6"]["lightmapArchive"]
        assert partial_archive["stats"]["embeddedGfxImageCount"] == 1
        assert partial_archive["stats"]["missingGfxImageCount"] == 2
        assert len(partial_archive["missing"]) == 2
        assert validate_lightmap_archive(partial, partial_raw)

        # Invalid DDS magic is never archived as a lightmap payload.
        bad_root = root / "bad"
        bad_root.mkdir()
        for name, payload in payloads.items():
            (bad_root / name).write_bytes(payload)
        (bad_root / "lm_secondary0.dds").write_bytes(b"NOTDDS")
        _expect_error(
            lambda: embed_lightmap_dds(
                source_gltf, geometry, manifest, dds_root=bad_root
            ),
            "is not a DDS file",
        )

        # OAT's '*' -> '_' filename transform is non-injective; reject aliases.
        collision = copy.deepcopy(manifest)
        collision["lightmaps"][1]["primaryImage"] = "_lm_primary"
        collision["lightmaps"][1]["primaryOatImageAsset"] = "_lm_primary"
        collision["lightmaps"][1]["primarySourceTexture"] = "_lm_primary.dds"
        _expect_error(
            lambda: embed_lightmap_dds(
                source_gltf, geometry, collision, dds_root=root
            ),
            "distinct T6 GfxImage identities share one lightmap disk source",
        )

        # A single T6 identity may not point at two different extracted files.
        split_identity = copy.deepcopy(manifest)
        split_identity["lightmaps"][1]["primarySourceTexture"] = "lm_secondary1.dds"
        _expect_error(
            lambda: embed_lightmap_dds(
                source_gltf, geometry, split_identity, dds_root=root
            ),
            "maps to multiple disk sources",
        )

        bad_length_gltf = _gltf(geometry)
        bad_length_gltf["buffers"][0]["byteLength"] += 1
        _expect_error(
            lambda: embed_lightmap_dds(
                bad_length_gltf, geometry, manifest, dds_root=root
            ),
            "input raw buffer length does not match",
        )

        # Post-build corruption is detected from both DDS magic and SHA-256.
        tampered = bytearray(raw1)
        tamper_view = out1["bufferViews"][lm0["secondary"]["bufferView"]]
        tampered[int(tamper_view["byteOffset"]) + 4] ^= 0x01
        _expect_error(
            lambda: validate_lightmap_archive(out1, bytes(tampered)),
            "SHA-256 mismatch",
        )

    print("PASS t6_world_lightmap_glb_embed_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
