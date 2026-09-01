#!/usr/bin/env python3
"""Regression for strict retail T6 deltaPart -> glTF semantics v2."""
from __future__ import annotations

import math

from t6_xanim_delta_gltf_semantics_v2 import (
    DeltaGltfError,
    delta_rotation_sampler,
    delta_translation_sampler,
    duration_seconds,
    timing_info,
)


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _hermite(v0, v1, m0, m1, dt, u):
    u2, u3 = u * u, u * u * u
    return [
        (2*u3 - 3*u2 + 1)*a
        + dt*(u3 - 2*u2 + u)*ma
        + (-2*u3 + 3*u2)*b
        + dt*(u3 - u2)*mb
        for a, b, ma, mb in zip(v0, v1, m0, m1)
    ]


def _must_fail(fn, contains: str):
    try:
        fn()
    except DeltaGltfError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError(f"expected DeltaGltfError containing {contains!r}")


def main() -> int:
    header = {
        "numframes": 300,
        "framerate": 30.0,
        "frequency": 0.1,
        "bDelta": False,
        "bDelta3D": True,
    }
    assert duration_seconds(header) == 10.0
    assert timing_info(header)["indexWidthBytes"] == 2

    delta = {
        "trans": {
            "mode": "dynamic",
            "smallTrans": False,
            "indices": [0, 100, 300],
            "decodedFrames": [[0, 0, 0], [3, 5, 7], [9, 12, 15]],
        },
        "quat": {
            "mode": "dynamic",
            "indices": [0, 100, 300],
            "rawInt16Frames": [
                [0, 0, 0, 32767],
                [4000, -3000, 5000, 31800],
                [7000, 2000, -4000, 31000],
            ],
        },
    }
    tr = delta_translation_sampler(delta, header)
    assert tr["times"] == [0.0, 100/30, 10.0]
    assert tr["values"] == delta["trans"]["decodedFrames"]
    assert tr["nativeDomainValidated"] is True
    assert tr["indexWidthBytes"] == 2

    qr = delta_rotation_sampler(delta, header)
    assert qr["times"] == [0.0, 100/30, 10.0]
    assert qr["interpolation"] == "CUBICSPLINE"
    assert qr["nativeDomainValidated"] is True
    assert qr["indexWidthBytes"] == 2
    assert len(qr["cubicRows"]) == 3 * len(qr["times"])
    for q in qr["values"]:
        assert abs(math.sqrt(sum(x*x for x in q)) - 1.0) < 1e-12

    scale = 1.0 / 32767.0
    raw = [[x*scale for x in row] for row in delta["quat"]["rawInt16Frames"]]
    for i in range(len(qr["times"]) - 1):
        dt = qr["times"][i+1] - qr["times"][i]
        for u in (0.0, 0.1, 0.37, 0.75, 1.0):
            p = _hermite(
                qr["values"][i], qr["values"][i+1],
                qr["outTangents"][i], qr["inTangents"][i+1], dt, u,
            )
            got = _unit(p)
            target = _unit([(1-u)*a + u*b for a, b in zip(raw[i], raw[i+1])])
            assert max(abs(a-b) for a, b in zip(got, target)) < 2e-12

    # Byte-index 2D delta path, complete 0..numframes native domain.
    q2 = delta_rotation_sampler(
        {"quat2": {
            "mode": "dynamic",
            "indices": [0, 1, 2],
            "rawInt16Frames": [[0, 32767], [8192, 31727], [16384, 28377]],
        }},
        {"numframes": 2, "framerate": 30.0, "frequency": 15.0,
         "bDelta": True, "bDelta3D": False},
    )
    assert q2["sourceType"] == "quat2"
    assert q2["indexWidthBytes"] == 1
    assert all(abs(q[0]) < 1e-15 and abs(q[1]) < 1e-15 for q in q2["values"])

    # Constant During and Entire paths read the same frame0/value, so the glTF
    # channel is constant over the complete animation interval.
    ctrans = delta_translation_sampler(
        {"trans": {"mode": "constant", "value": [4.0, -2.0, 1.5]}},
        {"numframes": 30, "framerate": 30.0, "frequency": 1.0},
    )
    assert ctrans["times"] == [0.0, 1.0]
    assert ctrans["values"] == [[4.0, -2.0, 1.5], [4.0, -2.0, 1.5]]
    cquat = delta_rotation_sampler(
        {"quat2": {"mode": "constant", "rawInt16": [0, 32767]}},
        {"numframes": 30, "framerate": 30.0, "frequency": 1.0,
         "bDelta": True, "bDelta3D": False},
    )
    assert cquat["times"] == [0.0, 1.0]
    assert cquat["values"] == [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]]

    def dynamic(indices):
        return lambda: delta_translation_sampler(
            {"trans": {"mode": "dynamic", "smallTrans": False,
                       "indices": indices,
                       "decodedFrames": [[0,0,0] for _ in indices]}},
            header,
        )

    # The exact bug v1 allowed: no endpoint fabrication is permitted in v2.
    _must_fail(dynamic([10, 250]), "first native key must be frame 0")
    _must_fail(dynamic([0, 250]), "final native key must be numframes 300")
    _must_fail(dynamic([0, 100, 100, 300]), "not strictly increasing")
    _must_fail(dynamic([0, 301, 300]), "outside 0..300")
    _must_fail(
        lambda: delta_translation_sampler(
            {"trans": {"mode": "dynamic", "indices": [0, 0],
                       "decodedFrames": [[0,0,0],[1,1,1]]}},
            {"numframes": 0, "framerate": 30.0, "frequency": 0.0},
        ),
        "dynamic track requires numframes > 0",
    )
    _must_fail(
        lambda: delta_rotation_sampler(
            {"quat": {"mode": "dynamic", "indices": [0, 300],
                      "rawInt16Frames": [[0,0,0,32767]]}},
            header,
        ),
        "index/frame mismatch",
    )
    _must_fail(
        lambda: timing_info({"numframes": 300, "framerate": 30.0, "frequency": 0.2}),
        "!= framerate/numframes",
    )

    print("PASS t6_xanim_delta_gltf_semantics_v2 strict native-domain regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
