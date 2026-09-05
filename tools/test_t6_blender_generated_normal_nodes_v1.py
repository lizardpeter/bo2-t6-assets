#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_blender_generated_normal_nodes_v1 as normal
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program
from test_t6_blender_height_dag_nodes_v1 import Links, Nodes, Socket
from test_t6_blender_normal_decode_dag_nodes_v1 import component

PS = "1" * 64
VS = "2" * 64
TECH = "lit_sm_r0c0n0_b1c1n1"


def recipe():
    base_components = [component("x"), component("y")]
    layer_components = [component("x"), component("y")]
    for row in base_components:
        dag = row["forensicDag"]
        for node in dag["nodes"]:
            if node.get("kind") == "sample":
                node["resource"] = "normalMapSampler"
        # Reuse the component-level regression only for preflight shape here;
        # recompute hash through its helper-free stable serializer.
        import hashlib, json
        value = {"format": dag["format"], "root": dag["root"], "nodes": dag["nodes"]}
        sha = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        dag["forensicDagSha256"] = sha
        row["forensicDagSha256"] = sha
    return {
        "material": "*fixture",
        "techniqueSet": TECH,
        "pixelShaderArchetype": f"sha256:{PS}",
        "vertexShaderArchetype": f"sha256:{VS}",
        "worldVertFormats": [0],
        "layerProgram": canonical_layer_program(TECH),
        "proof": {"kind": "synthetic Blender normal plan"},
        "normalSampleDecodeV2": {
            "format": "t6-generated-normal-sample-decode-recipe-v2",
            "material": "*fixture",
            "techniqueSet": TECH,
            "pixelShaderArchetype": f"sha256:{PS}",
            "baseline": {
                "mode": "explicit_normal",
                "normalResource": "normalMapSampler",
                "sampleChannels": ["x", "y"],
                "components": base_components,
                "materialArgument": "normalMap",
                "portableDependency": {"layerIndex": 0, "role": "normalMap"},
            },
            "layers": [{
                "layerIndex": 1,
                "normalResource": "normalMapSampler1",
                "sampleChannels": ["x", "y"],
                "components": layer_components,
                "materialArgument": "normalMap1",
                "portableDependency": {"layerIndex": 1, "role": "normalMap"},
                "transformMode": "direct",
                "normalTransformIndex": None,
                "normalTransformAttribute": None,
            }],
            "allDecodeLeavesExact": True,
        },
        "normalTransformShaderBindingsV1": {
            "format": "t6-generated-normal-transform-recipe-binding-v1",
            "material": "*fixture",
            "techniqueSet": TECH,
            "secondaryNormalBindings": [{
                "layerIndex": 1,
                "mode": "direct",
                "normalTransformIndex": None,
                "attribute": None,
            }],
            "crossProofAgreement": True,
        },
        "layeredNormalBasisV1": {
            "format": "t6-generated-layered-normal-basis-recipe-v1",
            "material": "*fixture",
            "techniqueSet": TECH,
            "secondaryNormalLayers": [1],
            "directRoleMatches": {
                "baseIsWorldNormalFromNormal0": True,
                "xBasisIsWorldTangentFromTangent0": True,
                "yBasisExactCrossHandedness": True,
                "yBasisPhysicalRole": "worldBinormal",
            },
            "attachmentSha256": "3" * 64,
        },
    }


def expect_error(row, text):
    try:
        normal.prepare_plan(row, technique_set=TECH, normal_layers=[1])
    except normal.BlenderGeneratedNormalError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError(f"expected normal plan error containing {text!r}")


def main() -> int:
    row = recipe()
    plan = normal.prepare_plan(row, technique_set=TECH, normal_layers=[1])
    assert plan.material == "*fixture"
    assert plan.baseline["mode"] == "explicit_normal"
    assert sorted(plan.layers) == [1]
    assert plan.layers[1]["transformMode"] == "direct"
    assert plan.basis["directRoleMatches"]["yBasisPhysicalRole"] == "worldBinormal"

    nodes = Nodes(); links = Links()
    prev = (Socket("prev-x"), Socket("prev-y"))
    current = (Socket("layer-x"), Socket("layer-y"))
    factor = Socket("factor")
    result = normal.compose_xy(
        nodes, links, prev, current, factor, operation="blend", layer_index=1
    )
    assert result[0] is nodes.created[2].outputs[0]
    assert result[1] is nodes.created[5].outputs[0]
    assert [node.operation for node in nodes.created] == [
        "SUBTRACT", "MULTIPLY", "ADD", "SUBTRACT", "MULTIPLY", "ADD"
    ]
    # Threshold uses the same recurrence arithmetic but relies on the exact 0/1
    # threshold factor socket produced by the diffuse dispatcher.
    nodes2 = Nodes(); links2 = Links()
    normal.compose_xy(nodes2, links2, prev, current, factor, operation="threshold", layer_index=1)
    assert [node.operation for node in nodes2.created] == [
        "SUBTRACT", "MULTIPLY", "ADD", "SUBTRACT", "MULTIPLY", "ADD"
    ]

    missing_basis = recipe(); missing_basis.pop("layeredNormalBasisV1")
    expect_error(missing_basis, "paired-VS layeredNormalBasisV1 is absent")

    bad_transform = recipe(); bad_transform["normalTransformShaderBindingsV1"]["crossProofAgreement"] = False
    expect_error(bad_transform, "dual-proof normal-transform ownership is absent")

    bad_layers = recipe(); bad_layers["normalSampleDecodeV2"]["layers"][0]["layerIndex"] = 2
    expect_error(bad_layers, "normal state layers [2]")

    bad_basis = recipe(); bad_basis["layeredNormalBasisV1"]["directRoleMatches"]["yBasisExactCrossHandedness"] = False
    expect_error(bad_basis, "all three paired-VS physical normal basis roles are not exact")

    transformed = recipe()
    transformed["normalSampleDecodeV2"]["layers"][0].update({
        "transformMode": "transform2x2",
        "normalTransformIndex": 0,
        "normalTransformAttribute": "_T6_NORMAL_TRANSFORM_0",
    })
    transformed["normalTransformShaderBindingsV1"]["secondaryNormalBindings"][0].update({
        "mode": "transform2x2",
        "normalTransformIndex": 0,
        "attribute": "_T6_NORMAL_TRANSFORM_0",
    })
    plan2 = normal.prepare_plan(transformed, technique_set=TECH, normal_layers=[1])
    assert plan2.layers[1]["normalTransformAttribute"] == "_T6_NORMAL_TRANSFORM_0"

    mismatch = copy.deepcopy(transformed)
    mismatch["normalTransformShaderBindingsV1"]["secondaryNormalBindings"][0]["normalTransformIndex"] = 1
    expect_error(mismatch, "v9/v15 transform identity disagrees")

    print("PASS: exact generated layered normal Blender plan/recurrence v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
