#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import zlib
from pathlib import Path

import bpy

import t6_blender_seal6_role_nodes_v1 as backend

TARGETS = [
    ("mc/mtl_c_usa_milcas_mcknight_head_camo", 5),
    ("mc/mtl_c_usa_mp_seal6_smg_arms", 4),
    ("mc/mtl_gen_eye_cornea", 3),
    ("mc/mtl_gen_eye_iris_green", 4),
    ("mc/mtl_c_gen_insidemouth", 4),
]


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def png_rgba(r: int, g: int, b: int, a: int = 255) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    scanline = b"\x00" + bytes((r, g, b, a))
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(scanline)) + _chunk(b"IEND", b"")


def build_fixture(root: Path) -> dict:
    rows = []
    image_counter = 0
    for material_index, (material, count) in enumerate(TARGETS):
        bpy.data.materials.new(material)
        slots = []
        for index in range(count):
            image = f"fixture_{material_index}_{index}"
            payload = png_rgba((37 * image_counter) % 256, (79 * image_counter) % 256, (131 * image_counter) % 256)
            filename = f"{image}.png"
            (root / filename).write_bytes(payload)
            sha = hashlib.sha256(payload).hexdigest()
            semantic = "normalMap" if index == min(2, count - 1) else ("specularMap" if index == 1 else "colorMap")
            slots.append({
                "slotIndex": index,
                "semantic": semantic,
                "nativeName": f"native_role_{index}",
                "image": image,
                "nativeRecord": {"semantic": semantic, "name": f"native_role_{index}", "image": image},
                "nodeName": f"T6_SLOT_{index:02d}_{semantic}",
                "sampling": "Non-Color/native-shader-data",
                "previewUse": (["legacy-authoring-base-color"] if index == 0 else []) + (["legacy-authoring-normal"] if index == min(2, count - 1) else []),
                "exactRetailPayload": {
                    "repository": "fixture.ipak",
                    "nameHash": image_counter,
                    "dataHash": image_counter + 1,
                    "iwiSha256": "a" * 64,
                    "pngSha256": sha,
                    "pngFile": filename,
                    "crc29Validated": True,
                    "exactKeyValidated": True,
                },
            })
            image_counter += 1
        rows.append({
            "material": material,
            "physicalMaterialCopyCount": 1,
            "activeRetailClientOwnerResolved": True,
            "wholeMaterialByteIdenticalAcrossCopies": True,
            "techniqueSet": f"fixture_ts_{material_index}",
            "textureRoleInvariantAcrossPhysicalCopies": True,
            "nativeSlotCount": count,
            "nativeSlots": slots,
            "authoringPreview": {
                "policy": "synthetic exact-identity preview fixture",
                "baseColorSlotIndex": 0,
                "normalSlotIndex": min(2, count - 1),
                "shaderApproximation": True,
            },
            "shaderLowering": {
                "status": "native-inputs-complete-shader-math-not-yet-promoted",
                "completeNativeInputGraph": True,
                "completeRetailPixelOutput": False,
                "forbidden": ["guess shader math"],
            },
        })
    assert image_counter == 20
    return {
        "format": backend.PLAN_FORMAT,
        "summary": {
            "targetMaterials": 5,
            "nativeTextureSlots": 20,
            "uniqueExactRetailImages": 20,
            "allNativeTextureSlotsRepresented": True,
            "allExactRetailPayloadsValidated": True,
            "completeRetailPixelOutput": False,
        },
        "materials": rows,
        "proofBoundary": "synthetic Blender transport test only",
    }


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with tempfile.TemporaryDirectory(prefix="t6-seal6-blender-") as td:
        root = Path(td)
        plan = build_fixture(root)
        backend.validate_plan(plan)
        result = backend.compile_plan(plan, root)

        assert result["summary"] == {
            "materialsCompiled": 5,
            "nativeSlotsCompiled": 20,
            "uniqueExactPngImagesLoaded": 20,
            "allNativeInputsRepresented": True,
            "completeRetailPixelOutput": False,
        }

        proof_rows = []
        total_source_nodes = 0
        total_preview_color_links = 0
        total_preview_normal_links = 0
        for material, expected_count in TARGETS:
            mat = bpy.data.materials[material]
            assert mat.get("t6_role_complete_native_inputs") is True
            assert mat.get("t6_complete_retail_pixel_output") is False
            assert int(mat.get("t6_native_slot_count")) == expected_count
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            source_nodes = [n for n in nodes if n.bl_idname == "ShaderNodeTexImage" and n.name.startswith("T6_SLOT_")]
            assert len(source_nodes) == expected_count, (material, len(source_nodes), expected_count)
            assert sorted(n.name for n in source_nodes) == [
                f"T6_SLOT_{i:02d}_{plan['materials'][[x[0] for x in TARGETS].index(material)]['nativeSlots'][i]['semantic']}"
                for i in range(expected_count)
            ]
            assert all(n.image is not None for n in source_nodes)
            assert all(n.image.colorspace_settings.name == "Non-Color" for n in source_nodes)
            assert all(n.image.get("t6_exact_key_validated") is True for n in source_nodes)
            assert all(n.image.get("t6_crc29_validated") is True for n in source_nodes)

            preview = nodes.get("T6_AUTHORING_PREVIEW_BSDF")
            normal = nodes.get("T6_AUTHORING_PREVIEW_NORMAL")
            output = nodes.get("T6_AUTHORING_OUTPUT")
            frame = nodes.get("T6_EXACT_NATIVE_SOURCE_SLOTS")
            assert preview and normal and output and frame
            assert "DO NOT TREAT AS RETAIL SHADER" in preview.label
            assert "EXACT T6 NATIVE SOURCE SLOTS" in frame.label

            base_links = [l for l in links if l.to_node == preview and l.to_socket.name == "Base Color"]
            normal_input_links = [l for l in links if l.to_node == normal and l.to_socket.name == "Color"]
            bsdf_links = [l for l in links if l.from_node == preview and l.to_node == output]
            assert len(base_links) == 1
            assert len(normal_input_links) == 1
            assert len(bsdf_links) == 1
            assert base_links[0].from_node.name.startswith("T6_SLOT_00_")

            # Every non-preview native source remains present but is not silently
            # wired into another Principled parameter.
            permitted_preview_sources = {base_links[0].from_node.name, normal_input_links[0].from_node.name}
            for source in source_nodes:
                outgoing = [l for l in links if l.from_node == source]
                if source.name in permitted_preview_sources:
                    assert len(outgoing) == 1
                else:
                    assert len(outgoing) == 0, (material, source.name, [(l.to_node.name, l.to_socket.name) for l in outgoing])

            total_source_nodes += len(source_nodes)
            total_preview_color_links += len(base_links)
            total_preview_normal_links += len(normal_input_links)
            proof_rows.append({
                "material": material,
                "nativeSourceNodes": len(source_nodes),
                "previewBaseColorLinks": len(base_links),
                "previewNormalSourceLinks": len(normal_input_links),
                "completeRetailPixelOutput": False,
            })

        assert total_source_nodes == 20
        assert total_preview_color_links == 5
        assert total_preview_normal_links == 5

        blend = Path("/tmp/T6_BLENDER_SEAL6_ROLE_NODES_V1_TEST.blend")
        report = Path("/tmp/T6_BLENDER_SEAL6_ROLE_NODES_V1_TEST.json")
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        out = {
            "format": "t6-blender-seal6-role-nodes-v1-test",
            "blenderVersion": bpy.app.version_string,
            "summary": result["summary"],
            "sourceNodeCount": total_source_nodes,
            "previewBaseColorLinkCount": total_preview_color_links,
            "previewNormalSourceLinkCount": total_preview_normal_links,
            "materials": proof_rows,
            "proofBoundary": "Synthetic bpy transport test. Exact retail identities are represented by SHA-checked fixture PNGs; this does not promote retail shader arithmetic.",
        }
        report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("T6_BLENDER_SEAL6_ROLE_NODES_V1_TEST=" + json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
