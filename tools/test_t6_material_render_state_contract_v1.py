#!/usr/bin/env python3
from __future__ import annotations

from t6_material_render_state_contract_v1 import RenderStateContractError, compile_manifest


def _state(**overrides):
    state = {
        "alphaTest": "disabled", "blendOpAlpha": "disabled", "blendOpRgb": "disabled",
        "colorWriteAlpha": True, "colorWriteRgb": True, "cullFace": "back",
        "depthTest": "less_equal", "depthWrite": True,
        "dstBlendAlpha": "zero", "dstBlendRgb": "zero",
        "polygonOffset": "offset0", "polymodeLine": False,
        "srcBlendAlpha": "one", "srcBlendRgb": "one",
        "stencilFront": None, "stencilBack": None,
    }
    state.update(overrides)
    return state


def _archive(states, routing):
    return {
        "sortKey": 4, "cameraRegion": "none", "constants": [],
        "stateBits": states, "stateBitsEntry": routing,
    }


def main() -> int:
    manifest = {
        "materials": [
            {"material": "opaque", "layered": False, "renderState": _archive([_state()], [0, -1])},
            {"material": "cutout_blend", "layered": False, "renderState": _archive([
                _state(
                    alphaTest="ge128", cullFace="none", depthWrite=False,
                    blendOpRgb="add", srcBlendRgb="srcalpha", dstBlendRgb="invsrcalpha",
                    blendOpAlpha="add", srcBlendAlpha="one", dstBlendAlpha="zero",
                    stencilFront={"pass":"keep","fail":"zero","zfail":"replace","func":"greaterequal"},
                )
            ], [0])},
            {"material": "*layered", "layered": True, "renderState": None},
        ]
    }
    doc = compile_manifest(manifest)
    assert doc["stats"]["materialCount"] == 3
    assert doc["stats"]["materialWithStandaloneStateCount"] == 2
    assert doc["stats"]["layeredCompositionMaterialCount"] == 1
    opaque = doc["materials"][0]["states"][0]
    assert opaque["depth"] == {"enabled": True, "compare": "less_equal", "writeEnabled": True}
    assert opaque["blend"]["enabled"] is False
    special = doc["materials"][1]["states"][0]
    assert special["alphaTest"]["reference"] == 128.0 / 255.0
    assert special["cullMode"] == "none"
    assert special["blend"]["color"]["srcFactor"] == "src_alpha"
    assert special["blend"]["color"]["dstFactor"] == "one_minus_src_alpha"
    assert special["stencilFront"]["depthFail"] == "replace"
    assert special["stencilFront"]["compare"] == "greater_equal"

    bad = {"materials": [{"material": "bad", "layered": False, "renderState": _archive([_state(alphaTest="mystery")], [0])}]}
    try:
        compile_manifest(bad)
    except RenderStateContractError as exc:
        assert "unknown alphaTest" in str(exc)
    else:
        raise AssertionError("expected fail-closed unknown enum")

    print("PASS t6_material_render_state_contract_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
