#!/usr/bin/env python3
"""Compare retained Nuketown GfxWorldSun angles with GfxWorldFog sun-fog angles.

This deliberately stays at the authored retail-byte boundary. It decodes the
84-byte GfxWorldSun immediately preceding fogTransitionTime/initWorldFog and the
64-byte GfxWorldFog already source-closed by the fog proof. The report records
wrapped pitch/yaw deltas but does not infer a runtime vector convention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

FORMAT = "t6-nuketown-init-world-sun-fog-relation-v1"
MAP = "mp_nuketown_2020"
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
GFXWORLD_START = 63_150_420
SUN_PARSE_OFFSET = 40
SUN_PARSE_NAME_BYTES = 64
SUN_BYTES = 84
FOG_TRANSITION_BYTES = 4
SUN_OFFSET = GFXWORLD_START + SUN_PARSE_OFFSET + SUN_PARSE_NAME_BYTES
FOG_OFFSET = SUN_OFFSET + SUN_BYTES + FOG_TRANSITION_BYTES


def wrap180(value: float) -> float:
    value = math.fmod(value + 180.0, 360.0)
    if value < 0.0:
        value += 360.0
    return value - 180.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.expanded.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPANDED_SHA256:
        raise SystemExit(f"expanded SHA {actual} != pinned {EXPANDED_SHA256}")

    sun_payload = raw[SUN_OFFSET:SUN_OFFSET + SUN_BYTES]
    if len(sun_payload) != SUN_BYTES:
        raise SystemExit("initial GfxWorldSun range is truncated")
    control = struct.unpack_from("<I", sun_payload, 0)[0]
    angles = list(struct.unpack_from("<3f", sun_payload, 4))
    ambient = list(struct.unpack_from("<4f", sun_payload, 16))
    sun_cd = list(struct.unpack_from("<4f", sun_payload, 32))
    sun_cs = list(struct.unpack_from("<4f", sun_payload, 48))
    sky = list(struct.unpack_from("<4f", sun_payload, 64))
    exposure = struct.unpack_from("<f", sun_payload, 80)[0]
    values = angles + ambient + sun_cd + sun_cs + sky + [exposure]
    if not all(math.isfinite(value) for value in values):
        raise SystemExit("initial GfxWorldSun contains non-finite float")

    fog_payload = raw[FOG_OFFSET:FOG_OFFSET + 64]
    if len(fog_payload) != 64:
        raise SystemExit("initial GfxWorldFog range is truncated")
    fog = struct.unpack("<16f", fog_payload)
    fog_pitch = float(fog[4])
    fog_yaw = float(fog[5])

    # T6 vec3 Euler storage convention is conventionally [pitch,yaw,roll], but
    # this report does not rely on that convention to derive a vector. It only
    # records the serialized lanes and their wrapped numeric relation.
    pitch_delta = wrap180(fog_pitch - float(angles[0]))
    yaw_delta = wrap180(fog_yaw - float(angles[1]))

    doc = {
        "format": FORMAT,
        "map": MAP,
        "source": {"sha256": EXPANDED_SHA256, "bytes": len(raw)},
        "layout": {
            "gfxWorldStart": GFXWORLD_START,
            "sunParseOffset": SUN_PARSE_OFFSET,
            "initWorldSunAbsoluteOffset": SUN_OFFSET,
            "initWorldSunBytes": SUN_BYTES,
            "initWorldSunSha256": hashlib.sha256(sun_payload).hexdigest(),
            "initWorldFogAbsoluteOffset": FOG_OFFSET,
            "initWorldFogSha256": hashlib.sha256(fog_payload).hexdigest(),
        },
        "worldSun": {
            "control": control,
            "anglesRaw": angles,
            "ambientColor": ambient,
            "sunCd": sun_cd,
            "sunCs": sun_cs,
            "skyColor": sky,
            "exposure": exposure,
        },
        "sunFog": {
            "pitch": fog_pitch,
            "yaw": fog_yaw,
        },
        "numericRelation": {
            "fogPitchMinusWorldSunLane0WrappedDegrees": pitch_delta,
            "fogYawMinusWorldSunLane1WrappedDegrees": yaw_delta,
            "pitchNumericallyEqual": abs(pitch_delta) <= 1.0e-5,
            "yawNumericallyEqual": abs(yaw_delta) <= 1.0e-5,
        },
        "proofBoundary": (
            "Direct decode of adjacent GfxWorld.sunParse.initWorldSun and initWorldFog from the SHA-pinned expanded retail Nuketown FastFile. "
            "The relation section compares serialized numeric angle lanes only. It does not infer AngleVectors handedness, negate pitch, swap axes, or claim the fog direction is sun-relative."
        ),
    }
    stable = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    doc["proofSha256"] = hashlib.sha256(stable).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "worldSunAngles": angles,
        "sunFogPitchYaw": [fog_pitch, fog_yaw],
        "relation": doc["numericRelation"],
        "proofSha256": doc["proofSha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
