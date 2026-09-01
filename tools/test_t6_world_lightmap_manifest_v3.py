#!/usr/bin/env python3
"""Regression for nullable retail T6 world-lightmap roles."""
from __future__ import annotations

import copy
import json

from t6_world_lightmap_manifest_v1 import LightmapManifestError
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
            {"index": 4, "groupIndex": 0, "lightmapIndex": 31},
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
                "primaryImage": "",
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
                "secondaryImage": "",
            },
        ],
    }


def main() -> int:
    world = _world()
    catalog = _catalog()
    doc = build_manifest(world, catalog)

    assert doc["format"] == "t6-world-lightmap-manifest-v3"
    assert doc["source"]["producer"] == "t6_world_lightmap_manifest_v3.py"
    stats = doc["stats"]
    assert stats["lightmapCount"] == 4
    assert stats["declaredRoleCount"] == 8
    assert stats["presentRoleDependencyUseCount"] == 4
    assert stats["presentPrimaryImageCount"] == 2
    assert stats["absentPrimaryImageCount"] == 2
    assert stats["presentSecondaryImageCount"] == 2
    assert stats["absentSecondaryImageCount"] == 2
    assert stats["oatImageFilenameChangedDependencyCount"] == 2
    assert stats["oatImageUniqueDiskSourceCount"] == 4
    assert stats["surfacesWithLightmap"] == 4
    assert stats["surfacesWithoutLightmap"] == 1

    both = doc["lightmaps"][0]
    assert both["primaryPresent"] is True
    assert both["primaryOatImageAsset"] == "*lm0_primary"
    assert both["primarySourceTexture"] == "_lm0_primary.dds"
    assert both["secondaryPresent"] is True
    assert both["secondarySourceTexture"] == "lm0_secondary.dds"

    secondary_only = doc["lightmaps"][1]
    assert secondary_only["primaryPresent"] is False
    assert secondary_only["primaryImage"] is None
    assert secondary_only["primaryOatImageAsset"] is None
    assert secondary_only["primarySourceTexture"] is None
    assert secondary_only["primaryOatImagePath"] is None
    assert secondary_only["primaryCodeTextureSource"] == 4
    assert secondary_only["primarySamplerAccessor"] == "lightmapSamplerPrimary"
    assert secondary_only["secondaryPresent"] is True
    assert secondary_only["secondarySourceTexture"] == "_lm1_secondary.dds"
    assert secondary_only["source"]["primaryPointer"]["kind"] == "null"

    primary_only = doc["lightmaps"][2]
    assert primary_only["primaryPresent"] is True
    assert primary_only["secondaryPresent"] is False
    assert primary_only["secondarySourceTexture"] is None
    assert primary_only["secondaryCodeTextureSource"] == 5
    assert primary_only["secondarySamplerAccessor"] == "lightmapSamplerSecondary"

    neither = doc["lightmaps"][3]
    assert neither["primaryPresent"] is False
    assert neither["secondaryPresent"] is False

    binding = doc["surfaceBindings"][1]
    assert binding["hasLightmap"] is True
    assert binding["primaryPresent"] is False
    assert binding["primarySourceTexture"] is None
    assert binding["primaryCodeTextureSource"] == 4
    assert binding["secondaryPresent"] is True
    assert binding["secondarySourceTexture"] == "_lm1_secondary.dds"
    assert binding["lightmapTexCoord"] == 2

    assert doc["surfaceBindings"][4]["hasLightmap"] is False

    doc2 = build_manifest(copy.deepcopy(world), copy.deepcopy(catalog))
    assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
        doc2, sort_keys=True, separators=(",", ":")
    )

    nested = _catalog()
    nested["lightmaps"][2]["primaryImage"] = "folder/lm2_primary"
    try:
        build_manifest(world, nested)
    except LightmapManifestError:
        pass
    else:
        raise AssertionError("nested present lightmap image path did not fail closed")

    collision = _catalog()
    collision["lightmaps"][0]["primaryImage"] = "*foo"
    collision["lightmaps"][2]["primaryImage"] = "_foo"
    try:
        build_manifest(world, collision)
    except LightmapManifestError as exc:
        text = str(exc)
        assert "collide after OAT filename mapping" in text
        assert "*foo" in text and "_foo" in text and "_foo.dds" in text
    else:
        raise AssertionError(
            "distinct present lightmap GfxImage identities were allowed to collide"
        )

    print("PASS t6_world_lightmap_manifest_v3 nullable-role regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
