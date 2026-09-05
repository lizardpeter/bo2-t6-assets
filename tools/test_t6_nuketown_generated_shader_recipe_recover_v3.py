#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v3 as recover


def _height_payload(shader_sha: str) -> dict:
    return {
        "format": "t6-generated-height-weight-dag-set-v1",
        "techniqueSet": "lit_sm_r0c0_b1c1v1",
        "pixelShaderSha256": shader_sha,
        "heightLayerCount": 1,
        "layers": [{
            "layerIndex": 1,
            "weightClass": "height",
            "semanticWeightDagSha256": "1" * 64,
            "forensicDag": {
                "format": "t6-generated-height-weight-dag-v1",
                "root": 0,
                "nodeCount": 1,
                "forensicDagSha256": "2" * 64,
                "nodes": [{"id": 0, "kind": "cb", "name": "cb1[59].x"}],
            },
        }],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_recipe_v3_") as td:
        root = Path(td)
        oat = root / "oat"
        (oat / "shader_bin").mkdir(parents=True)
        (oat / "techniques").mkdir(parents=True)
        shader_bytes = b"DXBC-shared-height-shader"
        shader_sha = hashlib.sha256(shader_bytes).hexdigest()
        (oat / "shader_bin" / "ps_fixture.cso").write_bytes(shader_bytes)
        (oat / "techniques" / "fixture.tech").write_text(
            "alphaRevealParms1 = material.alphaRevealParms1;\n", encoding="utf-8"
        )

        materials = ["*mat_a(base:layer)", "*mat_b(base:layer)"]
        base_manifest = {
            "format": "t6-generated-world-shader-recipe-manifest-v1",
            "materials": [
                {
                    "material": material,
                    "techniqueSet": "lit_sm_r0c0_b1c1v1",
                    "pixelShaderArchetype": "sha256:" + shader_sha,
                    "worldVertFormats": [1],
                    "proof": {"fixture": True},
                    recover.v2.HEIGHT_KEY: _height_payload(shader_sha),
                }
                for material in materials
            ],
            "recovery": {
                "format": "t6-nuketown-generated-shader-recipe-recovery-v2",
                "recipeRowsSha256": "a" * 64,
            },
        }
        source_bindings = [
            {
                "material": materials[0],
                "constants": [{"nameHash": 1, "literal": [0.25, 2.0, 0.0, 0.0]}],
                "materialIndex": 10,
                "materialStart": 1000,
                "materialArchiveSha256": "b" * 64,
            },
            {
                "material": materials[1],
                "constants": [{"nameHash": 1, "literal": [0.75, 4.0, 0.0, 0.0]}],
                "materialIndex": 11,
                "materialStart": 2000,
                "materialArchiveSha256": "c" * 64,
            },
        ]

        old_resolve = recover.resolve_slot_shader
        old_bind = recover.bind_cb_leaves
        bind_values = []
        try:
            recover.resolve_slot_shader = lambda oat_root, techset, slot_index: {
                "techniqueSet": techset,
                "slotIndex": 4,
                "slotLabel": "lit",
                "techniqueAsset": "fixture",
                "techniqueFile": "techniques/fixture.tech",
                "pixelShaders": [{
                    "asset": "fixture",
                    "relativeFile": "shader_bin/ps_fixture.cso",
                    "bytes": len(shader_bytes),
                    "sha256": shader_sha,
                }],
            }

            def fake_bind(leaves, *, dxbc, technique_text, material_constants):
                value = material_constants[0]["literal"][0]
                bind_values.append(value)
                return {
                    "format": "t6-dxbc-material-constant-binding-v1",
                    "dxbcSha256": hashlib.sha256(dxbc).hexdigest(),
                    "leafCount": 1,
                    "allLeavesExact": True,
                    "bindings": [{
                        "leaf": "cb1[59].x",
                        "materialConstant": {
                            "name": "alphaRevealParms1",
                            "nameHash": 0x88BEFC31,
                            "literal": list(material_constants[0]["literal"]),
                            "literalComponent": 0,
                            "value": value,
                        },
                    }],
                }

            recover.bind_cb_leaves = fake_bind
            result = recover._augment_material_constant_bindings(
                base_manifest,
                source_bindings=source_bindings,
                oat_root=oat,
            )
        finally:
            recover.resolve_slot_shader = old_resolve
            recover.bind_cb_leaves = old_bind

        assert bind_values == [0.25, 0.75]
        rows = {row["material"]: row for row in result["materials"]}
        a = rows[materials[0]][recover.HEIGHT_CONSTANT_KEY]
        b = rows[materials[1]][recover.HEIGHT_CONSTANT_KEY]
        assert a["bindings"][0]["materialConstant"]["value"] == 0.25
        assert b["bindings"][0]["materialConstant"]["value"] == 0.75
        assert a["materialArchiveSha256"] != b["materialArchiveSha256"]
        assert a["pixelShaderArchetype"] == b["pixelShaderArchetype"]

        rec = result["recovery"]
        assert rec["format"] == recover.FORMAT
        assert rec["baseRecoveryFormat"] == "t6-nuketown-generated-shader-recipe-recovery-v2"
        assert rec["heightConstantBoundMaterialCount"] == 2
        assert rec["heightConstantBoundLeafOccurrenceCount"] == 2
        assert rec["uniqueHeightCbufferLeafNames"] == ["cb1[59].x"]
        assert rec["uniqueHeightMaterialConstantHashes"] == ["0x88befc31"]
        assert rec["uniqueHeightConstantBindingSignatureCount"] == 2
        assert rec["heightConstantCoverageComplete"] is True

        # A height-bearing recipe cannot fall back to another Material's constants.
        try:
            recover._augment_material_constant_bindings(
                {
                    **base_manifest,
                    "materials": [dict(base_manifest["materials"][0])],
                    "recovery": {"format": "v2", "recipeRowsSha256": "x"},
                },
                source_bindings=[source_bindings[1]],
                oat_root=oat,
            )
        except recover.NuketownShaderRecipeRecoveryV3Error as exc:
            assert "no direct retail Material record" in str(exc)
        else:
            raise AssertionError("height recipe borrowed constants from a different Material")

    print("PASS: Nuketown generated shader recovery v3 per-Material height constants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
