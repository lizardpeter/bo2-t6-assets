#!/usr/bin/env python3
"""Renderer-neutral T6 reflection-probe semantics from retained retail DXBC.

This module intentionally separates globally proven reflection mechanics from
family-specific material/normal provenance.

Proven across all 5,888 retained reflectionProbeSampler cube fetches:
- cube coordinate is the exact normalized reflect-form
      B - 2*A*dot(A,B)
  with both raw A/B normalized immediately before use;
- probe RGB is alpha-biased decoded as
      probe.rgb / (probe.a + float32(0x358637bd));
- mip selection is one of the finite exact SAMPLE_L affine/literal forms or
  SAMPLE_B bias -3 recorded by the retained mip proof.

Additionally, one dominant 4,236-fetch family is source-closed end-to-end from
its shared scalar x through LOD, angular term, Q pack, reflection factor and
probe-RGB multiplication. It is exposed explicitly as the ``shared_4_minus_4x``
family. Callers MUST NOT apply that family to other reflection shaders merely
because it looks physically plausible.

Physical naming remains conservative: A/B/U/V/P/x are bytecode/dataflow labels
unless a separate family proof assigns stronger meaning. This module does not
translate the equations to metallic/roughness PBR.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Sequence


def _f32_bits(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", int(bits) & 0xFFFFFFFF))[0]


PROBE_ALPHA_BIAS = _f32_bits(0x358637BD)
ANGULAR_EXP_SCALE = _f32_bits(0xC1147AE1)  # -9.28 retained immediate
IMMEDIATE_MATERIAL_COLOR = _f32_bits(0x3D23D70A)  # ~0.04 retained immediate

# Exact retained SAMPLE_L forms, represented with float32 immediates rather than
# rounded decimal constants where the manifest gives bit identities.
MIP_AFFINE_FORMS = {
    "4_minus_4x": (_f32_bits(0xC0800000), _f32_bits(0x40800000)),
    "0_475x": (_f32_bits(0x3EF33333), _f32_bits(0x00000000)),
    "0_25x_plus_0_75": (_f32_bits(0x3E800000), _f32_bits(0x3F400000)),
    "compiled_zero": (_f32_bits(0x00000000), _f32_bits(0x00000000)),
}
MIP_LITERAL_LODS = {
    "lod_0": _f32_bits(0x00000000),
    "lod_0_8": _f32_bits(0x3F4CCCCD),
    "lod_2_4": _f32_bits(0x4019999A),
    "lod_4": _f32_bits(0x40800000),
}
SAMPLE_B_BIAS = _f32_bits(0xC0400000)  # -3

# Shared-parameter family Q=x*A+B exact float32 immediate vectors.
_SHARED_Q_A = tuple(
    _f32_bits(bits)
    for bits in (0x3F855556, 0x3EF33333, 0x3C955567, 0x3E800000)
)
_SHARED_Q_B = tuple(
    _f32_bits(bits)
    for bits in (0x00000000, 0x00000000, 0xBC800000, 0x3F400000)
)


class ReflectionProbeSemanticError(ValueError):
    pass


def saturate(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _vec(values: Sequence[float], width: int, label: str) -> tuple[float, ...]:
    if len(values) != width:
        raise ReflectionProbeSemanticError(f"{label} must contain exactly {width} components")
    out = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in out):
        raise ReflectionProbeSemanticError(f"{label} contains non-finite values")
    return out


def normalize3(values: Sequence[float], *, label: str = "vector") -> tuple[float, float, float]:
    v = _vec(values, 3, label)
    length2 = sum(x * x for x in v)
    if length2 <= 0.0:
        raise ReflectionProbeSemanticError(f"{label} is zero length")
    inv = 1.0 / math.sqrt(length2)
    return tuple(x * inv for x in v)


def reflection_cube_coordinate(
    raw_a: Sequence[float],
    raw_b: Sequence[float],
) -> tuple[float, float, float]:
    """Exact retained coordinate: normalize(B)-2*normalize(A)*dot(A,B)."""
    a = normalize3(raw_a, label="rawA")
    b = normalize3(raw_b, label="rawB")
    d = sum(a[i] * b[i] for i in range(3))
    return tuple(b[i] - 2.0 * a[i] * d for i in range(3))


def decode_probe_rgb(probe_rgba: Sequence[float]) -> tuple[float, float, float]:
    """Exact first RGB consumer: probe.rgb/(probe.a+float32(0x358637bd))."""
    p = _vec(probe_rgba, 4, "probeRGBA")
    divisor = p[3] + PROBE_ALPHA_BIAS
    if divisor == 0.0:
        raise ReflectionProbeSemanticError("probe alpha plus retained bias is zero")
    return tuple(p[i] / divisor for i in range(3))


def sample_l_lod(*, form: str, x: float | None = None) -> float:
    """Evaluate one exact retained SAMPLE_L LOD form.

    ``x`` is deliberately an opaque source scalar here. The global mip proof
    does not assign one universal gloss/roughness meaning to it.
    """
    if form in MIP_LITERAL_LODS:
        if x is not None:
            raise ReflectionProbeSemanticError(f"literal mip form {form!r} does not consume x")
        return MIP_LITERAL_LODS[form]
    if form in MIP_AFFINE_FORMS:
        if x is None:
            raise ReflectionProbeSemanticError(f"affine mip form {form!r} requires x")
        scale, offset = MIP_AFFINE_FORMS[form]
        return scale * float(x) + offset
    raise ReflectionProbeSemanticError(f"unknown retained reflection mip form {form!r}")


def sample_b_bias() -> float:
    """The only retained reflection SAMPLE_B form uses literal bias -3."""
    return SAMPLE_B_BIAS


def angular_e_from_normalized_pair(
    u_normalized: Sequence[float],
    v_normalized: Sequence[float],
    *,
    unit_tolerance: float = 1.0e-4,
) -> float:
    """Exact linked angular core E=2^(-9.28*saturate(dot(U,-V))).

    U/V must be the already-normalized writer-identical pair associated with the
    reflection-coordinate family proof. This function validates unit length but
    cannot infer which physical vector each label represents.
    """
    u = _vec(u_normalized, 3, "U")
    v = _vec(v_normalized, 3, "V")
    for label, q in (("U", u), ("V", v)):
        length = math.sqrt(sum(x * x for x in q))
        if abs(length - 1.0) > unit_tolerance:
            raise ReflectionProbeSemanticError(f"{label} must already be normalized")
    d = saturate(sum(u[i] * (-v[i]) for i in range(3)))
    return 2.0 ** (ANGULAR_EXP_SCALE * d)


def shared_parameter_q(x: float) -> tuple[float, float, float, float]:
    """Exact 4-lane Q=x*A+B for the 4,236-fetch LOD=4-4*x family."""
    xf = float(x)
    if not math.isfinite(xf):
        raise ReflectionProbeSemanticError("shared reflection x is non-finite")
    return tuple(xf * _SHARED_Q_A[i] + _SHARED_Q_B[i] for i in range(4))


def squared_material_color(source_rgb: Sequence[float]) -> tuple[float, float, float]:
    """Exact P.rgb=S.rgb*S.rgb family used by 4,216 shared-parameter fetches."""
    s = _vec(source_rgb, 3, "materialColorSource")
    return tuple(v * v for v in s)


def immediate_material_color() -> tuple[float, float, float]:
    """Exact immediate P family used by the remaining 20 shared-parameter fetches."""
    return (IMMEDIATE_MATERIAL_COLOR,) * 3


def shared_parameter_reflection_factor(
    *,
    x: float,
    angular_e: float,
    p_rgb: Sequence[float],
) -> tuple[float, float, float]:
    """Closed factor for the exact 4,236-fetch shared-parameter family.

    Q = x*A+B
    C = min(E,Qy)
    F = Qx*C + Qz
    factor.rgb = saturate(P.rgb*(Qw-F)+F)
    """
    p = _vec(p_rgb, 3, "P.rgb")
    e = float(angular_e)
    if not math.isfinite(e):
        raise ReflectionProbeSemanticError("angular E is non-finite")
    qx, qy, qz, qw = shared_parameter_q(x)
    c = min(e, qy)
    f = qx * c + qz
    return tuple(saturate(p[i] * (qw - f) + f) for i in range(3))


def evaluate_shared_4_minus_4x_reflection(
    *,
    raw_a: Sequence[float],
    raw_b: Sequence[float],
    probe_rgba: Sequence[float],
    x: float,
    p_rgb: Sequence[float],
) -> dict:
    """Evaluate the dominant retained 4,236-fetch reflection family.

    The returned cube coordinate and LOD specify the exact probe request. The
    caller supplies the resulting sampled probe RGBA because texture/cubemap
    sampling itself is renderer-owned.

    For this family the retained angular proof uses the same two normalized
    writer values as the coordinate construction. We preserve the mathematical
    labels by using normalized rawA/rawB as U/V; no physical normal/view naming
    is introduced.
    """
    a = normalize3(raw_a, label="rawA")
    b = normalize3(raw_b, label="rawB")
    d = sum(a[i] * b[i] for i in range(3))
    coordinate = tuple(b[i] - 2.0 * a[i] * d for i in range(3))
    lod = sample_l_lod(form="4_minus_4x", x=x)
    e = angular_e_from_normalized_pair(a, b)
    factor = shared_parameter_reflection_factor(x=x, angular_e=e, p_rgb=p_rgb)
    decoded = decode_probe_rgb(probe_rgba)
    rgb = tuple(decoded[i] * factor[i] for i in range(3))
    return {
        "cubeCoordinate": coordinate,
        "lod": lod,
        "angularE": e,
        "q": shared_parameter_q(x),
        "reflectionFactorRgb": factor,
        "decodedProbeRgb": decoded,
        "reflectionRgb": rgb,
        "family": "shared_4_minus_4x",
    }


def renderer_contract() -> dict:
    return {
        "allFetchCount": 5888,
        "allFetchUniqueShaderCount": 5868,
        "allFetchProven": {
            "coordinateReflectForm": True,
            "rawPairNormalized": True,
            "probeAlphaBiasedRgbDecode": True,
            "finiteMipFormSet": True,
        },
        "angularLinkedFetchCount": 5682,
        "angularUnlinkedFetchCount": 206,
        "shared4Minus4xFetchCount": 4236,
        "sharedMaterialColorSquaredFetchCount": 4216,
        "sharedMaterialColorImmediateFetchCount": 20,
        "measuredPhysicalFamilyClosure": {
            "closedFetchCount": 5823,
            "remainingFetchCount": 65,
            "totalFetchCount": 5888,
            "source": "T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2",
        },
        "failClosedBoundary": (
            "Do not assign physical A/B/U/V/P/x semantics or apply the shared 4-4x factor "
            "outside its proven family. The 65 closure-ledger residual fetches remain explicit."
        ),
    }
