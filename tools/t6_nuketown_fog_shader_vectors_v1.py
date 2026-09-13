#!/usr/bin/env python3
"""Derive the T6 Nuketown fog shader vectors from the exact authored record.

This verifier joins three independently recovered boundaries:
  1. the SHA-pinned GfxWorld.sunParse.initWorldFog float32 record;
  2. the exact multiply-decal VS symbolic DAG and its cb0[26..31] read lanes;
  3. the retained Treyarch fog-setting ABI inherited by T6.

It deliberately distinguishes exact T6 shader algebra from two remaining
renderer-lineage assumptions: maxDensity=100*density and the standard Treyarch
AngleVectors pitch/yaw forward convention. Those assumptions are emitted in the
result and are not silently promoted to direct T6 binary proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-fog-shader-vectors-v1"
INPUT_FORMAT = "t6-nuketown-init-world-fog-v1"
MAP = "mp_nuketown_2020"
PAYLOAD_SHA256 = "5e20b262d0e044f587e019b10790c977c926ec7bf5482e15298091eedacede83"
MAX_DENSITY_MULTIPLIER = 100.0
LN2 = math.log(2.0)


class ProofError(RuntimeError):
    pass


def req_finite(fields: dict[str, Any], name: str) -> float:
    value = float(fields[name])
    if not math.isfinite(value):
        raise ProofError(f"{name} is not finite")
    return value


def derive(fields: dict[str, Any], eye_z: float) -> dict[str, list[float]]:
    base_dist = req_finite(fields, "baseDist")
    half_dist = req_finite(fields, "halfDist")
    base_height = req_finite(fields, "baseHeight")
    half_height = req_finite(fields, "halfHeight")
    if half_dist <= 0.0 or half_height <= 0.0:
        raise ProofError("halfDist and halfHeight must be positive")
    if not math.isfinite(eye_z):
        raise ProofError("eye Z is not finite")

    density = 1.0 / half_dist
    height_density = 1.0 / half_height
    max_density = MAX_DENSITY_MULTIPLIER * density
    viewer_z = eye_z - base_height
    fog_x = math.log(density / max_density) - height_density * viewer_z * LN2
    fog_consts = [
        fog_x,
        -max_density,
        density * base_dist,
        -height_density * LN2,
    ]
    fog_consts2 = [math.exp(fog_x) if fog_x < 0.0 else fog_x + 1.0, 0.0, 0.0, 0.0]

    pitch = math.radians(req_finite(fields, "sunFogPitch"))
    yaw = math.radians(req_finite(fields, "sunFogYaw"))
    cp = math.cos(pitch)
    sun_fog_dir = [
        cp * math.cos(yaw),
        cp * math.sin(yaw),
        -math.sin(pitch),
        0.0,
    ]

    start_cos = math.cos(math.radians(req_finite(fields, "sunFogInner")))
    end_cos = math.cos(math.radians(req_finite(fields, "sunFogOuter")))
    delta = start_cos - end_cos
    slope = 1.0 / delta if delta != 0.0 else 1.0e7
    sun_fog = [-end_cos * slope, slope, 0.0, 0.0]

    slots = {
        "fogColor": [
            req_finite(fields, "fogColorR"),
            req_finite(fields, "fogColorG"),
            req_finite(fields, "fogColorB"),
            req_finite(fields, "fogOpacity"),
        ],
        "fogConsts": fog_consts,
        "fogConsts2": fog_consts2,
        "sunFogDir": sun_fog_dir,
        "sunFogColor": [
            req_finite(fields, "sunFogColorR"),
            req_finite(fields, "sunFogColorG"),
            req_finite(fields, "sunFogColorB"),
            req_finite(fields, "sunFogOpacity"),
        ],
        "sunFog": sun_fog,
    }
    if not all(math.isfinite(x) for vec in slots.values() for x in vec):
        raise ProofError("derived vector contains non-finite value")
    return slots


def exp2(x: float) -> float:
    return 2.0 ** x


def validate_shader_invariants(fields: dict[str, Any], slots: dict[str, list[float]]) -> dict[str, float]:
    """Validate the exact horizontal/base-height specialization of the T6 VS.

    With eye at baseHeight and P.z=0, the exact DXBC branch uses H=fogConsts2.x.
    The shader transmission is exp2(H*F.y*R + F.z). The authored names require
    R=baseDist to be the clear start and R=baseDist+halfDist to be half
    transmission. These two constraints distinguish T6 F.y=-maxDensity from
    the predecessor implementation that multiplied F.y by ln(2).
    """
    base_dist = float(fields["baseDist"])
    half_dist = float(fields["halfDist"])
    h = slots["fogConsts2"][0]
    f = slots["fogConsts"]
    exponent_start = h * f[1] * base_dist + f[2]
    exponent_half = h * f[1] * (base_dist + half_dist) + f[2]
    t_start = min(exp2(exponent_start), 1.0)
    t_half = min(exp2(exponent_half), 1.0)
    if abs(exponent_start) > 2.0e-6 or abs(t_start - 1.0) > 2.0e-6:
        raise ProofError(f"baseDist invariant failed: exponent={exponent_start} T={t_start}")
    if abs(exponent_half + 1.0) > 2.0e-6 or abs(t_half - 0.5) > 2.0e-6:
        raise ProofError(f"halfDist invariant failed: exponent={exponent_half} T={t_half}")

    d = slots["sunFogDir"]
    direction_len = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
    if abs(direction_len - 1.0) > 2.0e-7 or d[3] != 0.0:
        raise ProofError(f"sun fog direction is not unit xyz/zero w: {d}")

    if slots["fogColor"][3] != float(fields["fogOpacity"]):
        raise ProofError("fogOpacity did not reach fogColor.w unchanged")
    if slots["sunFogColor"][3] != float(fields["sunFogOpacity"]):
        raise ProofError("sunFogOpacity did not reach sunFogColor.w unchanged")
    return {
        "baseDistExponent": exponent_start,
        "baseDistTransmission": t_start,
        "halfDistExponent": exponent_half,
        "halfDistTransmission": t_half,
        "sunFogDirectionLength": direction_len,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fog", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    source = json.loads(a.fog.read_text(encoding="utf-8"))
    if source.get("format") != INPUT_FORMAT or source.get("map") != MAP:
        raise ProofError("unexpected initial-fog input identity")
    if source.get("layout", {}).get("payloadSha256") != PAYLOAD_SHA256:
        raise ProofError("initial GfxWorldFog payload SHA drift")
    fields = source.get("fields")
    if not isinstance(fields, dict):
        raise ProofError("initial-fog fields are missing")

    # Use baseHeight as the canonical numeric checkpoint because it collapses
    # the height integral to a direct half-distance transmission test while the
    # runtime formula remains parameterized by source-space eye Z.
    eye_z = req_finite(fields, "baseHeight")
    slots = derive(fields, eye_z)
    invariants = validate_shader_invariants(fields, slots)
    formula = {
        "density": "1 / halfDist",
        "heightDensity": "1 / halfHeight",
        "maxDensity": "100 * density  [Treyarch renderer-lineage assumption]",
        "viewerZ": "sourceEyeZ - baseHeight",
        "fogConsts.x": "ln(density/maxDensity) - heightDensity*viewerZ*ln(2)",
        "fogConsts.y": "-maxDensity  [forced by exact T6 DXBC + halfDist invariant]",
        "fogConsts.z": "density*baseDist",
        "fogConsts.w": "-heightDensity*ln(2)",
        "fogConsts2.x": "x < 0 ? exp(x) : x+1",
        "sunFogDir": "AngleVectorsForward(pitch,yaw,0) [Treyarch convention assumption]",
        "sunFog.xy": "(-cos(outer)/(cos(inner)-cos(outer)), 1/(cos(inner)-cos(outer)))",
    }
    assumptions = [
        {
            "id": "MAX_DENSITY_100X",
            "status": "LINEAGE_BACKED_NOT_DIRECT_T6_BODY",
            "claim": "R_SetFogFromServer initializes maxDensity = 100*density",
        },
        {
            "id": "SUN_DIRECTION_ANGLEVECTORS",
            "status": "LINEAGE_BACKED_NOT_DIRECT_T6_BODY",
            "claim": "sunFogPitch/sunFogYaw are converted with Treyarch AngleVectors forward convention",
        },
    ]
    checkpoint = {
        "sourceEyeZ": eye_z,
        "slots": slots,
        "invariants": invariants,
    }
    doc = {
        "format": FORMAT,
        "map": MAP,
        "inputPayloadSha256": PAYLOAD_SHA256,
        "formula": formula,
        "assumptions": assumptions,
        "baseHeightCheckpoint": checkpoint,
        "proofBoundary": (
            "The authored 64-byte GfxWorldFog input and the consuming T6 shader equation/read lanes are exact. "
            "The horizontal base-height specialization proves fogConsts.y=-maxDensity because baseDist must yield transmission 1 and baseDist+halfDist must yield transmission 0.5 under the exact SM4 EXP2 instruction. "
            "maxDensity=100*density and pitch/yaw-to-direction remain explicitly lineage-backed until a T6 R_SetFogFromServer/R_SetFrameFog body or equivalent binary trace closes them."
        ),
    }
    doc["checkpointSha256"] = hashlib.sha256(
        json.dumps(checkpoint, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(checkpoint, indent=2, sort_keys=True))
    print("checkpointSha256", doc["checkpointSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
