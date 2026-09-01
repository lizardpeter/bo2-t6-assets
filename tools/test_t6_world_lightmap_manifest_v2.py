#!/usr/bin/env python3
"""Regression for T6 lightmap asset identity vs OAT disk filename mapping."""
from __future__ import annotations

import copy
import json

from t6_world_lightmap_manifest_v1 import LightmapManifestError
from t6_world_lightmap_manifest_v2 import build_manifest


def _world() -> dict:
    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": "mp_test",
        "groups": [{"groupIndex": 0, "uvCount": 2}],
        "surfaces": [
            {"index": 0, "groupIndex": 0, "lightmapIndex": 0},
            {"index": 1, "groupIndex": 0, "lightmapIndex": 31},
        ],
    }


def _catalog() -> dict:
    return {
        "format": "t6-gfxworld-lightmap-catalog-v1",
        "map": "mp_test",
        "lightmapCount": 1,
        "lightmaps": [
            {
                "index": 0,
                "primaryImage": "*lm_primary",
                "secondaryImage": "lm_secondary",
            }
        ],
    }


def main() -> int:
    world = _world()
    catalog = _catalog()
    doc = build_manifest(world, catalog)
    assert doc["format"] == "t6-world-lightmap-manifest-v2"
    assert doc["source"]["producer"] == "t6_world_lightmap_manifest_v2.py"
    assert doc["stats"]["oatImageDependencyCount"] == 2
    assert doc["stats"]["oatImageFilenameChangedDependencyCount"] == 1

    lm = doc["lightmaps"][0]
    assert lm["primaryImage"] == "*lm_primary"
    assert lm["primaryOatImageAsset"] == "*lm_primary"
    assert lm["primarySourceTexture"] == "_lm_primary.dds"
    assert lm["primaryOatImagePath"] == "images/_lm_primary.dds"
    assert lm["primaryCodeTextureSource"] == 4
    assert lm["primarySamplerAccessor"] == "lightmapSamplerPrimary"
    assert lm["secondaryImage"] == "lm_secondary"
    assert lm["secondaryOatImageAsset"] == "lm_secondary"
    assert lm["secondarySourceTexture"] == "lm_secondary.dds"
    assert lm["secondaryOatImagePath"] == "images/lm_secondary.dds"
    assert lm["secondaryCodeTextureSource"] == 5
    assert lm["secondarySamplerAccessor"] == "lightmapSamplerSecondary"

    binding = doc["surfaceBindings"][0]
    assert binding["primarySourceTexture"] == "_lm_primary.dds"
    assert binding["primaryOatImageAsset"] == "*lm_primary"
    assert binding["secondarySourceTexture"] == "lm_secondary.dds"
    assert binding["lightmapTexCoord"] == 2
    assert doc["surfaceBindings"][1]["hasLightmap"] is False

    doc2 = build_manifest(copy.deepcopy(world), copy.deepcopy(catalog))
    assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
        doc2, sort_keys=True, separators=(",", ":")
    )

    nested = _catalog()
    nested["lightmaps"][0]["primaryImage"] = "folder/lm_primary"
    try:
        build_manifest(world, nested)
    except LightmapManifestError:
        pass
    else:
        raise AssertionError("nested OAT image path did not fail closed")

    print("PASS t6_world_lightmap_manifest_v2 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
