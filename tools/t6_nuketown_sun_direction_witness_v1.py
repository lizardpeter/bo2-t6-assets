#!/usr/bin/env python3
"""Cross-check Nuketown authored sun angles against the native ComWorld sun dir.

This proof uses two independently serialized T6 assets from the same SHA-pinned
retail FastFile:

* GfxWorld.sunParse.initWorldSun.angles (pitch/yaw/roll);
* the unique type-1 ComPrimaryLight.dir from ComWorld.

It evaluates the predecessor/common-COD AngleVectors forward equation and its
negation. A match to the native T6 ComPrimaryLight direction establishes the
T6 world-sun angle/sign convention without relying on the missing OpenT6
AngleVectors function body. The nearby GfxWorldFog sunFogPitch/Yaw values are
reported as a separate numeric relation only; this tool does not by itself
claim the T6 fog path invokes AngleVectors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import t6_nuketown_comworld_primary_lights_v1 as comworld

FORMAT = "t6-nuketown-sun-direction-witness-v1"
MAP = "mp_nuketown_2020"
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
GFXWORLD_START = 63_150_420
SUN_PARSE_OFFSET = 40
SUN_PARSE_NAME_BYTES = 64
SUN_BYTES = 84
SUN_OFFSET = GFXWORLD_START + SUN_PARSE_OFFSET + SUN_PARSE_NAME_BYTES
FOG_OFFSET = SUN_OFFSET + SUN_BYTES + 4


def forward(angles: list[float]) -> list[float]:
    pitch = math.radians(float(angles[0]))
    yaw = math.radians(float(angles[1]))
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    cy = math.cos(yaw)
    sy = math.sin(yaw)
    return [cp * cy, cp * sy, -sp]


def neg(values: list[float]) -> list[float]:
    return [-float(v) for v in values]


def error(a: list[float], b: list[float]) -> dict:
    lane = [abs(float(x) - float(y)) for x, y in zip(a, b)]
    return {
        "maxAbs": max(lane),
        "laneAbs": lane,
        "length": math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b))),
    }


def wrap180(value: float) -> float:
    value = math.fmod(float(value) + 180.0, 360.0)
    if value < 0.0:
        value += 360.0
    return value - 180.0


def build(expanded: Path) -> dict:
    raw = expanded.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPANDED_SHA256:
        raise RuntimeError(f"expanded SHA {digest} != pinned {EXPANDED_SHA256}")

    cw = comworld.build(expanded)
    lights = cw["primaryLights"]
    directional = [row for row in lights if int(row["type"]) == 1]
    if len(directional) != 1:
        raise RuntimeError(f"expected one native type-1 primary light, got {len(directional)}")
    sun_light = directional[0]
    native_dir = [float(v) for v in sun_light["dir"]]
    native_len = math.sqrt(sum(v * v for v in native_dir))
    if abs(native_len - 1.0) > 1.0e-5:
        raise RuntimeError(f"native type-1 primary-light direction is not unit length: {native_len}")

    world_angles = list(struct.unpack_from("<3f", raw, SUN_OFFSET + 4))
    fog = struct.unpack_from("<16f", raw, FOG_OFFSET)
    fog_angles = [float(fog[4]), float(fog[5]), 0.0]

    world_forward = forward(world_angles)
    world_forward_neg = neg(world_forward)
    fog_forward = forward(fog_angles)
    fog_forward_neg = neg(fog_forward)
    world_err = error(native_dir, world_forward)
    world_neg_err = error(native_dir, world_forward_neg)
    if not world_err["maxAbs"] < 2.0e-6:
        raise RuntimeError(
            f"native T6 type-1 sun dir does not match AngleVectors-forward world-sun convention: {world_err}"
        )
    if not world_neg_err["maxAbs"] > 1.0:
        raise RuntimeError("negated world-sun direction unexpectedly also appears plausible")

    doc = {
        "format": FORMAT,
        "map": MAP,
        "source": {"bytes": len(raw), "sha256": digest},
        "worldSun": {
            "angles": world_angles,
            "angleVectorsForward": world_forward,
            "angleVectorsForwardNegated": world_forward_neg,
        },
        "nativeDirectionalPrimaryLight": {
            "index": int(sun_light["index"]),
            "type": int(sun_light["type"]),
            "defName": sun_light.get("defName"),
            "dir": native_dir,
            "length": native_len,
        },
        "worldSunDirectionMatch": {
            "forwardError": world_err,
            "negatedForwardError": world_neg_err,
            "forwardConventionMatches": True,
        },
        "sunFog": {
            "angles": fog_angles,
            "angleVectorsForward": fog_forward,
            "angleVectorsForwardNegated": fog_forward_neg,
            "fogPitchMinusWorldSunPitchWrappedDegrees": wrap180(fog_angles[0] - world_angles[0]),
            "fogYawMinusWorldSunYawWrappedDegrees": wrap180(fog_angles[1] - world_angles[1]),
            "forwardDifferenceFromNativeWorldSunDir": error(native_dir, fog_forward),
        },
        "proofBoundary": (
            "Direct retail-byte proof that T6 Nuketown's serialized GfxWorld sun angles use the common Treyarch/AngleVectors forward sign convention because that equation reproduces the independently serialized unique type-1 ComPrimaryLight.dir. The fog pitch/yaw and their candidate forward vector are reported but this proof does not claim that the T6 fog runtime invokes the same conversion."
        ),
    }
    stable = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    doc["proofSha256"] = hashlib.sha256(stable).hexdigest()
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.expanded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "worldSun": doc["worldSun"],
        "nativeDirectionalPrimaryLight": doc["nativeDirectionalPrimaryLight"],
        "worldSunDirectionMatch": doc["worldSunDirectionMatch"],
        "sunFog": doc["sunFog"],
        "proofSha256": doc["proofSha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
