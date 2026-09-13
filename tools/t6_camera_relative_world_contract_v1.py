#!/usr/bin/env python3
"""Prove the camera-relative contract required by recovered T6 world shaders.

This joins three independent facts without inventing renderer behavior:
1. recovered retail T6 shaders consume worldMatrix output directly as a view
   vector / fog-distance vector;
2. the T6 renderer state ABI contains an aligned eyeOffset and its rigid-model
   world-matrix builder explicitly accepts that eyeOffset;
3. the immediately preceding Treyarch Black Ops renderer implementation builds
   world/model matrices with origin - eyeOffset.

The output deliberately does not claim that every T5 implementation detail is
identical in T6. It closes the narrower invariant needed by Rust-test: the
vector observed by these T6 shader families must be eye-relative, so an
absolute worldMatrix is not an exact replay contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FORMAT = "t6-camera-relative-world-contract-v1"
LPROBE_FORMAT = "t6-retail-lprobe-lit-semantics-v1"
T6_COMMIT = "a64812d21946baf710cec7fa26b98ad0d193903b"
T5_COMMIT = "2a7785269d2f969ecc1ce2931679a8a39536f5dd"


class ProofError(RuntimeError):
    pass


def read(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="strict")
    if not text:
        raise ProofError(f"{path}: empty source")
    return text


def require(text: str, pattern: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        raise ProofError(f"missing {label}: {pattern}")
    return match.group(0)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(args: argparse.Namespace) -> dict[str, Any]:
    lprobe = json.loads(args.lprobe.read_text(encoding="utf-8"))
    if lprobe.get("format") != LPROBE_FORMAT:
        raise ProofError(f"unexpected lprobe format {lprobe.get('format')!r}")
    reflection = lprobe.get("sharedSemantics", {}).get("reflectionProbe", {})
    if reflection.get("viewVector") != "V = normalize(vsWorldPosition.xyz)":
        raise ProofError("retail T6 lprobe reflection view-vector contract drift")

    fade = read(args.fade_tool)
    require(
        fade,
        r'"P":\s*"float3\(oWorldX,oWorldY,oWorldZ\) produced by cb3 worldMatrix from POSITION"',
        "multiply-decal worldMatrix P notation",
    )
    require(fade, r'"R":\s*"length\(P\)"', "multiply-decal fog distance from P")
    require(fade, r'dot\(D, normalize\(P\)\)', "multiply-decal directional fog from P")

    t6_types = read(args.t6_types)
    t6_xmodel = read(args.t6_xmodel)
    t5_static = read(args.t5_static)
    t5_state = read(args.t5_state)

    require(
        t6_types,
        r'__declspec\(align\(16\)\)\s+vec4_t\s+eyeOffset\s*;',
        "T6 GfxCmdBufSourceState eyeOffset",
    )
    require(
        t6_xmodel,
        r'R_GetWorldMatrixForModelSurf\s*\(\s*const GfxModelRigidSurface \*modelSurf,\s*const __m128 eyeOffset,\s*vector4 \*worldMat',
        "T6 rigid-model world-matrix eyeOffset parameter",
    )
    require(
        t5_static,
        r'origin\[0\]\s*=\s*smodelDrawInst->placement\.origin\[0\]\s*-\s*source->eyeOffset\[0\]\s*;.*?origin\[1\].*?source->eyeOffset\[1\].*?origin\[2\].*?source->eyeOffset\[2\]',
        "T5 static-model origin minus eyeOffset",
    )
    require(
        t5_state,
        r'R_MatrixIdentity44\(.*?worldMatrix.*?\).*?worldMatrix->matrices\.matrix\[0\]\.m\[3\]\[0\].*?source->eyeOffset\[0\].*?worldMatrix->matrices\.matrix\[0\]\.m\[3\]\[1\].*?source->eyeOffset\[1\]',
        "T5 3D identity world matrix eyeOffset subtraction",
    )

    sources = {
        "t6AllTypes": {"commit": T6_COMMIT, "sha256": sha(args.t6_types)},
        "t6DrawXModel": {"commit": T6_COMMIT, "sha256": sha(args.t6_xmodel)},
        "t5DrawStaticModel": {"commit": T5_COMMIT, "sha256": sha(args.t5_static)},
        "t5StateUtils": {"commit": T5_COMMIT, "sha256": sha(args.t5_state)},
        "t6LprobeSemantics": {"sha256": sha(args.lprobe)},
        "t6MultiplyDecalFadeTool": {"sha256": sha(args.fade_tool)},
    }

    return {
        "format": FORMAT,
        "producer": "tools/t6_camera_relative_world_contract_v1.py",
        "shaderRequirements": {
            "lprobeReflectionViewVector": reflection["viewVector"],
            "multiplyDecalPositionVector": "P = cb3 worldMatrix * POSITION",
            "multiplyDecalFogDistance": "R = length(P)",
            "multiplyDecalSunDirection": "dot(sunFogDir, normalize(P))",
        },
        "engineEvidence": {
            "t6HasEyeOffset": True,
            "t6ModelWorldBuilderAcceptsEyeOffset": True,
            "t5StaticModelSubtractsEyeOffset": True,
            "t5WorldIdentitySubtractsEyeOffset": True,
        },
        "conclusion": (
            "For the recovered T6 shader families, worldMatrix output is an eye-relative renderer vector. "
            "Feeding absolute map-space position into cb3 worldMatrix is outside the proved retail contract."
        ),
        "rustReplayRequirement": (
            "Rust-test may preserve its normalized axis/unit domain by subtracting the final render-eye from worldMatrix output and right-adjusting viewProjection so clip coordinates remain algebraically identical."
        ),
        "proofBoundary": (
            "This proof closes camera-relative worldMatrix semantics, not the complete T6 R_Set3D/R_SetFrameFog implementation. "
            "The T5 source is used only to identify the inherited Treyarch eyeOffset mechanism already exposed by the T6 ABI; no T5 fog constants are promoted here."
        ),
        "sources": sources,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lprobe", type=Path, required=True)
    ap.add_argument("--fade-tool", type=Path, required=True)
    ap.add_argument("--t6-types", type=Path, required=True)
    ap.add_argument("--t6-xmodel", type=Path, required=True)
    ap.add_argument("--t5-static", type=Path, required=True)
    ap.add_argument("--t5-state", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
