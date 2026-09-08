#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import bpy

import t6_blender_seal6_role_nodes_v1 as role_backend
import t6_blender_seal6_lit_nodes_v1 as lit_backend
import t6_blender_seal6_pipeline_state_v1 as pipeline_backend
import t6_seal6_blender_shader_plan_v1 as shader_planner
import t6_seal6_lit_pipeline_state_v1 as pipeline_planner
from test_t6_blender_seal6_lit_nodes_v1 import enrich_role_fixture
from test_t6_seal6_blender_shader_plan_v1 import fixtures, SEMANTICS
from test_t6_seal6_lit_pipeline_state_v1 import add_pipeline_state_fixture


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with tempfile.TemporaryDirectory(prefix="t6-seal6-pipeline-blender-") as td:
        root = Path(td)
        role, conflict = fixtures()
        enrich_role_fixture(role, root)
        add_pipeline_state_fixture(conflict)
        for row in role["materials"]:
            bpy.data.materials.new(row["material"])

        role_backend.validate_plan(role)
        role_backend.compile_plan(role, root)
        shader_plan = shader_planner.build(role, conflict, SEMANTICS)
        lit_backend.validate_plan(shader_plan)
        lit_backend.compile_plan(shader_plan)
        pipeline = pipeline_planner.build(shader_plan, conflict)
        pipeline_backend.validate_pipeline(pipeline)
        result = pipeline_backend.compile_report(pipeline)

        assert result["summary"] == {
            "materialsCompiled": 5,
            "exactD3DPipelineStatesPreserved": 5,
            "litOpaqueMaterials": 4,
            "litTransMaterials": 1,
            "allBlenderPipelineMappingsExplicitlyAuthoringOnly": True,
            "completeRetailPixelOutput": False,
        }

        rows = []
        for pipeline_row in pipeline["materials"]:
            name = pipeline_row["material"]
            mat = bpy.data.materials[name]
            state = json.loads(mat["t6_ordinary_lit_pipeline_state_json"])
            mapping = json.loads(mat["t6_blender_pipeline_authoring_mapping_json"])
            assert mat.get("t6_pipeline_state_exact_metadata") is True
            assert mat.get("t6_blender_pipeline_authoring_mapping_exact") is False
            assert mat.get("t6_ordinary_lit_technique_type") == "lit"
            assert int(mat.get("t6_ordinary_lit_technique_type_index")) == 4
            assert int(mat.get("t6_ordinary_lit_state_bits_entry_value")) == int(pipeline_row["stateBitsEntryValue"])
            assert mat.get("t6_ordinary_lit_pipeline_state_sha256") == pipeline_row["selectedStateBitsSha256"]
            assert state == pipeline_row["selectedStateBits"]
            assert mat.get("t6_complete_retail_pixel_output") is False
            assert state["cullFace"] == "back"
            if hasattr(mat, "use_backface_culling"):
                assert mat.use_backface_culling is True

            if name == "mc/mtl_gen_eye_cornea":
                assert pipeline_row["cameraRegion"] == "litTrans"
                assert state["alphaTest"] == "gt0"
                assert state["srcBlendRgb"] == "srcalpha"
                assert state["dstBlendRgb"] == "invsrcalpha"
                assert state["srcBlendAlpha"] == "invdestalpha"
                assert state["dstBlendAlpha"] == "one"
                assert state["depthWrite"] is False
                assert mapping["blend"] != "opaque-authoring"
            else:
                assert pipeline_row["cameraRegion"] == "litOpaque"
                assert state["blendOpRgb"] == "disabled"
                assert state["depthWrite"] is True
                assert mapping["blend"] == "opaque-authoring"

            rows.append({
                "material": name,
                "cameraRegion": pipeline_row["cameraRegion"],
                "stateBitsEntryValue": pipeline_row["stateBitsEntryValue"],
                "selectedStateBitsSha256": pipeline_row["selectedStateBitsSha256"],
                "authoringMapping": mapping,
                "completeRetailPixelOutput": False,
            })

        blend = Path("/tmp/T6_BLENDER_SEAL6_PIPELINE_STATE_V1_TEST.blend")
        report = Path("/tmp/T6_BLENDER_SEAL6_PIPELINE_STATE_V1_TEST.json")
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        out = {
            "format": "t6-blender-seal6-pipeline-state-v1-test",
            "blenderVersion": bpy.app.version_string,
            "summary": result["summary"],
            "materials": rows,
            "proofBoundary": (
                "Synthetic bpy execution canary. Exact T6 ordinary-lit selected stateBits are preserved as metadata. "
                "Blender cull/transparency settings are tested only as explicitly non-authoritative authoring mappings."
            ),
        }
        report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("T6_BLENDER_SEAL6_PIPELINE_STATE_V1_TEST=" + json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
