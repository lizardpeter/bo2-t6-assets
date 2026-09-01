#!/usr/bin/env python3
"""Regression for exact OAT T6 lightmap shader provenance inventory."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from t6_lightmap_shader_inventory_v1 import (
    LightmapShaderInventoryError,
    build_inventory,
    parse_lightmap_pixel_shaders,
    parse_techset,
)


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def _material(techset: str) -> str:
    return json.dumps(
        {
            "$schema": "http://openassettools.dev/schema/material.v1.json",
            "_game": "t6",
            "_type": "material",
            "_version": 1,
            "techniqueSet": techset,
            "textures": [],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except LightmapShaderInventoryError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected LightmapShaderInventoryError containing {needle!r}")


def main() -> int:
    # Parser-level coverage first.
    mappings = parse_techset(
        '"lit":\n  lm_world;\n\n"lit sun":\n"lit sun shadow":\n  lm_world_sun;\n'
    )
    assert mappings == [
        {"technique": "lm_world", "techniqueTypes": ["lit"]},
        {
            "technique": "lm_world_sun",
            "techniqueTypes": ["lit sun", "lit sun shadow"],
        },
    ]

    both_technique = '''
{
  stateMap "passthrough";
  vertexShader 4.0 "vs_world"
  {
  }
  pixelShader 4.0 "ps_world_both"
  {
    // Omitted due to matching accessors: lightmapSamplerPrimary = sampler.lightmapSamplerPrimary;
    lmSecondaryTexture = sampler.lightmapSamplerSecondary;
  }
}
'''
    assert parse_lightmap_pixel_shaders(both_technique) == [
        {
            "passIndex": 0,
            "shaderModel": "4.0",
            "pixelShader": "ps_world_both",
            "usesPrimary": True,
            "usesSecondary": True,
            "samplers": ["lightmapSamplerPrimary", "lightmapSamplerSecondary"],
        }
    ]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mats = root / "materials"
        techsets = root / "techsets"
        techniques = root / "techniques"
        shaders = root / "shader_bin"

        _write(mats / "wpc" / "brick.json", _material("wpc_world"))
        _write(mats / "wpc" / "metal.json", _material("wpc_world"))
        # Non-T6 JSON must be ignored, not counted as a material.
        _write(
            mats / "other.json",
            json.dumps({"_game": "t5", "_type": "material", "techniqueSet": "ignore"}),
        )

        _write(
            techsets / "wpc_world.techset",
            '"lit":\n  lm_world;\n\n"lit sun":\n"lit sun shadow":\n  lm_world_sun;\n\n"unlit":\n  unlit_world;\n',
        )
        _write(
            techniques / "lm_world.tech",
            '''
{
  stateMap "passthrough";
  vertexShader 4.0 "vs_world"
  {
  }
  pixelShader 4.0 "ps_world_both"
  {
    // Omitted due to matching accessors: lightmapSamplerPrimary = sampler.lightmapSamplerPrimary;
    // Omitted due to matching accessors: lightmapSamplerSecondary = sampler.lightmapSamplerSecondary;
  }
}
''',
        )
        _write(
            techniques / "lm_world_sun.tech",
            '''
{
  stateMap "passthrough";
  pixelShader 4.0 "ps_primary_only"
  {
    primaryTex = sampler.lightmapSamplerPrimary;
  }
}
{
  stateMap "passthrough";
  pixelShader 4.0 "ps_secondary_only"
  {
    secondaryTex = sampler.lightmapSamplerSecondary;
  }
}
''',
        )
        _write(
            techniques / "unlit_world.tech",
            '''
{
  stateMap "passthrough";
  pixelShader 4.0 "ps_unlit"
  {
  }
}
''',
        )

        _write(shaders / "ps_ps_world_both.cso", b"DXBC" + b"BOTH" * 7)
        _write(shaders / "ps_ps_primary_only.cso", b"DXBC" + b"PRIMARY" * 5)
        _write(shaders / "ps_ps_secondary_only.cso", b"DXBC" + b"SECONDARY" * 4)
        # Unlit is deliberately absent; it must never be requested by the lightmap scan.

        doc = build_inventory(
            material_root=mats,
            techset_root=techsets,
            technique_root=techniques,
            shader_root=shaders,
        )
        assert doc["format"] == "t6-lightmap-shader-inventory-v1"
        assert doc["stats"] == {
            "materialCount": 2,
            "techsetCount": 1,
            "techniqueCount": 3,
            "selectedProvenanceEdgeCount": 6,
            "uniqueLightmapPixelShaderCount": 3,
            "primaryAndSecondaryEdgeCount": 2,
            "primaryOnlyEdgeCount": 2,
            "secondaryOnlyEdgeCount": 2,
            "missingPixelShaderCount": 0,
        }
        assert [x["pixelShader"] for x in doc["uniqueLightmapPixelShaders"]] == [
            "ps_primary_only",
            "ps_secondary_only",
            "ps_world_both",
        ]
        assert all(x["present"] for x in doc["uniqueLightmapPixelShaders"])
        assert all(x["magic"] == "DXBC" for x in doc["uniqueLightmapPixelShaders"])
        assert {x["material"] for x in doc["provenance"]} == {"wpc/brick", "wpc/metal"}
        sun_edges = [x for x in doc["provenance"] if x["technique"] == "lm_world_sun"]
        assert all(x["techniqueTypes"] == ["lit sun", "lit sun shadow"] for x in sun_edges)

        # Determinism.
        doc2 = build_inventory(
            material_root=mats,
            techset_root=techsets,
            technique_root=techniques,
            shader_root=shaders,
        )
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        # Missing selected shader fails closed unless explicitly allowed.
        missing_shader = shaders / "ps_ps_secondary_only.cso"
        saved = missing_shader.read_bytes()
        missing_shader.unlink()
        _expect_error(
            lambda: build_inventory(
                material_root=mats,
                techset_root=techsets,
                technique_root=techniques,
                shader_root=shaders,
            ),
            "missing exact T6 pixel shader",
        )
        allowed = build_inventory(
            material_root=mats,
            techset_root=techsets,
            technique_root=techniques,
            shader_root=shaders,
            allow_missing_shaders=True,
        )
        assert allowed["stats"]["missingPixelShaderCount"] == 1
        assert next(
            x for x in allowed["uniqueLightmapPixelShaders"] if x["pixelShader"] == "ps_secondary_only"
        )["present"] is False
        missing_shader.write_bytes(saved)

        # A present selected shader must be an exact DXBC container, not arbitrary bytes.
        bad_shader = shaders / "ps_ps_primary_only.cso"
        original = bad_shader.read_bytes()
        bad_shader.write_bytes(b"NOPE")
        _expect_error(
            lambda: build_inventory(
                material_root=mats,
                techset_root=techsets,
                technique_root=techniques,
                shader_root=shaders,
            ),
            "not a DXBC container",
        )
        bad_shader.write_bytes(original)

        # Missing technique/techset provenance is never guessed.
        broken_materials = root / "broken_materials"
        _write(broken_materials / "x.json", _material("does_not_exist"))
        _expect_error(
            lambda: build_inventory(
                material_root=broken_materials,
                techset_root=techsets,
                technique_root=techniques,
                shader_root=shaders,
            ),
            "missing exact techset file",
        )

    print("PASS t6_lightmap_shader_inventory_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
