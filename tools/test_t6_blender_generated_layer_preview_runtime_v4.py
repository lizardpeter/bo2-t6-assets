#!/usr/bin/env python3
"""Run Blender preview v4 against a real imported vN generated material.

This reuses the proven v3 self-contained glTF fixture geometry/textures and
replaces only its canonical generated shader recipe with a complete synthetic
v4 height contract. The goal is Blender API/importer/node-runtime validation,
not a claim that the tiny synthetic DAG is a retail shader archetype.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import test_t6_blender_generated_layer_preview_runtime_v3 as runtime_v3  # noqa: E402
import t6_blender_generated_layer_preview_v4 as preview  # noqa: E402
from t6_generated_shader_recipe_contract_v1 import EXTRA_KEY  # noqa: E402


def _dag_sha(dag: dict) -> str:
    payload = {
        "format": dag["format"],
        "root": dag["root"],
        "nodes": dag["nodes"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def v4_recipe() -> dict:
    material = "*fixture"
    technique = "lit_sm_r0c0_b1c1v1"
    shader_sha = "a" * 64

    # sat((layerWeight * cb1[59].x) + layerAlpha)
    dag = {
        "format": "t6-generated-height-weight-dag-v1",
        "root": 5,
        "nodes": [
            {"id": 0, "kind": "input", "name": "TEXCOORD6.y"},
            {"id": 1, "kind": "cb", "name": "cb1[59].x"},
            {"id": 2, "kind": "mul", "args": [0, 1]},
            {
                "id": 3,
                "kind": "sample",
                "resource": "colorMapSampler1",
                "channel": "w",
                "sampler": "s1",
            },
            {"id": 4, "kind": "add", "args": [2, 3]},
            {"id": 5, "kind": "sat", "args": [4]},
        ],
        "nodeCount": 6,
        "ordering": "reachable child-before-parent; operation argument order preserved",
    }
    dag["forensicDagSha256"] = _dag_sha(dag)

    return {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": "sha256:" + shader_sha,
        "worldVertFormats": [1],
        "proof": {
            "kind": "synthetic-runtime-v4-height-smoke",
            "identity": "Blender vN DAG API/importer compatibility fixture",
        },
        "heightWeightDagsV1": {
            "format": "t6-generated-height-weight-dag-set-v1",
            "techniqueSet": technique,
            "pixelShaderSha256": shader_sha,
            "heightLayerCount": 1,
            "layers": [
                {
                    "layerIndex": 1,
                    "operation": "b",
                    "flags": ["v"],
                    "weightClass": "height",
                    "semanticWeightDagSha256": "b" * 64,
                    "forensicDag": dag,
                }
            ],
        },
        "heightConstantBindingsV1": {
            "format": "t6-dxbc-material-constant-binding-v1",
            "dxbcSha256": shader_sha,
            "leafCount": 1,
            "allLeavesExact": True,
            "material": material,
            "materialIndex": 0,
            "materialStart": 0,
            "materialArchiveSha256": "c" * 64,
            "techniqueSet": technique,
            "techniqueAsset": "runtime_fixture_lit",
            "techniqueFile": "techniques/runtime_fixture_lit.tech",
            "pixelShaderArchetype": "sha256:" + shader_sha,
            "bindings": [
                {
                    "leaf": "cb1[59].x",
                    "materialConstant": {
                        "name": "alphaRevealParms1",
                        "nameHash": 0x88BEFC31,
                        "nameHashHex": "0x88befc31",
                        "nameFragment": "alphaRevealP",
                        "literal": [0.5, 2.0, 0.0, 0.0],
                        "literalComponent": 0,
                        "value": 0.5,
                        "serializedSha256": "d" * 64,
                    },
                }
            ],
        },
        "heightLeafBindingsV1": {
            "format": "t6-generated-height-leaf-bindings-v1",
            "techniqueSet": technique,
            "pixelShaderSha256": shader_sha,
            "heightLayerCount": 1,
            "allNonconstantLeavesExact": True,
            "allLeavesExact": True,
            "material": material,
            "materialArchiveSha256": "c" * 64,
            "techniqueAsset": "runtime_fixture_lit",
            "techniqueFile": "techniques/runtime_fixture_lit.tech",
            "constantBindingsKey": "heightConstantBindingsV1",
            "layers": [
                {
                    "layerIndex": 1,
                    "rawVertexInputs": ["TEXCOORD6.y"],
                    "normalizedVertexWeight": {
                        "attribute": "_T6_LAYER_WEIGHTS",
                        "component": "G",
                        "layerIndex": 1,
                        "proof": "synthetic runtime fixture uses the exact normalized layer-1 contract",
                    },
                    "sampleBindings": [
                        {
                            "resource": "colorMapSampler1",
                            "channel": "w",
                            "samplers": ["s1"],
                            "materialArgument": "colorMap1",
                            "portableDependency": {"layerIndex": 1, "role": "colorMap"},
                        }
                    ],
                    "constantLeaves": ["cb1[59].x"],
                    "forensicDagSha256": dag["forensicDagSha256"],
                }
            ],
            "bindingSetSha256": "e" * 64,
        },
    }


def fixture_document() -> dict:
    doc = runtime_v3.fixture_document()
    t6 = doc["materials"][0]["extras"]["T6"]
    t6[EXTRA_KEY] = v4_recipe()
    return doc


def assert_runtime_state(blend_path: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    assert bpy.app.version >= (4, 5, 0), bpy.app.version_string
    material = bpy.data.materials.get("*fixture")
    assert material is not None, [m.name for m in bpy.data.materials]
    assert material.use_nodes
    assert material.get("T6_preview_status") == (
        "exact generated diffuse through RGB-square including serialized vN DAG; Blender downstream lighting"
    )
    assert material.get("T6_technique_set") == "lit_sm_r0c0_b1c1v1"
    assert "shader-specific vN DAG topology" in material.get("T6_preview_proof_boundary", "")

    height_rows = json.loads(material.get("T6_height_dags_json", "[]"))
    assert len(height_rows) == 1, height_rows
    assert height_rows[0]["layer"] == 1
    assert height_rows[0]["rawVertexInputs"] == ["TEXCOORD6.y"]
    assert height_rows[0]["normalizedWeightComponent"] == "G"
    assert height_rows[0]["sampleLeaves"] == [["colorMapSampler1", "w"]]
    assert height_rows[0]["constantLeafCount"] == 1

    nodes = material.node_tree.nodes
    math_nodes = [n for n in nodes if n.bl_idname == "ShaderNodeMath"]
    operations = [n.operation for n in math_nodes]
    assert "MULTIPLY" in operations, operations
    assert "ADD" in operations, operations
    assert "MAXIMUM" in operations, operations
    assert "MINIMUM" in operations, operations
    assert any(n.label == "T6 vN L1 #2 mul" for n in math_nodes), [n.label for n in math_nodes]
    assert any(n.label == "T6 vN L1 #4 add" for n in math_nodes), [n.label for n in math_nodes]
    assert any(n.label == "T6 vN L1 #5 sat max(0)" for n in math_nodes), [n.label for n in math_nodes]
    assert any(n.label == "T6 vN L1 #5 sat min(1)" for n in math_nodes), [n.label for n in math_nodes]

    value_nodes = [n for n in nodes if n.bl_idname == "ShaderNodeValue"]
    assert any(abs(float(n.outputs[0].default_value) - 0.5) < 1.0e-7 for n in value_nodes)

    meshes = list(bpy.data.meshes)
    assert len(meshes) == 1, [m.name for m in meshes]
    attribute_names = {attr.name for attr in meshes[0].attributes}
    assert "_T6_LAYER_WEIGHTS" in attribute_names, attribute_names

    report_path = blend_path.with_suffix(blend_path.suffix + ".t6_preview.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["format"] == "t6-blender-generated-layer-preview-v4"
    assert report["generatedMaterialCount"] == 1
    assert report["rebuiltMaterialCount"] == 1
    assert report["skippedMaterialCount"] == 0, report["skipped"]
    assert report["heightDagCompiledMaterialCount"] == 1
    assert report["heightDagCompiledLayerCount"] == 1


def main() -> int:
    print("BLENDER_RUNTIME_VERSION", bpy.app.version_string)
    with tempfile.TemporaryDirectory(prefix="t6_blender_runtime_v4_") as td:
        root = Path(td)
        gltf_path = root / "fixture_v4.gltf"
        blend_path = root / "fixture_t6_preview_v4.blend"
        gltf_path.write_text(json.dumps(fixture_document()), encoding="utf-8")

        result = preview.apply_preview(gltf_path, blend_path, strict=True)
        assert result["rebuiltMaterialCount"] == 1, result
        assert result["skippedMaterialCount"] == 0, result
        assert result["heightDagCompiledLayerCount"] == 1, result
        assert blend_path.is_file() and blend_path.stat().st_size > 0

        assert_runtime_state(blend_path)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "blender": bpy.app.version_string,
                    "blendBytes": blend_path.stat().st_size,
                    "rebuiltMaterialCount": result["rebuiltMaterialCount"],
                    "heightDagCompiledLayerCount": result["heightDagCompiledLayerCount"],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
