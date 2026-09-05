#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace

import t6_generated_layered_normal_vs_basis_probe_v1 as probe


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_normal_vs_probe_") as td:
        root = Path(td)
        (root / "shader_bin").mkdir()
        vs_blob = b"DXBC-layered-normal-vs-fixture"
        vs_sha = hashlib.sha256(vs_blob).hexdigest()
        ps_sha = "a" * 64
        vs_path = root / "shader_bin" / "vs_fixture.cso"
        vs_path.write_bytes(vs_blob)

        recipes = {
            "*a(base:layer)": {
                "material": "*a(base:layer)",
                "techniqueSet": "lit_sm_fixture",
                "pixelShaderArchetype": "sha256:" + ps_sha,
                "vertexShaderArchetype": "sha256:" + vs_sha,
                "layerProgram": [{"layerIndex": 1, "hasNormal": True}],
            },
            "*b(base:layer)": {
                "material": "*b(base:layer)",
                "techniqueSet": "lit_sm_fixture",
                "pixelShaderArchetype": "sha256:" + ps_sha,
                "vertexShaderArchetype": "sha256:" + vs_sha,
                "layerProgram": [{"layerIndex": 1, "hasNormal": True}],
            },
            "*color_only(base:layer)": {
                "material": "*color_only(base:layer)",
                "techniqueSet": "lit_sm_color_only",
                "pixelShaderArchetype": "sha256:" + "c" * 64,
                "vertexShaderArchetype": "sha256:" + "d" * 64,
                "layerProgram": [{"layerIndex": 1, "hasNormal": False}],
            },
        }

        paired = SimpleNamespace()
        paired.exact_role_candidates = lambda base, blob: {
            "worldPosition": [],
            "worldNormal": [{"semantic": "TEXCOORD1", "input": "NORMAL0"}],
            "worldTangent": [{"semantic": "TEXCOORD3", "input": "TANGENT0"}],
        }
        ancestry = {
            1: [{"component": "x", "inputLeaves": [["NORMAL", 0]]}],
            2: [{
                "component": "x",
                "inputLeaves": [["NORMAL", 0], ["TANGENT", 0]],
                "writerOpcode": 50,
            }],
            3: [{"component": "x", "inputLeaves": [["TANGENT", 0]]}],
        }
        paired.component_profile = lambda base, blob, tc: ancestry.get(tc)
        base = object()

        old_validate = probe.validate_manifest
        old_load = probe._load
        old_resolve = probe.resolve_slot_shaders
        calls = []
        try:
            probe.validate_manifest = lambda manifest: recipes
            probe._load = lambda path, name: paired if "paired_vs" in name else base

            def fake_resolve(oat_root, techset, **kwargs):
                calls.append(techset)
                return {
                    "vertexShaders": [{
                        "asset": "fixture_vs",
                        "relativeFile": "shader_bin/vs_fixture.cso",
                        "bytes": len(vs_blob),
                        "sha256": vs_sha,
                    }],
                    "pixelShaders": [{
                        "asset": "fixture_ps",
                        "relativeFile": "shader_bin/ps_fixture.cso",
                        "bytes": 123,
                        "sha256": ps_sha,
                    }],
                }

            probe.resolve_slot_shaders = fake_resolve
            doc = probe.build(
                {"ignored": True},
                oat_root=root,
                paired_vs_probe_path=Path("paired.py"),
                base_verifier_path=Path("base.py"),
            )
        finally:
            probe.validate_manifest = old_validate
            probe._load = old_load
            probe.resolve_slot_shaders = old_resolve

        assert calls == ["lit_sm_fixture"]
        summary = doc["summary"]
        assert summary["materialOwnerCount"] == 2
        assert summary["techniqueSetCount"] == 1
        assert summary["pairedVertexShaderIdentityCount"] == 1
        assert summary["directBaseNormalTechniqueSetCount"] == 1
        assert summary["directXBasisTangentTechniqueSetCount"] == 1
        assert summary["directBaseAndXPairTechniqueSetCount"] == 1
        assert summary["yBasisPromotedTechniqueSetCount"] == 0
        row = doc["profiles"][0]
        assert row["pixelBasis"] == {
            "base": "TEXCOORD1.xyz",
            "xBasis": "TEXCOORD3.xyz",
            "yBasis": "TEXCOORD2.xyz",
        }
        assert row["directRoleMatches"]["baseIsWorldNormalFromNormal0"] is True
        assert row["directRoleMatches"]["xBasisIsWorldTangentFromTangent0"] is True
        # Even with both NORMAL0 and TANGENT0 leaves and a MAD-looking writer,
        # ancestry alone is not enough to call TC2 a binormal.
        assert row["directRoleMatches"]["yBasisPhysicalRole"] == "unpromoted"
        assert row["basisComponentAncestry"]["TEXCOORD2"] == ancestry[2]

        # Paired OAT PS mismatch is fatal; a physically correct-looking VS from
        # another pass cannot be borrowed.
        old_validate = probe.validate_manifest
        old_load = probe._load
        old_resolve = probe.resolve_slot_shaders
        try:
            probe.validate_manifest = lambda manifest: recipes
            probe._load = lambda path, name: paired if "paired_vs" in name else base
            probe.resolve_slot_shaders = lambda *args, **kwargs: {
                "vertexShaders": [{
                    "asset": "fixture_vs",
                    "relativeFile": "shader_bin/vs_fixture.cso",
                    "sha256": vs_sha,
                }],
                "pixelShaders": [{"asset": "wrong", "sha256": "f" * 64}],
            }
            try:
                probe.build(
                    {"ignored": True},
                    oat_root=root,
                    paired_vs_probe_path=Path("paired.py"),
                    base_verifier_path=Path("base.py"),
                )
            except probe.LayeredNormalVsProbeError as exc:
                assert "disagrees with canonical owner recipes" in str(exc)
            else:
                raise AssertionError("VS from a mismatched slot-4 PS pass was accepted")
        finally:
            probe.validate_manifest = old_validate
            probe._load = old_load
            probe.resolve_slot_shaders = old_resolve

    print("PASS: generated layered-normal paired VS basis probe v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
