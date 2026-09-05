#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v2 as v2
import t6_blender_generated_layer_preview_v3 as v3
import t6_blender_generated_layer_preview_v4 as v4
import t6_blender_height_dag_nodes_v1 as height_nodes


def _dag_sha(dag):
    payload = {
        "format": dag["format"],
        "root": dag["root"],
        "nodes": dag["nodes"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _recipe(material="*fixture(base:layer)"):
    shader_sha = "a" * 64
    technique = "lit_sm_r0c0_b1c1v1"
    dag = {
        "format": "t6-generated-height-weight-dag-v1",
        "root": 4,
        "nodes": [
            {"id": 0, "kind": "input", "name": "TEXCOORD6.y"},
            {"id": 1, "kind": "sample", "resource": "colorMapSampler1", "channel": "w", "sampler": "s1"},
            {"id": 2, "kind": "cb", "name": "cb1[59].x"},
            {"id": 3, "kind": "add", "args": [0, 1]},
            {"id": 4, "kind": "add", "args": [3, 2]},
        ],
        "nodeCount": 5,
        "ordering": "reachable child-before-parent; operation argument order preserved",
    }
    dag["forensicDagSha256"] = _dag_sha(dag)
    return {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": "sha256:" + shader_sha,
        "worldVertFormats": [1],
        "proof": {"fixture": True},
        height_nodes.HEIGHT_DAG_KEY: {
            "techniqueSet": technique,
            "pixelShaderSha256": shader_sha,
            "layers": [{
                "layerIndex": 1,
                "forensicDag": dag,
            }],
        },
        height_nodes.HEIGHT_CONSTANT_KEY: {
            "material": material,
            "techniqueSet": technique,
            "pixelShaderArchetype": "sha256:" + shader_sha,
            "leafCount": 1,
            "bindings": [{
                "leaf": "cb1[59].x",
                "materialConstant": {"value": 0.25},
            }],
        },
        height_nodes.HEIGHT_LEAF_KEY: {
            "material": material,
            "techniqueSet": technique,
            "pixelShaderSha256": shader_sha,
            "allLeavesExact": True,
            "layers": [{
                "layerIndex": 1,
                "forensicDagSha256": dag["forensicDagSha256"],
                "rawVertexInputs": ["TEXCOORD6.y"],
                "normalizedVertexWeight": {
                    "attribute": "_T6_LAYER_WEIGHTS",
                    "component": "G",
                    "layerIndex": 1,
                },
                "sampleBindings": [{
                    "resource": "colorMapSampler1",
                    "channel": "w",
                    "portableDependency": {"layerIndex": 1, "role": "colorMap"},
                }],
            }],
        },
    }


def main() -> int:
    material = "*fixture(base:layer)"
    technique = "lit_sm_r0c0_b1c1v1"
    recipe = _recipe(material)
    plan = v4._height_identity_preflight(material, technique, recipe, 1)
    assert plan.layer_index == 1
    assert plan.vertex_leaf_names == ("TEXCOORD6.y",)
    assert plan.raw_vertex_component == "G"

    wrong_material = _recipe(material)
    wrong_material[height_nodes.HEIGHT_CONSTANT_KEY]["material"] = "*other(base:layer)"
    try:
        v4._height_identity_preflight(material, technique, wrong_material, 1)
    except v4.BlenderLayerPreviewError as exc:
        assert "payload belongs" in str(exc)
    else:
        raise AssertionError("height constants from another generated Material were accepted")

    wrong_shader = _recipe(material)
    wrong_shader[height_nodes.HEIGHT_DAG_KEY]["pixelShaderSha256"] = "b" * 64
    try:
        v4._height_identity_preflight(material, technique, wrong_shader, 1)
    except v4.BlenderLayerPreviewError as exc:
        assert "pixel-shader SHA disagrees" in str(exc)
    else:
        raise AssertionError("height DAG from another pixel shader was accepted")

    # Verify the integration maps the exact normalized layer-1 weight and exact
    # sample leaf to the current layer color texture's alpha before compilation.
    vertex_socket = object()
    alpha_socket = object()
    factor_socket = object()
    captured = {}
    old_vertex = v2._vertex_weight_socket
    old_compile = height_nodes.compile_height_dag
    try:
        v2._vertex_weight_socket = lambda nodes, links, attr, sep, layer: (
            vertex_socket if layer == 1 else None
        )

        def fake_compile(nodes, links, plan, *, vertex_socket, sample_sockets):
            captured["plan"] = plan
            captured["vertex"] = vertex_socket
            captured["samples"] = sample_sockets
            return factor_socket

        height_nodes.compile_height_dag = fake_compile
        color_tex = SimpleNamespace(outputs={"Alpha": alpha_socket})
        factor, used_plan = v4._height_factor(
            object(), object(),
            material=material,
            technique=technique,
            recipe=recipe,
            token=SimpleNamespace(layer=1),
            color_tex=color_tex,
            attr=object(),
            sep=object(),
        )
    finally:
        v2._vertex_weight_socket = old_vertex
        height_nodes.compile_height_dag = old_compile

    assert factor is factor_socket
    assert used_plan.layer_index == 1
    assert captured["vertex"] is vertex_socket
    assert captured["samples"] == {("colorMapSampler1", "w"): alpha_socket}

    # apply_preview must patch the legacy builder only for the duration of the
    # run, then restore it even though v4 is implemented as an incremental layer.
    with tempfile.TemporaryDirectory(prefix="t6_blender_v4_") as td:
        root = Path(td)
        output = root / "fixture.blend"
        originals = {
            "recipe_map": v1._recipe_map,
            "material_technique": v1._material_technique,
            "weight_attribute": v1._weight_attribute,
            "vertex_weight_socket": v1._vertex_weight_socket,
            "build_material": v1._build_material,
            "apply_preview": v1.apply_preview,
        }
        observed = {}

        def fake_apply(input_path, output_blend, *, recipes=None, strict=False):
            observed["recipe_map"] = v1._recipe_map
            observed["material_technique"] = v1._material_technique
            observed["weight_attribute"] = v1._weight_attribute
            observed["vertex_weight_socket"] = v1._vertex_weight_socket
            observed["build_material"] = v1._build_material
            return {
                "format": "t6-blender-generated-layer-preview-v1",
                "input": str(input_path),
                "output": str(output_blend),
                "generatedMaterialCount": 1,
                "rebuiltMaterialCount": 1,
                "skippedMaterialCount": 0,
                "rebuilt": [{
                    "material": material,
                    "heightDagCount": 1,
                    "heightDags": [{"layer": 1}],
                }],
                "skipped": [],
            }

        v1.apply_preview = fake_apply
        try:
            result = v4.apply_preview(root / "fixture.glb", output, strict=True)
        finally:
            v1.apply_preview = originals["apply_preview"]

        assert observed["recipe_map"] is v3._recipe_map
        assert observed["material_technique"] is v3._material_technique
        assert observed["weight_attribute"] is v2._weight_attribute
        assert observed["vertex_weight_socket"] is v2._vertex_weight_socket
        assert observed["build_material"] is v4._build_material_v4
        assert v1._recipe_map is originals["recipe_map"]
        assert v1._material_technique is originals["material_technique"]
        assert v1._weight_attribute is originals["weight_attribute"]
        assert v1._vertex_weight_socket is originals["vertex_weight_socket"]
        assert v1._build_material is originals["build_material"]
        assert result["format"] == "t6-blender-generated-layer-preview-v4"
        assert result["heightDagCompiledMaterialCount"] == 1
        assert result["heightDagCompiledLayerCount"] == 1
        report = output.with_suffix(output.suffix + ".t6_preview.json")
        assert report.is_file()
        persisted = json.loads(report.read_text(encoding="utf-8"))
        assert persisted["format"] == result["format"]
        assert persisted["heightDagCompiledLayerCount"] == 1

    print("PASS: Blender generated-layer preview v4 exact vN integration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
