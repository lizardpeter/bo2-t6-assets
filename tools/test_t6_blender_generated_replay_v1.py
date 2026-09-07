#!/usr/bin/env python3
"""Run inside Blender: validate direct v51 replay-contract leaf dispatch."""
from __future__ import annotations

import copy
import json
import bpy
import t6_blender_generated_replay_v1 as backend


def replay_doc():
    sha = "a" * 64
    tech = "lit_fixture"
    mat = "*fixture"
    program = {
        "pixelShaderSha256": sha,
        "shaderModel": "4.0",
        "techniqueSets": [tech],
        "externalNonCbufferSymbols": ["v0.x"],
        "nodes": [
            {"id": 0, "kind": "symbol", "name": "cb0[0].x"},
            {"id": 1, "kind": "symbol", "name": "cb0[1].x"},
            {"id": 2, "kind": "symbol", "name": "v0.x"},
            {"id": 3, "kind": "textureSample", "resource": "colorMapSampler", "channel": "x", "opcode": "sample", "args": [2]},
            {"id": 4, "kind": "textureSample", "resource": "reflectionProbeSampler", "channel": "x", "opcode": "sample_l", "args": [2]},
            {"id": 5, "kind": "op", "op": "add", "args": [0, 1]},
            {"id": 6, "kind": "op", "op": "add", "args": [3, 4]},
            {"id": 7, "kind": "op", "op": "mul", "args": [5, 6]},
            {"id": 8, "kind": "op", "op": "add", "args": [7, 2]},
            {"id": 9, "kind": "op", "op": "sqrt", "args": [7]},
            {"id": 10, "kind": "literal32", "bits": "3f800000"},
        ],
        "outputs": [{
            "register": 0,
            "lanes": [
                {"channel": "x", "written": True, "node": 7},
                {"channel": "y", "written": True, "node": 8},
                {"channel": "z", "written": True, "node": 9},
                {"channel": "w", "written": True, "node": 10},
            ],
        }],
        "samples": [],
        "branches": [],
        "discards": [],
        "programSha256": "fixture",
    }
    owner = {
        "material": mat,
        "techniqueSet": tech,
        "pixelShaderSha256": sha,
        "cbufferInputs": [
            {
                "symbol": "cb0[0].x",
                "bindingKind": "retailMaterialConstant",
                "staticValueResolved": True,
                "materialConstant": {"name": "foo", "scalarValue": 0.25, "literal": [0.25, 0.0, 0.0, 0.0]},
            },
            {
                "symbol": "cb0[1].x",
                "bindingKind": "t6CodeConstantDynamic",
                "staticValueResolved": False,
                "dynamicIdentity": {"accessor": "sunDiffuse", "resolvedEnumValue": 35, "updateFrequency": "CUSTOM"},
            },
        ],
        "textureInputs": [
            {
                "resource": "colorMapSampler",
                "sampleNodeIds": [3],
                "opcodes": ["sample"],
                "channels": ["x"],
                "bindingKind": "retailMaterialTexture",
                "runtimeResourceResolved": True,
                "resolvedTexture": {"imageAsset": "img_color", "sourceTexture": "img_color.png", "propertyHash": 123},
            },
            {
                "resource": "reflectionProbeSampler",
                "sampleNodeIds": [4],
                "opcodes": ["sample_l"],
                "channels": ["x"],
                "bindingKind": "t6CodeSamplerDynamic",
                "runtimeResourceResolved": False,
                "dynamicIdentity": {"accessor": "reflectionProbeSampler", "enumValue": 26, "updateFrequency": "CUSTOM"},
            },
        ],
        "materialStaticStateComplete": True,
        "dynamicEngineInputIdentityComplete": True,
        "sourceIdentityComplete": True,
        "programIdentityComplete": True,
        "replayIdentityComplete": True,
        "runtimeDynamicInputsStillRequired": True,
        "blockerCount": 0,
    }
    return {
        "format": backend.REPLAY_FORMAT,
        "programs": [program],
        "materials": [owner],
        "summary": {"programCount": 1, "materialCount": 1},
    }


def value_node(material, label: str, value: float):
    node = material.node_tree.nodes.new("ShaderNodeValue")
    node.label = label
    node.outputs[0].default_value = float(value)
    return node.outputs[0]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = bpy.data.materials.new("replay_fixture")
    calls = {"external": 0, "constant": 0, "materialTexture": 0, "dynamicSampler": 0}

    def external(name):
        calls["external"] += 1
        assert name == "v0.x"
        return value_node(material, "exact external v0.x", 0.5)

    def dynamic_constant(binding):
        calls["constant"] += 1
        assert binding["dynamicIdentity"]["accessor"] == "sunDiffuse"
        return value_node(material, "exact dynamic sunDiffuse", 0.75)

    def material_texture(binding, node, args):
        calls["materialTexture"] += 1
        assert binding["resolvedTexture"]["imageAsset"] == "img_color"
        assert node["opcode"] == "sample" and len(args) == 1
        return value_node(material, "exact material texture sample", 0.4)

    def dynamic_sampler(binding, node, args):
        calls["dynamicSampler"] += 1
        assert binding["dynamicIdentity"]["accessor"] == "reflectionProbeSampler"
        assert node["opcode"] == "sample_l" and len(args) == 1
        return value_node(material, "exact dynamic probe sample", 0.1)

    report = backend.compile_material(
        material,
        replay_doc(),
        "*fixture",
        external_symbol_resolver=external,
        dynamic_constant_resolver=dynamic_constant,
        material_texture_resolver=material_texture,
        dynamic_sampler_resolver=dynamic_sampler,
    )
    assert report["replayIdentityComplete"] is True
    assert report["runtimeDynamicInputsStillRequired"] is True
    assert report["leafResolverCalls"] == {
        "retailMaterialConstant": 1,
        "t6CodeConstantDynamic": 1,
        "externalNonCbufferSymbol": 1,
        "retailMaterialTexture": 1,
        "t6CodeSamplerDynamic": 1,
    }, report["leafResolverCalls"]
    assert calls == {"external": 1, "constant": 1, "materialTexture": 1, "dynamicSampler": 1}, calls
    assert report["output"]["completeSymbolicO0Arithmetic"] is True
    assert not [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]

    blocked = replay_doc()
    blocked["materials"][0]["replayIdentityComplete"] = False
    blocked["materials"][0]["blockerCount"] = 1
    rejected = False
    try:
        backend.compile_material(
            bpy.data.materials.new("blocked_fixture"),
            blocked,
            "*fixture",
            external_symbol_resolver=external,
            dynamic_constant_resolver=dynamic_constant,
            material_texture_resolver=material_texture,
            dynamic_sampler_resolver=dynamic_sampler,
        )
    except backend.BlenderGeneratedReplayError:
        rejected = True
    assert rejected, "blocked replay material was not rejected"

    final = {
        "format": "t6-blender-generated-replay-test-v1",
        "blenderVersion": bpy.app.version_string,
        "report": report,
        "validation": {
            "allFiveReplayLeafClassesDispatched": True,
            "exactStaticConstantConsumed": True,
            "dynamicInputsRequireCallbacks": True,
            "materialTextureIdentityPassedToSampler": True,
            "dynamicSamplerIdentityPassedToSampler": True,
            "blockedReplayMaterialRejected": True,
            "noPrincipledFallback": True,
        },
    }
    print("T6_BLENDER_GENERATED_REPLAY_TEST=" + json.dumps(final, sort_keys=True))
    bpy.ops.wm.save_as_mainfile(filepath="/tmp/T6_BLENDER_GENERATED_REPLAY_V1_TEST.blend")
    with open("/tmp/T6_BLENDER_GENERATED_REPLAY_V1_TEST.json", "w", encoding="utf-8") as handle:
        json.dump(final, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
