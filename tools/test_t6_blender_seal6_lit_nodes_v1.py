#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import zlib
from pathlib import Path

import bpy

import t6_blender_seal6_role_nodes_v1 as role_backend
import t6_blender_seal6_lit_nodes_v1 as lit_backend
import t6_seal6_blender_shader_plan_v1 as shader_planner
from test_t6_seal6_blender_shader_plan_v1 import fixtures, SEMANTICS


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def png_rgba(r: int, g: int, b: int, a: int = 255) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    scanline = b"\x00" + bytes((r, g, b, a))
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(scanline)) + _chunk(b"IEND", b"")


def enrich_role_fixture(role: dict, root: Path) -> None:
    role["summary"].update({
        "targetMaterials": 5,
        "uniqueExactRetailImages": 20,
        "allExactRetailPayloadsValidated": True,
        "completeRetailPixelOutput": False,
    })
    counter = 0
    for material in role["materials"]:
        slots = material["nativeSlots"]
        for slot in slots:
            payload = png_rgba((31 * counter) % 256, (83 * counter) % 256, (149 * counter) % 256)
            filename = f"seal6_lit_fixture_{counter}.png"
            (root / filename).write_bytes(payload)
            slot["nodeName"] = f"T6_SLOT_{int(slot['slotIndex']):02d}_{slot['semantic']}"
            slot["sampling"] = "Non-Color/native-shader-data"
            slot["previewUse"] = []
            slot["exactRetailPayload"] = {
                "repository": "synthetic-fixture.ipak",
                "nameHash": counter,
                "dataHash": counter + 1,
                "iwiSha256": hashlib.sha256((f"iwi-{counter}").encode()).hexdigest(),
                "pngSha256": hashlib.sha256(payload).hexdigest(),
                "pngFile": filename,
                "crc29Validated": True,
                "exactKeyValidated": True,
            }
            counter += 1

        names = [slot.get("nativeName") for slot in slots]
        if "Diffuse_Map" in names:
            cidx = names.index("Diffuse_Map")
        else:
            cidx = names.index("Mask")
        if "Normal_Map" in names:
            nidx = names.index("Normal_Map")
        else:
            nidx = names.index("Surface_Normal_Map")
        slots[cidx]["previewUse"].append("legacy-authoring-base-color")
        slots[nidx]["previewUse"].append("legacy-authoring-normal")
        material.update({
            "physicalMaterialCopyCount": 1,
            "activeRetailClientOwnerResolved": True,
            "wholeMaterialByteIdenticalAcrossCopies": True,
            "textureRoleInvariantAcrossPhysicalCopies": True,
            "nativeSlotCount": len(slots),
            "authoringPreview": {
                "policy": "synthetic role-node bootstrap before exact lit upgrade",
                "baseColorSlotIndex": cidx,
                "normalSlotIndex": nidx,
                "shaderApproximation": True,
            },
            "shaderLowering": {
                "status": "native-inputs-complete-shader-math-not-yet-promoted",
                "completeNativeInputGraph": True,
                "completeRetailPixelOutput": False,
                "forbidden": ["guess shader math"],
            },
        })
    assert counter == 20


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with tempfile.TemporaryDirectory(prefix="t6-seal6-lit-blender-") as td:
        root = Path(td)
        role, conflict = fixtures()
        enrich_role_fixture(role, root)
        for row in role["materials"]:
            bpy.data.materials.new(row["material"])

        role_backend.validate_plan(role)
        role_result = role_backend.compile_plan(role, root)
        assert role_result["summary"]["nativeSlotsCompiled"] == 20
        assert role_result["summary"]["completeRetailPixelOutput"] is False

        shader_plan = shader_planner.build(role, conflict, SEMANTICS)
        lit_backend.validate_plan(shader_plan)
        result = lit_backend.compile_plan(shader_plan)
        assert result["summary"] == {
            "materialsCompiled": 5,
            "nativeSourceNodesRetained": 20,
            "ordinaryLitReferencedSourceNodes": 15,
            "preservedNonLitSourceNodes": 5,
            "constantNodes": 22,
            "skinLocalDiffuseGraphs": 4,
            "heroDetailNormalGraphs": 1,
            "corneaLocalGraphs": 1,
            "allExactOrdinaryLitEquationsClosed": True,
            "globalRuntimeLightingInputsBound": False,
            "completeRetailPixelOutput": False,
        }

        proof_rows = []
        total_sources = 0
        total_constants = 0
        total_nonlit = 0
        for material_plan in shader_plan["materials"]:
            name = material_plan["material"]
            mat = bpy.data.materials[name]
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            assert mat.get("t6_role_complete_native_inputs") is True
            assert mat.get("t6_exact_ordinary_lit_equations_closed") is True
            assert mat.get("t6_exact_material_local_nodes_compiled") is True
            assert mat.get("t6_global_runtime_lighting_inputs_bound") is False
            assert mat.get("t6_complete_retail_pixel_output") is False
            assert nodes.get("T6_EXACT_ORDINARY_LIT_LOCAL_MATH") is not None
            unresolved_globals = nodes.get("T6_UNRESOLVED_RETAIL_GLOBALS")
            assert unresolved_globals is not None
            assert "RETAIL GLOBALS REQUIRED" in unresolved_globals.label

            sources = [n for n in nodes if n.bl_idname == "ShaderNodeTexImage" and n.name.startswith("T6_SLOT_")]
            constants = [n for n in nodes if n.name.startswith("T6_CONST_")]
            assert len(sources) == len(material_plan["nativeTextureSlots"])
            assert len(constants) == len(material_plan["nativeConstants"])
            total_sources += len(sources)
            total_constants += len(constants)

            by_slot = {int(n.name.split("_")[2]): n for n in sources}
            for slot in material_plan["nativeTextureSlots"]:
                node = by_slot[int(slot["slotIndex"])]
                referenced = slot["ordinaryLitBinding"]["referenced"]
                assert bool(node.get("t6_ordinary_lit_referenced")) == referenced
                if not referenced:
                    total_nonlit += 1
                    assert "PRESERVED NON-LIT" in node.label
                    assert sum(len(output.links) for output in node.outputs) == 0, (
                        name, node.name,
                        [(link.to_node.name, link.to_socket.name) for output in node.outputs for link in output.links],
                    )
                else:
                    assert "LIT-REFERENCED" in node.label

            family = material_plan["shaderFamilyId"]
            preview = nodes.get("T6_AUTHORING_PREVIEW_BSDF")
            output = nodes.get("T6_AUTHORING_OUTPUT")
            assert preview is not None and output is not None
            assert any(link.from_node == preview and link.to_node == output for link in links)

            if family in {lit_backend.HERO, lit_backend.STANDARD}:
                ndiff = nodes.get("T6_EXACT_NDIFF")
                nspec = nodes.get("T6_EXACT_NSPEC")
                linear = nodes.get("T6_EXACT_SKIN_LINEARLIKE_RGB")
                assert ndiff is not None and nspec is not None and linear is not None
                base_links = [l for l in links if l.to_node == preview and l.to_socket.name == "Base Color"]
                normal_links = [l for l in links if l.to_node == preview and l.to_socket.name == "Normal"]
                assert len(base_links) == 1 and base_links[0].from_node == linear
                assert len(normal_links) == 1 and normal_links[0].from_node == ndiff
                assert nodes.get("T6_EXACT_SPECULAR_P") is not None
                assert nodes.get("T6_EXACT_REFLECTION_P0") is not None
                assert nodes.get("T6_EXACT_REFLECTION_P1") is not None
                assert nodes.get("T6_EXACT_REFLECTION_P2") is not None
                assert nodes.get("T6_EXACT_REFLECTION_P3") is not None
                assert nodes.get("T6_EXACT_REFLECTION_LOD") is not None
                assert nodes.get("T6_EXACT_REFLECTION_WEIGHT") is not None
                if family == lit_backend.HERO:
                    detail = next(
                        by_slot[int(s["slotIndex"])] for s in material_plan["nativeTextureSlots"]
                        if s.get("nativeName") == "Normal_Detail_Map"
                    )
                    vector_links = list(detail.inputs["Vector"].links)
                    assert len(vector_links) == 1
                    assert "detailUV = UV0*Normal_Detail_Scale" in vector_links[0].from_node.label
            else:
                assert family == lit_backend.CORNEA
                assert nodes.get("T6_EXACT_CORNEA_NSURFACE") is not None
                assert nodes.get("T6_EXACT_CORNEA_MASK_R") is not None
                assert nodes.get("T6_EXACT_CORNEA_BRIGHTNESS2") is not None
                assert nodes.get("T6_EXACT_CORNEA_LOBE1_LOWER") is not None
                assert nodes.get("T6_EXACT_CORNEA_LOBE1_UPPER") is not None
                assert nodes.get("T6_EXACT_CORNEA_LOBE2_LOWER") is not None
                assert nodes.get("T6_EXACT_CORNEA_LOBE2_UPPER") is not None
                assert "CORNEA AUTHORING SUBSTITUTE" in preview.label
                assert mat.get("t6_global_runtime_lighting_inputs_bound") is False
                assert mat.get("t6_complete_retail_pixel_output") is False

            proof_rows.append({
                "material": name,
                "family": family,
                "sourceNodes": len(sources),
                "constantNodes": len(constants),
                "completeRetailPixelOutput": False,
            })

        assert total_sources == 20
        assert total_constants == 22
        assert total_nonlit == 5

        blend = Path("/tmp/T6_BLENDER_SEAL6_LIT_NODES_V1_TEST.blend")
        report = Path("/tmp/T6_BLENDER_SEAL6_LIT_NODES_V1_TEST.json")
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        out = {
            "format": "t6-blender-seal6-lit-nodes-v1-test",
            "blenderVersion": bpy.app.version_string,
            "summary": result["summary"],
            "materials": proof_rows,
            "proofBoundary": (
                "Synthetic bpy execution canary over the exact committed SEAL6 family equations. "
                "PNG bytes are synthetic SHA-checked transport fixtures; this validates Blender node lowering, "
                "not retail texture payload identity. Complete retail output remains false because runtime global "
                "lighting/probe/fog/HDR inputs are intentionally unbound."
            ),
        }
        report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("T6_BLENDER_SEAL6_LIT_NODES_V1_TEST=" + json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
