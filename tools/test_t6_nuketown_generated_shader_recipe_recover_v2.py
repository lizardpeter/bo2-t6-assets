#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_nuketown_generated_shader_recipe_recover_v2 as recover


def _fixture(root: Path):
    oat = root / "oat"
    for name in ("techsets", "techniques", "shader_bin"):
        (oat / name).mkdir(parents=True, exist_ok=True)
    techset = "lit_sm_r0c0_b1c1v1"
    (oat / "techsets" / f"{techset}.techset").write_text(
        '"lit":\n  fixture_lit;\n', encoding="utf-8"
    )
    (oat / "techniques" / "fixture_lit.tech").write_text(
        '{\n  pixelShader 4.0 "fixture_height"\n  {\n  }\n}\n', encoding="utf-8"
    )
    shader = b"DXBC-exact-height-fixture"
    (oat / "shader_bin" / "ps_fixture_height.cso").write_bytes(shader)
    bindings = [{
        "material": "*1_2(wpc/base:wpc/layer)",
        "techniqueSet": techset,
        "worldVertFormat": 1,
    }]
    return oat, bindings, shader


def _payload(shader: bytes, *, layers=True):
    row = {
        "layerIndex": 1,
        "operation": "b",
        "flags": ["v"],
        "weightClass": "height",
        "semanticWeightDagSha256": "1" * 64,
        "forensicDag": {
            "format": "t6-generated-height-weight-dag-v1",
            "root": 0,
            "nodes": [{"kind": "input", "name": "COLOR.y", "id": 0}],
            "nodeCount": 1,
            "ordering": "reachable child-before-parent; operation argument order preserved",
            "forensicDagSha256": "2" * 64,
        },
    }
    return {
        "format": "t6-generated-height-weight-dag-set-v1",
        "techniqueSet": "lit_sm_r0c0_b1c1v1",
        "pixelShaderSha256": hashlib.sha256(shader).hexdigest(),
        "layers": [row] if layers else [],
        "heightLayerCount": 1 if layers else 0,
        "heightSemanticDagSetSha256": "3" * 64,
        "proof": "synthetic exact extractor fixture",
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_recipe_v2_") as td:
        root = Path(td)
        oat, bindings, shader = _fixture(root)
        original = recover.extract_height_weight_dags
        calls = []
        try:
            def fake_extract(blob, technique_set):
                calls.append((blob, technique_set))
                return _payload(shader)
            recover.extract_height_weight_dags = fake_extract
            manifest = recover.build_from_bindings(
                bindings,
                oat_root=oat,
                expanded_sha256="a" * 64,
                strict_nuketown=False,
            )
        finally:
            recover.extract_height_weight_dags = original

        assert calls == [(shader, "lit_sm_r0c0_b1c1v1")]
        row = manifest["materials"][0]
        assert row[recover.HEIGHT_KEY]["heightLayerCount"] == 1
        assert row[recover.HEIGHT_KEY]["layers"][0]["layerIndex"] == 1
        assert row["pixelShaderArchetype"] == "sha256:" + hashlib.sha256(shader).hexdigest()
        rec = manifest["recovery"]
        assert rec["format"] == recover.FORMAT
        assert rec["baseRecoveryFormat"] == "t6-nuketown-generated-shader-recipe-recovery-v1"
        assert rec["heightDagMaterialCount"] == 1
        assert rec["heightDagLayerOccurrenceCount"] == 1
        assert rec["heightDagTechniqueSetCount"] == 1
        assert rec["uniqueHeightSemanticDagCount"] == 1
        assert rec["uniqueHeightForensicDagCount"] == 1
        assert rec["heightDagCoverageComplete"] is True
        assert rec["recipeRowsSha256"] != rec["baseRecipeRowsSha256"]

        # A shader extractor that fails to return the v1 layer cannot be accepted
        # just because the TechniqueSet name itself says v1.
        try:
            recover.extract_height_weight_dags = lambda blob, technique_set: _payload(shader, layers=False)
            try:
                recover.build_from_bindings(
                    bindings,
                    oat_root=oat,
                    expanded_sha256="a" * 64,
                    strict_nuketown=False,
                )
            except recover.NuketownShaderRecipeRecoveryV2Error as exc:
                assert "exact height-DAG layers []" in str(exc)
            else:
                raise AssertionError("missing exact vN height DAG was accepted")
        finally:
            recover.extract_height_weight_dags = original

    print("PASS: Nuketown generated shader recipe recovery v2 height DAG attachment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
