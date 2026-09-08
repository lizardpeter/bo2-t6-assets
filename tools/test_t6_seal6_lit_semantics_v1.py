#!/usr/bin/env python3
from __future__ import annotations

import unittest

from t6_seal6_lit_semantics_v1 import (
    EXPECTED_ARGS,
    FAMILY_PAIRS,
    cornea_sharp_window,
    cornea_side_gate,
    saturate,
)


def smooth_ref(x: float) -> float:
    t = min(max(x, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


class Seal6LitSemanticsTests(unittest.TestCase):
    def test_cornea_sharp_window_matches_translated_register_arithmetic(self) -> None:
        cases = [
            (0.0, 0.0), (0.25, 0.2), (0.55, 0.35), (0.72, 0.5),
            (0.81, 0.7), (0.95, 0.9), (1.0, 0.25),
        ]
        for power_term, sharpness in cases:
            a = 1.0 - sharpness
            upper = a * 0.18 + 0.72
            lower = -a * 0.18 + 0.72
            inv_range = 1.0 / (upper - lower)
            reference = smooth_ref((power_term - lower) * inv_range)
            self.assertAlmostEqual(cornea_sharp_window(power_term, sharpness), reference, places=14)

    def test_cornea_side_gate_matches_translated_smoothstep_sequence(self) -> None:
        for ndot in (-1.0, -0.2, -0.1, 0.0, 0.2, 0.7, 1.0):
            reference = smooth_ref((ndot + 0.2) * 5.0)
            self.assertAlmostEqual(cornea_side_gate(ndot), reference, places=14)

    def test_saturate_reference(self) -> None:
        self.assertEqual(saturate(-2.0), 0.0)
        self.assertEqual(saturate(0.25), 0.25)
        self.assertEqual(saturate(4.0), 1.0)

    def test_cornea_preserves_literal_oat_argument_order(self) -> None:
        self.assertEqual(
            EXPECTED_ARGS["mc_sw4_3d_char_eye_cornea_2eww29wu"],
            [
                "Mask", "Surface_Normal_Map", "Hightlight_1_Size",
                "Highlight_2_Brightness", "Highlight_1_Sharpness",
                "Highlight_2_Size", "Highlight_2_Sharpness",
                "Highlight_1_Brightness", "OverallBrightness",
            ],
        )

    def test_cornea_family_is_not_skin_shader_pair(self) -> None:
        cornea = FAMILY_PAIRS["mc_sw4_3d_char_eye_cornea_2eww29wu"]
        hero = FAMILY_PAIRS["mc_sw4_3d_char_skin_hero_9949fq1j"]
        standard = FAMILY_PAIRS["mc_sw4_3d_char_skin_j92387z3"]
        self.assertNotEqual(cornea[0], hero[0])
        self.assertNotEqual(cornea[1], hero[1])
        self.assertNotEqual(cornea[1], standard[1])
        self.assertNotIn("SpecularAndGloss", EXPECTED_ARGS["mc_sw4_3d_char_eye_cornea_2eww29wu"])
        self.assertNotIn("Reflection_Amount", EXPECTED_ARGS["mc_sw4_3d_char_eye_cornea_2eww29wu"])


if __name__ == "__main__":
    unittest.main()
