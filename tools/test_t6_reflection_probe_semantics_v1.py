#!/usr/bin/env python3
from __future__ import annotations

from math import isclose, sqrt

from t6_reflection_probe_semantics_v1 import (
    ANGULAR_EXP_SCALE,
    IMMEDIATE_MATERIAL_COLOR,
    MIP_AFFINE_FORMS,
    PROBE_ALPHA_BIAS,
    ReflectionProbeSemanticError,
    angular_e_from_normalized_pair,
    decode_probe_rgb,
    evaluate_shared_4_minus_4x_reflection,
    immediate_material_color,
    reflection_cube_coordinate,
    renderer_contract,
    sample_b_bias,
    sample_l_lod,
    shared_parameter_q,
    shared_parameter_reflection_factor,
    squared_material_color,
)


def _close(actual, expected, eps=1e-8):
    assert len(actual) == len(expected)
    assert all(isclose(float(a), float(b), abs_tol=eps) for a, b in zip(actual, expected)), (actual, expected)


def main() -> int:
    # A=(1,0,0), B=(1,1,0)/sqrt(2): exact reflect form flips B.x.
    s = sqrt(0.5)
    _close(reflection_cube_coordinate((2, 0, 0), (3, 3, 0)), (-s, s, 0.0))

    decoded = decode_probe_rgb((0.2, 0.4, 0.6, 0.5))
    _close(decoded, tuple(v / (0.5 + PROBE_ALPHA_BIAS) for v in (0.2, 0.4, 0.6)))

    assert isclose(sample_l_lod(form="4_minus_4x", x=0.25), 3.0)
    assert isclose(sample_l_lod(form="0_475x", x=2.0), MIP_AFFINE_FORMS["0_475x"][0] * 2.0)
    assert isclose(sample_l_lod(form="0_25x_plus_0_75", x=1.0), 1.0)
    assert isclose(sample_l_lod(form="compiled_zero", x=99.0), 0.0)
    assert isclose(sample_l_lod(form="lod_0_8"), 0.8, abs_tol=1e-7)
    assert isclose(sample_l_lod(form="lod_2_4"), 2.4, abs_tol=1e-7)
    assert isclose(sample_b_bias(), -3.0)

    try:
        sample_l_lod(form="lod_4", x=0.2)
    except ReflectionProbeSemanticError:
        pass
    else:
        raise AssertionError("literal LOD accepted an x input")

    try:
        sample_l_lod(form="unknown", x=0.2)
    except ReflectionProbeSemanticError:
        pass
    else:
        raise AssertionError("unknown mip form did not fail closed")

    # Opposed normalized pair gives D=1 in dot(U,-V).
    e = angular_e_from_normalized_pair((1, 0, 0), (-1, 0, 0))
    assert isclose(e, 2.0 ** ANGULAR_EXP_SCALE, rel_tol=1e-12)
    # Same-direction pair gives D=0 -> E=1.
    assert isclose(angular_e_from_normalized_pair((1, 0, 0), (1, 0, 0)), 1.0)

    try:
        angular_e_from_normalized_pair((2, 0, 0), (1, 0, 0))
    except ReflectionProbeSemanticError:
        pass
    else:
        raise AssertionError("angular evaluator accepted non-normalized U")

    _close(squared_material_color((0.2, 0.5, 1.0)), (0.04, 0.25, 1.0))
    _close(immediate_material_color(), (IMMEDIATE_MATERIAL_COLOR,) * 3)

    q0 = shared_parameter_q(0.0)
    _close(q0, (0.0, 0.0, -0.015625, 0.75))
    q1 = shared_parameter_q(1.0)
    assert q1[3] == 1.0

    # With x=0, Qy=0 => C=0 and F=Qz=-0.015625.
    # The exact formula still saturates the result lane-by-lane.
    factor = shared_parameter_reflection_factor(x=0.0, angular_e=1.0, p_rgb=(0.0, 0.5, 1.0))
    _close(factor, (0.0, 0.3671875, 0.75))

    result = evaluate_shared_4_minus_4x_reflection(
        raw_a=(1, 0, 0),
        raw_b=(0, 1, 0),
        probe_rgba=(0.25, 0.5, 1.0, 0.5),
        x=0.25,
        p_rgb=(0.04, 0.04, 0.04),
    )
    assert result["family"] == "shared_4_minus_4x"
    _close(result["cubeCoordinate"], (0.0, 1.0, 0.0))
    assert isclose(result["lod"], 3.0)
    _close(
        result["reflectionRgb"],
        tuple(result["decodedProbeRgb"][i] * result["reflectionFactorRgb"][i] for i in range(3)),
    )

    contract = renderer_contract()
    assert contract["allFetchCount"] == 5888
    assert contract["shared4Minus4xFetchCount"] == 4236
    assert contract["measuredPhysicalFamilyClosure"]["closedFetchCount"] == 5823
    assert contract["measuredPhysicalFamilyClosure"]["remainingFetchCount"] == 65

    print("PASS: T6 reflection probe semantics v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
