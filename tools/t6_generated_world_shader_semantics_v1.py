#!/usr/bin/env python3
"""Source-backed semantics for T6 generated/layered GfxWorld materials.

This module intentionally contains no map-specific names or offsets. It encodes
rules recovered from retail T6 MaterialTechniqueSet names, world vertex streams,
and compiled DXBC shaders so map exporters/renderers can share one contract.

Important invariants:
- GfxPackedWorldVertex COLOR is shader layer-control data for generated world
  materials, not ordinary display tint.
- TEXCOORD_1 in the normalized glTF contract is reserved for T6 lightmap UV.
  Secondary material UVs are TEXCOORD_2/3/4.
- The secondary-stream normal-transform word is stored as bytes
  [m00, m11, m01, m10]. The shader consumes logical
  [m00, m01, m10, m11] as UNORM8 and converts with value*2-1.
- Diffuse A/B/M equations below are transcribed from retail compiled DXBC.
- Layered specular state is an ordered XYZW recurrence. Blend steps lerp the
  previous state toward the layer specular sample with the exact RGB compositor
  weight. Threshold steps select layer-vs-previous with the exact RGB threshold
  condition. This recurrence is proven across all retained layered-specular
  shaders and is not a generic PBR approximation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence


WEIGHT_CHANNEL = {1: "G", 2: "B", 3: "A"}
UV_ATTRIBUTE = {0: "TEXCOORD_0", 1: "TEXCOORD_2", 2: "TEXCOORD_3", 3: "TEXCOORD_4"}

DIFFUSE_EQUATIONS = {
    "add": "base.rgb + layer.rgb * layer.a * weight",
    "blend": "base.rgb + (layer.rgb - base.rgb) * layer.a * weight",
    "multiply": "base.rgb * (1 + weight * (layer.rgb - 1))",
}

SPECULAR_EQUATIONS = {
    "b": "prevSpecRGBA + (layerSpecRGBA - prevSpecRGBA) * exactRgbWeight",
    "t": "select(exactRgbThresholdCondition, layerSpecRGBA, prevSpecRGBA)",
}


@dataclass(frozen=True)
class GeneratedLayerToken:
    layer: int
    operation: str
    has_normal: bool
    has_specular: bool
    x_variant: bool


def parse_generated_layer_tokens(technique_set: str) -> list[GeneratedLayerToken]:
    """Parse secondary layer declarations from a T6 generated TechniqueSet.

    Examples:
      b1c1       -> blend layer 1
      b1c1n1s1   -> blend layer 1 + normal1 + specular1
      b1c1n1x1   -> blend layer 1 + normal1, x1 normal weighting variant
      m2c2       -> multiply layer 2

    Layer-0 tokens are base-mode declarations and are deliberately ignored.
    """
    out: list[GeneratedLayerToken] = []
    op_name = {"a": "add", "b": "blend", "m": "multiply"}
    for m in re.finditer(r"(?:^|_)([abm])(\d+)c\2([^_]*)", technique_set):
        layer = int(m.group(2))
        if layer == 0:
            continue
        tail = m.group(3)
        out.append(
            GeneratedLayerToken(
                layer=layer,
                operation=op_name[m.group(1)],
                has_normal=f"n{layer}" in tail,
                has_specular=f"s{layer}" in tail,
                x_variant=f"x{layer}" in tail,
            )
        )
    return out


def unpack_normal_transform_bytes(raw4: bytes) -> tuple[int, int, int, int]:
    """Convert T6 disk order to the logical four UNORM8 values seen by DXBC.

    Disk:    [m00, m11, m01, m10]
    Logical: [m00, m01, m10, m11]
    """
    if len(raw4) != 4:
        raise ValueError("normal transform must be exactly four bytes")
    return raw4[0], raw4[2], raw4[3], raw4[1]


def decode_normal_transform(raw4: bytes) -> tuple[tuple[float, float], tuple[float, float]]:
    """Decode the exact 2x2 matrix used by the T6 pixel shader."""
    q = unpack_normal_transform_bytes(raw4)
    f = tuple((v / 255.0) * 2.0 - 1.0 for v in q)
    return (f[0], f[1]), (f[2], f[3])


def transform_layer_normal_xy(layer_xy: tuple[float, float], matrix) -> tuple[float, float]:
    """Retail DXBC dp2 pair for a transformed secondary normal layer."""
    x, y = layer_xy
    (a, b), (c, d) = matrix
    return x * a + y * b, x * c + y * d


def normal_layer_weight(vertex_weight: float, color_layer_alpha: float, x_variant: bool) -> float:
    """Retail normal-layer weighting recovered from n1 vs n1x1 DXBC."""
    return vertex_weight if x_variant else vertex_weight * color_layer_alpha


def compose_diffuse(base, layer, weight: float, operation: str):
    """Reference scalar/vector implementation of the retail A/B/M diffuse ops.

    base/layer are 4-tuples; RGB is returned. Generated color composition is
    performed in the encoded texture domain in the retail shader before an
    explicit RGB square used by the later lighting path.
    """
    if operation == "add":
        return tuple(base[i] + layer[i] * layer[3] * weight for i in range(3))
    if operation == "blend":
        f = layer[3] * weight
        return tuple(base[i] + (layer[i] - base[i]) * f for i in range(3))
    if operation == "multiply":
        return tuple(base[i] * (1.0 + weight * (layer[i] - 1.0)) for i in range(3))
    raise ValueError(operation)


def technique_uses_x0_specular_fallback(technique_set: str) -> bool:
    """Return whether the no-base-spec fallback takes base color alpha.

    Retained slot-4 shaders prove that missing base specular maps begin with
    RGB=(0.2,0.2,0.2). The W channel begins from base color alpha for x0
    techniques and from 0 otherwise.
    """
    return re.search(r"(?:^|_)r0c0(?:n0)?x0(?:_|$)", technique_set) is not None


def specular_baseline(
    *,
    base_specular: Sequence[float] | None,
    base_color_alpha: float,
    technique_set: str,
) -> tuple[float, float, float, float]:
    """Construct the source-closed initial XYZW layered-specular state."""
    if base_specular is not None:
        if len(base_specular) != 4:
            raise ValueError("base_specular must contain exactly four channels")
        return tuple(float(v) for v in base_specular)
    return (
        0.2,
        0.2,
        0.2,
        float(base_color_alpha) if technique_uses_x0_specular_fallback(technique_set) else 0.0,
    )


def compose_specular(
    previous: Sequence[float],
    layer_specular: Sequence[float],
    *,
    operator: str,
    exact_rgb_weight: float | None = None,
    exact_rgb_threshold_condition: bool | None = None,
) -> tuple[float, float, float, float]:
    """Apply one exact ordered layered-specular XYZW recurrence step.

    ``operator='b'`` requires the already-resolved exact RGB compositor weight.
    ``operator='t'`` requires the already-resolved exact RGB threshold condition.
    Keeping those as explicit inputs prevents an adapter from silently guessing
    a per-shader weight/threshold DAG that has not been attached to its recipe.
    """
    if len(previous) != 4 or len(layer_specular) != 4:
        raise ValueError("specular states must contain exactly four channels")
    prev = tuple(float(v) for v in previous)
    layer = tuple(float(v) for v in layer_specular)
    if operator == "b":
        if exact_rgb_weight is None:
            raise ValueError("blend specular recurrence requires exact_rgb_weight")
        w = float(exact_rgb_weight)
        return tuple(prev[i] + (layer[i] - prev[i]) * w for i in range(4))
    if operator == "t":
        if exact_rgb_threshold_condition is None:
            raise ValueError("threshold specular recurrence requires exact_rgb_threshold_condition")
        return layer if bool(exact_rgb_threshold_condition) else prev
    raise ValueError(f"unsupported layered specular operator {operator!r}")


def normalized_gltf_vertex_contract() -> dict:
    return {
        "TEXCOORD_0": "materialUV0",
        "TEXCOORD_1": "lightmapUV",
        "TEXCOORD_2": "materialUV1",
        "TEXCOORD_3": "materialUV2",
        "TEXCOORD_4": "materialUV3",
        "_T6_LAYER_WEIGHTS": "retail generated-material control channels; G/B/A -> layers 1/2/3",
        "_T6_NORMAL_TRANSFORM_0": "logical UNORM8 [m00,m01,m10,m11]; shader decode attr*2-1",
    }
