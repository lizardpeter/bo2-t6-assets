#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v26 as pipeline


def record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def base(out: Path, *, with_final: bool):
    glb_payload = b"v25-visual-bytes\x00\x01"
    gltf_payload = b"v25-gltf-bytes\n"
    glb = out / "fixture.world_oat_portable_textured_v25.glb"
    gltf = out / "fixture.world_oat_portable_textured_v25.gltf"
    manifest = out / "fixture.world_oat_textured_export_manifest_v25.json"
    glb.write_bytes(glb_payload); gltf.write_bytes(gltf_payload); manifest.write_text("{}\n", encoding="utf-8")
    outputs = {"oatPortableTexturedGlb": record(glb), "oatPortableTexturedGltf": record(gltf)}
    if with_final:
        final = out / "fixture.generated_slot4_final_output_symbolic_v3.json"
        final.write_text(json.dumps({"format": "fixture-final"}) + "\n", encoding="utf-8")
        outputs["generatedSlot4FinalOutputSymbolic"] = record(final)
    return ({
        "format": pipeline.v25.FORMAT,
        "outputs": outputs,
        "stats": {"v25Sentinel": 25},
        "validation": {"v25VisualGlbByteIdenticalToV24": True},
        "policies": {"v25Sentinel": "preserved"},
        "manifest": record(manifest),
    }, glb_payload, gltf_payload)


def anchor_doc() -> dict:
    return {
        "format": pipeline.rgb_anchor.FORMAT,
        "summary": {
            "shaderCount": 34,
            "rgbLaneCount": 102,
            "candidateCount": 102,
            "anchoredRgbLaneCount": 102,
            "missingRgbLaneCount": 0,
            "ambiguousRgbLaneCount": 0,
            "fullyAnchoredShaderCount": 34,
        },
        "shaders": [],
    }


def with_anchor() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v26_") as td:
        out = Path(td) / "out"; out.mkdir()
        base_result, expected_glb, expected_gltf = base(out, with_final=True)
        old_run = pipeline.v25.run_oat_textured_pipeline
        old_build = pipeline.rgb_anchor.build
        calls = []
        try:
            pipeline.v25.run_oat_textured_pipeline = lambda **kwargs: base_result
            def build(doc, *, strict=True):
                calls.append((dict(doc), bool(strict)))
                return anchor_doc()
            pipeline.rgb_anchor.build = build
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v25.run_oat_textured_pipeline = old_run
            pipeline.rgb_anchor.build = old_build

        assert len(calls) == 2 and calls[0][1] is True
        assert result["format"] == pipeline.FORMAT
        assert result["stats"]["v25Sentinel"] == 25
        assert result["validation"]["v25VisualGlbByteIdenticalToV24"] is True
        assert result["policies"]["v25Sentinel"] == "preserved"
        assert result["validation"]["v26RgbSquareAnchorGenerated"] is True
        assert result["validation"]["v26RgbSquareAnchorDeterministic"] is True
        assert result["validation"]["v26RgbSquareFullyAnchoredShaderCount"] == 34
        assert result["validation"]["v26RgbSquareMissingLaneCount"] == 0
        assert result["validation"]["v26RgbSquareAmbiguousLaneCount"] == 0
        assert result["validation"]["v26VisualGlbByteIdenticalToV25"] is True
        assert result["validation"]["v26VisualGltfByteIdenticalToV25"] is True

        glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        gltf = Path(result["outputs"]["oatPortableTexturedGltf"]["path"])
        sidecar = Path(result["outputs"]["generatedFinalOutputRgbSquareAnchor"]["path"])
        assert glb.name.endswith("_v26.glb") and glb.read_bytes() == expected_glb
        assert gltf.name.endswith("_v26.gltf") and gltf.read_bytes() == expected_gltf
        assert json.loads(sidecar.read_text(encoding="utf-8"))["format"] == pipeline.rgb_anchor.FORMAT
        assert sidecar.name.endswith("generated_final_output_rgb_square_anchor_v1.json")

        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT
        assert persisted["outputs"]["generatedFinalOutputRgbSquareAnchor"]["sha256"] == result["outputs"]["generatedFinalOutputRgbSquareAnchor"]["sha256"]


def without_anchor() -> None:
    with tempfile.TemporaryDirectory(prefix="t6_v26_none_") as td:
        out = Path(td) / "out"; out.mkdir()
        base_result, expected_glb, _ = base(out, with_final=False)
        old_run = pipeline.v25.run_oat_textured_pipeline
        try:
            pipeline.v25.run_oat_textured_pipeline = lambda **kwargs: base_result
            result = pipeline.run_oat_textured_pipeline(map_name="fixture", output_dir=out)
        finally:
            pipeline.v25.run_oat_textured_pipeline = old_run
        assert result["validation"]["v26RgbSquareAnchorGenerated"] is False
        assert result["stats"]["generatedFinalOutputRgbSquareAnchor"] is None
        assert "generatedFinalOutputRgbSquareAnchor" not in result["outputs"]
        assert Path(result["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes() == expected_glb


def main() -> int:
    with_anchor()
    without_anchor()
    print("PASS: production v26 generated RGB-square anchor sidecar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
