#!/usr/bin/env python3
"""Regression for generalized T6 rigid+blended skin-row validation in glTF v4."""
from __future__ import annotations

import copy

from t6_xanim_gltf_export_v3 import ExportError
from t6_xanim_skinned_gltf_export_v4 import validate_skin_rows


def _skeleton() -> dict:
    return {
        "format": "t6-xmodel-skeleton-normalized-v2-synthetic",
        "identity": {"name": "synthetic/skinned"},
        "skeleton": {
            "bones": [
                {"index": 0, "name": "root"},
                {"index": 1, "name": "bone1"},
                {"index": 2, "name": "bone2"},
                {"index": 3, "name": "bone3"},
            ]
        },
    }


def _mesh() -> dict:
    # Native serializer order for this surface is:
    #   rigid, then blended 1-influence, 2-influence, 3-influence, 4-influence.
    # The validator intentionally trusts those native bucket counts rather than
    # re-inferring influence cardinality from positive float weights.
    joints = [
        [0, 0, 0, 0],
        [1, 0, 0, 0],
        [1, 2, 0, 0],
        [0, 1, 2, 0],
        [0, 1, 2, 3],
    ]
    weights = [
        [1.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.25, 0.75, 0.0, 0.0],
        [0.20, 0.30, 0.50, 0.0],
        [0.10, 0.20, 0.30, 0.40],
    ]
    return {
        "format": "t6-xmodel-mesh-normalized-v1",
        "identity": {"name": "synthetic/skinned"},
        "xmodel": {"lods": [{"index": 0, "surfIndex": 0, "numSurfs": 1}]},
        "surfaces": [
            {
                "index": 0,
                "vertices": [[float(i), 0.0, 0.0] for i in range(5)],
                "triangles": [[0, 1, 2], [2, 3, 4]],
                "joints0": joints,
                "weights0": weights,
                "rigidVertLists": [{"vertCount": 1}],
                "blendCounts": [1, 1, 1, 1],
                "unweightedVertexCount": 0,
            }
        ],
    }


def _expect_error(mesh: dict, skeleton: dict, needle: str) -> None:
    try:
        validate_skin_rows(mesh, skeleton, 0)
    except ExportError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected ExportError containing {needle!r}")


def main() -> int:
    mesh = _mesh()
    skeleton = _skeleton()
    census = validate_skin_rows(mesh, skeleton, 0)
    assert census["surfaces"] == 1
    assert census["vertices"] == 5
    assert census["triangles"] == 2
    assert census["rigidVertices"] == 1
    assert census["blendedVertices"] == 4
    assert census["unweightedVertices"] == 0
    assert census["influenceHistogram"] == {"1": 2, "2": 1, "3": 1, "4": 1}
    assert census["allVerticesWeighted"] is True
    assert census["maxWeightSumError"] <= 1e-12
    assert abs(census["minPositiveWeight"] - 0.10) <= 1e-12
    assert abs(census["maxPositiveWeight"] - 1.0) <= 1e-12

    # A stored final native influence is allowed to quantize to zero. Bucket
    # cardinality is still taken from blendCounts, not from positive slots.
    quantized = copy.deepcopy(mesh)
    quantized["surfaces"][0]["weights0"][4] = [0.10, 0.20, 0.70, 0.0]
    quantized_census = validate_skin_rows(quantized, skeleton, 0)
    assert quantized_census["influenceHistogram"]["4"] == 1

    unweighted = copy.deepcopy(mesh)
    unweighted["surfaces"][0]["rigidVertLists"] = []
    unweighted["surfaces"][0]["blendCounts"] = [1, 1, 1, 1]
    unweighted["surfaces"][0]["unweightedVertexCount"] = 1
    _expect_error(unweighted, skeleton, "unweighted vertices")

    bad_joint = copy.deepcopy(mesh)
    bad_joint["surfaces"][0]["joints0"][4][3] = 99
    _expect_error(bad_joint, skeleton, "joint 99 outside 4")

    bad_padded_weight = copy.deepcopy(mesh)
    bad_padded_weight["surfaces"][0]["weights0"][2][2] = 0.1
    bad_padded_weight["surfaces"][0]["weights0"][2][1] = 0.65
    _expect_error(bad_padded_weight, skeleton, "nonzero padded weight slot 2")

    bad_sum = copy.deepcopy(mesh)
    bad_sum["surfaces"][0]["weights0"][3] = [0.2, 0.3, 0.4, 0.0]
    _expect_error(bad_sum, skeleton, "nonunit skin weights")

    bad_lengths = copy.deepcopy(mesh)
    bad_lengths["surfaces"][0]["weights0"].pop()
    _expect_error(bad_lengths, skeleton, "vertices/joints0/weights0 length mismatch")

    bad_histogram = copy.deepcopy(mesh)
    bad_histogram["surfaces"][0]["blendCounts"] = [2, 1, 1, 0]
    # The fifth row is then interpreted as 3-influence, where its fourth slot
    # is nonzero, proving that serializer bucket boundaries are enforced.
    _expect_error(bad_histogram, skeleton, "nonzero padded weight slot 3")

    print("PASS t6_xanim_skinned_gltf_export_v4 skin regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
