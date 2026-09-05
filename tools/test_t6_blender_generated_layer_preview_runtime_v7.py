#!/usr/bin/env python3
"""Real Blender 4.5+ runtime regression for generated layered-normal preview v7.

The fixture is intentionally production-shaped rather than a generic normal-map
smoke test:

* canonical v9/v15/v16 generated normal recipe;
* v5 generated-attribute and v20 N/T/B root contracts;
* _T6_WORLD_NORMAL aliases the standard NORMAL accessor;
* _T6_WORLD_TANGENT is a strided VEC3 view over the exact VEC4 TANGENT bytes;
* _T6_WORLD_BINORMAL is a separately stored per-vertex vector;
* base + layer normal textures execute their serialized 2*x-1 DAGs;
* v7 must explicitly map glTF custom basis vectors (x,y,z)->(x,-z,y)
  before OBJECT->WORLD and wire the reconstructed world normal to Principled.

This test does not claim the synthetic shader recipe itself came from retail; it
validates the real Blender importer/API/node runtime against the exact contracts
that the retail recovery pipeline now emits.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import struct
import sys
import tempfile

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import test_t6_blender_generated_layer_preview_runtime_v3 as runtime_v3  # noqa: E402
import test_t6_blender_generated_normal_nodes_v1 as normal_fixture  # noqa: E402
import t6_blender_generated_layer_preview_v7 as preview  # noqa: E402
from t6_generated_shader_recipe_contract_v1 import EXTRA_KEY  # noqa: E402
from t6_world_generated_attribute_contract_v1 import FORMAT as ATTRIBUTE_FORMAT  # noqa: E402
from t6_world_generated_normal_basis_attributes_v2 import FORMAT as BASIS_V2_FORMAT  # noqa: E402


def _buffer_bytes(doc: dict) -> bytearray:
    uri = str(doc["buffers"][0]["uri"])
    prefix = "data:application/octet-stream;base64,"
    assert uri.startswith(prefix)
    return bytearray(base64.b64decode(uri[len(prefix):]))


def _reset_buffer_uri(doc: dict, raw: bytearray) -> None:
    doc["buffers"][0]["byteLength"] = len(raw)
    doc["buffers"][0]["uri"] = runtime_v3.data_uri(
        "application/octet-stream", bytes(raw)
    )


def _append_view(doc: dict, raw: bytearray, payload: bytes, *, stride: int | None = None) -> int:
    runtime_v3.align4(raw)
    offset = len(raw)
    raw.extend(payload)
    row = {
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "target": 34962,
    }
    if stride is not None:
        row["byteStride"] = stride
    doc["bufferViews"].append(row)
    return len(doc["bufferViews"]) - 1


def _append_accessor(
    doc: dict,
    view: int,
    *,
    count: int,
    typ: str,
    component_type: int = 5126,
    normalized: bool = False,
    name: str | None = None,
) -> int:
    row = {
        "bufferView": view,
        "componentType": component_type,
        "count": count,
        "type": typ,
    }
    if normalized:
        row["normalized"] = True
    if name:
        row["name"] = name
    doc["accessors"].append(row)
    return len(doc["accessors"]) - 1


def fixture_document() -> dict:
    doc = runtime_v3.fixture_document()
    raw = _buffer_bytes(doc)
    primitive = doc["meshes"][0]["primitives"][0]

    # glTF-space basis. The triangle is in y=0, so +Y is its normal.  With
    # tangent +X and handedness +1, cross(N,T) is -Z.
    normals = [(0.0, 1.0, 0.0)] * 3
    tangents = [(1.0, 0.0, 0.0, 1.0)] * 3
    binormals = [(0.0, 0.0, -1.0)] * 3

    n_payload = struct.pack("<" + "f" * 9, *(v for row in normals for v in row))
    n_view = _append_view(doc, raw, n_payload)
    n_acc = _append_accessor(doc, n_view, count=3, typ="VEC3", name="runtime NORMAL")

    t_payload = struct.pack("<" + "f" * 12, *(v for row in tangents for v in row))
    # Production v19 exposes _T6_WORLD_TANGENT as a VEC3 view over VEC4
    # tangent records, so preserve the 16-byte stride here.
    t_view = _append_view(doc, raw, t_payload, stride=16)
    t_acc = _append_accessor(doc, t_view, count=3, typ="VEC4", name="runtime TANGENT")
    t_xyz_acc = _append_accessor(
        doc, t_view, count=3, typ="VEC3", name="_T6_WORLD_TANGENT"
    )

    b_payload = struct.pack("<" + "f" * 9, *(v for row in binormals for v in row))
    b_view = _append_view(doc, raw, b_payload)
    b_acc = _append_accessor(doc, b_view, count=3, typ="VEC3", name="_T6_WORLD_BINORMAL")

    attrs = primitive["attributes"]
    attrs["NORMAL"] = n_acc
    attrs["TANGENT"] = t_acc
    attrs["_T6_WORLD_NORMAL"] = n_acc
    attrs["_T6_WORLD_TANGENT"] = t_xyz_acc
    attrs["_T6_WORLD_BINORMAL"] = b_acc

    recipe = normal_fixture.recipe()
    recipe["proof"] = {
        "kind": "synthetic-runtime-v7-layered-normal-smoke",
        "identity": "real Blender importer/API validation of production normal contracts",
    }
    material_t6 = doc["materials"][0]["extras"]["T6"]
    material_t6[EXTRA_KEY] = recipe

    # Add exact portable normal dependencies used by the recipe.  Colors are
    # deliberately non-flat in XY so the DAG and N+X*T+Y*B path are exercised.
    base_normal = len(doc["images"])
    doc["images"].append({
        "name": "base_normal.png",
        "uri": runtime_v3.data_uri(
            "image/png", runtime_v3.png_rgba(2, 2, (128, 128, 255, 255))
        ),
    })
    layer_normal = len(doc["images"])
    doc["images"].append({
        "name": "layer_normal.png",
        "uri": runtime_v3.data_uri(
            "image/png", runtime_v3.png_rgba(2, 2, (191, 64, 255, 255))
        ),
    })
    base_normal_tex = len(doc["textures"])
    doc["textures"].append({"sampler": 0, "source": base_normal})
    layer_normal_tex = len(doc["textures"])
    doc["textures"].append({"sampler": 0, "source": layer_normal})
    material_t6["embeddedDependencyTextures"].extend([
        {
            "layerIndex": 0,
            "layer": "base",
            "role": "normalMap",
            "semantic": "normalMap",
            "sourceTexture": "base_normal.png",
            "gltfTextureIndex": base_normal_tex,
        },
        {
            "layerIndex": 1,
            "layer": "layer1",
            "role": "normalMap",
            "semantic": "normalMap",
            "sourceTexture": "layer_normal.png",
            "gltfTextureIndex": layer_normal_tex,
        },
    ])

    root_t6 = doc.setdefault("extras", {}).setdefault("T6", {})
    root_t6["generatedAttributeContract"] = {
        "format": ATTRIBUTE_FORMAT,
        "contractSha256": "runtime-generated-attribute-contract",
        "stats": {
            "generatedPrimitiveCount": 1,
            "generatedColorRetypeCount": 1,
        },
    }
    root_t6["generatedNormalBasisAttributesV2"] = {
        "format": BASIS_V2_FORMAT,
        "contractSha256": "runtime-v20-basis-contract",
        "stats": {
            "generatedPrimitiveCount": 1,
            "uniqueBasisSourcePairCount": 1,
            "derivedBinormalAccessorCount": 1,
            "derivedBinormalVertexCount": 3,
        },
        "equation": "B_vertex = cross(N_vertex,T_vertex) * TANGENT.w",
        "interpolationTopology": "derive per vertex before raster interpolation",
    }

    _reset_buffer_uri(doc, raw)
    return doc


def _vec3(value) -> tuple[float, float, float]:
    return tuple(float(x) for x in value[:3])


def _assert_close(actual, expected, eps=1.0e-6):
    assert len(actual) == len(expected)
    for a, b in zip(actual, expected):
        assert abs(float(a) - float(b)) <= eps, (actual, expected)


def assert_runtime_state(blend_path: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    assert bpy.app.version >= (4, 5, 0), bpy.app.version_string

    material = bpy.data.materials.get("*fixture")
    assert material is not None, [m.name for m in bpy.data.materials]
    assert material.use_nodes
    assert bool(material.get("T6_layered_normal_playback")) is True
    assert material.get("T6_preview_status") == (
        "exact generated diffuse + exact layered normal when paired-VS basis is present; Blender downstream lighting"
    )

    normal_steps = json.loads(material.get("T6_layered_normal_steps_json", "[]"))
    assert [row["layer"] for row in normal_steps] == [0, 1], normal_steps
    assert normal_steps[0]["mode"] == "explicit_normal"
    assert normal_steps[1]["transformMode"] == "direct"
    assert normal_steps[1]["usesExactDiffuseFactorSocket"] is True

    nodes = material.node_tree.nodes
    assert nodes.get("T6_L0_normalMap") is not None, [n.name for n in nodes]
    assert nodes.get("T6_L1_normalMap") is not None, [n.name for n in nodes]
    assert any(n.label == "T6 exact N glTF->Blender (x,-z,y)" for n in nodes)
    assert any(n.label == "T6 exact T glTF->Blender (x,-z,y)" for n in nodes)
    assert any(n.label == "T6 exact B glTF->Blender (x,-z,y)" for n in nodes)
    normalize = next(n for n in nodes if n.label == "T6 retail normalize(rawNormal)")
    principled = next(n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    normal_links = [
        link for link in material.node_tree.links
        if link.to_node == principled and link.to_socket.name == "Normal"
    ]
    assert len(normal_links) == 1
    assert normal_links[0].from_node == normalize

    # Crucial importer boundary: application custom attributes must retain the
    # numeric glTF-space vectors. v7 then converts them explicitly in nodes.
    meshes = list(bpy.data.meshes)
    assert len(meshes) == 1, [m.name for m in meshes]
    mesh = meshes[0]
    names = {attr.name for attr in mesh.attributes}
    for name in (
        "_T6_LAYER_WEIGHTS",
        "_T6_WORLD_NORMAL",
        "_T6_WORLD_TANGENT",
        "_T6_WORLD_BINORMAL",
    ):
        assert name in names, names
    n_attr = mesh.attributes["_T6_WORLD_NORMAL"]
    t_attr = mesh.attributes["_T6_WORLD_TANGENT"]
    b_attr = mesh.attributes["_T6_WORLD_BINORMAL"]
    assert len(n_attr.data) == len(t_attr.data) == len(b_attr.data) == 3
    _assert_close(_vec3(n_attr.data[0].vector), (0.0, 1.0, 0.0))
    _assert_close(_vec3(t_attr.data[0].vector), (1.0, 0.0, 0.0))
    _assert_close(_vec3(b_attr.data[0].vector), (0.0, 0.0, -1.0))

    report_path = blend_path.with_suffix(blend_path.suffix + ".t6_preview.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["format"] == "t6-blender-generated-layer-preview-v7"
    assert report["generatedMaterialCount"] == 1
    assert report["rebuiltMaterialCount"] == 1
    assert report["skippedMaterialCount"] == 0, report["skipped"]
    assert report["normalPlaybackMaterialCount"] == 1
    assert report["normalPlaybackLayerCount"] == 1
    assert report["normalBasisAttributeContract"] == BASIS_V2_FORMAT
    assert report["normalBasisCoordinateSpace"] == "glTF custom attribute vectors"
    assert report["normalBasisGltfToBlender"] == [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ]


def main() -> int:
    print("BLENDER_RUNTIME_VERSION", bpy.app.version_string)
    with tempfile.TemporaryDirectory(prefix="t6_blender_runtime_v7_") as td:
        root = Path(td)
        gltf_path = root / "fixture_v7.gltf"
        blend_path = root / "fixture_t6_preview_v7.blend"
        gltf_path.write_text(json.dumps(fixture_document()), encoding="utf-8")

        result = preview.apply_preview(gltf_path, blend_path, strict=True)
        assert result["rebuiltMaterialCount"] == 1, result
        assert result["skippedMaterialCount"] == 0, result
        assert result["normalPlaybackMaterialCount"] == 1, result
        assert result["normalPlaybackLayerCount"] == 1, result
        assert blend_path.is_file() and blend_path.stat().st_size > 0

        assert_runtime_state(blend_path)
        print(json.dumps({
            "status": "PASS",
            "blender": bpy.app.version_string,
            "blendBytes": blend_path.stat().st_size,
            "normalPlaybackMaterialCount": result["normalPlaybackMaterialCount"],
            "normalPlaybackLayerCount": result["normalPlaybackLayerCount"],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
