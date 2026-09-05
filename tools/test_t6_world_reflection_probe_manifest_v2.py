#!/usr/bin/env python3
from __future__ import annotations

import copy
import math

from t6_world_reflection_probe_manifest_v2 import (
    ReflectionProbeManifestError,
    build_manifest,
)


def _probe(index: int, image, *, bias: float = 0.25, volumes: int = 1) -> dict:
    volume_rows = []
    for volume_index in range(volumes):
        volume_rows.append(
            {
                "volumeIndex": volume_index,
                "volumePlanes": [
                    [1.0, 0.0, 0.0, -10.0 - volume_index],
                    [-1.0, 0.0, 0.0, -10.0 - volume_index],
                    [0.0, 1.0, 0.0, -20.0 - volume_index],
                    [0.0, -1.0, 0.0, -20.0 - volume_index],
                    [0.0, 0.0, 1.0, -30.0 - volume_index],
                    [0.0, 0.0, -1.0, -30.0 - volume_index],
                ],
            }
        )
    return {
        "index": index,
        "origin": [float(index), float(index + 1), float(index + 2)],
        "lightingSH": {
            "V0": [0.1, 0.2, 0.3, 0.4],
            "V1": [0.5, 0.6, 0.7, 0.8],
            "V2": [0.9, 1.0, 1.1, 1.2],
        },
        "reflectionImage": image,
        "probeVolumeCount": volumes,
        "probeVolumes": volume_rows,
        "mipLodBias": bias,
    }


def _world() -> dict:
    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": "mp_fixture",
        "surfaces": [
            {"index": 0, "reflectionProbeIndex": 0},
            {"index": 1, "reflectionProbeIndex": 1},
            {"index": 2, "reflectionProbeIndex": 0},
        ],
    }


def _catalog() -> dict:
    return {
        "format": "t6-gfxworld-reflection-probe-catalog-v1",
        "map": "mp_fixture",
        "reflectionProbeCount": 3,
        "reflectionProbes": [
            _probe(0, "probe*zero"),
            _probe(1, None, volumes=0),
            _probe(2, "unused_probe", bias=-0.5),
        ],
    }


def expect_error(world: dict, catalog: dict, needle: str) -> None:
    try:
        build_manifest(world, catalog)
    except ReflectionProbeManifestError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected ReflectionProbeManifestError containing {needle!r}")


def main() -> int:
    world = _world()
    catalog = _catalog()
    doc = build_manifest(world, catalog)

    assert doc["format"] == "t6-world-reflection-probe-manifest-v2"
    assert doc["stats"]["surfaceCount"] == 3
    assert doc["stats"]["reflectionProbeCount"] == 3
    assert doc["stats"]["presentReflectionImageProbeCount"] == 2
    assert doc["stats"]["absentReflectionImageProbeCount"] == 1
    assert doc["stats"]["referencedReflectionProbeCount"] == 2
    assert doc["stats"]["unreferencedReflectionProbeCount"] == 1
    assert doc["referencedReflectionProbeIndices"] == [0, 1]
    assert doc["unreferencedReflectionProbeIndices"] == [2]
    assert doc["stats"]["surfaceUseCountByReflectionProbe"] == {"0": 2, "1": 1}

    p0, p1, p2 = doc["reflectionProbes"]
    assert p0["reflectionImagePresent"] is True
    assert p0["reflectionImage"] == "probe*zero"
    assert p0["reflectionOatImageAsset"] == "probe*zero"
    assert p0["reflectionSourceTexture"] == "probe_zero.dds"
    assert p0["reflectionOatImagePath"] == "images/probe_zero.dds"
    assert doc["stats"]["oatImageFilenameChangedDependencyCount"] == 1

    assert p1["reflectionImagePresent"] is False
    assert p1["reflectionImage"] is None
    assert p1["reflectionOatImageAsset"] is None
    assert p1["reflectionSourceTexture"] is None
    assert p1["reflectionOatImagePath"] is None
    assert p1["probeVolumeCount"] == 0
    assert p1["probeVolumes"] == []

    assert p2["reflectionImagePresent"] is True
    assert p2["reflectionSourceTexture"] == "unused_probe.dds"
    assert p2["mipLodBias"] == -0.5

    # Probe index 0 is explicitly valid and is not treated as a sentinel.
    assert doc["surfaceBindings"][0]["reflectionProbeIndex"] == 0
    assert doc["surfaceBindings"][2]["reflectionProbeIndex"] == 0
    assert doc["surfaceBindings"][1]["reflectionImagePresent"] is False

    bad = copy.deepcopy(world)
    bad["surfaces"][0].pop("reflectionProbeIndex")
    expect_error(bad, catalog, "missing reflectionProbeIndex")

    bad = copy.deepcopy(world)
    bad["surfaces"][0]["reflectionProbeIndex"] = 3
    expect_error(bad, catalog, "outside 0..2")

    bad_catalog = copy.deepcopy(catalog)
    bad_catalog["reflectionProbes"][1]["index"] = 2
    expect_error(world, bad_catalog, "dense/in-order")

    bad_catalog = copy.deepcopy(catalog)
    bad_catalog["reflectionProbes"][0]["reflectionImage"] = ""
    expect_error(world, bad_catalog, "null or a non-empty")

    bad_catalog = copy.deepcopy(catalog)
    bad_catalog["reflectionProbes"][0]["mipLodBias"] = math.nan
    expect_error(world, bad_catalog, "non-finite mipLodBias")

    bad_catalog = copy.deepcopy(catalog)
    bad_catalog["reflectionProbes"][0]["probeVolumes"][0]["volumePlanes"] = [[1, 0, 0, 0]] * 5
    expect_error(world, bad_catalog, "expected six volume planes")

    # Current staging is deliberately flat; do not silently flatten a real OAT
    # image subpath differently from OAT itself.
    bad_catalog = copy.deepcopy(catalog)
    bad_catalog["reflectionProbes"][0]["reflectionImage"] = "folder/probe"
    expect_error(world, bad_catalog, "flat DDS staging")

    wrong_map = copy.deepcopy(catalog)
    wrong_map["map"] = "mp_other"
    expect_error(world, wrong_map, "map mismatch")

    print("PASS: T6 world reflection probe manifest v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
