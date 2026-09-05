#!/usr/bin/env python3
from __future__ import annotations

import t6_generated_height_leaf_bindings_v1 as bindings


def _payload(raw_input="COLOR.y", channel="w"):
    return {
        "techniqueSet": "lit_sm_r0c0_b1c1v1",
        "pixelShaderSha256": "a" * 64,
        "layers": [{
            "layerIndex": 1,
            "forensicDag": {
                "forensicDagSha256": "b" * 64,
                "nodes": [
                    {"id": 0, "kind": "input", "name": raw_input},
                    {"id": 1, "kind": "sample", "resource": "colorMapSampler1", "channel": channel, "sampler": "s1"},
                    {"id": 2, "kind": "cb", "name": "cb1[59].x"},
                    {"id": 3, "kind": "cb", "name": "cb1[59].y"},
                    {"id": 4, "kind": "add", "args": [0, 1]},
                ],
            },
        }],
    }


def main() -> int:
    tech = """
    pixelShader 4.0 "fixture"
    {
      colorMapSampler1 = material.colorMap1;
      alphaRevealParms1 = material.alphaRevealParms1;
    }
    """
    doc = bindings.build_height_leaf_bindings(_payload(), technique_text=tech)
    assert doc["format"] == bindings.FORMAT
    assert doc["heightLayerCount"] == 1
    assert doc["allNonconstantLeavesExact"] is True
    row = doc["layers"][0]
    assert row["rawVertexInputs"] == ["COLOR.y"]
    assert row["normalizedVertexWeight"] == {
        "attribute": "_T6_LAYER_WEIGHTS",
        "component": "G",
        "layerIndex": 1,
        "proof": row["normalizedVertexWeight"]["proof"],
    }
    sample = row["sampleBindings"][0]
    assert sample["resource"] == "colorMapSampler1"
    assert sample["channel"] == "w"
    assert sample["materialArgument"] == "colorMap1"
    assert sample["portableDependency"] == {"layerIndex": 1, "role": "colorMap"}
    assert row["constantLeaves"] == ["cb1[59].x", "cb1[59].y"]
    assert len(doc["bindingSetSha256"]) == 64

    # Raw semantic can differ (two-layer retail shaders use TEXCOORD6.y); layer
    # identity comes from the solved recurrence, so the normalized output stays G.
    alt = bindings.build_height_leaf_bindings(_payload("TEXCOORD6.y"), technique_text=tech)
    assert alt["layers"][0]["rawVertexInputs"] == ["TEXCOORD6.y"]
    assert alt["layers"][0]["normalizedVertexWeight"]["component"] == "G"

    try:
        bindings.build_height_leaf_bindings(_payload(channel="x"), technique_text=tech)
    except bindings.GeneratedHeightLeafBindingError as exc:
        assert "not alpha-only" in str(exc)
    else:
        raise AssertionError("non-alpha height sample was silently mapped to colorMap Alpha")

    try:
        bindings.build_height_leaf_bindings(_payload(), technique_text="pixelShader 4.0 \"fixture\" {}")
    except bindings.GeneratedHeightLeafBindingError as exc:
        assert "has no exact material.* assignment" in str(exc)
    else:
        raise AssertionError("sample resource without .tech material assignment was guessed")

    print("PASS: exact T6 generated height nonconstant leaf bindings v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
