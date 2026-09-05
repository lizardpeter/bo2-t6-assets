#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v21 as pipeline
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def fixture_document(raw: bytes) -> dict:
    technique = "lit_sm_r0c0n0x0_b1c1s1"
    recipe = {
        "material": "*fixture",
        "techniqueSet": technique,
        "pixelShaderArchetype": "sha256:" + "1" * 64,
        "vertexShaderArchetype": "sha256:" + "2" * 64,
        "worldVertFormats": [1],
        "layerProgram": canonical_layer_program(technique),
        "proof": {"kind": "synthetic v21 orchestration fixture"},
    }
    deps = [
        {
            "layerIndex": 0, "role": "colorMap", "semantic": "colorMap",
            "sourceTexture": "base.png", "gltfTextureIndex": 0,
        },
        {
            "layerIndex": 1, "role": "colorMap", "semantic": "colorMap",
            "sourceTexture": "layer.png", "gltfTextureIndex": 1,
        },
        {
            "layerIndex": 1, "role": "specularMap", "semantic": "specularMap",
            "sourceTexture": "layer_spec.png", "gltfTextureIndex": 2,
        },
    ]
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "materials": [{
            "name": "*fixture",
            "extras": {"T6": {
                "generatedShaderRecipeV1": recipe,
                "embeddedDependencyTextures": deps,
            }},
        }],
        "extras": {"T6": {
            "generatedNormalBasisAttributesV2": {
                "format": "t6-generated-normal-basis-attributes-v2",
                "contractSha256": "v20-sentinel",
            },
        }},
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v21_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        raw = b"v20-bin-preserved"
        doc = fixture_document(raw)
        old_glb = out / "mp_nuketown_2020.world_oat_portable_textured_v20.glb"
        old_glb.write_bytes(glb_bytes(doc, raw))
        old_manifest = out / "v20.json"
        old_manifest.write_text("{}\n", encoding="utf-8")

        original = pipeline.v20.run_oat_textured_pipeline
        calls = []
        try:
            def fake_v20(**kwargs):
                calls.append(kwargs["map_name"])
                return {
                    "format": "t6-oat-world-textured-export-pipeline-manifest-v20",
                    "map": pipeline.SPECULAR_PROOF_MAP,
                    "outputs": {"oatPortableTexturedGlb": _record(old_glb)},
                    "inputs": {},
                    "stats": {"v20Sentinel": {"kept": True}},
                    "validation": {"v20V19BinExactPrefix": True},
                    "policies": {"v20Sentinel": "preserved"},
                    "manifest": _record(old_manifest),
                }
            pipeline.v20.run_oat_textured_pipeline = fake_v20
            result = pipeline.run_oat_textured_pipeline(
                map_name=pipeline.SPECULAR_PROOF_MAP,
                output_dir=out,
            )
        finally:
            pipeline.v20.run_oat_textured_pipeline = original

        assert calls == [pipeline.SPECULAR_PROOF_MAP]
        assert result["format"] == pipeline.FORMAT
        assert result["validation"]["v20V19BinExactPrefix"] is True
        assert result["validation"]["v21GeneratedLayeredSpecularStateAttached"] is True
        assert result["validation"]["v21BinByteIdenticalToV20"] is True
        assert result["validation"]["v21LayeredSpecularMaterialCount"] == 1
        assert result["validation"]["v21SecondarySpecularLayerCount"] == 1
        assert result["policies"]["v20Sentinel"] == "preserved"
        assert result["stats"]["v20Sentinel"] == {"kept": True}

        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb.name.endswith("_v21.glb")
        final_doc, final_raw = parse_glb(final_glb.read_bytes())
        assert final_raw == raw
        state = final_doc["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"][
            "generatedSpecularStateV1"
        ]
        assert state["format"] == "t6-generated-layered-specular-state-v1"
        assert state["baseline"]["mode"] == "retail_fallback"
        assert state["baseline"]["alphaMode"] == "baseColorAlpha"
        assert state["steps"][0]["dependency"]["sourceTexture"] == "layer_spec.png"
        assert state["steps"][0]["factorBinding"]["kind"] == "exactRgbWeight"
        root_contract = final_doc["extras"]["T6"]["generatedLayeredSpecularState"]
        assert root_contract["format"] == "t6-generated-layered-specular-state-v1"
        assert root_contract["stats"]["binByteIdentical"] is True

        assert not old_glb.exists()
        assert not old_manifest.exists()
        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT
        assert persisted["validation"]["v21BinByteIdenticalToV20"] is True
        assert persisted["stats"]["generatedLayeredSpecularState"]["secondarySpecularLayerCount"] == 1

        # Map gating happens before v20 so an unretained map cannot accidentally
        # inherit the Nuketown-specific state promotion.
        pipeline.v20.run_oat_textured_pipeline = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("v20 should not run for rejected map")
        )
        try:
            try:
                pipeline.run_oat_textured_pipeline(map_name="mp_raid", output_dir=out)
            except pipeline.OatTexturedPipelineV21Error as exc:
                assert "source-gated" in str(exc)
            else:
                raise AssertionError("v21 accepted unretained map")
        finally:
            pipeline.v20.run_oat_textured_pipeline = original

    print("PASS: production v21 exact Nuketown generated specular-state orchestration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
