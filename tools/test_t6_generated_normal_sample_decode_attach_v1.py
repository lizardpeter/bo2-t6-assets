#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_generated_normal_sample_decode_attach_v1 as attach
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program

PS = "1" * 64
VS = "2" * 64
TECH = "lit_sm_r0c0n0_b1c1n1"


def recipe() -> dict:
    basis = {
        "format": "t6-generated-layered-normal-basis-recipe-v1",
        "material": "*fixture",
        "techniqueSet": TECH,
        "secondaryNormalLayers": [1],
        "attachmentSha256": "a" * 64,
    }
    return {
        "material": "*fixture",
        "techniqueSet": TECH,
        "pixelShaderArchetype": f"sha256:{PS}",
        "vertexShaderArchetype": f"sha256:{VS}",
        "worldVertFormats": [0],
        "layerProgram": canonical_layer_program(TECH),
        "proof": {"kind": "synthetic decode attachment"},
        "normalTransformShaderBindingsV1": {
            "secondaryNormalBindings": [{
                "layerIndex": 1,
                "mode": "direct",
                "normalTransformIndex": None,
                "attribute": None,
            }],
            "crossProofAgreement": True,
            "bindingSha256": "b" * 64,
        },
        "layeredNormalBasisV1": basis,
    }


def proof() -> dict:
    item = {
        "scale": 2.0,
        "offset": -1.0,
        "scaleFloat32Bits": "40000000",
        "offsetFloat32Bits": "bf800000",
        "equation": "decodedChannel = sampledChannel * scale + offset",
    }
    channel = {
        "scaleFloat32Bits": "40000000",
        "offsetFloat32Bits": "bf800000",
    }
    return {
        "format": "t6-generated-normal-sample-decode-probe-v1",
        "summary": {
            "affineDecodeFailureCount": 0,
            "uniformAffineDecode": True,
            "uniqueAffineDecodeCount": 1,
            "normalLayerCount": 1,
            "channelDecodeObservationCount": 2,
            "rowsSha256": "c" * 64,
        },
        "uniformDecode": item,
        "rows": [{
            "sha256": PS,
            "techniqueSet": TECH,
            "worldVertFormat": 0,
            "normalLayers": [{
                "layerIndex": 1,
                "decode": {
                    "x": {**channel, "boundarySha256": "d" * 64},
                    "y": {**channel, "boundarySha256": "e" * 64},
                },
            }],
        }],
    }


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except attach.NormalSampleDecodeAttachError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected NormalSampleDecodeAttachError containing {text!r}")


def main() -> int:
    row = recipe()
    payload = attach.build_attachment(row, proof())
    assert payload is not None
    assert payload["format"] == attach.FORMAT
    assert payload["playbackReady"] is True
    assert payload["pixelShaderSha256"] == PS
    assert payload["secondaryNormalLayers"] == [1]
    assert payload["decode"]["scale"] == 2.0
    assert payload["decode"]["offset"] == -1.0
    assert payload["basisAttachmentSha256"] == "a" * 64
    assert payload["transformBindingSha256"] == "b" * 64
    assert payload["layerEvidence"][0]["channels"]["x"]["boundarySha256"] == "d" * 64

    gltf = {
        "materials": [{
            "name": "*fixture",
            "extras": {"T6": {"generatedShaderRecipeV1": copy.deepcopy(row)}},
        }]
    }
    stats = attach.attach_gltf(gltf, proof())
    assert stats["secondaryNormalMaterialCount"] == 1
    assert stats["playbackReadyMaterialCount"] == 1
    assert stats["allSecondaryNormalMaterialsPlaybackReady"] is True
    embedded = gltf["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"]
    assert embedded[attach.ATTACHMENT_KEY]["playbackReady"] is True
    assert gltf["extras"]["T6"]["generatedLayeredNormalPlayback"]["stats"] == stats

    bad_ps = proof()
    bad_ps["rows"][0]["sha256"] = "f" * 64
    expect_error(lambda: attach.build_attachment(recipe(), bad_ps), "pixel shader differs")

    nonuniform = proof()
    nonuniform["summary"]["uniformAffineDecode"] = False
    nonuniform["summary"]["uniqueAffineDecodeCount"] = 2
    nonuniform["uniformDecode"] = None
    expect_error(lambda: attach.build_attachment(recipe(), nonuniform), "lacks summary/uniformDecode")

    missing_basis = recipe()
    missing_basis.pop("layeredNormalBasisV1")
    expect_error(lambda: attach.build_attachment(missing_basis, proof()), "v16 exact layered normal basis is absent")

    bad_transform = recipe()
    bad_transform["normalTransformShaderBindingsV1"]["crossProofAgreement"] = False
    expect_error(lambda: attach.build_attachment(bad_transform, proof()), "v15 dual-proof normal transform binding is absent")

    bad_channel = proof()
    bad_channel["rows"][0]["normalLayers"][0]["decode"]["y"]["scaleFloat32Bits"] = "3f800000"
    expect_error(lambda: attach.build_attachment(recipe(), bad_channel), "per-layer decode disagrees")

    print("PASS: t6_generated_normal_sample_decode_attach_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
