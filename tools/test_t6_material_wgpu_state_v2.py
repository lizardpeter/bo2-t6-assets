#!/usr/bin/env python3
from __future__ import annotations

from t6_material_wgpu_state_v2 import compile_contract


def _state(mode: str = "offset0", **overrides):
    state = {
        "stateIndex": 0,
        "alphaTest": {"enabled": False},
        "blend": {
            "enabled": False,
            "color": {"srcFactor": "one", "dstFactor": "zero", "operation": "add"},
            "alpha": {"srcFactor": "one", "dstFactor": "zero", "operation": "add"},
        },
        "cullMode": "back",
        "depth": {"enabled": True, "compare": "less_equal", "writeEnabled": True},
        "colorWriteMask": {"rgb": True, "alpha": True},
        "polygonMode": "fill",
        "polygonOffset": {"mode": mode},
        "stencilFront": None,
        "stencilBack": None,
    }
    state.update(overrides)
    return state


def _contract(states):
    return {
        "format": "t6-material-render-state-contract-v1",
        "materials": [
            {
                "material": "test",
                "layered": False,
                "sortKey": 4,
                "cameraRegion": "none",
                "stateBitsEntry": list(range(len(states))),
                "referencedStateIndices": list(range(len(states))),
                "states": states,
                "requiresLayeredComposition": False,
            }
        ],
    }


def main() -> int:
    states = [_state("offset0"), _state("offset1"), _state("offset2"), _state("offsetShadowmap")]
    doc = compile_contract(_contract(states))
    assert doc["stats"]["allPipelineDescriptorsExact"] is True
    mapped = doc["materials"][0]["states"]
    assert all(state["primitive"]["frontFace"] == "Cw" for state in mapped)
    assert mapped[0]["depthStencil"]["bias"] == {"constant": 0, "slopeScale": 0.0, "clamp": 0.0}
    assert mapped[1]["depthStencil"]["bias"] == {"constant": 256, "slopeScale": 1.0, "clamp": 0.0}
    assert mapped[2]["depthStencil"]["bias"] == {"constant": 512, "slopeScale": 2.0, "clamp": 0.0}
    assert mapped[3]["depthStencil"]["bias"] == {"constant": -8192, "slopeScale": -2.0, "clamp": 0.0}
    assert mapped[3]["depthStencil"]["biasProvenance"]["usesRuntimeDvars"] is True
    assert doc["retailD3d11Proof"]["shadowmapDvars"]["usingRetailDefaults"] is True

    custom = compile_contract(_contract([_state("offsetShadowmap")]), shadowmap_bias=4096, shadowmap_scale=1.5)
    bias = custom["materials"][0]["states"][0]["depthStencil"]["bias"]
    assert bias == {"constant": -4096, "slopeScale": -1.5, "clamp": 0.0}
    assert custom["retailD3d11Proof"]["shadowmapDvars"]["usingRetailDefaults"] is False

    stencil = _state(
        "offset1",
        stencilFront={"compare": "always", "fail": "keep", "depthFail": "keep", "pass": "replace"},
    )
    stencil_doc = compile_contract(_contract([stencil]))
    s = stencil_doc["materials"][0]["states"][0]
    assert s["depthStencil"]["stencil"]["readMask"] == 255
    assert s["depthStencil"]["stencil"]["writeMask"] == 255
    assert s["dynamicDrawStateRequired"] == ["stencilReference"]
    assert s["pipelineDescriptorExact"] is True

    print("PASS t6_material_wgpu_state_v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
