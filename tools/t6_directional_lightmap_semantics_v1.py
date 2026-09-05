#!/usr/bin/env python3
"""Renderer-neutral T6 layered directional-lightmap semantics.

This module transcribes the exact slot-4 retail equation proven in
`T6_RETAIL_LAYERED_DIRECTIONAL_LIGHTMAP_V1.json` across all 173 unique retained
layered pixel shaders. It intentionally stops before environment/reflection and
other downstream lighting whose physical interpretation is not yet closed.

Normalized renderer contract:
- input lightmap UV is glTF `TEXCOORD_1` (the T6 shader's packed lightmap pair),
- `lightmapSamplerSecondary` is treated as a vertically stacked 3-row texture,
- sampled RGBA values are passed exactly to the equation below,
- N is the already reconstructed/normalized layered world normal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


ALPHA_EPSILON = 1.0e-6

EQUATION = {
    "row0": "sample(secondary, (u, v/3))",
    "row1": "sample(secondary, (u, v/3 + 1/3))",
    "row2": "sample(secondary, (u, v/3 + 2/3))",
    "direction": "2 * row2.rgb - 1",
    "rgb": "row0.rgb/(row0.a+1e-6) + row1.rgb/(row1.a+1e-6) * saturate(dot(direction,N))",
}


@dataclass(frozen=True)
class DirectionalLightmapRows:
    row0_uv: tuple[float, float]
    row1_uv: tuple[float, float]
    row2_uv: tuple[float, float]


def directional_lightmap_row_uvs(lightmap_uv: Sequence[float]) -> DirectionalLightmapRows:
    """Return the exact three `lightmapSamplerSecondary` coordinates."""
    if len(lightmap_uv) != 2:
        raise ValueError("lightmap UV must contain exactly two components")
    u = float(lightmap_uv[0])
    third_v = float(lightmap_uv[1]) / 3.0
    return DirectionalLightmapRows(
        row0_uv=(u, third_v),
        row1_uv=(u, third_v + 1.0 / 3.0),
        row2_uv=(u, third_v + 2.0 / 3.0),
    )


def decode_direction(row2_rgba: Sequence[float]) -> tuple[float, float, float]:
    """Retail signed direction decode: `2 * row2.rgb - 1`."""
    if len(row2_rgba) != 4:
        raise ValueError("directional lightmap row2 must be RGBA")
    return tuple(2.0 * float(row2_rgba[i]) - 1.0 for i in range(3))


def saturate(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def directional_factor(row2_rgba: Sequence[float], normal: Sequence[float]) -> float:
    """Exact `saturate(dot(direction, N))`; direction is NOT renormalized."""
    if len(normal) != 3:
        raise ValueError("normal must contain exactly three components")
    direction = decode_direction(row2_rgba)
    return saturate(sum(direction[i] * float(normal[i]) for i in range(3)))


def normalize_lightmap_rgb(row_rgba: Sequence[float]) -> tuple[float, float, float]:
    """Exact row0/row1 RGB alpha-biased normalization."""
    if len(row_rgba) != 4:
        raise ValueError("directional lightmap row must be RGBA")
    divisor = float(row_rgba[3]) + ALPHA_EPSILON
    return tuple(float(row_rgba[i]) / divisor for i in range(3))


def evaluate_directional_lightmap(
    row0_rgba: Sequence[float],
    row1_rgba: Sequence[float],
    row2_rgba: Sequence[float],
    normal: Sequence[float],
) -> tuple[float, float, float]:
    """Evaluate the bytecode-proven directional-lightmap RGB expression."""
    row0 = normalize_lightmap_rgb(row0_rgba)
    row1 = normalize_lightmap_rgb(row1_rgba)
    factor = directional_factor(row2_rgba, normal)
    return tuple(row0[i] + row1[i] * factor for i in range(3))


def renderer_contract() -> dict:
    return {
        "lightmapUvAttribute": "TEXCOORD_1",
        "sampler": "lightmapSamplerSecondary",
        "verticalRows": 3,
        "alphaEpsilon": ALPHA_EPSILON,
        "directionRenormalized": False,
        "normalInput": "normalized fully composed layered normal",
        "proofBoundary": (
            "exact row coordinates, alpha-biased row normalization, signed row2 direction, "
            "saturated dot and final RGB mad; environment/reflection lighting remains separate"
        ),
    }
