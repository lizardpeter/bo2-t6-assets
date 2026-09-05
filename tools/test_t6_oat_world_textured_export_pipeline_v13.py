#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v13 as pipeline


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": _sha(data)}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v13_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        v12_glb = out / "mp_nuketown_2020.world_oat_portable_textured_v12.glb"
        v12_glb.write_bytes(b"v12-portable-glb-fixture")
        v12_gltf = out / "mp_nuketown_2020.world_oat_portable_textured_v12.gltf"
        v12_gltf.write_text('{"asset":{"version":"2.0"}}\n', encoding="utf-8")
        old_manifest = out / "mp_nuketown_2020.world_oat_textured_export_manifest_v12.json"
        old_manifest.write_text("{}\n", encoding="utf-8")

        original_run = pipeline.v12.run_oat_textured_pipeline
        original_recovery = pipeline.v11.recipe_recovery_v4
        calls = []
        seen_recovery = []
        try:
            def fake_v12(**kwargs):
                calls.append(kwargs)
                seen_recovery.append(pipeline.v11.recipe_recovery_v4)
                return {
                    "format": "t6-oat-world-textured-export-pipeline-manifest-v12",
                    "map": "mp_nuketown_2020",
                    "inputs": {"fixture": True},
                    "outputs": {
                        "oatPortableTexturedGlb": _record(v12_glb),
                        "oatPortableTexturedGltf": _record(v12_gltf),
                    },
                    "stats": {
                        "generatedShaderRecipeRecovery": {
                            "format": pipeline.recipe_recovery_v5.FORMAT,
                            "generatedMaterialCount": 120,
                            "pairedVertexShaderMaterialCount": 120,
                            "pairedVertexShaderTechniqueSetCount": 34,
                            "uniquePairedVertexShaderCount": 19,
                            "pairedVertexShaderCoverageComplete": True,
                        },
                        "generatedAttributeContract": {"generatedPrimitiveCount": 933},
                    },
                    "validation": {
                        "v12GeneratedAttributeRegenerationByteIdentical": True,
                        "v12ExistingBinaryPrefixPreserved": True,
                    },
                    "policies": {"v12Sentinel": "preserved"},
                    "manifest": _record(old_manifest),
                }

            pipeline.v12.run_oat_textured_pipeline = fake_v12
            result = pipeline.run_oat_textured_pipeline(
                map_name="mp_nuketown_2020",
                surfaces_path=root / "unused.surfaces",
                vd0_path=root / "unused.vd0",
                vd1_path=root / "unused.vd1",
                indices_path=root / "unused.indices",
                materials_path=root / "unused.materials",
                catalog_path=root / "unused.catalog",
                prefix_path=root / "unused.prefix",
                asset_pointer_array_virtual_base=0,
                oat_material_root=root / "unused_oat",
                dds_root=root / "unused_dds",
                output_dir=out,
                format_registry_path=root / "unused_registry",
                write_gltf=True,
            )
        finally:
            pipeline.v12.run_oat_textured_pipeline = original_run

        assert len(calls) == 1
        assert seen_recovery == [pipeline.recipe_recovery_v5]
        # v13 must restore the old v11 module global even after the wrapped call.
        assert pipeline.v11.recipe_recovery_v4 is original_recovery
        assert result["format"] == pipeline.FORMAT
        assert result["policies"]["v12Sentinel"] == "preserved"
        assert result["validation"]["v12GeneratedAttributeRegenerationByteIdentical"] is True
        assert result["validation"]["v13AutomaticRecipeRecoveryUsesV5"] is True
        assert result["validation"]["v13PairedVertexShaderCoverageComplete"] is True
        assert result["validation"]["v13PairedVertexShaderMaterialCount"] == 120
        assert result["validation"]["v13PairedVertexShaderTechniqueSetCount"] == 34
        assert result["validation"]["v13UniquePairedVertexShaderCount"] == 19

        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        final_gltf = Path(result["outputs"]["oatPortableTexturedGltf"]["path"])
        assert final_glb.name.endswith("_v13.glb")
        assert final_gltf.name.endswith("_v13.gltf")
        assert final_glb.read_bytes() == b"v12-portable-glb-fixture"
        assert not v12_glb.exists()
        assert not v12_gltf.exists()
        assert not old_manifest.exists()
        final_manifest = Path(result["manifest"]["path"])
        assert final_manifest.name.endswith("_v13.json")
        persisted = json.loads(final_manifest.read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT

        # An automatic recovery that does not actually reach v5 must fail closed.
        bad_glb = out / "mp_nuketown_2020.world_oat_portable_textured_v12.glb"
        bad_glb.write_bytes(b"bad")
        bad_manifest = out / "mp_nuketown_2020.world_oat_textured_export_manifest_v12.json"
        bad_manifest.write_text("{}\n", encoding="utf-8")
        try:
            pipeline.v12.run_oat_textured_pipeline = lambda **kwargs: {
                "format": "t6-oat-world-textured-export-pipeline-manifest-v12",
                "map": "mp_nuketown_2020",
                "outputs": {"oatPortableTexturedGlb": _record(bad_glb)},
                "stats": {"generatedShaderRecipeRecovery": {"format": "v4"}},
                "validation": {},
                "policies": {},
                "manifest": _record(bad_manifest),
            }
            try:
                pipeline.run_oat_textured_pipeline(
                    map_name="mp_nuketown_2020",
                    output_dir=out,
                )
            except pipeline.OatTexturedPipelineV13Error as exc:
                assert "did not reach v5" in str(exc)
            else:
                raise AssertionError("automatic non-v5 recipe recovery was accepted")
        finally:
            pipeline.v12.run_oat_textured_pipeline = original_run
            pipeline.v11.recipe_recovery_v4 = original_recovery

    print("PASS: production T6 OAT world textured pipeline v13 paired VS promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
