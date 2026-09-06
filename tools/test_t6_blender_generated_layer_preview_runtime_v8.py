#!/usr/bin/env python3
"""Real Blender runtime regression for v8 directional lightmap state.

Builds on the v7 generated diffuse/normal fixture, adds one exact per-surface
lightmap preview shell and a 3-row secondary-lightmap PNG, then imports through
Blender v8.  It verifies the retained directional equation is present but not
silently connected to final material shading.
"""
from __future__ import annotations

import base64
import hashlib
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

import test_t6_blender_generated_layer_preview_runtime_v7 as runtime_v7  # noqa: E402
import t6_blender_generated_layer_preview_v8 as preview  # noqa: E402
import t6_world_lightmap_material_specialize_v1 as specialize  # noqa: E402
from t6_world_lightmap_preview_embed_v1 import FORMAT as PREVIEW_FORMAT, ROOT_KEY as PREVIEW_ROOT  # noqa: E402


def _png_rows() -> bytes:
    width, height = 2, 6
    # Two texel rows per logical T6 lightmap row. Values deliberately differ so
    # the runtime graph cannot collapse the three samples into one image node.
    colors = [
        (32, 64, 96, 128), (32, 64, 96, 128),
        (128, 96, 64, 192), (128, 96, 64, 192),
        (255, 128, 0, 255), (255, 128, 0, 255),
    ]
    raw = b"".join(bytes([0]) + bytes(color) * width for color in colors)
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def fixture_document() -> dict:
    doc = runtime_v7.fixture_document()
    uri = str(doc["buffers"][0]["uri"])
    prefix = "data:application/octet-stream;base64,"
    assert uri.startswith(prefix)
    raw = bytearray(base64.b64decode(uri[len(prefix):]))
    while len(raw) % 4:
        raw.append(0)
    png = _png_rows()
    png_offset = len(raw)
    raw.extend(png)
    view_index = len(doc["bufferViews"])
    doc["bufferViews"].append({
        "buffer": 0,
        "byteOffset": png_offset,
        "byteLength": len(png),
        "name": "T6 runtime directional lightmap PNG",
    })
    image_index = len(doc["images"])
    png_sha = hashlib.sha256(png).hexdigest()
    dds_sha = "d" * 64
    doc["images"].append({
        "name": "T6_LIGHTMAP_PREVIEW_runtime_secondary",
        "bufferView": view_index,
        "mimeType": "image/png",
        "extras": {"T6": {
            "previewOnly": True,
            "dataTexture": True,
            "sourceKind": "canonical embedded lightmap DDS",
            "gfxImageAsset": "runtime_secondary",
            "sourceTexture": "runtime_secondary.dds",
            "sourceDdsSha256": dds_sha,
            "decoder": "runtime synthetic PNG",
        }},
    })
    texture_index = len(doc["textures"])
    doc["textures"].append({"sampler": 0, "source": image_index})

    primitive = doc["meshes"][0]["primitives"][0]
    primitive.setdefault("extras", {}).setdefault("T6", {}).update({
        "index": 0,
        "groupIndex": 0,
        "lightmapIndex": 0,
    })
    root = doc.setdefault("extras", {}).setdefault("T6", {})
    root[PREVIEW_ROOT] = {
        "format": PREVIEW_FORMAT,
        "map": "runtime",
        "stats": {"lightmapCount": 1, "uniquePreviewImageCount": 1},
    }
    root["lightmapArchive"] = {
        "format": "t6-world-lightmap-glb-archive-v3",
        "lightmaps": [{
            "index": 0,
            "primary": {
                "present": False, "embedded": False, "gfxImageAsset": None,
                "sourceTexture": None, "codeTextureSource": 4,
                "samplerAccessor": "lightmapSamplerPrimary",
            },
            "secondary": {
                "present": True,
                "embedded": True,
                "gfxImageAsset": "runtime_secondary",
                "sourceTexture": "runtime_secondary.dds",
                "codeTextureSource": 5,
                "samplerAccessor": "lightmapSamplerSecondary",
                "sha256": dds_sha,
                "preview": {
                    "format": PREVIEW_FORMAT,
                    "previewOnly": True,
                    "dataTexture": True,
                    "previewTextureIndex": texture_index,
                    "previewImageIndex": image_index,
                    "previewBufferView": view_index,
                    "previewPngSha256": png_sha,
                    "sourceDdsSha256": dds_sha,
                    "width": 2,
                    "height": 6,
                },
            },
        }],
        "surfaceBindings": [{
            "surfaceIndex": 0,
            "groupIndex": 0,
            "lightmapIndex": 0,
            "hasLightmap": True,
            "lightmapTexCoord": 1,
        }],
    }

    specialized, raw2, stats = specialize.specialize(doc, bytes(raw))
    assert stats["specializedMaterialCount"] == 1
    assert stats["redirectedLightmappedPrimitiveCount"] == 1
    specialized["buffers"][0]["byteLength"] = len(raw2)
    specialized["buffers"][0]["uri"] = prefix + base64.b64encode(raw2).decode("ascii")
    return specialized


def assert_runtime_state(blend_path: Path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    variants = [m for m in bpy.data.materials if "__T6_LM0000_TC1" in m.name]
    assert len(variants) == 1, [m.name for m in bpy.data.materials]
    material = variants[0]
    assert material.get("T6_retail_material_name") == "*fixture"
    assert bool(material.get("T6_layered_normal_playback")) is True
    assert bool(material.get("T6_directional_lightmap_state")) is True

    nodes = material.node_tree.nodes
    for row in range(3):
        node = nodes.get(f"T6_LIGHTMAP_SECONDARY_ROW{row}")
        assert node is not None, [n.name for n in nodes]
        assert node.image is not None
        assert node.image.colorspace_settings.name == "Non-Color"
        assert node.image.packed_file is not None
    assert any(n.label == "T6 exact lightmap TEXCOORD_1" for n in nodes)
    assert any(n.label == "T6 LM dot(direction, reconstructed N)" for n in nodes)
    final = next(n for n in nodes if n.label == "T6 exact directional secondary-lightmap RGB")
    normalize = next(n for n in nodes if n.label == "T6 retail normalize(rawNormal)")
    dot = next(n for n in nodes if n.label == "T6 LM dot(direction, reconstructed N)")
    assert any(link.from_node == normalize and link.to_node == dot for link in material.node_tree.links)

    # Final T6 composition is not source-closed: the directional RGB state must
    # remain deliberately unconsumed by Principled/Material Output.
    outgoing = [link for link in material.node_tree.links if link.from_node == final]
    assert outgoing == [], [(link.to_node.name, link.to_socket.name) for link in outgoing]

    meta = json.loads(material.get("T6_directional_lightmap_state_json", "{}"))
    assert meta["lightmapTexCoord"] == 1
    assert meta["blenderUvMap"] == "UVMap.001"
    assert meta["directionNormalization"] is False
    assert meta["usesReconstructedT6WorldNormal"] is True
    assert meta["finalComposition"].startswith("unassigned")

    report = json.loads(
        blend_path.with_suffix(blend_path.suffix + ".t6_preview.json").read_text(encoding="utf-8")
    )
    assert report["format"] == preview.FORMAT
    assert report["lightmapPreviewVariantRebuiltCount"] == 1
    assert report["directionalLightmapStateMaterialCount"] == 1
    assert "final material/lightmap/specular/reflection composition remains unassigned" in report["directionalLightmapPolicy"]


def main() -> int:
    print("BLENDER_RUNTIME_VERSION", bpy.app.version_string)
    with tempfile.TemporaryDirectory(prefix="t6_blender_runtime_v8_") as td:
        root = Path(td)
        gltf = root / "fixture_v8.gltf"
        blend = root / "fixture_v8.blend"
        gltf.write_text(json.dumps(fixture_document()), encoding="utf-8")
        result = preview.apply_preview(gltf, blend, strict=True)
        assert result["lightmapPreviewVariantRebuiltCount"] == 1, result
        assert result["directionalLightmapStateMaterialCount"] == 1, result
        assert blend.is_file() and blend.stat().st_size > 0
        assert_runtime_state(blend)
        print(json.dumps({
            "status": "PASS",
            "blender": bpy.app.version_string,
            "blendBytes": blend.stat().st_size,
            "directionalLightmapStateMaterialCount": result["directionalLightmapStateMaterialCount"],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
