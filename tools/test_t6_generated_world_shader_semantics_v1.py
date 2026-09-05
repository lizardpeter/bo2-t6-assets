#!/usr/bin/env python3
"""Small deterministic regression suite for the renderer-facing T6 layer contract."""
from __future__ import annotations

from math import isclose

from t6_generated_world_shader_semantics_v1 import (
    compose_diffuse,
    compose_diffuse_exact,
    compose_specular,
    decode_normal_transform,
    layer_weight_class,
    normal_layer_weight,
    parse_generated_layer_tokens,
    resolve_ordinary_layer_weight,
    specular_baseline,
    technique_uses_x0_specular_fallback,
    transform_layer_normal_xy,
    unpack_normal_transform_bytes,
)


def _close_tuple(actual, expected, eps=1e-9):
    assert len(actual) == len(expected)
    assert all(isclose(float(a), float(b), abs_tol=eps) for a, b in zip(actual, expected)), (actual, expected)


def main() -> int:
    tokens = parse_generated_layer_tokens("lit_sm_r0c0n0x0_b1c1n1s1v1_b2c2n2s2x2_m3c3")
    assert [(x.layer, x.operation, x.has_normal, x.has_specular, x.x_variant, x.height_variant) for x in tokens] == [
        (1, "blend", True, True, False, True),
        (2, "blend", True, True, True, False),
        (3, "multiply", False, False, False, False),
    ]
    assert [layer_weight_class(x) for x in tokens] == ["height", "vertex_only", "vertex_only"]

    threshold = parse_generated_layer_tokens("lit_sm_r0c0n0_t1c1n1s1")[0]
    assert threshold.operation == "threshold"
    assert layer_weight_class(threshold) == "threshold_alpha_vertex"
    assert resolve_ordinary_layer_weight(threshold, vertex_weight=0.8, layer_alpha=0.7) is True
    assert resolve_ordinary_layer_weight(threshold, vertex_weight=0.5, layer_alpha=0.7) is False

    ordinary_blend = parse_generated_layer_tokens("lit_sm_r0c0n0_b1c1")[0]
    assert isclose(resolve_ordinary_layer_weight(ordinary_blend, vertex_weight=0.6, layer_alpha=0.25), 0.15)
    x_blend = parse_generated_layer_tokens("lit_sm_r0c0n0_b1c1x1")[0]
    assert isclose(resolve_ordinary_layer_weight(x_blend, vertex_weight=0.6, layer_alpha=0.25), 0.6)
    height_blend = parse_generated_layer_tokens("lit_sm_r0c0n0_b1c1v1")[0]
    try:
        resolve_ordinary_layer_weight(height_blend, vertex_weight=0.6, layer_alpha=0.25)
    except ValueError:
        pass
    else:
        raise AssertionError("height layer accepted a guessed non-DAG weight")
    assert isclose(resolve_ordinary_layer_weight(height_blend, vertex_weight=0.6, layer_alpha=0.25, exact_height_weight=0.42), 0.42)

    raw = bytes((255, 255, 128, 128))
    assert unpack_normal_transform_bytes(raw) == (255, 128, 128, 255)
    matrix = decode_normal_transform(raw)
    _close_tuple(matrix[0], (1.0, 128.0 / 255.0 * 2.0 - 1.0))
    _close_tuple(matrix[1], (128.0 / 255.0 * 2.0 - 1.0, 1.0))
    transformed = transform_layer_normal_xy((0.25, -0.5), ((0.0, -1.0), (1.0, 0.0)))
    _close_tuple(transformed, (0.5, 0.25))

    assert isclose(normal_layer_weight(0.6, 0.25, False), 0.15)
    assert isclose(normal_layer_weight(0.6, 0.25, True), 0.6)

    base = (0.2, 0.4, 0.6, 1.0)
    layer = (0.8, 0.2, 0.4, 0.5)
    _close_tuple(compose_diffuse(base, layer, 0.25, "add"), (0.3, 0.425, 0.65))
    _close_tuple(compose_diffuse(base, layer, 0.25, "blend"), (0.275, 0.375, 0.575))
    _close_tuple(compose_diffuse(base, layer, 0.25, "multiply"), (0.19, 0.32, 0.51))
    _close_tuple(compose_diffuse_exact(base, layer, operation="blend", exact_weight=0.6), (0.56, 0.28, 0.48))
    _close_tuple(compose_diffuse_exact(base, layer, operation="threshold", exact_threshold_condition=True), layer[:3])
    _close_tuple(compose_diffuse_exact(base, layer, operation="threshold", exact_threshold_condition=False), base[:3])

    assert technique_uses_x0_specular_fallback("lit_sm_r0c0x0_b1c1n1s1")
    assert technique_uses_x0_specular_fallback("lit_sm_r0c0n0x0_b1c1s1")
    assert not technique_uses_x0_specular_fallback("lit_sm_r0c0n0_b1c1n1s1")

    _close_tuple(
        specular_baseline(
            base_specular=None,
            base_color_alpha=0.7,
            technique_set="lit_sm_r0c0x0_b1c1n1s1",
        ),
        (0.2, 0.2, 0.2, 0.7),
    )
    _close_tuple(
        specular_baseline(
            base_specular=None,
            base_color_alpha=0.7,
            technique_set="lit_sm_r0c0n0_b1c1n1s1",
        ),
        (0.2, 0.2, 0.2, 0.0),
    )
    explicit = (0.1, 0.3, 0.5, 0.9)
    assert specular_baseline(
        base_specular=explicit,
        base_color_alpha=0.2,
        technique_set="lit_sm_r0c0x0_b1c1s1",
    ) == explicit

    prev = (0.2, 0.4, 0.6, 0.8)
    spec = (1.0, 0.0, 0.5, 0.2)
    _close_tuple(
        compose_specular(prev, spec, operator="b", exact_rgb_weight=0.25),
        (0.4, 0.3, 0.575, 0.65),
    )
    assert compose_specular(prev, spec, operator="t", exact_rgb_threshold_condition=True) == spec
    assert compose_specular(prev, spec, operator="t", exact_rgb_threshold_condition=False) == prev

    try:
        compose_specular(prev, spec, operator="b")
    except ValueError:
        pass
    else:
        raise AssertionError("blend recurrence accepted missing exact weight")

    try:
        compose_specular(prev, spec, operator="t")
    except ValueError:
        pass
    else:
        raise AssertionError("threshold recurrence accepted missing condition")

    print("PASS: T6 generated world shader semantics v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
