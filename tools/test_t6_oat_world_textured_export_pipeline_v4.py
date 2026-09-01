#!/usr/bin/env python3
"""Regression for production T6 world export pipeline v4 stage wiring."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v4 as pipeline


def _write(path: Path, data: bytes = b"fixture") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def main() -> int:
    originals = {
        name: getattr(pipeline, name)
        for name in (
            "run_pipeline",
            "build_manifest",
            "stage_dds",
            "build_lightmap_manifest",
            "export_textured",
            "embed_lightmap_dds",
        )
    }
    calls = {
        "base": 0,
        "material": 0,
        "stage": 0,
        "lightmap": 0,
        "export": 0,
        "embed": 0,
    }

    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            oat_material_root = root / "materials"
            dds_root = root / "images"
            oat_material_root.mkdir()
            dds_root.mkdir()

            surfaces = _write(root / "world.surfaces.bin")
            vd0 = _write(root / "world.vd0.bin")
            vd1 = _write(root / "world.vd1.bin")
            indices = _write(root / "world.indices.bin")
            materials = _write(root / "world.materials.bin")
            prefix = _write(root / "zone.prefix.bin")
            catalog = root / "materials.json"
            catalog.write_text(json.dumps({"materials": []}), encoding="utf-8")
            lightmap_catalog = root / "lightmaps.json"
            lightmap_catalog.write_text(
                json.dumps(
                    {
                        "format": "t6-gfxworld-lightmap-catalog-v1",
                        "map": "mp_test",
                        "lightmapCount": 1,
                        "lightmaps": [
                            {
                                "index": 0,
                                "primaryImage": "*lm_p",
                                "secondaryImage": "lm_s",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            normalized_path = out / "mp_test.world.normalized.json"

            def fake_run_pipeline(**kwargs):
                calls["base"] += 1
                assert kwargs["map_name"] in ("mp_test", "mp_no_lm")
                kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
                normalized_path.write_text(
                    json.dumps({"format": "t6-world-mesh-normalized-v1", "map": kwargs["map_name"]}),
                    encoding="utf-8",
                )
                return {
                    "outputs": {"normalizedWorld": {"path": str(normalized_path)}},
                    "validation": {"fixture": True},
                    "manifest": {"format": "base-fixture"},
                    "stats": {"surfaceCount": 1},
                }

            def fake_build_manifest(**kwargs):
                calls["material"] += 1
                assert kwargs["material_root"] == oat_material_root
                assert kwargs["source_texture_extension"] == ".dds"
                return {
                    "format": "t6-material-texture-manifest-v1",
                    "source": {"producer": "t6_oat_material_manifest_v3.py"},
                    "materials": [],
                    "stats": {
                        "missingMaterialCount": 0,
                        "compoundMaterialCount": 2,
                        "reconstructedCompoundMaterialCount": 2,
                        "compoundLayerNormalValidationCount": 4,
                        "oatImageFilenameChangedDependencyCount": 3,
                    },
                }

            def fake_stage_dds(manifest, **kwargs):
                calls["stage"] += 1
                assert manifest["source"]["producer"] == "t6_oat_material_manifest_v3.py"
                assert kwargs["texture_root"] == dds_root
                kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
                return {
                    "format": "t6-dds-texture-stage-manifest-v2",
                    "stats": {
                        "missingTextureCount": 0,
                        "unsupportedTextureCount": 0,
                        "semanticNormalSourceCount": 2,
                        "bc5NormalReconstructionCount": 1,
                    },
                }

            def fake_build_lightmap_manifest(world, catalog_doc, **kwargs):
                calls["lightmap"] += 1
                assert world["format"] == "t6-world-mesh-normalized-v1"
                assert catalog_doc["format"] == "t6-gfxworld-lightmap-catalog-v1"
                assert kwargs["source_texture_extension"] == ".dds"
                return {
                    "format": "t6-world-lightmap-manifest-v2",
                    "map": world["map"],
                    "t6CodeSamplerContract": {
                        "primary": {"codeTextureSource": 4, "samplerAccessor": "lightmapSamplerPrimary"},
                        "secondary": {"codeTextureSource": 5, "samplerAccessor": "lightmapSamplerSecondary"},
                    },
                    "lightmaps": [],
                    "surfaceBindings": [],
                    "stats": {
                        "lightmapCount": 1,
                        "surfacesWithLightmap": 1,
                        "surfacesWithoutLightmap": 0,
                        "referencedLightmapCount": 1,
                    },
                }

            export_stats = {
                "materialManifestMatchedCount": 1,
                "materialManifestUnmatchedCount": 0,
                "missingPreviewTextureCount": 0,
                "missingDependencyTextureCount": 0,
                "materialDependencySourceCount": 2,
                "embeddedDependencyImageCount": 2,
            }

            def fake_export_textured(world, material_manifest, stage_manifest, **kwargs):
                calls["export"] += 1
                assert material_manifest["source"]["producer"] == "t6_oat_material_manifest_v3.py"
                assert stage_manifest["format"] == "t6-dds-texture-stage-manifest-v2"
                assert kwargs["stage_root"].name.endswith(".dds_textures_v2")
                raw = b"BASE"
                return (
                    {
                        "asset": {"version": "2.0"},
                        "buffers": [{"byteLength": len(raw)}],
                        "bufferViews": [],
                        "extras": {"T6": {"exportStats": dict(export_stats)}},
                    },
                    raw,
                )

            def fake_embed_lightmap_dds(gltf, raw, lightmap_manifest, **kwargs):
                calls["embed"] += 1
                assert lightmap_manifest["format"] == "t6-world-lightmap-manifest-v2"
                assert kwargs["dds_root"] == dds_root
                assert kwargs["allow_missing"] is True
                out_gltf = json.loads(json.dumps(gltf))
                out_raw = raw + b"LMAP"
                out_gltf["buffers"][0]["byteLength"] = len(out_raw)
                out_gltf["extras"]["T6"]["lightmapArchive"] = {
                    "format": "t6-world-lightmap-glb-archive-v2",
                    "stats": {
                        "uniqueGfxImageCount": 2,
                        "embeddedGfxImageCount": 1,
                        "missingGfxImageCount": 1,
                        "accountedGfxImageCount": 2,
                    },
                }
                return out_gltf, out_raw

            pipeline.run_pipeline = fake_run_pipeline
            pipeline.build_manifest = fake_build_manifest
            pipeline.stage_dds = fake_stage_dds
            pipeline.build_lightmap_manifest = fake_build_lightmap_manifest
            pipeline.export_textured = fake_export_textured
            pipeline.embed_lightmap_dds = fake_embed_lightmap_dds

            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_test",
                surfaces_path=surfaces,
                vd0_path=vd0,
                vd1_path=vd1,
                indices_path=indices,
                materials_path=materials,
                catalog_path=catalog,
                prefix_path=prefix,
                asset_pointer_array_virtual_base=0x10000000,
                oat_material_root=oat_material_root,
                dds_root=dds_root,
                output_dir=out,
                lightmap_catalog_path=lightmap_catalog,
                write_gltf=True,
                allow_missing_lightmap_dds=True,
            )

            assert result["format"] == "t6-oat-world-textured-export-pipeline-manifest-v4"
            assert result["validation"]["materialManifestProducer"] == "t6_oat_material_manifest_v3.py"
            assert result["validation"]["oatImageFilenameChangedDependencyCount"] == 3
            assert result["validation"]["lightmapCatalogJoined"] is True
            assert result["validation"]["lightmapRawDdsArchiveEmbedded"] is True
            assert result["validation"]["lightmapUniqueGfxImageCount"] == 2
            assert result["validation"]["lightmapEmbeddedGfxImageCount"] == 1
            assert result["validation"]["lightmapMissingGfxImageCount"] == 1
            assert result["validation"]["lightmapAccountedGfxImageCount"] == 2
            assert result["validation"]["oatTexturedGlbRegenerationByteIdentical"] is True
            assert result["validation"]["oatTexturedGltfRegenerationByteIdentical"] is True
            assert result["stats"]["lightmapArchive"]["accountedGfxImageCount"] == 2
            assert result["outputs"]["oatMaterialTextureManifest"]["file"].endswith(
                ".oat_material_texture_manifest_v3.json"
            )
            assert result["outputs"]["worldLightmapManifest"]["file"].endswith(
                ".world_lightmap_manifest_v2.json"
            )
            assert result["outputs"]["oatPortableTexturedGlb"]["file"].endswith(
                ".world_oat_portable_textured_v4.glb"
            )
            assert result["outputs"]["oatPortableTexturedGltf"]["file"].endswith(
                ".world_oat_portable_textured_v4.gltf"
            )
            assert result["manifest"]["file"].endswith(
                ".world_oat_textured_export_manifest_v4.json"
            )
            assert calls == {
                "base": 1,
                "material": 1,
                "stage": 1,
                "lightmap": 1,
                "export": 2,
                "embed": 2,
            }

            # No lightmap catalog: v4 must stay a normal portable textured export
            # and never call the lightmap builder/archive layer.
            calls["lightmap"] = 0
            calls["embed"] = 0
            out_no_lm = root / "out_no_lm"
            result_no_lm = pipeline.run_oat_textured_pipeline(
                map_name="mp_no_lm",
                surfaces_path=surfaces,
                vd0_path=vd0,
                vd1_path=vd1,
                indices_path=indices,
                materials_path=materials,
                catalog_path=catalog,
                prefix_path=prefix,
                asset_pointer_array_virtual_base=0x10000000,
                oat_material_root=oat_material_root,
                dds_root=dds_root,
                output_dir=out_no_lm,
            )
            assert result_no_lm["validation"]["lightmapCatalogJoined"] is False
            assert result_no_lm["validation"]["lightmapRawDdsArchiveEmbedded"] is False
            assert result_no_lm["stats"]["lightmaps"] is None
            assert result_no_lm["stats"]["lightmapArchive"] is None
            assert calls["lightmap"] == 0
            assert calls["embed"] == 0

    finally:
        for name, value in originals.items():
            setattr(pipeline, name, value)

    print("PASS t6_oat_world_textured_export_pipeline_v4 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
