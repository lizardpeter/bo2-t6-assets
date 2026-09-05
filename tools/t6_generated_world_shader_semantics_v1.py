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
- Layer color composition is an ordered A/B/M/T recurrence. The scalar weight
  dispatcher is source-closed for ordinary alpha/vertex/x/threshold cases.
  vN height weights remain exact per-shader DAGs and MUST be supplied by the
  recipe; this module deliberately does not guess a universal height formula.
- Layered specular state is an ordered XYZW recurrence. Blend steps lerp the
  previous state toward the layer specular sample with the exact RGB compositor
  weight. Threshold steps select layer-vs-previous with the exact RGB threshold
  condition. This recurrence is proven across all retained layered-specular
  shaders and is not a generic PBR approximation.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence


WEIGHT_CHANNEL = {1: "G", 2: "B", 3: "A"}
UV_ATTRIBUTE = {0: "TEXCOORD_0", 1: "TEXCOORD_2", 2: "TEXCOORD_3", 3: "TEXCOORD_4"}

DIFFUSE_EQUATIONS = {
    "add": "prev.rgb + layer.rgb * exactWeight",
    "blend": "prev.rgb + (layer.rgb - prev.rgb) * exactWeight",
    "multiply": "prev.rgb * (1 + (layer.rgb - 1) * exactWeight)",
    "threshold": "select(exactThresholdCondition, layer.rgb, prev.rgb)",
}

WEIGHT_DISPATCH = {
    "add": "alpha_vertex",
    "blend": "vN -> height; else xN -> vertex_only; else alpha_vertex",
    "multiply": "vertex_only",
    "threshold": "threshold_alpha_vertex",
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
    height_variant: bool


def parse_generated_layer_tokens(technique_set: str) -> list[GeneratedLayerToken]:
    """Parse secondary layer declarations from a T6 generated TechniqueSet.

    Examples:
      b1c1       -> blend layer 1
      b1c1n1s1   -> blend layer 1 + normal1 + specular1
      b1c1n1x1   -> blend layer 1 + normal1, x1 vertex-only weighting variant
      b1c1n1s1v1 -> blend layer 1 + exact per-shader height weighting
      m2c2       -> multiply layer 2
      t2c2       -> threshold-select layer 2

    Layer-0 tokens are base-mode declarations and are deliberately ignored.
    """
    out: list[GeneratedLayerToken] = []
    op_name = {"a": "add", "b": "blend", "m": "multiply", "t": "threshold"}
    for m in re.finditer(r"(?:^|_)([abmt])(\d+)c\2([^_]*)", technique_set):
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
                height_variant=f"v{layer}" in tail,
            )
        )
    return out


def layer_weight_class(token: GeneratedLayerToken) -> str:
    """Source-closed scalar-weight dispatcher for one layer token."""
    if token.operation == "add":
        return "alpha_vertex"
    if token.operation == "blend":
        if token.height_variant:
            return "height"
        if token.x_variant:
            return "vertex_only"
        return "alpha_vertex"
    if token.operation == "multiply":
        return "vertex_only"
    if token.operation == "threshold":
        return "threshold_alpha_vertex"
    raise ValueError(token.operation)


def resolve_ordinary_layer_weight(
    token: GeneratedLayerToken,
    *,
    vertex_weight: float,
    layer_alpha: float,
    exact_height_weight: float | None = None,
):
    """Resolve the scalar/condition for a source-closed layer step.

    Height variants are never simplified. A caller must provide the exact
    per-shader vN DAG result from its shader recipe.
    """
    cls = layer_weight_class(token)
    if cls == "alpha_vertex":
        return float(layer_alpha) * float(vertex_weight)
    if cls == "vertex_only":
        return float(vertex_weight)
    if cls == "threshold_alpha_vertex":
        return float(layer_alpha) * float(vertex_weight) >= 0.5
    if cls == "height":
        if exact_height_weight is None:
            raise ValueError("vN height layer requires exact_height_weight from the retained shader recipe")
        return float(exact_height_weight)
    raise ValueError(cls)


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


def compose_diffuse_exact(previous, layer, *, operation: str, exact_weight=None, exact_threshold_condition=None):
    """Apply one exact ordered RGB compositor step.

    ``exact_weight`` is the post-dispatch scalar. For threshold mode the caller
    supplies ``exact_threshold_condition`` instead. This API is the preferred
    renderer contract because it also represents xN and vN correctly.
    """
    if operation == "add":
        if exact_weight is None:
            raise ValueError("add requires exact_weight")
        return tuple(previous[i] + layer[i] * float(exact_weight) for i in range(3))
    if operation == "blend":
        if exact_weight is None:
            raise ValueError("blend requires exact_weight")
        w = float(exact_weight)
        return tuple(previous[i] + (layer[i] - previous[i]) * w for i in range(3))
    if operation == "multiply":
        if exact_weight is None:
            raise ValueError("multiply requires exact_weight")
        w = float(exact_weight)
        return tuple(previous[i] * (1.0 + (layer[i] - 1.0) * w) for i in range(3))
    if operation == "threshold":
        if exact_threshold_condition is None:
            raise ValueError("threshold requires exact_threshold_condition")
        return tuple(layer[i] if bool(exact_threshold_condition) else previous[i] for i in range(3))
    raise ValueError(operation)


def compose_diffuse(base, layer, weight: float, operation: str):
    """Compatibility helper for ordinary non-vN layer cases.

    ``weight`` is the raw per-vertex layer control and ``layer[3]`` is color
    alpha. This helper is exact for ordinary A/B and M. It intentionally does
    not represent xN B, vN B, or threshold steps; use
    :func:`resolve_ordinary_layer_weight` + :func:`compose_diffuse_exact` there.
    """
    if operation == "add":
        exact = layer[3] * weight
    elif operation == "blend":
        exact = layer[3] * weight
    elif operation == "multiply":
        exact = weight
    else:
        raise ValueError(operation)
    return compose_diffuse_exact(base, layer, operation=operation, exact_weight=exact)


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
