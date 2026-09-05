#!/usr/bin/env python3
"""Renderer-neutral playback core for source-closed T6 generated layered normals.

This module deliberately starts *after* texture sample decoding.  It consumes
already-decoded normal-map XY values and only combines semantics that are already
proved independently:

* ordered layered-normal XY recurrence from
  ``T6_RETAIL_LAYERED_NORMAL_COMPOSITOR_V1``;
* logical per-vertex 2x2 transform attributes from the v12+ generated-attribute
  contract (stored bytes reordered to [m00,m01,m10,m11], normalized UBYTE4,
  shader decode component*2-1);
* world-space reconstruction from the universal pixel-shader equation
  ``N + X*T + Y*B``;
* physical basis roles only when the paired slot-4 VS proof v2 says TC1 is the
  world normal, TC3 the world tangent, and TC2 exactly
  ``cross(normal,tangent)*TANGENT0.w``.

Normal-map channel packing/XY sample decode and automatic selection of which
``_T6_NORMAL_TRANSFORM_N`` belongs to a layer remain separate bindings.  Callers
must provide those explicitly; this module never guesses them.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence


BASIS_PROOF_FORMAT = "t6-generated-layered-normal-vs-basis-probe-v2"


class LayeredNormalPlaybackError(RuntimeError):
    pass


def _vec(values: Sequence[float], width: int, label: str) -> tuple[float, ...]:
    if len(values) != width:
        raise LayeredNormalPlaybackError(f"{label} must contain {width} components")
    out = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in out):
        raise LayeredNormalPlaybackError(f"{label} contains non-finite values")
    return out


def _shader_sha(recipe: dict, key: str) -> str:
    value = str(recipe.get(key) or "")
    if not value.startswith("sha256:") or len(value) != 71:
        raise LayeredNormalPlaybackError(
            f"canonical recipe lacks exact {key} sha256 identity"
        )
    return value[7:]


def resolve_exact_basis_profile(recipe: dict, basis_proof: dict) -> dict:
    """Return the exact paired-VS basis profile for one generated recipe.

    No TechniqueSet-only fallback is accepted: the recipe's exact paired VS and
    PS identities must equal the proof profile identities.
    """
    if basis_proof.get("format") != BASIS_PROOF_FORMAT:
        raise LayeredNormalPlaybackError(
            f"unsupported layered-normal basis proof {basis_proof.get('format')!r}"
        )
    technique = str(recipe.get("techniqueSet") or "")
    if not technique:
        raise LayeredNormalPlaybackError("canonical recipe has empty TechniqueSet")
    matches = [
        row for row in basis_proof.get("profiles", [])
        if str(row.get("techniqueSet") or "") == technique
    ]
    if len(matches) != 1:
        raise LayeredNormalPlaybackError(
            f"TechniqueSet {technique!r} matched {len(matches)} paired-VS basis profiles"
        )
    profile = matches[0]
    expected_vs = _shader_sha(recipe, "vertexShaderArchetype")
    expected_ps = _shader_sha(recipe, "pixelShaderArchetype")
    if str(profile.get("vertexShaderSha256") or "") != expected_vs:
        raise LayeredNormalPlaybackError(
            f"{technique!r}: basis proof VS differs from canonical paired vertex shader"
        )
    if str(profile.get("pixelShaderSha256") or "") != expected_ps:
        raise LayeredNormalPlaybackError(
            f"{technique!r}: basis proof PS differs from canonical pixel shader"
        )

    roles = profile.get("directRoleMatches")
    algebra = profile.get("binormalAlgebra")
    if not isinstance(roles, dict) or not isinstance(algebra, dict):
        raise LayeredNormalPlaybackError(f"{technique!r}: incomplete paired-VS basis proof")
    required = (
        bool(roles.get("baseIsWorldNormalFromNormal0")),
        bool(roles.get("xBasisIsWorldTangentFromTangent0")),
        bool(roles.get("yBasisExactCrossHandedness")),
        str(roles.get("yBasisPhysicalRole") or "") == "worldBinormal",
        str(algebra.get("status") or "") == "exact-binormal",
    )
    if not all(required):
        raise LayeredNormalPlaybackError(
            f"{technique!r}: all three physical normal-basis roles are not exact"
        )
    comparison = algebra.get("comparison", {})
    if str(comparison.get("uniqueMatch") or "") != "cross(normal,tangent)*handedness":
        raise LayeredNormalPlaybackError(
            f"{technique!r}: TC2 binormal algebra is not the exact expected cross orientation"
        )
    return profile


def decode_logical_normal_transform_unorm4(
    logical_unorm4: Sequence[float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Decode a v12+ logical normalized-UBYTE transform attribute.

    v12 has already reordered the original stored bytes to logical
    ``[m00,m01,m10,m11]``. glTF normalization presents each UBYTE as [0,1], and
    retained DXBC proves the shader conversion ``component*2-1``.
    """
    q = _vec(logical_unorm4, 4, "logical normal transform")
    if any(value < 0.0 or value > 1.0 for value in q):
        raise LayeredNormalPlaybackError(
            "logical normalized-UBYTE transform component lies outside [0,1]"
        )
    decoded = tuple(value * 2.0 - 1.0 for value in q)
    return (decoded[0], decoded[1]), (decoded[2], decoded[3])


def transform_layer_xy(
    decoded_xy: Sequence[float],
    logical_unorm4: Sequence[float],
) -> tuple[float, float]:
    x, y = _vec(decoded_xy, 2, "decoded layer normal XY")
    (m00, m01), (m10, m11) = decode_logical_normal_transform_unorm4(logical_unorm4)
    return x * m00 + y * m01, x * m10 + y * m11


def compose_xy(
    previous_xy: Sequence[float] | None,
    layer_xy: Sequence[float],
    *,
    operator: str,
    exact_rgb_weight: float | None = None,
    exact_rgb_threshold_condition: bool | None = None,
) -> tuple[float, float]:
    """Apply one exact ordered layered-normal XY transition."""
    layer = _vec(layer_xy, 2, "layer normal XY")
    previous = (0.0, 0.0) if previous_xy is None else _vec(previous_xy, 2, "previous normal XY")
    if operator in ("b", "blend"):
        if exact_rgb_weight is None or not math.isfinite(float(exact_rgb_weight)):
            raise LayeredNormalPlaybackError("normal blend requires finite exact_rgb_weight")
        w = float(exact_rgb_weight)
        return (
            previous[0] + (layer[0] - previous[0]) * w,
            previous[1] + (layer[1] - previous[1]) * w,
        )
    if operator in ("t", "threshold"):
        if exact_rgb_threshold_condition is None:
            raise LayeredNormalPlaybackError(
                "normal threshold requires exact_rgb_threshold_condition"
            )
        return layer if bool(exact_rgb_threshold_condition) else previous
    raise LayeredNormalPlaybackError(
        f"unsupported retained layered-normal operator {operator!r}"
    )


def compose_steps(
    baseline_xy: Sequence[float] | None,
    steps: Iterable[dict],
) -> tuple[float, float]:
    """Compose explicit renderer-ready normal steps in source order.

    Each step must already contain ``decodedXY`` and either ``transformUNorm4``
    or explicit ``transform='direct'``. Weight/threshold values must likewise be
    the exact RGB compositor result supplied by the generated shader recipe.
    """
    state = None if baseline_xy is None else _vec(baseline_xy, 2, "baseline normal XY")
    for ordinal, step in enumerate(steps):
        decoded = step.get("decodedXY")
        if decoded is None:
            raise LayeredNormalPlaybackError(f"normal step {ordinal} lacks decodedXY")
        transform = str(step.get("transform") or "")
        if transform == "direct":
            layer_xy = _vec(decoded, 2, f"normal step {ordinal} decodedXY")
            if step.get("transformUNorm4") is not None:
                raise LayeredNormalPlaybackError(
                    f"normal step {ordinal} is direct but also supplies transformUNorm4"
                )
        elif transform == "transform2x2":
            matrix = step.get("transformUNorm4")
            if matrix is None:
                raise LayeredNormalPlaybackError(
                    f"normal step {ordinal} requires explicit transformUNorm4"
                )
            layer_xy = transform_layer_xy(decoded, matrix)
        else:
            raise LayeredNormalPlaybackError(
                f"normal step {ordinal} has unproven transform mode {transform!r}"
            )
        state = compose_xy(
            state,
            layer_xy,
            operator=str(step.get("operator") or ""),
            exact_rgb_weight=step.get("exactRgbWeight"),
            exact_rgb_threshold_condition=step.get("exactRgbThresholdCondition"),
        )
    return (0.0, 0.0) if state is None else state


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def reconstruct_world_normal(
    world_normal: Sequence[float],
    world_tangent: Sequence[float],
    tangent_handedness: float,
    layered_xy: Sequence[float],
) -> tuple[float, float, float]:
    """Apply the source-closed paired-VS/PS world normal equation."""
    n = _vec(world_normal, 3, "world normal")
    t = _vec(world_tangent, 3, "world tangent")
    h = float(tangent_handedness)
    if not math.isfinite(h):
        raise LayeredNormalPlaybackError("tangent handedness is non-finite")
    x, y = _vec(layered_xy, 2, "layered normal XY")
    cross = _cross(n, t)
    b = tuple(value * h for value in cross)
    raw = tuple(n[i] + x * t[i] + y * b[i] for i in range(3))
    length2 = sum(value * value for value in raw)
    if not math.isfinite(length2) or length2 <= 0.0:
        raise LayeredNormalPlaybackError(
            "retail layered-normal reconstruction produced zero/non-finite vector"
        )
    inv = 1.0 / math.sqrt(length2)
    return tuple(value * inv for value in raw)


def playback(
    recipe: dict,
    basis_proof: dict,
    *,
    world_normal: Sequence[float],
    world_tangent: Sequence[float],
    tangent_handedness: float,
    baseline_xy: Sequence[float] | None,
    steps: Iterable[dict],
) -> dict:
    """Validate exact basis ownership, compose XY, and reconstruct the world normal."""
    profile = resolve_exact_basis_profile(recipe, basis_proof)
    layered_xy = compose_steps(baseline_xy, steps)
    normal = reconstruct_world_normal(
        world_normal,
        world_tangent,
        tangent_handedness,
        layered_xy,
    )
    return {
        "techniqueSet": recipe["techniqueSet"],
        "vertexShaderSha256": profile["vertexShaderSha256"],
        "pixelShaderSha256": profile["pixelShaderSha256"],
        "layeredXY": list(layered_xy),
        "worldNormal": list(normal),
        "basis": {
            "base": "world NORMAL0 / paired VS TEXCOORD1",
            "x": "world TANGENT0 / paired VS TEXCOORD3",
            "y": "cross(normal,tangent)*TANGENT0.w / paired VS TEXCOORD2",
        },
        "proofBoundary": (
            "exact paired-VS basis ownership + exact retained layered-normal XY recurrence/2x2 transform "
            "+ universal retained PS reconstruction; normal-map sample decode and transform-slot selection "
            "must be supplied by separately proven bindings"
        ),
    }
