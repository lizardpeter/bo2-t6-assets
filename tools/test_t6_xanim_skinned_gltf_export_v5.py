#!/usr/bin/env python3
"""Integration regression for v5 retail delta-root sampler rewriting."""
from __future__ import annotations

import base64

from t6_xanim_skinned_gltf_export_v5 import _replace_delta_channels, _validate_v5


def main() -> int:
    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": 0, "uri": "data:application/octet-stream;base64,"}],
        "bufferViews": [],
        "accessors": [],
        "animations": [{
            "samplers": [
                {"input": 0, "output": 0, "interpolation": "LINEAR"},
                {"input": 0, "output": 0, "interpolation": "LINEAR"},
            ],
            "channels": [
                {
                    "sampler": 0,
                    "target": {"node": 0, "path": "rotation"},
                    "extras": {"trackName": "__T6_DELTA_ROOT__"},
                },
                {
                    "sampler": 1,
                    "target": {"node": 0, "path": "translation"},
                    "extras": {"trackName": "__T6_DELTA_ROOT__"},
                },
            ],
            "extras": {"T6": {}},
        }],
    }
    xanim = {
        "header": {"numframes": 300, "framerate": 30.0, "bDelta": False, "bDelta3D": True},
        "delta": {
            "quat": {
                "mode": "dynamic",
                "indices": [10, 250],
                "rawInt16Frames": [
                    [2000, -3000, 4000, 32000],
                    [6000, 1000, -5000, 31500],
                ],
            },
            "trans": {
                "mode": "dynamic",
                "smallTrans": False,
                "indices": [10, 250],
                "decodedFrames": [[1, 2, 3], [7, 11, 13]],
            },
        },
    }

    raw = bytearray()
    stats = _replace_delta_channels(gltf, raw, xanim)
    gltf["buffers"][0] = {
        "byteLength": len(raw),
        "uri": "data:application/octet-stream;base64," + base64.b64encode(raw).decode("ascii"),
    }
    _validate_v5(gltf)

    rot = gltf["animations"][0]["samplers"][0]
    trans = gltf["animations"][0]["samplers"][1]
    rot_in = gltf["accessors"][rot["input"]]
    rot_out = gltf["accessors"][rot["output"]]
    trans_in = gltf["accessors"][trans["input"]]
    trans_out = gltf["accessors"][trans["output"]]

    assert rot["interpolation"] == "CUBICSPLINE"
    assert rot_out["count"] == rot_in["count"] * 3
    assert trans["interpolation"] == "LINEAR"
    assert trans_out["count"] == trans_in["count"]
    assert rot_in["min"] == [0.0] and rot_in["max"] == [10.0]
    assert trans_in["min"] == [0.0] and trans_in["max"] == [10.0]
    assert stats == {"rotation": True, "translation": True, "durationSeconds": 10.0}

    print("PASS t6_xanim_skinned_gltf_export_v5 delta rewrite regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
