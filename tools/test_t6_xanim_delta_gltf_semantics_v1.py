#!/usr/bin/env python3
from __future__ import annotations

import math

from t6_xanim_delta_gltf_semantics_v1 import delta_rotation_sampler, delta_translation_sampler


def _unit(v):
    n = math.sqrt(sum(x*x for x in v))
    return [x/n for x in v]


def _hermite(v0, v1, m0, m1, dt, u):
    u2 = u*u
    u3 = u2*u
    return [
        (2*u3-3*u2+1)*a + dt*(u3-2*u2+u)*ma + (-2*u3+3*u2)*b + dt*(u3-u2)*mb
        for a, b, ma, mb in zip(v0, v1, m0, m1)
    ]


def main() -> int:
    header = {"numframes": 300, "framerate": 30.0, "bDelta": False, "bDelta3D": True}
    delta = {
        "trans": {
            "mode": "dynamic",
            "smallTrans": False,
            "indices": [10, 250],
            "decodedFrames": [[1, 2, 3], [7, 11, 13]],
        },
        "quat": {
            "mode": "dynamic",
            "indices": [10, 250],
            "rawInt16Frames": [[2000, -3000, 4000, 32000], [6000, 1000, -5000, 31500]],
        },
    }
    tr = delta_translation_sampler(delta, header)
    assert tr["times"] == [0.0, 10/30, 250/30, 10.0]
    assert tr["values"][0] == tr["values"][1]
    assert tr["values"][-1] == tr["values"][-2]

    qr = delta_rotation_sampler(delta, header)
    assert qr["interpolation"] == "CUBICSPLINE"
    assert qr["times"] == [0.0, 10/30, 250/30, 10.0]
    assert len(qr["cubicRows"]) == 3 * len(qr["times"])
    for q in qr["values"]:
        assert abs(math.sqrt(sum(x*x for x in q)) - 1.0) < 1e-12

    scale = 1/32767.0
    native = [
        [2000*scale, -3000*scale, 4000*scale, 32000*scale],
        [6000*scale, 1000*scale, -5000*scale, 31500*scale],
    ]
    expanded = [native[0], native[0], native[1], native[1]]
    for i in range(len(qr["times"]) - 1):
        dt = qr["times"][i+1] - qr["times"][i]
        for u in (0.0, 0.1, 0.37, 0.75, 1.0):
            p = _hermite(
                qr["values"][i], qr["values"][i+1],
                qr["outTangents"][i], qr["inTangents"][i+1], dt, u,
            )
            got = _unit(p)
            target = _unit([(1-u)*a + u*b for a, b in zip(expanded[i], expanded[i+1])])
            assert max(abs(a-b) for a, b in zip(got, target)) < 2e-12

    q2 = delta_rotation_sampler(
        {"quat2": {"mode": "dynamic", "indices": [0, 2], "rawInt16Frames": [[0, 32767], [16384, 28377]]}},
        {"numframes": 2, "framerate": 30.0, "bDelta": True, "bDelta3D": False},
    )
    assert all(abs(q[0]) < 1e-15 and abs(q[1]) < 1e-15 for q in q2["values"])
    assert q2["sourceType"] == "quat2"

    const = delta_rotation_sampler(
        {"quat": {"mode": "constant", "rawInt16": [0, 0, 0, 32767]}},
        {"numframes": 30, "framerate": 30.0, "bDelta": False, "bDelta3D": True},
    )
    assert const["interpolation"] == "LINEAR"
    assert const["times"] == [0.0, 1.0]
    assert const["values"] == [[0, 0, 0, 1], [0, 0, 0, 1]]

    print("PASS t6_xanim_delta_gltf_semantics_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
