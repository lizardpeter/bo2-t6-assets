#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

import t6_seal6_blender_shader_plan_v1 as shader_planner
from t6_seal6_lit_pipeline_state_v1 import (
    Seal6PipelineStateError,
    build,
    LIT_TYPE_INDEX,
    OPAQUE_STATE,
    CORNEA_STATE,
)
from test_t6_seal6_blender_shader_plan_v1 import fixtures, SEMANTICS


def add_pipeline_state_fixture(conflict: dict) -> None:
    for material in conflict["materials"]:
        name = material["material"]
        is_cornea = name == "mc/mtl_gen_eye_cornea"
        state = copy.deepcopy(CORNEA_STATE if is_cornea else OPAQUE_STATE)
        camera = "litTrans" if is_cornea else "litOpaque"
        sort_key = 40 if is_cornea else 4
        state_flags = 21 if is_cornea else 121
        surface_flags = 7602176 if is_cornea else 7340032
        state_index = 0 if is_cornea else 2
        for copy_row in material["copies"]:
            rec = copy_row["nativeMaterialRecord"]
            entries = [-1] * 36
            entries[LIT_TYPE_INDEX] = state_index
            if is_cornea:
                states = [copy.deepcopy(state)]
            else:
                states = [
                    {"fixture": "unused0"},
                    {"fixture": "unused1"},
                    copy.deepcopy(state),
                ]
            rec.update({
                "stateBitsEntry": entries,
                "stateBits": states,
                "cameraRegion": camera,
                "sortKey": sort_key,
                "stateFlags": state_flags,
                "surfaceFlags": surface_flags,
                "surfaceTypeBits": 64,
            })


def build_fixture():
    role, conflict = fixtures()
    add_pipeline_state_fixture(conflict)
    shader_plan = shader_planner.build(role, conflict, SEMANTICS)
    return shader_plan, conflict


class Seal6LitPipelineStateTests(unittest.TestCase):
    def test_exact_lit_state_selection(self):
        shader_plan, conflict = build_fixture()
        out = build(shader_plan, conflict)
        self.assertEqual(out["summary"]["techniqueType"], "lit")
        self.assertEqual(out["summary"]["techniqueTypeIndex"], 4)
        self.assertEqual(out["summary"]["pipelineStatesClosed"], 5)
        self.assertEqual(out["summary"]["uniqueSelectedStatePayloads"], 2)
        self.assertEqual(out["summary"]["litOpaqueMaterials"], 4)
        self.assertEqual(out["summary"]["litTransMaterials"], 1)
        self.assertTrue(out["summary"]["allSelectedStatesInvariantAcrossPhysicalCopies"])
        self.assertFalse(out["summary"]["completeRetailPixelOutputInBlender"])

        by_name = {row["material"]: row for row in out["materials"]}
        head = by_name["mc/mtl_c_usa_milcas_mcknight_head_camo"]
        self.assertEqual(head["stateBitsEntryValue"], 2)
        self.assertEqual(head["cameraRegion"], "litOpaque")
        self.assertEqual(head["selectedStateBits"], OPAQUE_STATE)
        self.assertFalse(head["activeRetailClientWholeMaterialOwnerResolved"])
        self.assertTrue(head["selectedStateInvariantAcrossPhysicalCopies"])

        eye = by_name["mc/mtl_gen_eye_cornea"]
        self.assertEqual(eye["stateBitsEntryValue"], 0)
        self.assertEqual(eye["cameraRegion"], "litTrans")
        self.assertEqual(eye["sortKey"], 40)
        self.assertEqual(eye["selectedStateBits"], CORNEA_STATE)
        self.assertEqual(eye["selectedStateBits"]["srcBlendRgb"], "srcalpha")
        self.assertEqual(eye["selectedStateBits"]["dstBlendRgb"], "invsrcalpha")
        self.assertEqual(eye["selectedStateBits"]["srcBlendAlpha"], "invdestalpha")
        self.assertEqual(eye["selectedStateBits"]["dstBlendAlpha"], "one")
        self.assertFalse(eye["selectedStateBits"]["depthWrite"])
        self.assertEqual(eye["selectedStateBits"]["alphaTest"], "gt0")

    def test_head_selected_state_divergence_fails(self):
        shader_plan, conflict = build_fixture()
        head = conflict["materials"][0]
        head["copies"][1]["nativeMaterialRecord"]["stateBits"][2]["depthWrite"] = False
        with self.assertRaises(Seal6PipelineStateError):
            build(shader_plan, conflict)

    def test_wrong_state_bits_entry_fails(self):
        shader_plan, conflict = build_fixture()
        arms = next(r for r in conflict["materials"] if r["material"] == "mc/mtl_c_usa_mp_seal6_smg_arms")
        arms["copies"][0]["nativeMaterialRecord"]["stateBitsEntry"][4] = 1
        with self.assertRaises(Seal6PipelineStateError):
            build(shader_plan, conflict)

    def test_cornea_opaque_substitution_fails(self):
        shader_plan, conflict = build_fixture()
        eye = next(r for r in conflict["materials"] if r["material"] == "mc/mtl_gen_eye_cornea")
        eye["copies"][0]["nativeMaterialRecord"]["stateBits"][0] = copy.deepcopy(OPAQUE_STATE)
        with self.assertRaises(Seal6PipelineStateError):
            build(shader_plan, conflict)


if __name__ == "__main__":
    unittest.main()
