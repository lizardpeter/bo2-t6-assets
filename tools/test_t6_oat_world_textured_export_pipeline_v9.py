#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import t6_oat_world_textured_export_pipeline_v9 as pipeline
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": _sha(data)}


def _write_json(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _reflection_probe() -> dict:
    return {
        "index": 0,
        "origin": [1.0, 2.0, 3.0],
        "lightingSH": {
            "V0": [0.1, 0.2, 0.3, 0.4],
            "V1": [0.5, 0.6, 0.7, 0.8],
            "V2": [0.9, 1.0, 1.1, 1.2],
        },
        "reflectionImage": "probe*fixture",
        "probeVolumeCount": 0,
        "probeVolumes": [],
        "mipLodBias": 0.25,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v9_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        dds_root = root / "dds"
        dds_root.mkdir()

        normalized_path = _write_json(
            out / "fixture.normalized.json",
            {
                "format": "t6-world-mesh-normalized-v1",
                "map": "mp_fixture",
                "surfaces": [{"index": 7, "reflectionProbeIndex": 0}],
            },
        )
        base_manifest_path = _write_json(
            out / "fixture.base_manifest.json",
            {
                "format": "synthetic-base-world-pipeline",
                "outputs": {"normalizedWorld": _record(normalized_path)},
            },
        )

        raw = b"BASE"
        base_doc = {
            "asset": {"version": "2.0"},
            "buffers": [{"byteLength": len(raw)}],
            "bufferViews": [],
            "materials": [
                {
                    "name": "*fixture",
                    "extras": {
                        "T6": {
                            "sourceMaterial": "*fixture",
                            "embeddedDependencyTextures": [],
                        }
                    },
                },
                {"name": "ordinary"},
            ],
            "extras": {"T6": {"sentinel": "v8-preserved"}},
        }
        v8_glb = glb_bytes(base_doc, raw)
        v8_glb_path = out / "mp_fixture.world_oat_portable_textured_v8.glb"
        v8_glb_path.write_bytes(v8_glb)
        old_manifest_path = _write_json(
            out / "mp_fixture.world_oat_textured_export_manifest_v8.json",
            {"format": "obsolete-v8-manifest"},
        )

        reflection_catalog_path = _write_json(
            root / "reflection_catalog.json",
            {
                "format": "t6-gfxworld-reflection-probe-catalog-v1",
                "map": "mp_fixture",
                "reflectionProbeCount": 1,
                "reflectionProbes": [_reflection_probe()],
            },
        )
        recipe_path = _write_json(
            root / "recipes.json",
            {
                "format": "t6-generated-world-shader-recipe-manifest-v1",
                "materials": [
                    {
                        "material": "*fixture",
                        "techniqueSet": "lit_sm_r0c0n0_b1c1n1s1",
                        "pixelShaderArchetype": "ps-fixture",
                        "worldVertFormats": [1],
                        "proof": {
                            "kind": "synthetic-pipeline-v9",
                            "identity": "ps-fixture",
                        },
                    }
                ],
            },
        )
        reflection_dds = b"DDS " + bytes(range(80))
        (dds_root / "probe_fixture.dds").write_bytes(reflection_dds)

        synthetic_v8 = {
            "format": "t6-oat-world-textured-export-pipeline-manifest-v8",
            "map": "mp_fixture",
            "inputs": {"baseWorldPipelineManifest": _record(base_manifest_path)},
            "outputs": {"oatPortableTexturedGlb": _record(v8_glb_path)},
            "validation": {
                "worldVertexFormatRegistryGate": True,
                "t6WgpuAllPipelineDescriptorsExact": True,
            },
            "stats": {
                "worldVertexFormatGate": {"observedFormats": [1]},
                "t6WgpuState": {"allPipelineDescriptorsExact": True},
            },
            "policies": {"v8Sentinel": "preserved"},
            "manifest": _record(old_manifest_path),
        }

        original_runner = pipeline.v8.run_oat_textured_pipeline
        try:
            pipeline.v8.run_oat_textured_pipeline = lambda **kwargs: json.loads(
                json.dumps(synthetic_v8)
            )
            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_fixture",
                surfaces_path=root / "unused.surfaces",
                vd0_path=root / "unused.vd0",
                vd1_path=root / "unused.vd1",
                indices_path=root / "unused.indices",
                materials_path=root / "unused.materials",
                catalog_path=root / "unused.catalog",
                prefix_path=root / "unused.prefix",
                asset_pointer_array_virtual_base=0x1000,
                oat_material_root=root / "unused_oat",
                dds_root=dds_root,
                output_dir=out,
                format_registry_path=root / "unused_registry.json",
                reflection_probe_catalog_path=reflection_catalog_path,
                generated_shader_recipe_manifest_path=recipe_path,
                write_gltf=False,
            )
        finally:
            pipeline.v8.run_oat_textured_pipeline = original_runner

        assert result["format"] == "t6-oat-world-textured-export-pipeline-manifest-v9"
        assert result["policies"]["v8Sentinel"] == "preserved"
        assert result["validation"]["worldVertexFormatRegistryGate"] is True
        assert result["validation"]["t6WgpuAllPipelineDescriptorsExact"] is True
        assert result["validation"]["canonicalGeneratedShaderRecipesAttached"] is True
        assert result["validation"]["generatedShaderRecipeAttachedCount"] == 1
        assert result["validation"]["reflectionProbeCatalogJoined"] is True
        assert result["validation"]["reflectionProbeRawDdsArchiveEmbedded"] is True
        assert result["validation"]["v9PostpassGlbRegenerationByteIdentical"] is True
        assert result["validation"]["reflectionProbeCount"] == 1
        assert result["validation"]["reflectionProbeEmbeddedGfxImageCount"] == 1
        assert result["stats"]["generatedShaderRecipes"]["attachedRecipeCount"] == 1
        assert result["stats"]["reflectionProbeArchive"]["uniquePresentGfxImageCount"] == 1
        assert result["stats"]["reflectionProbeArchive"]["missingGfxImageCount"] == 0

        final_glb_path = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb_path.name.endswith("_v9.glb")
        assert final_glb_path.is_file()
        assert not v8_glb_path.exists()
        assert not old_manifest_path.exists()

        document, final_raw = parse_glb(final_glb_path.read_bytes())
        assert final_raw.startswith(raw)
        assert reflection_dds in final_raw
        assert document["extras"]["T6"]["sentinel"] == "v8-preserved"
        archive = document["extras"]["T6"]["reflectionProbeArchive"]
        assert archive["format"] == "t6-world-reflection-probe-glb-archive-v1"
        assert archive["reflectionProbes"][0]["embedded"] is True
        assert archive["reflectionProbes"][0]["reflectionOatImageAsset"] == "probe*fixture"
        assert archive["reflectionProbes"][0]["reflectionSourceTexture"] == "probe_fixture.dds"

        generated = document["materials"][0]["extras"]["T6"]
        recipe = generated["generatedShaderRecipeV1"]
        assert recipe["material"] == "*fixture"
        assert recipe["techniqueSet"] == "lit_sm_r0c0n0_b1c1n1s1"
        assert recipe["pixelShaderArchetype"] == "ps-fixture"
        assert recipe["layerProgram"][0]["hasNormal"] is True
        assert recipe["layerProgram"][0]["hasSpecular"] is True

        reflection_manifest_path = Path(
            result["outputs"]["worldReflectionProbeManifest"]["path"]
        )
        reflection_manifest = json.loads(
            reflection_manifest_path.read_text(encoding="utf-8")
        )
        assert reflection_manifest["format"] == "t6-world-reflection-probe-manifest-v2"
        assert reflection_manifest["surfaceBindings"][0]["surfaceIndex"] == 7
        assert reflection_manifest["surfaceBindings"][0]["reflectionProbeIndex"] == 0

        final_manifest_path = Path(result["manifest"]["path"])
        persisted = json.loads(final_manifest_path.read_text(encoding="utf-8"))
        assert persisted["format"] == result["format"]
        assert persisted["outputs"]["oatPortableTexturedGlb"]["sha256"] == _sha(
            final_glb_path.read_bytes()
        )

    print("PASS: T6 OAT world textured export pipeline v9 post-pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
