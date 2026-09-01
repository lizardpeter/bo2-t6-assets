#!/usr/bin/env python3
"""Compile exact archived T6 material state into an executable renderer contract.

Input is the v4 material manifest. Output does not approximate unsupported GPU
state; it maps the OAT-decoded T6 state vocabulary into a renderer-neutral,
fully explicit contract suitable for Blender integration or a wgpu backend.

The contract includes exact per-state blend equations/factors, alpha test,
culling, depth compare/write, color write masks, polygon offset, line mode and
front/back stencil, plus the original stateBitsEntry routing table.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class RenderStateContractError(RuntimeError):
    pass


ALPHA_TEST = {
    "disabled": {"enabled": False},
    "gt0": {"enabled": True, "compare": "greater", "reference": 0.0},
    "ge128": {"enabled": True, "compare": "greater_equal", "reference": 128.0 / 255.0},
}
CULL = {"none": "none", "back": "back", "front": "front"}
DEPTH = {
    "disabled": {"enabled": False, "compare": "always"},
    "always": {"enabled": True, "compare": "always"},
    "less": {"enabled": True, "compare": "less"},
    "equal": {"enabled": True, "compare": "equal"},
    "less_equal": {"enabled": True, "compare": "less_equal"},
}
BLEND_FACTOR = {
    "disabled": "zero",
    "zero": "zero",
    "one": "one",
    "srccolor": "src",
    "invsrccolor": "one_minus_src",
    "srcalpha": "src_alpha",
    "invsrcalpha": "one_minus_src_alpha",
    "destalpha": "dst_alpha",
    "invdestalpha": "one_minus_dst_alpha",
    "destcolor": "dst",
    "invdestcolor": "one_minus_dst",
}
BLEND_OP = {
    "disabled": "add",
    "add": "add",
    "subtract": "subtract",
    "revsubtract": "reverse_subtract",
    "min": "min",
    "max": "max",
}
STENCIL_OP = {
    "keep": "keep", "zero": "zero", "replace": "replace",
    "incrsat": "increment_clamp", "decrsat": "decrement_clamp",
    "invert": "invert", "incr": "increment_wrap", "decr": "decrement_wrap",
}
STENCIL_FUNC = {
    "never": "never", "less": "less", "equal": "equal",
    "lessequal": "less_equal", "greater": "greater",
    "notequal": "not_equal", "greaterequal": "greater_equal", "always": "always",
}
POLYGON_OFFSET = {
    "offset0": {"mode": "offset0"},
    "offset1": {"mode": "offset1"},
    "offset2": {"mode": "offset2"},
    "offsetShadowmap": {"mode": "offsetShadowmap"},
}


def _enum(table: dict, value: object, field: str, material: str) -> object:
    key = str(value)
    if key not in table:
        raise RenderStateContractError(f"{material!r}: unknown {field} value {key!r}")
    return table[key]


def _stencil(value: object, *, material: str, field: str) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RenderStateContractError(f"{material!r}: {field} must be object/null")
    required = ("pass", "fail", "zfail", "func")
    missing = [key for key in required if key not in value]
    if missing:
        raise RenderStateContractError(f"{material!r}: {field} missing {missing}")
    return {
        "pass": _enum(STENCIL_OP, value["pass"], f"{field}.pass", material),
        "fail": _enum(STENCIL_OP, value["fail"], f"{field}.fail", material),
        "depthFail": _enum(STENCIL_OP, value["zfail"], f"{field}.zfail", material),
        "compare": _enum(STENCIL_FUNC, value["func"], f"{field}.func", material),
    }


def compile_state(state: dict, *, material: str, state_index: int) -> dict:
    alpha = _enum(ALPHA_TEST, state.get("alphaTest"), "alphaTest", material)
    cull = _enum(CULL, state.get("cullFace"), "cullFace", material)
    depth = dict(_enum(DEPTH, state.get("depthTest"), "depthTest", material))
    depth["writeEnabled"] = bool(state.get("depthWrite"))
    rgb_op_raw = str(state.get("blendOpRgb"))
    alpha_op_raw = str(state.get("blendOpAlpha"))
    blend_enabled = rgb_op_raw != "disabled" or alpha_op_raw != "disabled"
    blend = {
        "enabled": blend_enabled,
        "color": {
            "srcFactor": _enum(BLEND_FACTOR, state.get("srcBlendRgb"), "srcBlendRgb", material),
            "dstFactor": _enum(BLEND_FACTOR, state.get("dstBlendRgb"), "dstBlendRgb", material),
            "operation": _enum(BLEND_OP, rgb_op_raw, "blendOpRgb", material),
        },
        "alpha": {
            "srcFactor": _enum(BLEND_FACTOR, state.get("srcBlendAlpha"), "srcBlendAlpha", material),
            "dstFactor": _enum(BLEND_FACTOR, state.get("dstBlendAlpha"), "dstBlendAlpha", material),
            "operation": _enum(BLEND_OP, alpha_op_raw, "blendOpAlpha", material),
        },
    }
    return {
        "stateIndex": state_index,
        "alphaTest": alpha,
        "blend": blend,
        "cullMode": cull,
        "depth": depth,
        "colorWriteMask": {
            "rgb": bool(state.get("colorWriteRgb")),
            "alpha": bool(state.get("colorWriteAlpha")),
        },
        "polygonMode": "line" if bool(state.get("polymodeLine")) else "fill",
        "polygonOffset": _enum(POLYGON_OFFSET, state.get("polygonOffset"), "polygonOffset", material),
        "stencilFront": _stencil(state.get("stencilFront"), material=material, field="stencilFront"),
        "stencilBack": _stencil(state.get("stencilBack"), material=material, field="stencilBack"),
        "source": state,
    }


def compile_manifest(material_manifest: dict) -> dict:
    materials = material_manifest.get("materials")
    if not isinstance(materials, list):
        raise RenderStateContractError("material manifest lacks materials[]")
    rows: list[dict] = []
    unique_states: set[str] = set()
    routed_state_count = 0
    for material in materials:
        name = str(material.get("material") or "")
        if not name:
            raise RenderStateContractError("material entry has empty identity")
        archive = material.get("renderState")
        if archive is None:
            # Generated layered materials have no standalone OAT material; their
            # component layers still retain exact state and remain a separate
            # shader-composition gate.
            rows.append({
                "material": name,
                "layered": bool(material.get("layered")),
                "standaloneRenderState": None,
                "stateBitsEntry": None,
                "states": [],
                "requiresLayeredComposition": bool(material.get("layered")),
            })
            continue
        if not isinstance(archive, dict):
            raise RenderStateContractError(f"{name!r}: renderState must be object/null")
        state_bits = archive.get("stateBits")
        routing = archive.get("stateBitsEntry")
        if not isinstance(state_bits, list) or not isinstance(routing, list):
            raise RenderStateContractError(f"{name!r}: renderState missing stateBits/stateBitsEntry")
        compiled = [compile_state(state, material=name, state_index=i) for i, state in enumerate(state_bits)]
        for state in compiled:
            unique_states.add(json.dumps(state["source"], sort_keys=True, separators=(",", ":")))
        routed = sorted({int(v) for v in routing if int(v) >= 0})
        for index in routed:
            if index >= len(compiled):
                raise RenderStateContractError(f"{name!r}: route {index} outside state table")
        routed_state_count += len(routed)
        rows.append({
            "material": name,
            "layered": bool(material.get("layered")),
            "sortKey": archive.get("sortKey"),
            "cameraRegion": archive.get("cameraRegion"),
            "constants": archive.get("constants", []),
            "stateBitsEntry": [int(v) for v in routing],
            "referencedStateIndices": routed,
            "states": compiled,
            "requiresLayeredComposition": bool(material.get("layered")),
        })
    return {
        "format": "t6-material-render-state-contract-v1",
        "materials": rows,
        "stats": {
            "materialCount": len(rows),
            "materialWithStandaloneStateCount": sum(row["standaloneRenderState"] is not None if "standaloneRenderState" in row else bool(row["states"]) for row in rows),
            "uniqueStateCount": len(unique_states),
            "referencedStateUseCount": routed_state_count,
            "layeredCompositionMaterialCount": sum(bool(row["requiresLayeredComposition"]) for row in rows),
        },
        "semantics": {
            "alphaReference": "normalized 0..1; gt0=0, ge128=128/255",
            "blend": "separate color and alpha equations retained exactly from decoded T6 state",
            "routing": "stateBitsEntry is retained verbatim; technique-slot meaning remains tied to the exact T6 technique table",
            "polygonOffset": "symbolic T6 offset mode retained; numeric depth-bias constants require backend/runtime proof before claiming exact raster equivalence",
        },
        "proofBoundary": (
            "This contract closes exact state vocabulary translation into renderer-neutral operations. "
            "It does not by itself prove backend-specific numeric polygon bias, technique selection, or visual parity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.material_manifest.read_text(encoding="utf-8"))
    result = compile_manifest(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.output), **result["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
