#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v27 as pipeline


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def make_base(out: Path, *, with_final: bool):
    glb_payload = b"v26-visual-byte-identical\x00\x01"
    gltf_payload = b"v26-gltf-byte-identical\n"
    glb = out / "fixture.world_oat_portable_textured_v26.glb"
    gltf = out / "fixture.world_oat_portable_textured_v26.gltf"
    manifest = out / "fixture.world_oat_textured_export_manifest_v26.json"
    glb.write_bytes(glb_payload); gltf.write_bytes(gltf_payload); manifest.write_text("{}\n", encoding="utf-8")
    outputs = {"oatPortableTexturedGlb": record(glb), "oatPortableTexturedGltf": record(gltf)}
    if with_final:
        final = out / "fixture.generated_slot4_final_output_symbolic_v3.json"
        final.write_text(json.dumps({"format": "fixture-final"}) + "\n", encoding="utf-8")
        outputs["generatedSlot4FinalOutputSymbolic"] = record(final)
    return ({
        "format": pipeline.v26.FORMAT,
        "outputs": outputs,
        "stats": {"v26Sentinel": 26},
        "validation": {"v26VisualGlbByteIdenticalToV25": True},
        "policies": {"v26Sentinel": "preserved"},
        "manifest": record(manifest),
    }, glb_payload, gltf_payload)


def probe_doc(*, zero=3, one=29, two=2, equations=33) -> dict:
    return {
        "format": pipeline.directional.FORMAT,
        "summary": {
            "shaderCount": zero + one + two,
            "rowTripletCount": zero + one + two,
            "explicitDirectionalEquationCount": equations,
            "zeroExplicitEquationShaderCount": zero,
            "oneExplicitEquationShaderCount": one,
            "twoOrMoreExplicitEquationShaderCount": two,
        },
        "shaders": [],
    }


def with_diagnostic_matches() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v27_") as td:
        out = Path(td) / "out"; out.mkdir()
        base, expected_glb, expected_gltf = make_base(out, with_final=True)
        old_run = pipeline.v26.run_oat_textured_pipeline
        old_build = pipeline.directional.build
        calls = []
        try:
            pipeline.v26.run_oat_textured_pipeline = lambda **kwargs: base
            def build(doc):
                calls.append(dict(doc))
                return probe_doc()
            pipeline.directional.build = build
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v26.run_oat_textured_pipeline = old_run
            pipeline.directional.build = old_build

        assert len(calls) == 2
        assert result["format"] == pipeline.FORMAT
        assert result["stats"]["v26Sentinel"] == 26
        assert result["validation"]["v26VisualGlbByteIdenticalToV25"] is True
        assert result["policies"]["v26Sentinel"] == "preserved"
        assert result["validation"]["v27DirectionalLightmapProbeGenerated"] is True
        assert result["validation"]["v27DirectionalLightmapProbeDeterministic"] is True
        assert result["validation"]["v27DirectionalExplicitEquationCount"] == 33
        assert result["validation"]["v27DirectionalZeroExplicitShaderCount"] == 3
        assert result["validation"]["v27DirectionalOneExplicitShaderCount"] == 29
        assert result["validation"]["v27DirectionalTwoOrMoreExplicitShaderCount"] == 2
        assert result["validation"]["v27VisualGlbByteIdenticalToV26"] is True
        assert result["validation"]["v27VisualGltfByteIdenticalToV26"] is True

        glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        gltf = Path(result["outputs"]["oatPortableTexturedGltf"]["path"])
        sidecar = Path(result["outputs"]["generatedFinalOutputDirectionalLightmapProbe"]["path"])
        assert glb.name.endswith("_v27.glb") and glb.read_bytes() == expected_glb
        assert gltf.name.endswith("_v27.gltf") and gltf.read_bytes() == expected_gltf
        assert sidecar.name.endswith("generated_final_output_directional_lightmap_anchor_probe_v1.json")
        assert json.loads(sidecar.read_text(encoding="utf-8"))["format"] == pipeline.directional.FORMAT


def zero_matches_are_valid_evidence() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v27_zero_") as td:
        out = Path(td) / "out"; out.mkdir()
        base, _, _ = make_base(out, with_final=True)
        old_run = pipeline.v26.run_oat_textured_pipeline
        old_build = pipeline.directional.build
        try:
            pipeline.v26.run_oat_textured_pipeline = lambda **kwargs: base
            pipeline.directional.build = lambda doc: probe_doc(zero=34, one=0, two=0, equations=0)
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v26.run_oat_textured_pipeline = old_run
            pipeline.directional.build = old_build
        assert result["validation"]["v27DirectionalLightmapProbeGenerated"] is True
        assert result["validation"]["v27DirectionalExplicitEquationCount"] == 0
        assert result["validation"]["v27DirectionalZeroExplicitShaderCount"] == 34


def without_final_sidecar() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v27_none_") as td:
        out = Path(td) / "out"; out.mkdir()
        base, expected_glb, _ = make_base(out, with_final=False)
        old_run = pipeline.v26.run_oat_textured_pipeline
        try:
            pipeline.v26.run_oat_textured_pipeline = lambda **kwargs: base
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v26.run_oat_textured_pipeline = old_run
        assert result["validation"]["v27DirectionalLightmapProbeGenerated"] is False
        assert result["stats"]["generatedFinalOutputDirectionalLightmapProbe"] is None
        assert "generatedFinalOutputDirectionalLightmapProbe" not in result["outputs"]
        assert Path(result["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes() == expected_glb


def main() -> int:
    with_diagnostic_matches()
    zero_matches_are_valid_evidence()
    without_final_sidecar()
    print("PASS: production v27 explicit directional-lightmap diagnostic sidecar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
