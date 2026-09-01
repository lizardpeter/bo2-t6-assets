#!/usr/bin/env python3
"""Extend the retail T6 XAnim delta proof through quaternion application.

v1 closes deltaPart layout, 2D/3D evaluators, byte/ushort index dispatch,
translation interpolation, and loop-range composition. v2 additionally pins the
retail code that consumes those interpolated rotation values:

- planar quat2 relative-delta composition removes pair magnitude explicitly via
  2/(a^2+b^2), so only the normalized component-linear direction/angle matters;
- full bDelta3D values are scaled by exactly 1/32767, accumulated by weight, and
  the downstream animation-tree delta path computes x^2+y^2+z^2+w^2 and an
  inverse-square-root normalization before writing the quaternion back.

This closes the normalization premise used by the exact glTF CUBICSPLINE delta
encoding: T6's stored quaternion components are interpolated linearly, while the
applied rotation depends on their normalized direction rather than glTF SLERP.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from t6_retail_xanim_delta_proof_v1 import (
    EXPECTED_SHA256,
    PE,
    ProofError,
    _expect,
    _expect_target,
    prove as prove_v1,
)


def prove(path: Path) -> dict:
    doc = prove_v1(path)
    pe = PE(path)

    # Planar relative-delta application. The retail code squares the two delta
    # pair components, sums them, loads 2.0f, divides by the norm squared, then
    # uses that scale in the 2D rotation composition. Scaling both components by
    # any non-zero common factor therefore leaves the applied rotation unchanged.
    _expect(pe, 0x8D74B9, bytes.fromhex("0f28ca"), "quat2 component copy")
    _expect(pe, 0x8D74BC, bytes.fromhex("f30f59dd"), "quat2 component0 square")
    _expect(pe, 0x8D74C0, bytes.fromhex("f30f59ca"), "quat2 component1 square")
    _expect(pe, 0x8D74C4, bytes.fromhex("f30f58cb"), "quat2 norm-squared sum")
    if pe.f32(0xBF607C) != 2.0:
        raise ProofError("quat2 normalization numerator is not 2.0f")
    _expect(
        pe,
        0x8D74E2,
        bytes.fromhex("f30f10357c60bf00f30f5ef1"),
        "quat2 2.0/normSquared",
    )
    if pe.f32(0xBEE720) != 1.0:
        raise ProofError("quat2 rotation identity constant is not 1.0f")
    _expect(
        pe,
        0x8D74F6,
        bytes.fromhex(
            "0f28c6f30f59c3f30f59d5f30f59d6"
            "f30f107508f30f5cc8f30f59cff30f59fa"
            "0f28dcf30f59da0f28d4f30f59d0"
            "f30f58faf30f58cbf30f5ce7"
        ),
        "quat2 magnitude-invariant rotation composition",
    )

    # Full-quaternion weighted accumulator. The evaluator is the v1-proven 3D
    # path and every component is multiplied by the exact int16 unit scale before
    # entering the accumulator.
    _expect_target(pe, 0x8D8F6C, 0x667940, "3D delta evaluator dispatch")
    expected_scale = 1.0 / 32767.0
    actual_scale = pe.f32(0xBC48BC)
    if not math.isclose(actual_scale, expected_scale, rel_tol=2e-8, abs_tol=1e-12):
        raise ProofError(
            f"3D quaternion int16 scale {actual_scale!r} != 1/32767 {expected_scale!r}"
        )
    _expect(
        pe,
        0x8D8F76,
        bytes.fromhex("0f28c1f30f5905bc48bc00"),
        "3D weight times 1/32767 scale",
    )
    _expect(
        pe,
        0x8D8F81,
        bytes.fromhex(
            "0f28d0f30f59542410f30f5816f30f1116"
            "0f28d0f30f59542414f30f585604f30f115604"
        ),
        "3D accumulated x/y components",
    )
    _expect(
        pe,
        0x8D8FA5,
        bytes.fromhex(
            "0f28d0f30f5944241cf30f59542418"
            "f30f585608f30f115608f30f58460cf30f11460c"
        ),
        "3D accumulated z/w components",
    )

    # Downstream animation-tree delta normalization. This code computes the full
    # quaternion norm squared and runs an inverse-square-root Newton step using
    # the classic 0x5f3759df seed, then multiplies x/y/z/w by the resulting common
    # scalar before storing the quaternion back. A later weight factor may be
    # folded into that common scalar; the quaternion direction is normalized.
    _expect(
        pe,
        0x8D9AE7,
        bytes.fromhex(
            "f30f105304f30f101bf30f106308f30f106b0c"
            "0f28c3f30f59c30f28caf30f59ca"
            "f30f58c10f28ccf30f59ccf30f58c1"
            "0f28cdf30f59cdf30f58c1"
        ),
        "3D quaternion norm-squared accumulation",
    )
    _expect(pe, 0x8D9B22, bytes.fromhex("0f2ec79ff6c444"), "3D nonzero norm gate")
    if pe.f32(0xBB40CC) != 1.5 or pe.f32(0xC12804) != 0.5:
        raise ProofError("inverse-sqrt Newton constants mismatch")
    _expect(
        pe,
        0x8D9B2B,
        bytes.fromhex(
            "f30f100dcc40bb00f30f1144243c8b4c243c"
            "f30f59050428c100d1f9badf59375f2bd1"
            "8954243cf30f1074243cf30f59c6f30f59c6"
            "f30f5cc8f30f59ce"
        ),
        "3D inverse-sqrt normalization step",
    )
    _expect(
        pe,
        0x8D9B68,
        bytes.fromhex(
            "f30f10742440f30f59cef30f59d9f30f59d1"
            "f30f59e1f30f59e9f30f111bf30f115304"
            "f30f116308f30f116b0c"
        ),
        "3D normalized quaternion writeback",
    )

    doc["format"] = "t6-retail-xanim-delta-proof-v2"
    doc["extends"] = "manifests/xanim/T6_RETAIL_XANIM_DELTA_PROOF_V1.json"
    doc["quaternionApplication"] = {
        "quat2": {
            "consumerVaHex": "0x008d72d0",
            "normalizationBlockVaHex": "0x008d74b9",
            "semantics": (
                "relative-delta pair magnitude is removed explicitly by a 2/(a^2+b^2) "
                "rotation construction; applied planar rotation depends only on normalized "
                "component-linear pair direction"
            ),
            "retailByteProven": True,
        },
        "quat3D": {
            "weightedAccumulatorVaHex": "0x008d8f10",
            "normalizationBlockVaHex": "0x008d9ae7",
            "int16Scale": actual_scale,
            "semantics": (
                "XAnim_CalcDelta3DForTime output is converted by 1/32767 and accumulated "
                "component-wise by weight; the downstream delta-tree path computes the full "
                "quat norm and inverse-square-root normalizes x/y/z/w before writeback"
            ),
            "retailByteProven": True,
        },
        "gltfConsequence": (
            "For delta rotation, core glTF LINEAR quaternion interpolation (SLERP) is not the "
            "native path. A glTF encoding is exact only when its normalized result follows "
            "normalize(componentLerp(storedT6Quaternion))."
        ),
    }
    doc["validation"].update({
        "quat2MagnitudeInvariantApplicationMatched": True,
        "quat3DInt16UnitScaleMatched": True,
        "quat3DDownstreamNormalizationMatched": True,
    })
    doc["proofBoundary"] = (
        "Direct static proof for the pinned retail PC executable. v2 extends v1 through the "
        "rotation-application boundary: planar delta magnitude is explicitly normalized out, "
        "and full 3D delta quaternion components are normalized in the downstream animation-tree "
        "delta path after weighted accumulation. Ordinary animated root-bone translation remains "
        "a separate unresolved model/bind-pose composition path."
    )
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    doc = prove(args.exe)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
