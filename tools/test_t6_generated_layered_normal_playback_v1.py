#!/usr/bin/env python3
from __future__ import annotations

import math

import t6_generated_layered_normal_playback_v1 as playback


def _recipe() -> dict:
    return {
        "material": "*fixture(base:layer)",
        "techniqueSet": "lit_sm_r0c0n0x0_b1c1n1",
        "vertexShaderArchetype": "sha256:" + "a" * 64,
        "pixelShaderArchetype": "sha256:" + "b" * 64,
    }


def _proof(*, exact=True, reverse=False) -> dict:
    unique = (
        "cross(tangent,normal)*handedness"
        if reverse
        else "cross(normal,tangent)*handedness"
    )
    return {
        "format": playback.BASIS_PROOF_FORMAT,
        "profiles": [{
            "techniqueSet": "lit_sm_r0c0n0x0_b1c1n1",
            "vertexShaderSha256": "a" * 64,
            "pixelShaderSha256": "b" * 64,
            "directRoleMatches": {
                "baseIsWorldNormalFromNormal0": True,
                "xBasisIsWorldTangentFromTangent0": True,
                "yBasisPhysicalRole": "worldBinormal" if exact and not reverse else "unpromoted",
                "yBasisExactCrossHandedness": exact and not reverse,
            },
            "binormalAlgebra": {
                "status": "exact-binormal" if exact and not reverse else (
                    "reversed-cross" if reverse else "unresolved"
                ),
                "comparison": {"uniqueMatch": unique if exact or reverse else None},
            },
        }],
    }


def main() -> int:
    profile = playback.resolve_exact_basis_profile(_recipe(), _proof())
    assert profile["vertexShaderSha256"] == "a" * 64

    # Logical UBYTE order [m00,m01,m10,m11]. 255,128,128,255 is the closest
    # representable identity-like T6 matrix after UNORM8 -> [-1,+1].
    q = [255 / 255.0, 128 / 255.0, 128 / 255.0, 255 / 255.0]
    matrix = playback.decode_logical_normal_transform_unorm4(q)
    eps = 1.0 / 255.0
    assert abs(matrix[0][0] - 1.0) < 1e-12
    assert abs(matrix[0][1] - eps) < 1e-12
    assert abs(matrix[1][0] - eps) < 1e-12
    assert abs(matrix[1][1] - 1.0) < 1e-12

    transformed = playback.transform_layer_xy((0.25, -0.5), q)
    assert abs(transformed[0] - (0.25 - 0.5 * eps)) < 1e-12
    assert abs(transformed[1] - (0.25 * eps - 0.5)) < 1e-12

    # Blend from zero, then threshold-select a second directly decoded normal.
    state = playback.compose_steps(None, [
        {
            "decodedXY": [0.4, -0.2],
            "transform": "direct",
            "operator": "blend",
            "exactRgbWeight": 0.5,
        },
        {
            "decodedXY": [-0.3, 0.1],
            "transform": "direct",
            "operator": "threshold",
            "exactRgbThresholdCondition": False,
        },
    ])
    assert state == (0.2, -0.1)

    # N=(0,0,1), T=(1,0,0), handedness=+1 gives B=(0,1,0).
    normal = playback.reconstruct_world_normal(
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        1.0,
        state,
    )
    length = math.sqrt(0.2 * 0.2 + 0.1 * 0.1 + 1.0)
    expected = (0.2 / length, -0.1 / length, 1.0 / length)
    assert all(abs(a - b) < 1e-12 for a, b in zip(normal, expected))

    result = playback.playback(
        _recipe(),
        _proof(),
        world_normal=(0.0, 0.0, 1.0),
        world_tangent=(1.0, 0.0, 0.0),
        tangent_handedness=1.0,
        baseline_xy=None,
        steps=[{
            "decodedXY": [0.4, -0.2],
            "transform": "direct",
            "operator": "blend",
            "exactRgbWeight": 0.5,
        }],
    )
    assert result["layeredXY"] == [0.2, -0.1]
    assert "cross(normal,tangent)" in result["basis"]["y"]

    # Reversed cross orientation is intentionally not accepted as the T6 basis.
    try:
        playback.resolve_exact_basis_profile(_recipe(), _proof(reverse=True))
    except playback.LayeredNormalPlaybackError as exc:
        assert "all three physical normal-basis roles are not exact" in str(exc)
    else:
        raise AssertionError("reversed binormal cross was accepted")

    # Exact shader identity is part of the basis proof; TechniqueSet name alone
    # is never sufficient.
    bad_recipe = _recipe()
    bad_recipe["vertexShaderArchetype"] = "sha256:" + "c" * 64
    try:
        playback.resolve_exact_basis_profile(bad_recipe, _proof())
    except playback.LayeredNormalPlaybackError as exc:
        assert "basis proof VS differs" in str(exc)
    else:
        raise AssertionError("mismatched paired vertex shader was accepted")

    # Transform2x2 cannot silently degrade to direct decoding.
    try:
        playback.compose_steps(None, [{
            "decodedXY": [0.1, 0.2],
            "transform": "transform2x2",
            "operator": "blend",
            "exactRgbWeight": 1.0,
        }])
    except playback.LayeredNormalPlaybackError as exc:
        assert "requires explicit transformUNorm4" in str(exc)
    else:
        raise AssertionError("missing exact normal transform was accepted")

    print("PASS: exact T6 generated layered-normal playback core v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
