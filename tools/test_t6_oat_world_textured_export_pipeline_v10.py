#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v10 as pipeline


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": _sha(data)}


def _recovery_doc() -> dict:
    return {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": [],
        "recovery": {
            "format": "t6-nuketown-generated-shader-recipe-recovery-v1",
            "producer": "synthetic-v10-test",
            "map": "mp_nuketown_2020",
            "retailExpandedSha256": "e" * 64,
            "generatedMaterialCount": 120,
            "uniqueTechniqueSetCount": 34,
            "uniqueSlot4PixelShaderCount": 34,
            "crossTechniqueSetShaderReuseCount": 0,
            "worldVertFormatHistogram": {"1": 95, "2": 7, "3": 17, "6": 1},
            "slotIndex": 4,
            "slotLabel": "lit",
            "recipeRowsSha256": "r" * 64,
            "strictNuketownInvariants": True,
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v10_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        expanded = root / "mp_nuketown_2020.expanded.bin"
        expanded.write_bytes(b"retail-expanded-fixture")
        oat_shader_root = root / "oat"
        oat_shader_root.mkdir()

        recovery_calls: list[tuple[Path, Path, bool]] = []
        v9_calls: list[dict] = []
        original_recover = pipeline.recipe_recovery.recover
        original_v9 = pipeline.v9.run_oat_textured_pipeline

        def fake_recover(*, expanded_world, oat_root, strict_nuketown):
            recovery_calls.append((Path(expanded_world), Path(oat_root), strict_nuketown))
            return json.loads(json.dumps(_recovery_doc()))

        def fake_v9(**kwargs):
            v9_calls.append(kwargs)
            recipe_path = Path(kwargs["generated_shader_recipe_manifest_path"])
            assert recipe_path.is_file()
            persisted_recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            assert persisted_recipe["recovery"]["generatedMaterialCount"] == 120
            glb = out / "mp_nuketown_2020.world_oat_portable_textured_v9.glb"
            glb.write_bytes(b"GLB-v9-content")
            old_manifest = out / "mp_nuketown_2020.world_oat_textured_export_manifest_v9.json"
            old_manifest.write_text("{}\n", encoding="utf-8")
            return {
                "format": "t6-oat-world-textured-export-pipeline-manifest-v9",
                "map": "mp_nuketown_2020",
                "inputs": {"generatedShaderRecipeManifest": _record(recipe_path)},
                "outputs": {"oatPortableTexturedGlb": _record(glb)},
                "stats": {"generatedShaderRecipes": {"attachedRecipeCount": 120}},
                "validation": {
                    "canonicalGeneratedShaderRecipesAttached": True,
                    "generatedShaderRecipeAttachedCount": 120,
                    "v9PostpassGlbRegenerationByteIdentical": True,
                },
                "policies": {"v9Sentinel": "preserved"},
                "manifest": _record(old_manifest),
            }

        try:
            pipeline.recipe_recovery.recover = fake_recover
            pipeline.v9.run_oat_textured_pipeline = fake_v9
            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_nuketown_2020",
                surfaces_path=root / "unused.surfaces",
                vd0_path=root / "unused.vd0",
                vd1_path=root / "unused.vd1",
                indices_path=root / "unused.indices",
                materials_path=root / "unused.materials",
                catalog_path=root / "unused.catalog",
                prefix_path=root / "unused.prefix",
                asset_pointer_array_virtual_base=0x1000,
                oat_material_root=root / "unused_material_oat",
                dds_root=root / "unused_dds",
                output_dir=out,
                format_registry_path=root / "unused_registry.json",
                generated_shader_expanded_world_path=expanded,
                oat_shader_root=oat_shader_root,
            )
        finally:
            pipeline.recipe_recovery.recover = original_recover
            pipeline.v9.run_oat_textured_pipeline = original_v9

        assert len(recovery_calls) == 2
        assert all(call == (expanded, oat_shader_root, True) for call in recovery_calls)
        assert len(v9_calls) == 1
        assert result["format"] == "t6-oat-world-textured-export-pipeline-manifest-v10"
        assert result["policies"]["v9Sentinel"] == "preserved"
        assert result["validation"]["canonicalGeneratedShaderRecipesAttached"] is True
        assert result["validation"]["v10AutomaticGeneratedShaderRecipeRecovery"] is True
        assert result["validation"]["v10RecoveredRecipeManifestDeterministic"] is True
        assert result["validation"]["v10RecoveredGeneratedMaterialCount"] == 120
        assert result["validation"]["v10RecoveredUniqueTechniqueSetCount"] == 34
        assert result["validation"]["v10RecoveredUniqueSlot4PixelShaderCount"] == 34
        assert result["validation"]["v10RecoveredCrossTechniqueSetShaderReuseCount"] == 0
        assert result["stats"]["generatedShaderRecipeRecovery"]["worldVertFormatHistogram"] == {
            "1": 95, "2": 7, "3": 17, "6": 1
        }

        recipe_path = Path(result["inputs"]["generatedShaderRecipeManifest"]["path"])
        assert recipe_path.name == "mp_nuketown_2020.generated_shader_recipes_v1.json"
        assert recipe_path.is_file()
        assert result["inputs"]["generatedShaderRecipeRecoveryExpandedWorld"]["sha256"] == _sha(
            expanded.read_bytes()
        )
        assert result["inputs"]["generatedShaderRecipeRecoveryOatRoot"] == str(oat_shader_root)

        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb.name.endswith("_v10.glb")
        assert final_glb.read_bytes() == b"GLB-v9-content"
        assert not (out / "mp_nuketown_2020.world_oat_portable_textured_v9.glb").exists()
        assert not (out / "mp_nuketown_2020.world_oat_textured_export_manifest_v9.json").exists()
        final_manifest = Path(result["manifest"]["path"])
        assert final_manifest.name.endswith("_v10.json")
        persisted = json.loads(final_manifest.read_text(encoding="utf-8"))
        assert persisted["format"] == result["format"]

        # Automatic recovery cannot silently compete with a manual recipe source.
        try:
            pipeline.run_oat_textured_pipeline(
                map_name="mp_nuketown_2020",
                surfaces_path=root / "x", vd0_path=root / "x", vd1_path=root / "x",
                indices_path=root / "x", materials_path=root / "x", catalog_path=root / "x",
                prefix_path=root / "x", asset_pointer_array_virtual_base=0,
                oat_material_root=root / "x", dds_root=root / "x", output_dir=out,
                format_registry_path=root / "x",
                generated_shader_recipe_manifest_path=root / "manual.json",
                generated_shader_expanded_world_path=expanded,
                oat_shader_root=oat_shader_root,
            )
        except pipeline.OatTexturedPipelineV10Error as exc:
            assert "mutually exclusive" in str(exc)
        else:
            raise AssertionError("manual + automatic shader recipe sources were both accepted")

        # The recovery contract is intentionally not generalized to an unproven map.
        original_recover = pipeline.recipe_recovery.recover
        pipeline.recipe_recovery.recover = fake_recover
        try:
            try:
                pipeline.run_oat_textured_pipeline(
                    map_name="mp_raid",
                    surfaces_path=root / "x", vd0_path=root / "x", vd1_path=root / "x",
                    indices_path=root / "x", materials_path=root / "x", catalog_path=root / "x",
                    prefix_path=root / "x", asset_pointer_array_virtual_base=0,
                    oat_material_root=root / "x", dds_root=root / "x", output_dir=out,
                    format_registry_path=root / "x",
                    generated_shader_expanded_world_path=expanded,
                    oat_shader_root=oat_shader_root,
                )
            except pipeline.OatTexturedPipelineV10Error as exc:
                assert "source-gated" in str(exc)
            else:
                raise AssertionError("Nuketown-only automatic recovery widened to another map")
        finally:
            pipeline.recipe_recovery.recover = original_recover

    print("PASS: T6 OAT world textured export pipeline v10 automatic shader recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
