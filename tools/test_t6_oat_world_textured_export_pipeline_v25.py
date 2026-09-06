#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v25 as pipeline


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def fake_ancestry() -> dict:
    return {
        "format": pipeline.ancestry.FORMAT,
        "summary": {
            "shaderCount": 34,
            "sampleCount": 321,
            "outputAncestryCheckCount": 136,
            "outputAncestryMismatchCount": 0,
            "unknownOutputResourceCount": 2,
            "ancestrySignatureCount": 5,
        },
        "shaders": [],
    }


def make_base(out: Path, *, final_sidecar: bool):
    glb_payload = b"v24-glb-exact-bytes\x00\x01"
    gltf_payload = b"v24-gltf-exact-bytes\n"
    glb = out / "fixture.world_oat_portable_textured_v24.glb"
    gltf = out / "fixture.world_oat_portable_textured_v24.gltf"
    manifest = out / "fixture.world_oat_textured_export_manifest_v24.json"
    glb.write_bytes(glb_payload)
    gltf.write_bytes(gltf_payload)
    manifest.write_text("{}\n", encoding="utf-8")
    outputs = {
        "oatPortableTexturedGlb": record(glb),
        "oatPortableTexturedGltf": record(gltf),
    }
    if final_sidecar:
        sidecar = out / "fixture.generated_slot4_final_output_symbolic_v3.json"
        sidecar.write_text(json.dumps({"format": "fixture-final"}) + "\n", encoding="utf-8")
        outputs["generatedSlot4FinalOutputSymbolic"] = record(sidecar)
    return ({
        "format": pipeline.v24.FORMAT,
        "outputs": outputs,
        "stats": {"v24Sentinel": 24},
        "validation": {"v24VisualGlbByteIdenticalToV23": True},
        "policies": {"v24Sentinel": "preserved"},
        "manifest": record(manifest),
    }, glb_payload, gltf_payload)


def with_sidecar() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v25_") as td:
        out = Path(td) / "out"
        out.mkdir()
        base, expected_glb, expected_gltf = make_base(out, final_sidecar=True)
        old_run = pipeline.v24.run_oat_textured_pipeline
        old_build = pipeline.ancestry.build
        calls = []
        try:
            pipeline.v24.run_oat_textured_pipeline = lambda **kwargs: base

            def build(doc, *, strict_nuketown=False):
                calls.append((dict(doc), bool(strict_nuketown)))
                return fake_ancestry()

            pipeline.ancestry.build = build
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v24.run_oat_textured_pipeline = old_run
            pipeline.ancestry.build = old_build

        assert len(calls) == 2
        assert calls[0][1] is False
        assert result["format"] == pipeline.FORMAT
        assert result["stats"]["v24Sentinel"] == 24
        assert result["validation"]["v24VisualGlbByteIdenticalToV23"] is True
        assert result["policies"]["v24Sentinel"] == "preserved"
        assert result["validation"]["v25FinalOutputResourceAncestryGenerated"] is True
        assert result["validation"]["v25FinalOutputResourceAncestryDeterministic"] is True
        assert result["validation"]["v25OutputAncestryMismatchCount"] == 0
        assert result["validation"]["v25UnknownOutputResourceCount"] == 2
        assert result["validation"]["v25OutputAncestrySignatureCount"] == 5
        assert result["validation"]["v25VisualGlbByteIdenticalToV24"] is True
        assert result["validation"]["v25VisualGltfByteIdenticalToV24"] is True

        glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        gltf = Path(result["outputs"]["oatPortableTexturedGltf"]["path"])
        sidecar = Path(result["outputs"]["generatedFinalOutputResourceAncestry"]["path"])
        assert glb.name.endswith("_v25.glb") and glb.read_bytes() == expected_glb
        assert gltf.name.endswith("_v25.gltf") and gltf.read_bytes() == expected_gltf
        assert json.loads(sidecar.read_text(encoding="utf-8"))["format"] == pipeline.ancestry.FORMAT
        assert sidecar.name.endswith("generated_final_output_resource_ancestry_v1.json")
        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT
        assert persisted["outputs"]["generatedFinalOutputResourceAncestry"]["sha256"] == result["outputs"]["generatedFinalOutputResourceAncestry"]["sha256"]


def without_sidecar() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v25_none_") as td:
        out = Path(td) / "out"
        out.mkdir()
        base, expected_glb, _ = make_base(out, final_sidecar=False)
        old_run = pipeline.v24.run_oat_textured_pipeline
        try:
            pipeline.v24.run_oat_textured_pipeline = lambda **kwargs: base
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v24.run_oat_textured_pipeline = old_run
        assert result["validation"]["v25FinalOutputResourceAncestryGenerated"] is False
        assert result["stats"]["generatedFinalOutputResourceAncestry"] is None
        assert "generatedFinalOutputResourceAncestry" not in result["outputs"]
        assert Path(result["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes() == expected_glb


def main() -> int:
    with_sidecar()
    without_sidecar()
    print("PASS: production v25 generated final-output resource ancestry sidecar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
