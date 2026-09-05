#!/usr/bin/env python3
"""Pure-Python provenance tests for Blender generated-layer preview v3."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import t6_blender_generated_layer_preview_v3 as v3
from t6_generated_shader_recipe_contract_v1 import EXTRA_KEY, FORMAT


def _recipe(material: str, technique: str = "lit_sm_r0c0n0_b1c1") -> dict:
    return {
        "material": material,
        "techniqueSet": technique,
        "pixelShaderArchetype": "ps-fixture",
        "worldVertFormats": [1],
        "proof": {"kind": "fixture", "identity": "ps-fixture"},
    }


def main() -> int:
    canonical = _recipe("*fixture")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "recipes.json"
        path.write_text(json.dumps({"format": FORMAT, "materials": [canonical]}), encoding="utf-8")
        rows = v3._recipe_map(path)
        assert rows["*fixture"]["techniqueSet"] == canonical["techniqueSet"]
        assert rows["*fixture"]["layerProgram"][0]["operation"] == "blend"

        legacy = Path(td) / "legacy.json"
        legacy.write_text(json.dumps({
            "format": "t6-generated-world-shader-recipes-v1",
            "materials": [canonical],
        }), encoding="utf-8")
        try:
            v3._recipe_map(legacy)
        except v3.BlenderLayerPreviewError:
            pass
        else:
            raise AssertionError("v3 accepted historical non-canonical sidecar format")

    technique, row = v3._material_technique("*fixture", {EXTRA_KEY: canonical}, {})
    assert technique == canonical["techniqueSet"]
    assert row is not None and row["material"] == "*fixture"

    # Historical key names are not searched in v3.
    technique, row = v3._material_technique(
        "*fixture",
        {"shaderRecipe": canonical, "techniqueSet": canonical["techniqueSet"]},
        {},
    )
    assert technique is None and row is None

    # If embedded and sidecar canonical copies coexist they must be identical
    # after canonical normalization; no precedence rule is invented.
    normalized = dict(canonical)
    normalized["worldVertFormats"] = [1]
    normalized["layerProgram"] = [{
        "layerIndex": 1,
        "operation": "blend",
        "weightClass": "alpha_vertex",
        "hasNormal": False,
        "hasSpecular": False,
        "xVariant": False,
        "heightVariant": False,
    }]
    normalized["contract"] = "source-closed generated layer program; downstream lighting remains separate"
    technique, row = v3._material_technique(
        "*fixture",
        {EXTRA_KEY: canonical},
        {"*fixture": normalized},
    )
    assert technique == canonical["techniqueSet"] and row == normalized

    conflicting = dict(normalized)
    conflicting["pixelShaderArchetype"] = "ps-other"
    try:
        v3._material_technique(
            "*fixture",
            {EXTRA_KEY: canonical},
            {"*fixture": conflicting},
        )
    except v3.BlenderLayerPreviewError:
        pass
    else:
        raise AssertionError("conflicting canonical sidecar did not fail closed")

    print("PASS: Blender generated-layer preview v3 canonical provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
