#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v14 as pipeline


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v14_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        glb = out / "mp_nuketown_2020.world_oat_portable_textured_v13.glb"
        glb.write_bytes(b"v13-preserved")
        manifest = out / "mp_nuketown_2020.world_oat_textured_export_manifest_v13.json"
        manifest.write_text("{}\n", encoding="utf-8")

        original_run = pipeline.v13.run_oat_textured_pipeline
        original_recovery = pipeline.v13.recipe_recovery_v5
        seen = []
        try:
            def fake_v13(**kwargs):
                seen.append(pipeline.v13.recipe_recovery_v5)
                return {
                    "format": "t6-oat-world-textured-export-pipeline-manifest-v13",
                    "map": "mp_nuketown_2020",
                    "outputs": {"oatPortableTexturedGlb": _record(glb)},
                    "stats": {"generatedShaderRecipeRecovery": {
                        "format": pipeline.recipe_recovery_v6.FORMAT,
                        "generatedMaterialCount": 120,
                        "normalTransformBoundMaterialCount": 120,
                        "secondaryNormalMaterialCount": 20,
                        "secondaryNormalLayerCount": 21,
                        "directSecondaryNormalLayerCount": 9,
                        "transformedSecondaryNormalLayerCount": 12,
                        "normalTransformBindingCoverageComplete": True,
                    }},
                    "validation": {"v13PairedVertexShaderCoverageComplete": True},
                    "policies": {"v13Sentinel": "preserved"},
                    "manifest": _record(manifest),
                }
            pipeline.v13.run_oat_textured_pipeline = fake_v13
            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_nuketown_2020",
                output_dir=out,
            )
        finally:
            pipeline.v13.run_oat_textured_pipeline = original_run

        assert seen == [pipeline.recipe_recovery_v6]
        assert pipeline.v13.recipe_recovery_v5 is original_recovery
        assert result["format"] == pipeline.FORMAT
        assert result["validation"]["v13PairedVertexShaderCoverageComplete"] is True
        assert result["validation"]["v14AutomaticRecipeRecoveryUsesV6"] is True
        assert result["validation"]["v14NormalTransformBindingCoverageComplete"] is True
        assert result["validation"]["v14NormalTransformBoundMaterialCount"] == 120
        assert result["validation"]["v14SecondaryNormalLayerCount"] == 21
        assert result["validation"]["v14DirectSecondaryNormalLayerCount"] == 9
        assert result["validation"]["v14TransformedSecondaryNormalLayerCount"] == 12
        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb.name.endswith("_v14.glb")
        assert final_glb.read_bytes() == b"v13-preserved"
        assert not glb.exists()
        assert not manifest.exists()
        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT

        bad_glb = out / "mp_nuketown_2020.world_oat_portable_textured_v13.glb"
        bad_glb.write_bytes(b"bad")
        bad_manifest = out / "bad_v13.json"
        bad_manifest.write_text("{}\n", encoding="utf-8")
        try:
            pipeline.v13.run_oat_textured_pipeline = lambda **kwargs: {
                "format": "t6-oat-world-textured-export-pipeline-manifest-v13",
                "map": "mp_nuketown_2020",
                "outputs": {"oatPortableTexturedGlb": _record(bad_glb)},
                "stats": {"generatedShaderRecipeRecovery": {
                    "format": "t6-nuketown-generated-shader-recipe-recovery-v5"
                }},
                "validation": {}, "policies": {}, "manifest": _record(bad_manifest),
            }
            try:
                pipeline.run_oat_textured_pipeline(map_name="mp_nuketown_2020", output_dir=out)
            except pipeline.OatTexturedPipelineV14Error as exc:
                assert "did not reach v6" in str(exc)
            else:
                raise AssertionError("automatic non-v6 normal recipe was accepted")
        finally:
            pipeline.v13.run_oat_textured_pipeline = original_run
            pipeline.v13.recipe_recovery_v5 = original_recovery

    print("PASS: production T6 OAT world textured pipeline v14 normal transform promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
