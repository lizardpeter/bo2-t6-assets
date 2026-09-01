#!/usr/bin/env python3
"""Integration regression for v6 strict retail delta-root rewriting."""
from __future__ import annotations

import base64

from t6_xanim_gltf_export_v3 import ExportError
from t6_xanim_rigid_gltf_export_v3 import trans_values
from t6_xanim_skinned_gltf_export_v6 import _replace_delta_channels, _validate_v5


def _base_gltf() -> dict:
    return {
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


def main() -> int:
    xanim = {
        "header": {
            "numframes": 300,
            "framerate": 30.0,
            "frequency": 0.1,
            "bDelta": False,
            "bDelta3D": True,
        },
        "delta": {
            "quat": {
                "mode": "dynamic",
                "indices": [0, 100, 300],
                "rawInt16Frames": [
                    [0, 0, 0, 32767],
                    [4000, -3000, 5000, 31800],
                    [7000, 2000, -4000, 31000],
                ],
            },
            "trans": {
                "mode": "dynamic",
                "smallTrans": False,
                "indices": [0, 100, 300],
                "decodedFrames": [[0, 0, 0], [3, 5, 7], [9, 12, 15]],
            },
        },
    }

    gltf = _base_gltf()
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
    assert rot_out["count"] == rot_in["count"] * 3 == 9
    assert trans["interpolation"] == "LINEAR"
    assert trans_out["count"] == trans_in["count"] == 3
    assert rot_in["min"] == [0.0] and rot_in["max"] == [10.0]
    assert trans_in["min"] == [0.0] and trans_in["max"] == [10.0]
    assert stats == {
        "rotation": True,
        "translation": True,
        "durationSeconds": 10.0,
        "nativeDynamicDomainRequired": True,
        "rotationIndexWidthBytes": 2,
        "translationIndexWidthBytes": 2,
    }
    for ch in gltf["animations"][0]["channels"]:
        assert ch["extras"]["t6NativeDynamicDomainValidated"] is True
        assert ch["extras"]["t6IndexWidthBytes"] == 2
    assert gltf["animations"][0]["extras"]["T6"]["deltaEndpointPolicy"] == (
        "use stored native keys only; never fabricate 0/end keys"
    )

    # The v1/v5 permissive synthetic domain must now fail rather than creating
    # frame-0/frame-end copies.
    bad = _base_gltf()
    bad_xanim = {
        "header": xanim["header"],
        "delta": {
            "quat": {
                "mode": "dynamic",
                "indices": [10, 250],
                "rawInt16Frames": [[0,0,0,32767], [4000,-3000,5000,31800]],
            },
            "trans": {
                "mode": "dynamic",
                "indices": [10, 250],
                "decodedFrames": [[1,2,3], [7,11,13]],
            },
        },
    }
    try:
        _replace_delta_channels(bad, bytearray(), bad_xanim)
    except ExportError as exc:
        assert "first native key must be frame 0" in str(exc), str(exc)
    else:
        raise AssertionError("expected incomplete native delta domain to fail")

    # deltaPart root motion is a separate path; ordinary animated root-bone
    # translation remains fail-closed through the existing composition helper.
    try:
        trans_values(
            {"trans": {"type": "TRANS_NO_SIZE", "constant": [1.0, 2.0, 3.0]}},
            {"name": "root", "parentIndex": None, "localTranslation": [0,0,0]},
        )
    except ExportError as exc:
        assert "animated root translation not source-closed" in str(exc), str(exc)
    else:
        raise AssertionError("ordinary animated root translation must remain rejected")

    print("PASS t6_xanim_skinned_gltf_export_v6 strict retail delta integration regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
