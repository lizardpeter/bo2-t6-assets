#!/usr/bin/env python3
"""Run the canonical T6 generated-layer adapter inside real Blender.

This is intentionally a Blender runtime test rather than another pure-Python
preflight. It builds a tiny self-contained glTF fixture with:

- one generated material `*fixture`,
- exact canonical `generatedShaderRecipeV1`,
- exact embedded base/layer color dependencies,
- TEXCOORD_0/1/2 so layer 1 resolves to Blender's third UV map,
- `_T6_LAYER_WEIGHTS` as normalized UBYTE VEC4,
- a one-triangle mesh.

Then it executes adapter v3, saves a .blend, reopens it, and verifies the actual
Blender datablocks/node graph/custom attributes survived. The goal is to catch
real Blender API/importer incompatibilities that static tests cannot see.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import struct
import sys
import tempfile
import zlib

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import t6_blender_generated_layer_preview_v3 as preview  # noqa: E402
from t6_generated_shader_recipe_contract_v1 import EXTRA_KEY  # noqa: E402


def png_rgba(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    row = bytes([0]) + bytes(rgba) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def data_uri(mime: str, payload: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


def align4(raw: bytearray) -> None:
    while len(raw) % 4:
        raw.append(0)


def append(raw: bytearray, payload: bytes) -> tuple[int, int]:
    align4(raw)
    offset = len(raw)
    raw.extend(payload)
    return offset, len(payload)


def fixture_document() -> dict:
    raw = bytearray()

    # glTF Y-up triangle. Blender importer will rotate it to Blender Z-up.
    positions = [
        (-0.8, 0.0, -0.6),
        (0.8, 0.0, -0.6),
        (0.0, 0.0, 0.8),
    ]
    uv0 = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
    uv1 = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]  # lightmap placeholder
    uv2 = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]  # T6 material layer 1
    weights = [(0, 255, 0, 0)] * 3  # layer 1 = G = 1.0
    indices = (0, 1, 2)

    views: list[dict] = []
    accessors: list[dict] = []

    def add_view(payload: bytes, *, target: int | None = None) -> int:
        off, size = append(raw, payload)
        row = {"buffer": 0, "byteOffset": off, "byteLength": size}
        if target is not None:
            row["target"] = target
        views.append(row)
        return len(views) - 1

    def add_accessor(view: int, component: int, count: int, typ: str, **extra) -> int:
        row = {
            "bufferView": view,
            "componentType": component,
            "count": count,
            "type": typ,
        }
        row.update(extra)
        accessors.append(row)
        return len(accessors) - 1

    pos_payload = struct.pack("<" + "f" * 9, *(v for row in positions for v in row))
    pos_view = add_view(pos_payload, target=34962)
    pos_acc = add_accessor(
        pos_view,
        5126,
        3,
        "VEC3",
        min=[-0.8, 0.0, -0.6],
        max=[0.8, 0.0, 0.8],
    )

    def uv_accessor(rows) -> int:
        payload = struct.pack("<" + "f" * 6, *(v for row in rows for v in row))
        return add_accessor(add_view(payload, target=34962), 5126, 3, "VEC2")

    uv0_acc = uv_accessor(uv0)
    uv1_acc = uv_accessor(uv1)
    uv2_acc = uv_accessor(uv2)

    weight_payload = bytes(v for row in weights for v in row)
    weight_acc = add_accessor(
        add_view(weight_payload, target=34962),
        5121,
        3,
        "VEC4",
        normalized=True,
    )

    idx_payload = struct.pack("<HHH", *indices)
    idx_acc = add_accessor(
        add_view(idx_payload, target=34963),
        5123,
        3,
        "SCALAR",
        min=[0],
        max=[2],
    )

    recipe = {
        "material": "*fixture",
        "techniqueSet": "lit_sm_r0c0n0_b1c1",
        "pixelShaderArchetype": "ps-runtime-smoke",
        "worldVertFormats": [1],
        "proof": {
            "kind": "synthetic-runtime-smoke",
            "identity": "Blender API/importer compatibility fixture",
        },
    }

    return {
        "asset": {"version": "2.0", "generator": "T6 Blender runtime smoke fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "T6_Runtime_Fixture"}],
        "meshes": [
            {
                "name": "T6_Runtime_Fixture",
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": pos_acc,
                            "TEXCOORD_0": uv0_acc,
                            "TEXCOORD_1": uv1_acc,
                            "TEXCOORD_2": uv2_acc,
                            "_T6_LAYER_WEIGHTS": weight_acc,
                        },
                        "indices": idx_acc,
                        "material": 0,
                        "mode": 4,
                    }
                ],
            }
        ],
        "materials": [
            {
                "name": "*fixture",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0, "texCoord": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
                "extras": {
                    "T6": {
                        EXTRA_KEY: recipe,
                        "embeddedDependencyTextures": [
                            {
                                "layerIndex": 0,
                                "layer": "base",
                                "role": "colorMap",
                                "semantic": "colorMap",
                                "sourceTexture": "base.png",
                                "gltfTextureIndex": 0,
                            },
                            {
                                "layerIndex": 1,
                                "layer": "layer1",
                                "role": "colorMap",
                                "semantic": "colorMap",
                                "sourceTexture": "layer.png",
                                "gltfTextureIndex": 1,
                            },
                        ],
                    }
                },
            }
        ],
        "samplers": [{"magFilter": 9729, "minFilter": 9729, "wrapS": 10497, "wrapT": 10497}],
        "images": [
            {"name": "base.png", "uri": data_uri("image/png", png_rgba(2, 2, (255, 32, 16, 255)))},
            {"name": "layer.png", "uri": data_uri("image/png", png_rgba(2, 2, (16, 255, 32, 255)))},
        ],
        "textures": [
            {"sampler": 0, "source": 0},
            {"sampler": 0, "source": 1},
        ],
        "bufferViews": views,
        "accessors": accessors,
        "buffers": [{"byteLength": len(raw), "uri": data_uri("application/octet-stream", bytes(raw))}],
    }


def assert_runtime_state(blend_path: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    assert bpy.app.version >= (4, 5, 0), bpy.app.version_string
    material = bpy.data.materials.get("*fixture")
    assert material is not None, [m.name for m in bpy.data.materials]
    assert material.use_nodes
    assert material.get("T6_preview_status") == (
        "exact generated diffuse through RGB-square; Blender downstream lighting"
    )
    assert material.get("T6_technique_set") == "lit_sm_r0c0n0_b1c1"
    assert "Principled lighting is preview-only" in material.get("T6_preview_proof_boundary", "")

    nodes = material.node_tree.nodes
    assert nodes.get("T6_L0_colorMap") is not None, [n.name for n in nodes]
    assert nodes.get("T6_L1_colorMap") is not None, [n.name for n in nodes]
    assert any(n.label == "T6 encoded RGB square (retail shader)" for n in nodes)
    assert any(n.label == "T6 exact L1 blend" for n in nodes)
    assert any("T6 exact layer controls" == n.label for n in nodes)

    image_names = {img.name for img in bpy.data.images}
    assert any(name.startswith("base.png__T6_colorMap_DATA") for name in image_names), image_names
    assert any(name.startswith("layer.png__T6_colorMap_DATA") for name in image_names), image_names

    meshes = list(bpy.data.meshes)
    assert len(meshes) == 1, [m.name for m in meshes]
    mesh = meshes[0]
    uv_names = [layer.name for layer in mesh.uv_layers]
    assert len(uv_names) >= 3, uv_names
    assert "UVMap" in uv_names, uv_names
    assert "UVMap.002" in uv_names, uv_names

    # Blender's glTF importer should retain custom underscore attributes.
    attribute_names = {attr.name for attr in mesh.attributes}
    assert "_T6_LAYER_WEIGHTS" in attribute_names, attribute_names

    report_path = blend_path.with_suffix(blend_path.suffix + ".t6_preview.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["format"] == "t6-blender-generated-layer-preview-v3"
    assert report["generatedMaterialCount"] == 1
    assert report["rebuiltMaterialCount"] == 1
    assert report["skippedMaterialCount"] == 0, report["skipped"]
    assert report["recipeContract"].endswith("generatedShaderRecipeV1")


def main() -> int:
    print("BLENDER_RUNTIME_VERSION", bpy.app.version_string)
    with tempfile.TemporaryDirectory(prefix="t6_blender_runtime_") as td:
        root = Path(td)
        gltf_path = root / "fixture.gltf"
        blend_path = root / "fixture_t6_preview.blend"
        gltf_path.write_text(json.dumps(fixture_document()), encoding="utf-8")

        result = preview.apply_preview(gltf_path, blend_path, strict=True)
        assert result["rebuiltMaterialCount"] == 1, result
        assert result["skippedMaterialCount"] == 0, result
        assert blend_path.is_file() and blend_path.stat().st_size > 0

        assert_runtime_state(blend_path)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "blender": bpy.app.version_string,
                    "blendBytes": blend_path.stat().st_size,
                    "rebuiltMaterialCount": result["rebuiltMaterialCount"],
                    "skippedMaterialCount": result["skippedMaterialCount"],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
