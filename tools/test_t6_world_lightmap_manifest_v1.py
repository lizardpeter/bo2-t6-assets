#!/usr/bin/env python3
"""Regression for exact T6 GfxWorld surface -> primary/secondary lightmap joins."""
from __future__ import annotations

import copy
import json

from t6_world_lightmap_manifest_v1 import (
    LightmapManifestError,
    NO_LIGHTMAP_INDEX,
    build_manifest,
)


def _world() -> dict:
    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": "mp_test",
        "groups": [
            {"groupIndex": 0, "uvCount": 1},
            {"groupIndex": 1, "uvCount": 3},
            {"groupIndex": 2, "uvCount": 4},
        ],
        "surfaces": [
            {"index": 0, "groupIndex": 0, "lightmapIndex": 0},
            {"index": 1, "groupIndex": 1, "lightmapIndex": 1},
            {"index": 2, "groupIndex": 2, "lightmapIndex": NO_LIGHTMAP_INDEX},
            {"index": 3, "groupIndex": 1, "lightmapIndex": 0},
        ],
    }


def _catalog() -> dict:
    return {
        "format": "t6-gfxworld-lightmap-catalog-v1",
        "map": "mp_test",
        "lightmapCount": 2,
        "lightmaps": [
            {
                "index": 0,
                "primaryImage": "*lightmap0_primary",
                "secondaryImage": "*lightmap0_secondary",
                "source": {"primaryPointerHex": "0x1000", "secondaryPointerHex": "0x2000"},
            },
            {
                "index": 1,
                "primaryImage": "*lightmap1_primary",
                "secondaryImage": "*lightmap1_secondary",
                "source": {"primaryPointerHex": "0x3000", "secondaryPointerHex": "0x4000"},
            },
        ],
    }


def _expect_error(world: dict, catalog: dict, needle: str, **kwargs) -> None:
    try:
        build_manifest(world, catalog, **kwargs)
    except LightmapManifestError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected LightmapManifestError containing {needle!r}")


def main() -> int:
    world = _world()
    catalog = _catalog()
    doc = build_manifest(world, catalog)

    assert doc["format"] == "t6-world-lightmap-manifest-v1"
    assert doc["map"] == "mp_test"
    assert doc["policy"]["surfaceJoin"] == "exact GfxSurface.lightmapIndex"
    assert doc["policy"]["noLightmapSentinel"] == 31
    assert doc["policy"]["lightmapUv"] == "TEXCOORD_<group native uvCount>"
    assert doc["stats"] == {
        "surfaceCount": 4,
        "lightmapCount": 2,
        "surfacesWithLightmap": 3,
        "surfacesWithoutLightmap": 1,
        "referencedLightmapCount": 2,
        "unreferencedLightmapCount": 0,
        "surfaceUseCountByLightmap": {"0": 2, "1": 1},
    }
    assert doc["referencedLightmapIndices"] == [0, 1]
    assert doc["unreferencedLightmapIndices"] == []

    assert doc["lightmaps"][0]["primarySourceTexture"] == "*lightmap0_primary.dds"
    assert doc["lightmaps"][0]["secondarySourceTexture"] == "*lightmap0_secondary.dds"
    assert doc["lightmaps"][1]["primarySourceTexture"] == "*lightmap1_primary.dds"
    assert doc["lightmaps"][1]["secondarySourceTexture"] == "*lightmap1_secondary.dds"

    by_surface = {entry["surfaceIndex"]: entry for entry in doc["surfaceBindings"]}
    assert by_surface[0] == {
        "surfaceIndex": 0,
        "groupIndex": 0,
        "lightmapIndex": 0,
        "hasLightmap": True,
        "lightmapTexCoord": 1,
        "primarySourceTexture": "*lightmap0_primary.dds",
        "secondarySourceTexture": "*lightmap0_secondary.dds",
    }
    assert by_surface[1]["lightmapTexCoord"] == 3
    assert by_surface[2] == {
        "surfaceIndex": 2,
        "groupIndex": 2,
        "lightmapIndex": 31,
        "hasLightmap": False,
        "lightmapTexCoord": 4,
    }
    assert by_surface[3]["lightmapIndex"] == 0

    # Deterministic output for identical logical inputs.
    doc2 = build_manifest(copy.deepcopy(world), copy.deepcopy(catalog))
    assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
        doc2, sort_keys=True, separators=(",", ":")
    )

    # Extension policy is explicit and deterministic.
    no_ext = build_manifest(world, catalog, source_texture_extension="")
    assert no_ext["lightmaps"][0]["primarySourceTexture"] == "*lightmap0_primary"
    _expect_error(world, catalog, "begin with '.'", source_texture_extension="dds")

    # Fail closed on structural or cross-input disagreement.
    mismatch = copy.deepcopy(catalog)
    mismatch["map"] = "mp_other"
    _expect_error(world, mismatch, "map mismatch")

    sparse = copy.deepcopy(catalog)
    sparse["lightmaps"][1]["index"] = 3
    _expect_error(world, sparse, "dense/in-order")

    bad_count = copy.deepcopy(catalog)
    bad_count["lightmapCount"] = 3
    _expect_error(world, bad_count, "array/count mismatch")

    bad_group = copy.deepcopy(world)
    bad_group["surfaces"][0]["groupIndex"] = 99
    _expect_error(bad_group, catalog, "groupIndex 99 is unavailable")

    bad_uv = copy.deepcopy(world)
    bad_uv["groups"][0]["uvCount"] = 0
    _expect_error(bad_uv, catalog, "invalid group uvCount")

    bad_index = copy.deepcopy(world)
    bad_index["surfaces"][0]["lightmapIndex"] = 2
    _expect_error(bad_index, catalog, "outside 0..1 or sentinel 31")

    missing_index = copy.deepcopy(world)
    del missing_index["surfaces"][0]["lightmapIndex"]
    _expect_error(missing_index, catalog, "missing lightmapIndex")

    empty_primary = copy.deepcopy(catalog)
    empty_primary["lightmaps"][0]["primaryImage"] = ""
    _expect_error(world, empty_primary, "empty lightmap image asset")

    print("PASS t6_world_lightmap_manifest_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
