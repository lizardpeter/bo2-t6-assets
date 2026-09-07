#!/usr/bin/env python3
"""Run inside Blender: test shared generated o0 DAG lowering and Emission output."""
from __future__ import annotations

import json
import bpy
import t6_blender_generated_retail_output_v1 as output_backend


def fixture_shader():
    # One shared textureSample feeds all three RGB roots. A correct multi-root
    # compiler must call the texture resolver once, not once per output lane.
    return {
        "sha256": "1" * 64,
        "techniqueSets": ["lit_fixture"],
        "nodes": [
            {"id": 0, "kind": "literal32", "bits": "3f000000"},
            {"id": 1, "kind": "textureSample", "resource": "colorMapSampler", "channel": "x", "opcode": "sample", "args": [0]},
            {"id": 2, "kind": "op", "op": "mul", "args": [1, 1]},
            {"id": 3, "kind": "op", "op": "add", "args": [2, 0]},
            {"id": 4, "kind": "op", "op": "sqrt", "args": [2]},
            {"id": 5, "kind": "literal32", "bits": "3f800000"},
        ],
        "outputs": [{
            "register": 0,
            "lanes": [
                {"channel": "x", "written": True, "node": 2, "resources": ["colorMapSampler"]},
                {"channel": "y", "written": True, "node": 3, "resources": ["colorMapSampler"]},
                {"channel": "z", "written": True, "node": 4, "resources": ["colorMapSampler"]},
                {"channel": "w", "written": True, "node": 5, "resources": []},
            ],
        }],
    }


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = bpy.data.materials.new("generated_fixture")
    calls = {"texture": 0, "symbol": 0}

    def symbol(name):
        calls["symbol"] += 1
        raise AssertionError(f"unexpected symbol {name}")

    def texture(row, args):
        calls["texture"] += 1
        assert row["resource"] == "colorMapSampler"
        node = material.node_tree.nodes.new("ShaderNodeValue")
        node.label = "fixture exact texture scalar"
        node.outputs[0].default_value = 0.5
        return node.outputs[0]

    report = output_backend.compile_material_output(
        material,
        fixture_shader(),
        symbol_resolver=symbol,
        texture_resolver=texture,
    )
    assert calls["texture"] == 1, calls
    assert calls["symbol"] == 0, calls
    assert report["completeSymbolicO0Arithmetic"] is True
    assert report["compiledO0Lanes"] == ["w", "x", "y", "z"]
    assert report["dagCompiler"]["sharedDagMemoization"] is True
    assert report["dagCompiler"]["textureResolverCallCount"] == 1
    assert material["t6_complete_symbolic_o0_arithmetic"] is True

    outs = [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    emits = [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeEmission"]
    assert len(outs) == len(emits) == 1
    assert len(outs[0].inputs["Surface"].links) == 1
    assert outs[0].inputs["Surface"].links[0].from_node == emits[0]
    assert not [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]

    final = {
        "format": "t6-blender-generated-retail-output-test-v1",
        "blenderVersion": bpy.app.version_string,
        "report": report,
        "validation": {
            "allO0LanesCompiled": True,
            "sharedTextureSampleCompiledOnce": True,
            "sharedDagMemoization": True,
            "emissionTransportOnly": True,
            "noPrincipledFallback": True,
        },
    }
    print("T6_BLENDER_GENERATED_RETAIL_OUTPUT_TEST=" + json.dumps(final, sort_keys=True))
    bpy.ops.wm.save_as_mainfile(filepath="/tmp/T6_BLENDER_GENERATED_RETAIL_OUTPUT_V1_TEST.blend")
    with open("/tmp/T6_BLENDER_GENERATED_RETAIL_OUTPUT_V1_TEST.json", "w", encoding="utf-8") as handle:
        json.dump(final, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
