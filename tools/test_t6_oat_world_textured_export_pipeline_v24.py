#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v24 as pipeline


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def base_result(out: Path, *, recipe: Path | None) -> tuple[dict, bytes, bytes]:
    glb_bytes = b"glTF-v23-byte-identical-fixture\x00\x01\x02"
    gltf_bytes = b'{"asset":{"version":"2.0"},"fixture":"v23"}\n'
    glb = out / "fixture.world_oat_portable_textured_v23.glb"
    gltf = out / "fixture.world_oat_portable_textured_v23.gltf"
    manifest = out / "fixture.world_oat_textured_export_manifest_v23.json"
    glb.write_bytes(glb_bytes)
    gltf.write_bytes(gltf_bytes)
    manifest.write_text("{}\n", encoding="utf-8")
    inputs = {}
    if recipe is not None:
        inputs["generatedShaderRecipeManifest"] = record(recipe)
    return ({
        "format": pipeline.v23.FORMAT,
        "map": "fixture",
        "inputs": inputs,
        "outputs": {
            "oatPortableTexturedGlb": record(glb),
            "oatPortableTexturedGltf": record(gltf),
        },
        "stats": {"v23Sentinel": 23},
        "validation": {"v23BinByteIdenticalToV22": True},
        "policies": {"v23Sentinel": "preserved"},
        "manifest": record(manifest),
    }, glb_bytes, gltf_bytes)


def final_doc() -> dict:
    return {
        "format": pipeline.final_output.FORMAT,
        "summary": {
            "materialCount": 120,
            "techniqueSetCount": 34,
            "uniquePixelShaderCount": 34,
            "canonicalShaderIdentityMismatchCount": 0,
            "exactPixelShaderSetSha256": "a" * 64,
        },
        "materials": [],
        "shaders": [],
    }


def run_with_sidecar() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v24_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        recipe = root / "recipes.json"
        recipe.write_text(json.dumps({"format": "fixture"}) + "\n", encoding="utf-8")
        oat = root / "oat"
        oat.mkdir()
        base, expected_glb, expected_gltf = base_result(out, recipe=recipe)
        old_run = pipeline.v23.run_oat_textured_pipeline
        old_build = pipeline.final_output.build
        calls = []
        try:
            pipeline.v23.run_oat_textured_pipeline = lambda **kwargs: base

            def fake_build(doc, *, oat_root, strict_nuketown=False):
                calls.append((dict(doc), Path(oat_root), bool(strict_nuketown)))
                return final_doc()

            pipeline.final_output.build = fake_build
            result = pipeline.run_oat_textured_pipeline(
                map_name="fixture",
                output_dir=out,
                oat_shader_root=oat,
            )
        finally:
            pipeline.v23.run_oat_textured_pipeline = old_run
            pipeline.final_output.build = old_build

        assert len(calls) == 2
        assert calls[0][1] == oat
        assert calls[0][2] is False
        assert result["format"] == pipeline.FORMAT
        assert result["stats"]["v23Sentinel"] == 23
        assert result["validation"]["v23BinByteIdenticalToV22"] is True
        assert result["policies"]["v23Sentinel"] == "preserved"
        assert result["validation"]["v24FinalOutputSymbolicGenerated"] is True
        assert result["validation"]["v24FinalOutputSymbolicDeterministic"] is True
        assert result["validation"]["v24FinalOutputCanonicalIdentityMismatchCount"] == 0
        assert result["validation"]["v24FinalOutputUniquePixelShaderCount"] == 34
        assert result["validation"]["v24VisualGlbByteIdenticalToV23"] is True
        assert result["validation"]["v24VisualGltfByteIdenticalToV23"] is True

        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        final_gltf = Path(result["outputs"]["oatPortableTexturedGltf"]["path"])
        final_sidecar = Path(result["outputs"]["generatedSlot4FinalOutputSymbolic"]["path"])
        assert final_glb.name.endswith("_v24.glb")
        assert final_gltf.name.endswith("_v24.gltf")
        assert final_glb.read_bytes() == expected_glb
        assert final_gltf.read_bytes() == expected_gltf
        assert hashlib.sha256(final_glb.read_bytes()).hexdigest() == hashlib.sha256(expected_glb).hexdigest()
        assert json.loads(final_sidecar.read_text(encoding="utf-8"))["format"] == pipeline.final_output.FORMAT
        assert final_sidecar.name.endswith("generated_slot4_final_output_symbolic_v3.json")

        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT
        assert persisted["validation"]["v24FinalOutputSymbolicGenerated"] is True
        assert persisted["outputs"]["generatedSlot4FinalOutputSymbolic"]["sha256"] == result["outputs"]["generatedSlot4FinalOutputSymbolic"]["sha256"]


def run_without_sidecar() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v24_none_") as td:
        out = Path(td) / "out"
        out.mkdir()
        base, expected_glb, _ = base_result(out, recipe=None)
        old_run = pipeline.v23.run_oat_textured_pipeline
        try:
            pipeline.v23.run_oat_textured_pipeline = lambda **kwargs: base
            result = pipeline.run_oat_textured_pipeline(
                map_name="fixture",
                output_dir=out,
            )
        finally:
            pipeline.v23.run_oat_textured_pipeline = old_run
        assert result["validation"]["v24FinalOutputSymbolicRequested"] is False
        assert result["validation"]["v24FinalOutputSymbolicGenerated"] is False
        assert result["stats"]["generatedSlot4FinalOutputSymbolic"] is None
        assert "generatedSlot4FinalOutputSymbolic" not in result["outputs"]
        assert Path(result["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes() == expected_glb


def run_incomplete_inputs_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v24_bad_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        recipe = root / "recipes.json"
        recipe.write_text("{}\n", encoding="utf-8")
        base, _, _ = base_result(out, recipe=recipe)
        old_run = pipeline.v23.run_oat_textured_pipeline
        try:
            pipeline.v23.run_oat_textured_pipeline = lambda **kwargs: base
            try:
                pipeline.run_oat_textured_pipeline(
                    map_name="fixture",
                    output_dir=out,
                )
            except pipeline.OatTexturedPipelineV24Error as exc:
                assert "requires both canonical generated recipes and oat_shader_root" in str(exc)
            else:
                raise AssertionError("v24 allowed recipe proof without exact OAT shader root")
        finally:
            pipeline.v23.run_oat_textured_pipeline = old_run


def main() -> int:
    run_with_sidecar()
    run_without_sidecar()
    run_incomplete_inputs_fail_closed()
    print("PASS: production v24 generated final-output symbolic sidecar orchestration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
