#!/usr/bin/env python3
"""Regression for T6 code-lightmap-sampler -> DXBC resource-name bridge."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from t6_lightmap_shader_inventory_v2 import (
    build_inventory,
    parse_lightmap_pixel_shaders_v2,
)


def _write(path: Path, payload: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")


def _material() -> str:
    return json.dumps(
        {
            "_game": "t6",
            "_type": "material",
            "_version": 1,
            "techniqueSet": "world",
            "textures": [],
        },
        sort_keys=True,
    )


def main() -> int:
    technique = '''
{
  stateMap "passthrough";
  pixelShader 4.0 "world_lm"
  {
    lmPrimaryTexture = sampler.lightmapSamplerPrimary;
    // Omitted due to matching accessors: lightmapSamplerSecondary = sampler.lightmapSamplerSecondary;
  }
}
'''
    parsed = parse_lightmap_pixel_shaders_v2(technique)
    assert len(parsed) == 1
    assert parsed[0]["usesPrimary"] is True
    assert parsed[0]["usesSecondary"] is True
    assert parsed[0]["lightmapBindings"] == [
        {
            "codeSampler": "lightmapSamplerPrimary",
            "shaderResource": "lmPrimaryTexture",
            "sourceLine": "lmPrimaryTexture = sampler.lightmapSamplerPrimary;",
        },
        {
            "codeSampler": "lightmapSamplerSecondary",
            "shaderResource": "lightmapSamplerSecondary",
            "sourceLine": "// Omitted due to matching accessors: lightmapSamplerSecondary = sampler.lightmapSamplerSecondary;",
        },
    ]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mats = root / "materials"
        techsets = root / "techsets"
        techniques = root / "techniques"
        shaders = root / "shader_bin"

        _write(mats / "wpc" / "wall.json", _material())
        _write(techsets / "world.techset", '"lit":\n  world_lm;\n')
        _write(techniques / "world_lm.tech", technique)
        _write(shaders / "ps_world_lm.cso", b"DXBC" + b"fixture")

        doc = build_inventory(
            material_root=mats,
            techset_root=techsets,
            technique_root=techniques,
            shader_root=shaders,
        )
        assert doc["format"] == "t6-lightmap-shader-inventory-v2"
        assert doc["source"]["producer"] == "t6_lightmap_shader_inventory_v2.py"
        assert doc["stats"]["primaryBindingCount"] == 1
        assert doc["stats"]["secondaryBindingCount"] == 1
        assert doc["stats"]["distinctLightmapShaderResourceCount"] == 2
        edge = doc["provenance"][0]
        assert edge["lightmapBindings"] == parsed[0]["lightmapBindings"]
        shader = doc["uniqueLightmapPixelShaders"][0]
        assert shader["lightmapCodeSamplers"] == [
            "lightmapSamplerPrimary",
            "lightmapSamplerSecondary",
        ]
        assert shader["lightmapShaderResources"] == [
            "lightmapSamplerSecondary",
            "lmPrimaryTexture",
        ]

        # Output remains deterministic.
        doc2 = build_inventory(
            material_root=mats,
            techset_root=techsets,
            technique_root=techniques,
            shader_root=shaders,
        )
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

    print("PASS t6_lightmap_shader_inventory_v2 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
