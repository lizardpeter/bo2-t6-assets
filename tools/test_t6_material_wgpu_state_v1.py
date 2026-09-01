#!/usr/bin/env python3
from __future__ import annotations

from t6_material_wgpu_state_v1 import compile_contract


def _state(**overrides):
    state = {
        "stateIndex": 0,
        "alphaTest": {"enabled": False},
        "blend": {
            "enabled": False,
            "color": {"srcFactor":"one","dstFactor":"zero","operation":"add"},
            "alpha": {"srcFactor":"one","dstFactor":"zero","operation":"add"},
        },
        "cullMode": "back",
        "depth": {"enabled": True, "compare": "less_equal", "writeEnabled": True},
        "colorWriteMask": {"rgb": True, "alpha": True},
        "polygonMode": "fill",
        "polygonOffset": {"mode": "offset0"},
        "stencilFront": None,
        "stencilBack": None,
    }
    state.update(overrides)
    return state


def main() -> int:
    contract = {
        "format": "t6-material-render-state-contract-v1",
        "materials": [{
            "material": "opaque",
            "layered": False,
            "sortKey": 4,
            "cameraRegion": "none",
            "stateBitsEntry": [0],
            "referencedStateIndices": [0],
            "states": [_state()],
            "requiresLayeredComposition": False,
        }],
    }
    doc = compile_contract(contract)
    assert doc["stats"]["allStatesExactBackendReady"] is True
    state = doc["materials"][0]["states"][0]
    assert state["primitive"]["cullMode"] == "Back"
    assert state["depthStencil"]["depthCompare"] == "LessEqual"
    assert state["depthStencil"]["bias"] == {"constant":0,"slopeScale":0.0,"clamp":0.0}

    special_state = _state(
        alphaTest={"enabled": True, "compare": "greater_equal", "reference": 128.0/255.0},
        blend={
            "enabled": True,
            "color": {"srcFactor":"src_alpha","dstFactor":"one_minus_src_alpha","operation":"add"},
            "alpha": {"srcFactor":"one","dstFactor":"zero","operation":"add"},
        },
        cullMode="none",
        depth={"enabled": True, "compare": "less", "writeEnabled": False},
        polygonOffset={"mode": "offset1"},
        stencilFront={"compare":"always","fail":"keep","depthFail":"keep","pass":"replace"},
    )
    special = {
        "format": "t6-material-render-state-contract-v1",
        "materials": [{
            "material":"special","layered":False,"sortKey":7,"cameraRegion":"none",
            "stateBitsEntry":[0],"referencedStateIndices":[0],"states":[special_state],
            "requiresLayeredComposition":False,
        }],
    }
    doc2 = compile_contract(special)
    assert doc2["stats"]["allStatesExactBackendReady"] is False
    mapped = doc2["materials"][0]["states"][0]
    assert mapped["fragmentTarget"]["blend"]["color"]["srcFactor"] == "SrcAlpha"
    assert mapped["fragmentTarget"]["blend"]["color"]["dstFactor"] == "OneMinusSrcAlpha"
    assert mapped["alphaTestShaderContract"]["reference"] == 128.0/255.0
    kinds = {item["kind"] for item in mapped["blockers"]}
    assert kinds == {"polygon-offset-numeric-constants", "dynamic-stencil-parameters"}

    print("PASS t6_material_wgpu_state_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
