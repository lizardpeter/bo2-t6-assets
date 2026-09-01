#!/usr/bin/env python3
"""Compile renderer-neutral T6 material state contracts into wgpu templates.

This is an executable backend mapping layer, not a generic-glTF approximation.
It consumes `t6-material-render-state-contract-v1` and emits per-state wgpu-like
pipeline descriptors for every operation with a direct semantic equivalent.

Exact/direct mappings:
- separate RGB/alpha blend factors + operations;
- front/back/none culling;
- depth compare and depth write;
- RGB/alpha color write masks;
- fill/line polygon mode (line requires backend feature);
- front/back stencil operations and compare functions.

Explicit unresolved backend inputs:
- T6 symbolic polygon offset modes offset1/offset2/offsetShadowmap need their
  numeric depth-bias constants source-closed before exact raster equivalence;
- stencil read/write masks and reference are dynamic state not contained in the
  archived JsonStencil record and must be supplied by the technique/runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class T6WgpuStateError(RuntimeError):
    pass


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


def _lookup(table: dict[str, str], value: object, *, field: str, material: str) -> str:
    key = str(value)
    if key not in table:
        raise T6WgpuStateError(f"{material!r}: unsupported {field}={key!r}")
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
        "compare": _lookup(COMPARE, face["compare"], field="stencil.compare", material=material),
        "failOp": _lookup(STENCIL_OP, face["fail"], field="stencil.fail", material=material),
        "depthFailOp": _lookup(STENCIL_OP, face["depthFail"], field="stencil.depthFail", material=material),
        "passOp": _lookup(STENCIL_OP, face["pass"], field="stencil.pass", material=material),
    }


def compile_state(state: dict, *, material: str) -> dict:
    blockers: list[dict] = []
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
                "srcFactor": _lookup(BLEND_FACTOR, blend["color"]["srcFactor"], field="blend.color.srcFactor", material=material),
                "dstFactor": _lookup(BLEND_FACTOR, blend["color"]["dstFactor"], field="blend.color.dstFactor", material=material),
                "operation": _lookup(BLEND_OP, blend["color"]["operation"], field="blend.color.operation", material=material),
            },
            "alpha": {
                "srcFactor": _lookup(BLEND_FACTOR, blend["alpha"]["srcFactor"], field="blend.alpha.srcFactor", material=material),
                "dstFactor": _lookup(BLEND_FACTOR, blend["alpha"]["dstFactor"], field="blend.alpha.dstFactor", material=material),
                "operation": _lookup(BLEND_OP, blend["alpha"]["operation"], field="blend.alpha.operation", material=material),
            },
        }

    depth = state["depth"]
    depth_stencil: dict = {
        "depthWriteEnabled": bool(depth["writeEnabled"]),
        "depthCompare": _lookup(COMPARE, depth["compare"], field="depth.compare", material=material),
        "stencil": {
            "front": _stencil_face(state.get("stencilFront"), material=material),
            "back": _stencil_face(state.get("stencilBack"), material=material),
            "readMask": None,
            "writeMask": None,
            "reference": None,
        },
        "bias": {"constant": None, "slopeScale": None, "clamp": None},
    }
    if state.get("stencilFront") is not None or state.get("stencilBack") is not None:
        blockers.append({
            "kind": "dynamic-stencil-parameters",
            "detail": "readMask/writeMask/reference are not present in archived JsonStencil and require runtime/technique provenance",
        })

    offset_mode = str(state["polygonOffset"]["mode"])
    if offset_mode == "offset0":
        depth_stencil["bias"] = {"constant": 0, "slopeScale": 0.0, "clamp": 0.0}
    elif offset_mode in ("offset1", "offset2", "offsetShadowmap"):
        blockers.append({
            "kind": "polygon-offset-numeric-constants",
            "mode": offset_mode,
            "detail": "T6 symbolic mode is preserved but numeric D3D depth-bias constants are not yet source-closed",
        })
    else:
        raise T6WgpuStateError(f"{material!r}: unknown polygon offset mode {offset_mode!r}")

    cull = str(state["cullMode"])
    if cull not in ("none", "front", "back"):
        raise T6WgpuStateError(f"{material!r}: unsupported cull mode {cull!r}")
    polygon_mode = str(state["polygonMode"])
    if polygon_mode not in ("fill", "line"):
        raise T6WgpuStateError(f"{material!r}: unsupported polygon mode {polygon_mode!r}")
    required_features: list[str] = []
    if polygon_mode == "line":
        required_features.append("POLYGON_MODE_LINE")

    alpha = state["alphaTest"]
    fragment_discard = None
    if alpha["enabled"]:
        fragment_discard = {
            "source": "fragment-alpha",
            "compare": _lookup(COMPARE, alpha["compare"], field="alphaTest.compare", material=material),
            "reference": float(alpha["reference"]),
            "implementation": "shader discard/clip before blend/depth write",
        }

    return {
        "stateIndex": int(state["stateIndex"]),
        "primitive": {
            "frontFace": "Ccw",
            "cullMode": None if cull == "none" else cull.title(),
            "polygonMode": polygon_mode.title(),
        },
        "fragmentTarget": target,
        "depthStencil": depth_stencil,
        "alphaTestShaderContract": fragment_discard,
        "requiredWgpuFeatures": required_features,
        "blockers": blockers,
        "exactBackendReady": len(blockers) == 0,
    }


def compile_contract(contract: dict) -> dict:
    if contract.get("format") != "t6-material-render-state-contract-v1":
        raise T6WgpuStateError(f"unsupported state contract {contract.get('format')!r}")
    results: list[dict] = []
    ready = blocked = 0
    for material in contract.get("materials", []):
        name = str(material.get("material") or "")
        states = [compile_state(state, material=name) for state in material.get("states", [])]
        ready += sum(int(state["exactBackendReady"]) for state in states)
        blocked += sum(int(not state["exactBackendReady"]) for state in states)
        results.append({
            "material": name,
            "layered": bool(material.get("layered")),
            "sortKey": material.get("sortKey"),
            "cameraRegion": material.get("cameraRegion"),
            "stateBitsEntry": material.get("stateBitsEntry"),
            "referencedStateIndices": material.get("referencedStateIndices", []),
            "states": states,
            "requiresLayeredComposition": bool(material.get("requiresLayeredComposition")),
        })
    return {
        "format": "t6-material-wgpu-state-v1",
        "materials": results,
        "stats": {
            "materialCount": len(results),
            "stateCount": ready + blocked,
            "exactBackendReadyStateCount": ready,
            "blockedStateCount": blocked,
            "allStatesExactBackendReady": blocked == 0,
        },
        "policy": {
            "genericGltfApproximation": False,
            "directStateMapping": True,
            "alphaTest": "explicit shader discard contract",
            "polygonOffset": "numeric T6 constants required before exact backend-ready status",
            "stencil": "ops/compare mapped exactly; dynamic masks/reference require runtime provenance when stencil is used",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    result = compile_contract(contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.output), **result["stats"]}, indent=2))
    return 0 if result["stats"]["allStatesExactBackendReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
