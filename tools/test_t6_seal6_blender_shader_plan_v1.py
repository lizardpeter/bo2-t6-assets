#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from t6_seal6_blender_shader_plan_v1 import (
    Seal6BlenderShaderPlanError,
    build,
)

SEMANTICS = json.loads(Path("manifests/render/T6_RETAIL_SEAL6_LIT_SEMANTICS_V1.json").read_text())

MATERIALS = [
    (
        "mc/mtl_c_usa_milcas_mcknight_head_camo",
        "mc_sw4_3d_char_skin_hero_9949fq1j",
        [None, "SpecularAndGloss", "Normal_Map", "Normal_Detail_Map", "Diffuse_Map"],
        [
            ("Reflection_Amount", [1.0, 0.0, 0.0, 1.0]),
            ("Normal_Detail_Scale", [8.0, 0.0, 0.0, 1.0]),
            ("Specular_Amount", [1.5, 0.0, 0.0, 1.0]),
            ("Diffuse_Normal_Height", [0.800000011920929, 0.0, 0.0, 1.0]),
        ],
        2,
        False,
    ),
    (
        "mc/mtl_c_usa_mp_seal6_smg_arms",
        "mc_sw4_3d_char_skin_j92387z3",
        [None, "SpecularAndGloss", "Normal_Map", "Diffuse_Map"],
        [
            ("Reflection_Amount", [1.0, 0.0, 0.0, 1.0]),
            ("Diffuse_Normal_Height_Facing", [0.800000011920929, 0.0, 0.0, 1.0]),
            ("Specular_Amount", [1.5, 0.0, 0.0, 1.0]),
        ],
        1,
        True,
    ),
    (
        "mc/mtl_gen_eye_cornea",
        "mc_sw4_3d_char_eye_cornea_2eww29wu",
        ["Mask", "Surface_Normal_Map", "radiantDiffuseMap"],
        [
            ("Hightlight_1_Size", [0.011699999682605267, 0.0, 0.0, 1.0]),
            ("Highlight_2_Brightness", [1.0, 0.0, 0.0, 1.0]),
            ("Fill_Direction2", [-66.0, -47.0, -167.0, 1.0]),
            ("Highlight_1_Sharpness", [0.0, 0.0, 0.0, 1.0]),
            ("Fill_Direction", [73.0, 52.0, -167.87899780273438, 1.0]),
            ("Highlight_2_Size", [0.0020000000949949026, 0.0, 0.0, 1.0]),
            ("Highlight_2_Sharpness", [-2.880000114440918, 0.0, 0.0, 1.0]),
            ("Highlight_1_Brightness", [1.0, 0.0, 0.0, 1.0]),
            ("OverallBrightness", [0.8899999856948853, 0.0, 0.0, 1.0]),
        ],
        1,
        True,
    ),
    (
        "mc/mtl_gen_eye_iris_green",
        "mc_sw4_3d_char_skin_j92387z3",
        [None, "SpecularAndGloss", "Normal_Map", "Diffuse_Map"],
        [
            ("Reflection_Amount", [1.0, 0.0, 0.0, 1.0]),
            ("Diffuse_Normal_Height_Facing", [0.6499999761581421, 0.0, 0.0, 1.0]),
            ("Specular_Amount", [1.5, 0.0, 0.0, 1.0]),
        ],
        1,
        True,
    ),
    (
        "mc/mtl_c_gen_insidemouth",
        "mc_sw4_3d_char_skin_j92387z3",
        [None, "SpecularAndGloss", "Normal_Map", "Diffuse_Map"],
        [
            ("Reflection_Amount", [1.0, 0.0, 0.0, 1.0]),
            ("Diffuse_Normal_Height_Facing", [0.6499999761581421, 0.0, 0.0, 1.0]),
            ("Specular_Amount", [1.5, 0.0, 0.0, 1.0]),
        ],
        1,
        True,
    ),
]


def fixtures():
    role = {
        "format": "t6-seal6-blender-role-plan-v1",
        "summary": {"nativeTextureSlots": 20, "allNativeTextureSlotsRepresented": True},
        "materials": [],
    }
    conflict = {"format": "t6-seal6-native-material-conflict-report-v1", "materials": []}
    image_counter = 0
    for material, techset, names, constants, copies, owner_resolved in MATERIALS:
        slots = []
        for idx, name in enumerate(names):
            slots.append({
                "slotIndex": idx,
                "semantic": "normalMap" if name in {"Normal_Map", "Normal_Detail_Map", "Surface_Normal_Map"} else "specularMap" if name == "SpecularAndGloss" else "colorMap",
                "nativeName": name,
                "image": f"image_{image_counter}",
                "exactRetailPayload": {"exactKeyValidated": True, "crc29Validated": True, "pngSha256": "a" * 64, "pngFile": f"{image_counter}.png"},
            })
            image_counter += 1
        role["materials"].append({"material": material, "techniqueSet": techset, "nativeSlots": slots})
        crows = [{"name": name, "literal": literal} for name, literal in constants]
        conflict["materials"].append({
            "material": material,
            "physicalCopyCount": copies,
            "activeRetailClientOwnerResolved": owner_resolved,
            "techniqueSetIdenticalAcrossCopies": True,
            "copies": [
                {"techniqueSet": techset, "nativeMaterialRecord": {"constants": copy.deepcopy(crows)}}
                for _ in range(copies)
            ],
        })
    return role, conflict


class Seal6BlenderShaderPlanTests(unittest.TestCase):
    def test_exact_pass_usage_split_and_argument_closure(self):
        role, conflict = fixtures()
        out = build(role, conflict, SEMANTICS)
        self.assertEqual(out["summary"]["nativeTextureSlotsPreserved"], 20)
        self.assertEqual(out["summary"]["ordinaryLitReferencedTextureSlots"], 15)
        self.assertEqual(out["summary"]["preservedNativeTextureSlotsNotReferencedByOrdinaryLit"], 5)
        self.assertEqual(out["summary"]["nativeMaterialConstants"], 22)
        self.assertEqual(out["summary"]["exactVsPsMaterialArgumentBindings"], 37)
        self.assertTrue(out["summary"]["allOrdinaryLitMaterialArgumentsClosed"])
        self.assertTrue(out["summary"]["exactOrdinaryLitEquationsClosed"])
        self.assertFalse(out["summary"]["globalRuntimeLightingInputsBoundInBlender"])
        self.assertFalse(out["summary"]["completeRetailPixelOutputInBlender"])

        unused = []
        for material in out["materials"]:
            for slot in material["nativeTextureSlots"]:
                if not slot["ordinaryLitBinding"]["referenced"]:
                    unused.append((material["material"], slot["nativeName"], slot["slotIndex"]))
        self.assertEqual(
            unused,
            [
                ("mc/mtl_c_usa_milcas_mcknight_head_camo", None, 0),
                ("mc/mtl_c_usa_mp_seal6_smg_arms", None, 0),
                ("mc/mtl_gen_eye_cornea", "radiantDiffuseMap", 2),
                ("mc/mtl_gen_eye_iris_green", None, 0),
                ("mc/mtl_c_gen_insidemouth", None, 0),
            ],
        )

    def test_cornea_fill_constants_are_exact_vertex_arguments(self):
        role, conflict = fixtures()
        out = build(role, conflict, SEMANTICS)
        eye = next(r for r in out["materials"] if r["material"] == "mc/mtl_gen_eye_cornea")
        constants = {r["name"]: r for r in eye["nativeConstants"]}
        self.assertEqual(constants["Fill_Direction"]["ordinaryLitBinding"]["stage"], "vertex")
        self.assertEqual(constants["Fill_Direction2"]["ordinaryLitBinding"]["stage"], "vertex")
        self.assertEqual(constants["OverallBrightness"]["ordinaryLitBinding"]["stage"], "pixel")

    def test_head_constant_divergence_across_physical_copies_fails(self):
        role, conflict = fixtures()
        head = conflict["materials"][0]
        head["copies"][1]["nativeMaterialRecord"]["constants"][0]["literal"][0] = 0.5
        with self.assertRaises(Seal6BlenderShaderPlanError):
            build(role, conflict, SEMANTICS)

    def test_missing_hero_detail_normal_argument_fails(self):
        role, conflict = fixtures()
        head = role["materials"][0]
        head["nativeSlots"][3]["nativeName"] = None
        with self.assertRaises(Seal6BlenderShaderPlanError):
            build(role, conflict, SEMANTICS)

    def test_unreferenced_rim_slot_is_preserved_not_guessed(self):
        role, conflict = fixtures()
        out = build(role, conflict, SEMANTICS)
        arms = next(r for r in out["materials"] if r["material"] == "mc/mtl_c_usa_mp_seal6_smg_arms")
        rim = arms["nativeTextureSlots"][0]
        self.assertFalse(rim["ordinaryLitBinding"]["referenced"])
        self.assertIsNone(rim["ordinaryLitBinding"]["shaderArgument"])
        self.assertIn("preserved-native-slot", rim["ordinaryLitBinding"]["status"])


if __name__ == "__main__":
    unittest.main()
