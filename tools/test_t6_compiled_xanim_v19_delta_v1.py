#!/usr/bin/env python3
"""Regression for source-closed T6 compiled XAnim v19 delta subsection codec."""
from __future__ import annotations

import math
import struct

from t6_compiled_xanim_v19_delta_v1 import (
    CompiledDeltaError,
    RADIUS_SQ,
    decode_delta_section,
    encode_delta_section,
)


def omitted(*stored: int) -> int:
    return int(math.floor(math.sqrt(max(0, RADIUS_SQ - sum(v*v for v in stored))) + 0.5))


def q2(z: int):
    return [z, omitted(z)]


def q3(x: int, y: int, z: int):
    return [x, y, z, omitted(x, y, z)]


def must_fail(fn, contains: str):
    try:
        fn()
    except CompiledDeltaError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError(f"expected CompiledDeltaError containing {contains!r}")


def main() -> int:
    # T6 2D delta, byte indices, sequential complete coverage. OAT omits the
    # explicit index bytes because count == numframes+1 and indices are 0..N.
    h2 = {"numframes": 2, "framerate": 30.0, "frequency": 15.0,
          "bDelta": True, "bDelta3D": False}
    d2 = {
        "quat2": {
            "mode": "dynamic",
            "indices": [0, 1, 2],
            "rawInt16Frames": [q2(0), q2(8192), q2(16384)],
        },
        "trans": None,
    }
    p2 = encode_delta_section(d2, h2)
    # u16 qcount + 3*i16 stored z + u16 transCount. No explicit indices.
    assert len(p2) == 10
    assert p2[:2] == struct.pack("<H", 3)
    r2 = decode_delta_section(p2, h2)
    assert r2["indexWidthBytes"] == 1
    assert r2["quat2"]["indices"] == [0, 1, 2]
    assert r2["quat2"]["rawInt16Frames"] == d2["quat2"]["rawInt16Frames"]
    assert r2["trans"] is None

    # T6 3D delta, ushort sparse indices, full quantized translation. Raw size
    # and quantized frames must survive exactly through the compiled subsection.
    h3 = {"numframes": 300, "framerate": 30.0, "frequency": 0.1,
          "bDelta": False, "bDelta3D": True}
    d3 = {
        "quat": {
            "mode": "dynamic",
            "indices": [0, 100, 300],
            "rawInt16Frames": [q3(0,0,0), q3(3000,-2000,4000), q3(6000,1000,-5000)],
        },
        "trans": {
            "mode": "dynamic",
            "smallTrans": False,
            "indices": [0, 100, 300],
            "mins": [-10.0, 2.0, 7.0],
            "rawSize": [65535.0, 32767.5, 16383.75],
            "quantizedFrames": [[0,0,0], [12345,23456,34567], [65535,32768,11111]],
        },
    }
    p3a = encode_delta_section(d3, h3)
    p3b = encode_delta_section(d3, h3)
    assert p3a == p3b
    r3 = decode_delta_section(p3a, h3)
    assert r3["indexWidthBytes"] == 2
    assert r3["quat"]["indices"] == [0, 100, 300]
    assert r3["quat"]["rawInt16Frames"] == d3["quat"]["rawInt16Frames"]
    assert r3["trans"]["indices"] == [0, 100, 300]
    assert r3["trans"]["quantizedFrames"] == d3["trans"]["quantizedFrames"]
    assert struct.pack("<3f", *r3["trans"]["rawSize"]) == struct.pack("<3f", *d3["trans"]["rawSize"])
    assert struct.pack("<3f", *r3["trans"]["mins"]) == struct.pack("<3f", *d3["trans"]["mins"])

    # Small translation uses 3 bytes per frame and preserves raw quantization.
    ds = {
        "trans": {
            "mode": "dynamic", "smallTrans": True,
            "indices": [0, 1, 2],
            "mins": [1.0, 2.0, 3.0], "rawSize": [255.0, 127.5, 63.75],
            "quantizedFrames": [[0,0,0], [1,128,254], [255,255,255]],
        }
    }
    rs = decode_delta_section(encode_delta_section(ds, h2), h2)
    assert rs["trans"]["smallTrans"] is True
    assert rs["trans"]["quantizedFrames"] == ds["trans"]["quantizedFrames"]

    # Constant branches.
    dc2 = {
        "quat2": {"mode": "constant", "rawInt16": q2(5000)},
        "trans": {"mode": "constant", "value": [1.25, -2.5, 9.0]},
    }
    rc2 = decode_delta_section(encode_delta_section(dc2, h2), h2)
    assert rc2["quat2"]["mode"] == "constant"
    assert rc2["quat2"]["rawInt16"] == dc2["quat2"]["rawInt16"]
    assert struct.pack("<3f", *rc2["trans"]["value"]) == struct.pack("<3f", *dc2["trans"]["value"])

    dc3 = {
        "quat": {"mode": "constant", "rawInt16": q3(1000, -2000, 3000)},
        "trans": None,
    }
    rc3 = decode_delta_section(encode_delta_section(dc3, h3), h3)
    assert rc3["quat"]["rawInt16"] == dc3["quat"]["rawInt16"]

    # Sparse native domains are allowed only when they still cover frame 0..N.
    must_fail(
        lambda: encode_delta_section({"quat": {"mode": "dynamic", "indices": [10,300],
                                                "rawInt16Frames": [q3(0,0,0), q3(1,2,3)]}}, h3),
        "must span 0..300",
    )

    # A first frame whose omitted component is negative but whose stored prefix
    # is nonzero is not generally equivalent to the compiled positive-sqrt
    # reconstruction. Fail closed rather than silently altering rotation.
    badq = [12000, -omitted(12000)]
    must_fail(
        lambda: encode_delta_section({"quat2": {"mode": "constant", "rawInt16": badq}}, h2),
        "not representable",
    )

    must_fail(
        lambda: encode_delta_section({"quat": {"mode": "constant", "rawInt16": q3(0,0,0)}}, h2),
        "quat3D present but header.bDelta3D is false",
    )
    must_fail(
        lambda: encode_delta_section({"quat2": {"mode": "constant", "rawInt16": q2(0)}}, h3),
        "quat2 present while header.bDelta3D selects 3D delta",
    )

    print("PASS t6_compiled_xanim_v19_delta_v1 non-empty delta codec regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
