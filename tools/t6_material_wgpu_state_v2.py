#!/usr/bin/env python3
"""Compile T6 material render-state contracts into retail-grounded wgpu state v2.

V2 replaces v1's polygon-offset blocker with direct evidence from the pinned
retail T6 PC executable (SHA-256
11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1):

  offset0        DepthBias=0,    SlopeScaledDepthBias=0
  offset1        DepthBias=256,  SlopeScaledDepthBias=1
  offset2        DepthBias=512,  SlopeScaledDepthBias=2
  offsetShadowmap = -sm_polygonOffsetBias, -sm_polygonOffsetScale

Retail defaults are bias=8192 and scale=2.0; callers can override them to match
live DVAR state. The same retail builder hardcodes FrontCounterClockwise=FALSE,
so native T6 front-face winding is clockwise.

Depth/stencil retail proof also closes ordinary material masks at read=0xff,
write=0xff. Stencil reference remains dynamic draw state, exactly as D3D11's
OMSetDepthStencilState and wgpu RenderPass::set_stencil_reference model it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class T6WgpuStateV2Error(RuntimeError):
    pass


RETAIL_EXE_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
RETAIL_PROOF = "manifests/render/T6_RETAIL_D3D11_STATE_PROOF_V1.json"
DEFAULT_SHADOWMAP_BIAS = 8192
DEFAULT_SHADOWMAP_SCALE = 2.0

BLEND_FACTOR = {
    "zero": "Zero",
    "one": "One",
    "src": "Src",
    "one_minus_src": "OneMinusSrc",
    "src_alpha": "SrcAlpha",
    "one_minus_src_alpha": "OneMinusSrcAlpha",
    "dst_alpha": "DstAlpha",
    "one_minus_dst_alpha": "OneMinusDstAlpha",
    "dst": "Dst",
    "one_minus_dst": "OneMinusDst",
}
BLEND_OP = {
    "add": "Add",
    "subtract": "Subtract",
    "reverse_subtract": "ReverseSubtract",
    "min": "Min",
    "max": "Max",
}
COMPARE = {
    "never": "Never",
    "less": "Less",
    "equal": "Equal",
    "less_equal": "LessEqual",
    "greater": "Greater",
    "not_equal": "NotEqual",
    "greater_equal": "GreaterEqual",
    "always": "Always",
}
STENCIL_OP = {
    "keep": "Keep",
    "zero": "Zero",
    "replace": "Replace",
    "increment_clamp": "IncrementClamp",
    "decrement_clamp": "DecrementClamp",
    "invert": "Invert",
    "increment_wrap": "IncrementWrap",
    "decrement_wrap": "DecrementWrap",
}
FIXED_POLYGON_BIAS = {
    "offset0": (0, 0.0),
    "offset1": (256, 1.0),
    "offset2": (512, 2.0),
}


def _lookup(table: dict[str, str], value: object, *, field: str, material: str) -> str:
    key = str(value)
    if key not in table:
        raise T6WgpuStateV2Error(f"{material!r}: unsupported {field}={key!r}")
    return table[key]


def _stencil_face(face: dict | None, *, material: str) -> dict:
    if face is None:
        return {
            "compare": "Always",
            "failOp": "Keep",
            "depthFailOp": "Keep",
            "passOp": "Keep",
        }
    return {
        "compare": _lookup(
            COMPARE, face["compare"], field="stencil.compare", material=material
        ),
        "failOp": _lookup(
            STENCIL_OP, face["fail"], field="stencil.fail", material=material
        ),
        "depthFailOp": _lookup(
            STENCIL_OP,
            face["depthFail"],
            field="stencil.depthFail",
            material=material,
        ),
        "passOp": _lookup(
            STENCIL_OP, face["pass"], field="stencil.pass", material=material
        ),
    }


def _bias(mode: str, *, shadowmap_bias: int, shadowmap_scale: float) -> tuple[dict, dict]:
    if mode in FIXED_POLYGON_BIAS:
        constant, slope = FIXED_POLYGON_BIAS[mode]
        return (
            {"constant": constant, "slopeScale": slope, "clamp": 0.0},
            {"mode": mode, "usesRuntimeDvars": False},
        )
    if mode == "offsetShadowmap":
        if not 0 <= shadowmap_bias <= 65536:
            raise T6WgpuStateV2Error(
                f"sm_polygonOffsetBias {shadowmap_bias} outside retail DVAR range 0..65536"
            )
        if not 0.0 <= shadowmap_scale <= 8.0:
            raise T6WgpuStateV2Error(
                f"sm_polygonOffsetScale {shadowmap_scale} outside retail DVAR range 0..8"
            )
        return (
            {
                "constant": -int(shadowmap_bias),
                "slopeScale": -float(shadowmap_scale),
                "clamp": 0.0,
            },
            {
                "mode": mode,
                "usesRuntimeDvars": True,
                "sm_polygonOffsetBias": int(shadowmap_bias),
                "sm_polygonOffsetScale": float(shadowmap_scale),
                "retailDefaultsUsed": (
                    int(shadowmap_bias) == DEFAULT_SHADOWMAP_BIAS
                    and float(shadowmap_scale) == DEFAULT_SHADOWMAP_SCALE
                ),
            },
        )
    raise T6WgpuStateV2Error(f"unknown polygon offset mode {mode!r}")


def compile_state(
    state: dict,
    *,
    material: str,
    shadowmap_bias: int,
    shadowmap_scale: float,
) -> dict:
    blend = state["blend"]
    target: dict = {
        "writeMask": {
            "red": bool(state["colorWriteMask"]["rgb"]),
            "green": bool(state["colorWriteMask"]["rgb"]),
            "blue": bool(state["colorWriteMask"]["rgb"]),
            "alpha": bool(state["colorWriteMask"]["alpha"]),
        },
        "blend": None,
    }
    if blend["enabled"]:
        target["blend"] = {
            "color": {
                "srcFactor": _lookup(
                    BLEND_FACTOR,
                    blend["color"]["srcFactor"],
                    field="blend.color.srcFactor",
                    material=material,
                ),
                "dstFactor": _lookup(
                    BLEND_FACTOR,
                    blend["color"]["dstFactor"],
                    field="blend.color.dstFactor",
                    material=material,
                ),
                "operation": _lookup(
                    BLEND_OP,
                    blend["color"]["operation"],
                    field="blend.color.operation",
                    material=material,
                ),
            },
            "alpha": {
                "srcFactor": _lookup(
                    BLEND_FACTOR,
                    blend["alpha"]["srcFactor"],
                    field="blend.alpha.srcFactor",
                    material=material,
                ),
                "dstFactor": _lookup(
                    BLEND_FACTOR,
                    blend["alpha"]["dstFactor"],
                    field="blend.alpha.dstFactor",
                    material=material,
                ),
                "operation": _lookup(
                    BLEND_OP,
                    blend["alpha"]["operation"],
                    field="blend.alpha.operation",
                    material=material,
                ),
            },
        }

    depth = state["depth"]
    offset_mode = str(state["polygonOffset"]["mode"])
    bias, bias_provenance = _bias(
        offset_mode,
        shadowmap_bias=shadowmap_bias,
        shadowmap_scale=shadowmap_scale,
    )
    stencil_used = state.get("stencilFront") is not None or state.get("stencilBack") is not None
    depth_stencil = {
        # Wgpu has no DepthEnable flag; compare=Always + write=false is the
        # behaviorally equivalent no-depth form when a depth/stencil attachment
        # is still needed for stencil.
        "depthReadEnabled": bool(depth["enabled"]),
        "depthWriteEnabled": bool(depth["writeEnabled"]) if depth["enabled"] else False,
        "depthCompare": (
            _lookup(COMPARE, depth["compare"], field="depth.compare", material=material)
            if depth["enabled"]
            else "Always"
        ),
        "stencil": {
            "front": _stencil_face(state.get("stencilFront"), material=material),
            "back": _stencil_face(state.get("stencilBack"), material=material),
            "readMask": 255,
            "writeMask": 255,
            "reference": {
                "dynamic": True,
                "source": "draw-time stencil reference / RenderPass::set_stencil_reference",
                "requiredWhenStencilUsed": stencil_used,
            },
        },
        "bias": bias,
        "biasProvenance": bias_provenance,
    }

    cull = str(state["cullMode"])
    if cull not in ("none", "front", "back"):
        raise T6WgpuStateV2Error(f"{material!r}: unsupported cull mode {cull!r}")
    polygon_mode = str(state["polygonMode"])
    if polygon_mode not in ("fill", "line"):
        raise T6WgpuStateV2Error(
            f"{material!r}: unsupported polygon mode {polygon_mode!r}"
        )
    required_features: list[str] = []
    if polygon_mode == "line":
        required_features.append("POLYGON_MODE_LINE")

    alpha = state["alphaTest"]
    fragment_discard = None
    if alpha["enabled"]:
        fragment_discard = {
            "source": "fragment-alpha",
            "compare": _lookup(
                COMPARE, alpha["compare"], field="alphaTest.compare", material=material
            ),
            "reference": float(alpha["reference"]),
            "implementation": "shader discard/clip before blend/depth write",
        }

    return {
        "stateIndex": int(state["stateIndex"]),
        "primitive": {
            "frontFace": "Cw",
            "frontFaceProvenance": (
                "retail D3D11_RASTERIZER_DESC.FrontCounterClockwise = FALSE"
            ),
            "cullMode": None if cull == "none" else cull.title(),
            "polygonMode": polygon_mode.title(),
        },
        "fragmentTarget": target,
        "depthStencil": depth_stencil,
        "alphaTestShaderContract": fragment_discard,
        "requiredWgpuFeatures": required_features,
        "pipelineDescriptorExact": True,
        "dynamicDrawStateRequired": ["stencilReference"] if stencil_used else [],
    }


def compile_contract(
    contract: dict,
    *,
    shadowmap_bias: int = DEFAULT_SHADOWMAP_BIAS,
    shadowmap_scale: float = DEFAULT_SHADOWMAP_SCALE,
) -> dict:
    if contract.get("format") != "t6-material-render-state-contract-v1":
        raise T6WgpuStateV2Error(
            f"unsupported state contract {contract.get('format')!r}"
        )
    results: list[dict] = []
    state_count = 0
    dynamic_stencil_count = 0
    for material in contract.get("materials", []):
        name = str(material.get("material") or "")
        states = [
            compile_state(
                state,
                material=name,
                shadowmap_bias=shadowmap_bias,
                shadowmap_scale=shadowmap_scale,
            )
            for state in material.get("states", [])
        ]
        state_count += len(states)
        dynamic_stencil_count += sum(
            int(bool(state["dynamicDrawStateRequired"])) for state in states
        )
        results.append(
            {
                "material": name,
                "layered": bool(material.get("layered")),
                "sortKey": material.get("sortKey"),
                "cameraRegion": material.get("cameraRegion"),
                "stateBitsEntry": material.get("stateBitsEntry"),
                "referencedStateIndices": material.get("referencedStateIndices", []),
                "states": states,
                "requiresLayeredComposition": bool(
                    material.get("requiresLayeredComposition")
                ),
            }
        )
    return {
        "format": "t6-material-wgpu-state-v2",
        "materials": results,
        "stats": {
            "materialCount": len(results),
            "stateCount": state_count,
            "exactPipelineDescriptorStateCount": state_count,
            "stateWithDynamicStencilReferenceCount": dynamic_stencil_count,
            "allPipelineDescriptorsExact": True,
        },
        "retailD3d11Proof": {
            "manifest": RETAIL_PROOF,
            "retailExecutableSha256": RETAIL_EXE_SHA256,
            "shadowmapDvars": {
                "sm_polygonOffsetBias": int(shadowmap_bias),
                "sm_polygonOffsetScale": float(shadowmap_scale),
                "usingRetailDefaults": (
                    int(shadowmap_bias) == DEFAULT_SHADOWMAP_BIAS
                    and float(shadowmap_scale) == DEFAULT_SHADOWMAP_SCALE
                ),
            },
        },
        "policy": {
            "genericGltfApproximation": False,
            "frontFace": "clockwise from retail D3D11 FrontCounterClockwise=FALSE",
            "polygonOffset": "exact retail D3D11 values; shadowmap mode parameterized by live/default T6 DVARs",
            "stencilMasks": "ordinary material state uses read=0xff/write=0xff from retail builder",
            "stencilReference": "dynamic draw state; not a pipeline-descriptor unknown",
            "alphaTest": "explicit shader discard contract",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--sm-polygon-offset-bias", type=int, default=DEFAULT_SHADOWMAP_BIAS
    )
    parser.add_argument(
        "--sm-polygon-offset-scale", type=float, default=DEFAULT_SHADOWMAP_SCALE
    )
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    result = compile_contract(
        contract,
        shadowmap_bias=args.sm_polygon_offset_bias,
        shadowmap_scale=args.sm_polygon_offset_scale,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out": str(args.output), **result["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
