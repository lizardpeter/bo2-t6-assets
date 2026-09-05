#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v1 as recover
from t6_generated_shader_recipe_contract_v1 import validate_manifest
from t6_oat_slot_shader_resolver_v1 import OatSlotShaderError, resolve_slot_shader


def _fixture(root: Path) -> tuple[Path, list[dict]]:
    oat = root / "oat"
    for name in ("techsets", "techniques", "shader_bin"):
        (oat / name).mkdir(parents=True, exist_ok=True)

    techsets: list[str] = []
    for i in range(34):
        techset = f"lit_sm_b0c0_b1c1_fixture{i:02d}"
        technique = f"fixture_lit_{i:02d}"
        shader = f"fixture_ps_{i:02d}"
        techsets.append(techset)
        (oat / "techsets" / f"{techset}.techset").write_text(
            f'"depth prepass":\n  fixture_depth_{i:02d};\n\n"lit":\n  {technique};\n',
            encoding="utf-8",
        )
        (oat / "techniques" / f"{technique}.tech").write_text(
            "{\n"
            f'  pixelShader 4.0 "{shader}"\n'
            "  {\n  }\n"
            "}\n",
            encoding="utf-8",
        )
        # Unique, nonempty bytecode payload per TechniqueSet.
        (oat / "shader_bin" / f"ps_{shader}.cso").write_bytes(
            b"DXBC-fixture-" + i.to_bytes(2, "little")
        )

    formats = [1] * 95 + [2] * 7 + [3] * 17 + [6]
    assert len(formats) == 120
    bindings: list[dict] = []
    for i, world_format in enumerate(formats):
        bindings.append({
            "material": f"*fixture_{i:03d}(wpc/base:wpc/layer)",
            "techniqueSet": techsets[i % len(techsets)],
            "worldVertFormat": world_format,
            "family": "layered_lit",
        })
    return oat, bindings


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        oat, bindings = _fixture(root)

        direct = resolve_slot_shader(
            oat, "lit_sm_b0c0_b1c1_fixture00", slot_index=4
        )
        assert direct["slotLabel"] == "lit"
        assert direct["techniqueAsset"] == "fixture_lit_00"
        assert direct["pixelShaders"][0]["asset"] == "fixture_ps_00"
        assert direct["pixelShaders"][0]["bytes"] == len(b"DXBC-fixture-\x00\x00")

        manifest = recover.build_from_bindings(
            bindings,
            oat_root=oat,
            expanded_sha256="a" * 64,
            strict_nuketown=True,
        )
        r = manifest["recovery"]
        assert r["generatedMaterialCount"] == 120
        assert r["uniqueTechniqueSetCount"] == 34
        assert r["uniqueSlot4PixelShaderCount"] == 34
        assert r["crossTechniqueSetShaderReuseCount"] == 0
        assert r["worldVertFormatHistogram"] == {"1": 95, "2": 7, "3": 17, "6": 1}
        assert r["slotIndex"] == 4 and r["slotLabel"] == "lit"
        assert r["generatedDiffuseOperationHistogram"] == {"blend": 120}
        rows = validate_manifest(manifest)
        assert len(rows) == 120
        assert all(v["pixelShaderArchetype"].startswith("sha256:") for v in rows.values())
        assert all(v["layerProgram"][0]["operation"] == "blend" for v in rows.values())

        # World-format drift must fail rather than quietly changing the recovered table.
        bad_formats = [dict(row) for row in bindings]
        bad_formats[0]["worldVertFormat"] = 6
        try:
            recover.build_from_bindings(
                bad_formats,
                oat_root=oat,
                expanded_sha256="a" * 64,
                strict_nuketown=True,
            )
        except recover.NuketownShaderRecipeRecoveryError as exc:
            assert "worldVertFormat histogram mismatch" in str(exc)
        else:
            raise AssertionError("worldVertFormat drift did not fail closed")

        # Cross-TechniqueSet shader reuse must also fail the old v31 34/34 invariant.
        (oat / "shader_bin" / "ps_fixture_ps_01.cso").write_bytes(
            (oat / "shader_bin" / "ps_fixture_ps_00.cso").read_bytes()
        )
        try:
            recover.build_from_bindings(
                bindings,
                oat_root=oat,
                expanded_sha256="a" * 64,
                strict_nuketown=True,
            )
        except recover.NuketownShaderRecipeRecoveryError as exc:
            assert "unique slot-4 shader count" in str(exc) or "shader reuse" in str(exc)
        else:
            raise AssertionError("cross-TechniqueSet shader reuse did not fail closed")

        # Missing slot 4 is an OAT provenance failure, not a fallback opportunity.
        missing = oat / "techsets" / "missing_lit.techset"
        missing.write_text('"depth prepass":\n  only_depth;\n', encoding="utf-8")
        try:
            resolve_slot_shader(oat, "missing_lit", slot_index=4)
        except OatSlotShaderError as exc:
            assert "has no T6 slot 4" in str(exc)
        else:
            raise AssertionError("missing slot 4 did not fail closed")

        # Serialization remains stable and directly consumable by v9's recipe contract.
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        assert '"format":"t6-generated-world-shader-recipe-manifest-v1"' in encoded

    print("PASS: exact Nuketown generated shader recipe recovery v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
