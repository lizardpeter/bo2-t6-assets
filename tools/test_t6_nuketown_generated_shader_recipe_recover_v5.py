#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v5 as recover


def _manifest(ps_sha: str):
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [
            {
                "material": "*fixture_a(base:layer)",
                "techniqueSet": "lit_sm_fixture",
                "pixelShaderArchetype": "sha256:" + ps_sha,
                "worldVertFormats": [1],
                "proof": {"fixture": True},
            },
            {
                "material": "*fixture_b(base:layer)",
                "techniqueSet": "lit_sm_fixture",
                "pixelShaderArchetype": "sha256:" + ps_sha,
                "worldVertFormats": [1],
                "proof": {"fixture": True},
            },
        ],
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v4",
            "recipeRowsSha256": "a" * 64,
        },
    }


def main() -> int:
    vs_bytes = b"DXBC-vs-fixture"
    ps_bytes = b"DXBC-ps-fixture"
    vs_sha = hashlib.sha256(vs_bytes).hexdigest()
    ps_sha = hashlib.sha256(ps_bytes).hexdigest()

    old = recover.resolve_slot_shaders
    calls = []
    try:
        def fake_resolve(oat_root, techset, **kwargs):
            calls.append((Path(oat_root), techset, kwargs))
            return {
                "techniqueSet": techset,
                "slotIndex": 4,
                "slotLabel": "lit",
                "techniqueAsset": "fixture_lit",
                "techniqueFile": "techniques/fixture_lit.tech",
                "vertexShaders": [{
                    "asset": "fixture_vs",
                    "relativeFile": "shader_bin/vs_fixture_vs.cso",
                    "bytes": len(vs_bytes),
                    "sha256": vs_sha,
                }],
                "pixelShaders": [{
                    "asset": "fixture_ps",
                    "relativeFile": "shader_bin/ps_fixture_ps.cso",
                    "bytes": len(ps_bytes),
                    "sha256": ps_sha,
                }],
            }
        recover.resolve_slot_shaders = fake_resolve
        with tempfile.TemporaryDirectory(prefix="t6_recipe_v5_") as td:
            result = recover._augment_vertex_shader_identities(
                _manifest(ps_sha), oat_root=Path(td)
            )
    finally:
        recover.resolve_slot_shaders = old

    # Same TechniqueSet must resolve once and be reused by exact identity.
    assert len(calls) == 1
    for row in result["materials"]:
        assert row[recover.VERTEX_ARCHETYPE_KEY] == "sha256:" + vs_sha
        assert row["proof"]["vertexShaderAsset"] == "fixture_vs"
        assert row["proof"]["vertexShaderFile"] == "shader_bin/vs_fixture_vs.cso"
        assert row["proof"]["vertexShaderBytes"] == len(vs_bytes)
        assert row["proof"]["vertexShaderSha256"] == vs_sha
    rec = result["recovery"]
    assert rec["format"] == recover.FORMAT
    assert rec["baseRecoveryFormat"] == "t6-nuketown-generated-shader-recipe-recovery-v4"
    assert rec["pairedVertexShaderMaterialCount"] == 2
    assert rec["pairedVertexShaderTechniqueSetCount"] == 1
    assert rec["uniquePairedVertexShaderCount"] == 1
    assert rec["pairedVertexShaderCoverageComplete"] is True

    # The paired pass PS must be the already-canonical pixel shader; otherwise
    # the VS would belong to a different pass/owner and cannot be attached.
    old = recover.resolve_slot_shaders
    try:
        recover.resolve_slot_shaders = lambda *args, **kwargs: {
            "vertexShaders": [{
                "asset": "fixture_vs",
                "relativeFile": "shader_bin/vs_fixture_vs.cso",
                "bytes": len(vs_bytes),
                "sha256": vs_sha,
            }],
            "pixelShaders": [{
                "asset": "wrong_ps",
                "relativeFile": "shader_bin/ps_wrong.cso",
                "bytes": 4,
                "sha256": "f" * 64,
            }],
        }
        try:
            recover._augment_vertex_shader_identities(_manifest(ps_sha), oat_root=Path("."))
        except recover.NuketownShaderRecipeRecoveryV5Error as exc:
            assert "paired OAT slot-4" in str(exc)
        else:
            raise AssertionError("vertex shader from a different pixel pass was accepted")
    finally:
        recover.resolve_slot_shaders = old

    print("PASS: Nuketown recipe recovery v5 exact paired slot-4 vertex shader identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
