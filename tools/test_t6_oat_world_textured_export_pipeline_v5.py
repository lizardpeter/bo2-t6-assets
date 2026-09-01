#!/usr/bin/env python3
"""Regression for production T6 world export pipeline v5 promotion/wiring."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v5 as pipeline


def _record(path: Path) -> dict:
    payload = path.read_bytes()
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(payload),
        "sha256": pipeline._sha256(payload),
    }


def main() -> int:
    old_run = pipeline.v4.run_oat_textured_pipeline
    old_builder = pipeline.v4.build_lightmap_manifest
    old_embedder = pipeline.v4.embed_lightmap_dds
    calls = {"run": 0}

    def fake_v4_run(**kwargs):
        calls["run"] += 1
        assert pipeline.v4.build_lightmap_manifest is pipeline.build_lightmap_manifest_v3
        assert pipeline.v4.embed_lightmap_dds is pipeline.embed_lightmap_dds_v3

        out = kwargs["output_dir"]
        out.mkdir(parents=True, exist_ok=True)
        stem = kwargs["map_name"]

        glb = out / f"{stem}.world_oat_portable_textured_v4.glb"
        glb.write_bytes(b"GLB-V4-STAGING-WITH-V3-LIGHTMAPS")
        outputs = {
            "oatMaterialTextureManifest": {
                "file": f"{stem}.oat_material_texture_manifest_v3.json",
                "path": str(out / f"{stem}.oat_material_texture_manifest_v3.json"),
                "bytes": 0,
                "sha256": "",
            },
            "ddsTextureStageManifest": {
                "file": f"{stem}.dds_texture_stage_manifest_v2.json",
                "path": str(out / f"{stem}.dds_texture_stage_manifest_v2.json"),
                "bytes": 0,
                "sha256": "",
            },
            "oatPortableTexturedGlb": _record(glb),
        }

        if kwargs["write_gltf"]:
            gltf = out / f"{stem}.world_oat_portable_textured_v4.gltf"
            gltf.write_bytes(b"GLTF-V4-STAGING-WITH-V3-LIGHTMAPS")
            outputs["oatPortableTexturedGltf"] = _record(gltf)

        lightmap_stats = None
        archive_stats = None
        if kwargs["lightmap_catalog_path"] is not None:
            lm = out / f"{stem}.world_lightmap_manifest_v2.json"
            lm.write_text(
                json.dumps(
                    {
                        "format": "t6-world-lightmap-manifest-v3",
                        "map": stem,
                        "stats": {"fixture": True},
                    }
                ),
                encoding="utf-8",
            )
            outputs["worldLightmapManifest"] = _record(lm)
            lightmap_stats = {
                "lightmapCount": 2,
                "declaredRoleCount": 4,
                "presentRoleDependencyUseCount": 2,
                "presentPrimaryImageCount": 0,
                "absentPrimaryImageCount": 2,
                "presentSecondaryImageCount": 2,
                "absentSecondaryImageCount": 0,
                "surfacesWithLightmap": 10,
                "surfacesWithoutLightmap": 3,
                "referencedLightmapCount": 2,
            }
            archive_stats = {
                "lightmapCount": 2,
                "declaredRoleCount": 4,
                "presentDependencyUseCount": 2,
                "absentRoleCount": 2,
                "uniqueGfxImageCount": 2,
                "embeddedGfxImageCount": 2,
                "missingGfxImageCount": 0,
                "accountedGfxImageCount": 2,
            }

        old_manifest = out / f"{stem}.world_oat_textured_export_manifest_v4.json"
        old_manifest.write_text('{"format":"v4-staging"}\n', encoding="utf-8")

        return {
            "format": "t6-oat-world-textured-export-pipeline-manifest-v4",
            "map": stem,
            "inputs": {"fixture": True},
            "outputs": outputs,
            "validation": {
                "oatTexturedGlbRegenerationByteIdentical": True,
                "oatTexturedGltfRegenerationByteIdentical": bool(kwargs["write_gltf"]),
                "lightmapCatalogJoined": kwargs["lightmap_catalog_path"] is not None,
                "lightmapRawDdsArchiveEmbedded": kwargs["lightmap_catalog_path"] is not None,
            },
            "stats": {
                "baseWorld": {"surfaceCount": 1},
                "oatMaterials": {},
                "ddsStage": {},
                "texturedGltf": {"materialManifestMatchedCount": 1},
                "lightmaps": lightmap_stats,
                "lightmapArchive": archive_stats,
            },
            "policies": {"lightmaps": "v4-staging-policy"},
            "manifest": _record(old_manifest),
        }

    pipeline.v4.run_oat_textured_pipeline = fake_v4_run
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs = {}
            for name in (
                "surfaces",
                "vd0",
                "vd1",
                "indices",
                "materials",
                "catalog",
                "prefix",
            ):
                path = root / f"{name}.fixture"
                path.write_bytes(b"x")
                inputs[name] = path
            oat_root = root / "oat"
            dds_root = root / "dds"
            oat_root.mkdir()
            dds_root.mkdir()
            lightmap_catalog = root / "lightmaps.json"
            lightmap_catalog.write_text("{}", encoding="utf-8")

            out = root / "out"
            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_nuketown_2020",
                surfaces_path=inputs["surfaces"],
                vd0_path=inputs["vd0"],
                vd1_path=inputs["vd1"],
                indices_path=inputs["indices"],
                materials_path=inputs["materials"],
                catalog_path=inputs["catalog"],
                prefix_path=inputs["prefix"],
                asset_pointer_array_virtual_base=0x1000,
                oat_material_root=oat_root,
                dds_root=dds_root,
                output_dir=out,
                lightmap_catalog_path=lightmap_catalog,
                write_gltf=True,
            )

            assert result["format"] == "t6-oat-world-textured-export-pipeline-manifest-v5"
            assert result["validation"]["nullableRetailLightmapRoles"] is True
            assert result["validation"]["lightmapManifestFormat"] == "t6-world-lightmap-manifest-v3"
            assert result["validation"]["lightmapArchiveFormat"] == "t6-world-lightmap-glb-archive-v3"
            assert result["validation"]["lightmapDeclaredRoleCount"] == 4
            assert result["validation"]["lightmapPresentRoleDependencyUseCount"] == 2
            assert result["validation"]["lightmapAbsentPrimaryImageCount"] == 2
            assert result["validation"]["lightmapPresentSecondaryImageCount"] == 2
            assert result["validation"]["lightmapArchivePresentDependencyUseCount"] == 2
            assert result["validation"]["lightmapArchiveAbsentRoleCount"] == 2
            assert "never synthesized" in result["policies"]["lightmapRolePresence"]

            assert result["outputs"]["worldLightmapManifest"]["file"].endswith(
                ".world_lightmap_manifest_v3.json"
            )
            assert result["outputs"]["oatPortableTexturedGlb"]["file"].endswith(
                ".world_oat_portable_textured_v5.glb"
            )
            assert result["outputs"]["oatPortableTexturedGltf"]["file"].endswith(
                ".world_oat_portable_textured_v5.gltf"
            )
            assert result["manifest"]["file"].endswith(
                ".world_oat_textured_export_manifest_v5.json"
            )
            assert not (out / "mp_nuketown_2020.world_oat_portable_textured_v4.glb").exists()
            assert not (out / "mp_nuketown_2020.world_oat_portable_textured_v4.gltf").exists()
            assert not (out / "mp_nuketown_2020.world_lightmap_manifest_v2.json").exists()
            assert not (out / "mp_nuketown_2020.world_oat_textured_export_manifest_v4.json").exists()

            out_no_lm = root / "out_no_lm"
            no_lm = pipeline.run_oat_textured_pipeline(
                map_name="mp_no_lm",
                surfaces_path=inputs["surfaces"],
                vd0_path=inputs["vd0"],
                vd1_path=inputs["vd1"],
                indices_path=inputs["indices"],
                materials_path=inputs["materials"],
                catalog_path=inputs["catalog"],
                prefix_path=inputs["prefix"],
                asset_pointer_array_virtual_base=0x1000,
                oat_material_root=oat_root,
                dds_root=dds_root,
                output_dir=out_no_lm,
                lightmap_catalog_path=None,
                write_gltf=False,
            )
            assert no_lm["format"].endswith("-v5")
            assert no_lm["validation"]["lightmapManifestFormat"] is None
            assert no_lm["validation"]["lightmapArchiveFormat"] is None
            assert "worldLightmapManifest" not in no_lm["outputs"]
            assert no_lm["outputs"]["oatPortableTexturedGlb"]["file"].endswith(
                ".world_oat_portable_textured_v5.glb"
            )
            assert no_lm["manifest"]["file"].endswith(
                ".world_oat_textured_export_manifest_v5.json"
            )

            assert calls["run"] == 2

        assert pipeline.v4.build_lightmap_manifest is old_builder
        assert pipeline.v4.embed_lightmap_dds is old_embedder

        def raising_v4_run(**kwargs):
            assert pipeline.v4.build_lightmap_manifest is pipeline.build_lightmap_manifest_v3
            assert pipeline.v4.embed_lightmap_dds is pipeline.embed_lightmap_dds_v3
            raise RuntimeError("fixture failure")

        pipeline.v4.run_oat_textured_pipeline = raising_v4_run
        try:
            pipeline.run_oat_textured_pipeline(
                map_name="mp_fail",
                surfaces_path=Path("s"),
                vd0_path=Path("v0"),
                vd1_path=Path("v1"),
                indices_path=Path("i"),
                materials_path=Path("m"),
                catalog_path=Path("c"),
                prefix_path=Path("p"),
                asset_pointer_array_virtual_base=0,
                oat_material_root=Path("o"),
                dds_root=Path("d"),
                output_dir=Path("out"),
            )
        except RuntimeError as exc:
            assert str(exc) == "fixture failure"
        else:
            raise AssertionError("fixture failure did not propagate")
        assert pipeline.v4.build_lightmap_manifest is old_builder
        assert pipeline.v4.embed_lightmap_dds is old_embedder

    finally:
        pipeline.v4.run_oat_textured_pipeline = old_run
        pipeline.v4.build_lightmap_manifest = old_builder
        pipeline.v4.embed_lightmap_dds = old_embedder

    print("PASS t6_oat_world_textured_export_pipeline_v5 promotion regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
