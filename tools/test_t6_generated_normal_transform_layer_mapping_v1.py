#!/usr/bin/env python3
from __future__ import annotations

import t6_generated_normal_transform_layer_mapping_v1 as mapping


def main() -> int:
    text = """
      vertex.texcoord[5] = code.normalTransform[0];
      vertex.texcoord[6] = code.normalTransform[1];
      // unrelated stream
      vertex.texcoord[4] = code.texCoord[2];
    """
    assert mapping.parse_normal_transform_routes(text) == {0: 5, 1: 6}

    # Transformed layer 2 depends only on outputs proven from transform 0;
    # transformed layer 3 depends only on transform 1. Direct layer 1 needs none.
    layers = [
        {
            "layerIndex": 1,
            "normalPairKind": "direct",
            "pixelInputDependencies": [],
        },
        {
            "layerIndex": 2,
            "normalPairKind": "matrix2x2",
            "pixelInputDependencies": ["TEXCOORD7.x", "TEXCOORD7.y"],
        },
        {
            "layerIndex": 3,
            "normalPairKind": "matrix2x2",
            "pixelInputDependencies": ["TEXCOORD8.x", "TEXCOORD8.y"],
        },
    ]
    outputs = {
        0: ["TEXCOORD7.x", "TEXCOORD7.y", "TEXCOORD7.z"],
        1: ["TEXCOORD8.x", "TEXCOORD8.y", "TEXCOORD8.z"],
    }
    assigned = mapping._assign_transforms(layers, outputs)
    assert assigned[0]["normalTransformRequired"] is False
    assert assigned[0]["normalTransformIndex"] is None
    assert assigned[1]["candidateTransformIndices"] == [0]
    assert assigned[1]["normalTransformIndex"] == 0
    assert assigned[2]["candidateTransformIndices"] == [1]
    assert assigned[2]["normalTransformIndex"] == 1

    # Crucial anti-shortcut case: generated layer 2 can map to transform 0.
    only_layer2 = mapping._assign_transforms([
        {
            "layerIndex": 2,
            "normalPairKind": "matrix2x2",
            "pixelInputDependencies": ["TEXCOORD9.x", "TEXCOORD9.y"],
        }
    ], {0: ["TEXCOORD9.x", "TEXCOORD9.y"]})
    assert only_layer2[0]["normalTransformIndex"] == 0

    # Ambiguous ancestry must fail closed rather than choose the lower slot.
    try:
        mapping._assign_transforms([
            {
                "layerIndex": 1,
                "normalPairKind": "matrix2x2",
                "pixelInputDependencies": ["TEXCOORD7.x"],
            }
        ], {
            0: ["TEXCOORD7.x"],
            1: ["TEXCOORD7.x", "TEXCOORD8.x"],
        })
    except mapping.NormalTransformLayerMappingError as exc:
        assert "transform candidates [0, 1]" in str(exc)
    else:
        raise AssertionError("ambiguous normalTransform ancestry was accepted")

    # A transform cannot be claimed by two different generated normal layers.
    try:
        mapping._assign_transforms([
            {
                "layerIndex": 1,
                "normalPairKind": "matrix2x2",
                "pixelInputDependencies": ["TEXCOORD7.x"],
            },
            {
                "layerIndex": 2,
                "normalPairKind": "matrix2x2",
                "pixelInputDependencies": ["TEXCOORD7.y"],
            },
        ], {0: ["TEXCOORD7.x", "TEXCOORD7.y"]})
    except mapping.NormalTransformLayerMappingError as exc:
        assert "maps to generated normal layers" in str(exc)
    else:
        raise AssertionError("one transform was assigned to two generated normal layers")

    # Conflicting .tech routes are provenance failures.
    try:
        mapping.parse_normal_transform_routes("""
          vertex.texcoord[5] = code.normalTransform[0];
          vertex.texcoord[6] = code.normalTransform[0];
        """)
    except mapping.NormalTransformLayerMappingError as exc:
        assert "routes to both" in str(exc)
    else:
        raise AssertionError("conflicting normalTransform routes were accepted")

    print("PASS: exact generated normal transform layer mapping v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
