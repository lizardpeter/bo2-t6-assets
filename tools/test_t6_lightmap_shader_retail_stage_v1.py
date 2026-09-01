#!/usr/bin/env python3
"""Synthetic regression for retail lightmap shader staging v1."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from t6_lightmap_shader_retail_stage_v1 import RetailLightmapStageError, build_stage


def _write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def _material(techset: str) -> str:
    return json.dumps({
        "_game": "t6", "_type": "material", "_version": 1,
        "techniqueSet": techset, "textures": [], "constants": [],
        "stateBits": [], "stateBitsEntry": [],
    })


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "oat"
        out = Path(td) / "out"
        _write(root / "materials" / "world" / "brick.json", _material("world_lm"))
        _write(root / "techsets" / "world_lm.techset", 'technique "world_lit.tech";\n')
        _write(
            root / "techniques" / "world_lit.tech",
            'lightmapSamplerPrimary = sampler.lightmapSamplerPrimary;\n'
            'lightmapSamplerSecondary = sampler.lightmapSamplerSecondary;\n'
            'pixelShader 5.0 "world_lit_ps";\n',
        )
        _write(root / "shader_bin" / "ps_world_lit_ps.cso", b"DXBCsynthetic")

        doc = build_stage(
            oat_root=root,
            output_dir=out,
            map_name="mp_fixture",
            retail_ff_sha256="a" * 64,
        )
        assert doc["stats"]["materialChainCount"] == 1
        assert doc["stats"]["uniquePixelShaderCount"] == 1
        assert doc["stats"]["primaryTechniqueEdgeCount"] == 1
        assert doc["stats"]["secondaryTechniqueEdgeCount"] == 1
        assert doc["stats"]["bothRoleTechniqueEdgeCount"] == 1
        staged = Path(doc["stagedRoot"])
        assert (staged / "materials" / "world" / "brick.json").is_file()
        assert (staged / "techsets" / "world_lm.techset").is_file()
        assert (staged / "techniques" / "world_lit.tech").is_file()
        assert (staged / "shader_bin" / "ps_world_lit_ps.cso").read_bytes() == b"DXBCsynthetic"

        # Broken provenance must fail closed rather than silently dropping the edge.
        bad = Path(td) / "bad"
        _write(bad / "materials" / "a.json", _material("missing"))
        for dirname in ("techsets", "techniques", "shader_bin"):
            (bad / dirname).mkdir(parents=True, exist_ok=True)
        try:
            build_stage(oat_root=bad, output_dir=Path(td) / "badout", map_name="bad")
        except RetailLightmapStageError as exc:
            assert "missing techniqueSet" in str(exc)
        else:
            raise AssertionError("expected missing techniqueSet failure")

    print("PASS t6_lightmap_shader_retail_stage_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
