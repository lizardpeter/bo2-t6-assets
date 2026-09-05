#!/usr/bin/env python3
"""Pure-Python preflight tests for the T6 Blender generated-layer adapter.

No Blender runtime is required: this covers the fail-closed GLB/recipe/dependency
boundary so malformed or guessed material joins cannot reach node generation.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile

import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v2 as v2


def _glb(doc: dict) -> bytes:
    payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    while len(payload) % 4:
        payload += b" "
    total = 12 + 8 + len(payload)
    return b"glTF" + struct.pack("<II", 2, total) + struct.pack("<II", len(payload), 0x4E4F534A) + payload


def main() -> int:
    assert v1.bpy is None or v1.bpy is not None  # importing outside Blender must remain legal
    assert v2.BlenderLayerPreviewError is v1.BlenderLayerPreviewError

    doc = {
        "asset": {"version": "2.0"},
        "materials": [{"name": "*fixture"}],
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gltf = root / "fixture.gltf"
        gltf.write_text(json.dumps(doc), encoding="utf-8")
        assert v1._read_gltf_json(gltf) == doc

        glb = root / "fixture.glb"
        glb.write_bytes(_glb(doc))
        assert v1._read_gltf_json(glb) == doc

        recipe = root / "recipes.json"
        recipe.write_text(json.dumps({
            "format": "t6-generated-world-shader-recipes-v1",
            "materials": [
                {"material": "*fixture", "techniqueSet": "lit_sm_r0c0n0_b1c1"}
            ],
        }), encoding="utf-8")
        recipes = v1._recipe_map(recipe)
        assert recipes["*fixture"]["techniqueSet"] == "lit_sm_r0c0n0_b1c1"

    deps = v1._embedded_dependencies({
        "materialDependencyGraph": {
            "layers": [
                {"layerIndex": 0, "layer": "base", "textures": [
                    {"semantic": "colorMap", "sourceTexture": "base.png", "textureIndex": 3},
                    {"semantic": "specularMap", "sourceTexture": "base_s.png", "textureIndex": 4},
                ]},
                {"layerIndex": 1, "layer": "decal", "textures": [
                    {"semantic": "colorMap", "sourceTexture": "decal.png", "textureIndex": 5},
                ]},
            ]
        }
    })
    assert [(x["layerIndex"], x["semantic"], x["sourceTexture"]) for x in deps] == [
        (0, "colorMap", "base.png"),
        (0, "specularMap", "base_s.png"),
        (1, "colorMap", "decal.png"),
    ]
    assert v1._role_dependency(deps, 0, "specularMap")["sourceTexture"] == "base_s.png"
    assert v1._role_dependency(deps, 1, "normalMap") is None

    embedded = [{
        "layerIndex": 2,
        "semantic": "colorMap",
        "sourceTexture": "exact_embedded.png",
        "gltfTextureIndex": 17,
    }]
    assert v1._embedded_dependencies({"embeddedDependencyTextures": embedded}) is embedded

    technique, recipe = v1._material_technique(
        "*fixture",
        {"techniqueSet": "lit_sm_wrong"},
        {"*fixture": {"material": "*fixture", "techniqueSet": "lit_sm_exact"}},
    )
    assert technique == "lit_sm_exact" and recipe is not None

    technique, recipe = v1._material_technique(
        "*fixture",
        {"generatedShaderRecipeV1": {"techniqueSet": "lit_sm_attached"}},
        {},
    )
    assert technique == "lit_sm_attached" and recipe is not None

    duplicate = deps + [{
        "layerIndex": 0,
        "semantic": "specularMap",
        "sourceTexture": "other_s.png",
    }]
    try:
        v1._role_dependency(duplicate, 0, "specularMap")
    except v1.BlenderLayerPreviewError:
        pass
    else:
        raise AssertionError("ambiguous exact dependency did not fail closed")

    try:
        v1._source(None, material="*fixture", layer=3, role="colorMap", required=True)
    except v1.BlenderLayerPreviewError:
        pass
    else:
        raise AssertionError("missing required dependency did not fail closed")

    print("PASS: T6 Blender generated-layer preview v2 preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
