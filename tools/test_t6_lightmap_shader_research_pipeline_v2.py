#!/usr/bin/env python3
"""Regression for v1-bundle -> authoritative-lineage-v2 promotion."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_lightmap_shader_research_pipeline_v2 as pipe


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    original_base = pipe.run_pipeline_v1
    original_lineage = pipe.build_lineage_v2
    lineage_calls = 0

    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir()
            disassembly = out / "disassembly"
            disassembly.mkdir()
            dxbc_path = out / "t6_lightmap_shader_dxbc_manifest_v1.json"
            archive_path = out / "t6_dxbc_disassembly_archive_v1.json"
            legacy_path = out / "t6_lightmap_dxbc_lineage_v1.json"
            base_manifest_path = out / "t6_lightmap_shader_research_manifest_v1.json"
            dump_path = disassembly / "ps_world_lm.fxc.dumpbin.txt"

            dxbc = {
                "format": "t6-lightmap-shader-dxbc-manifest-v1",
                "provenance": [{"pixelShader": "world_lm", "shaderPresent": True}],
            }
            dump = b"sample_indexable(texture2d)(float,float,float,float) r0.x, v0.xyxx, t3.x, s0\n"
            archive = {
                "format": "t6-dxbc-disassembly-archive-v1",
                "shaders": [
                    {
                        "pixelShader": "world_lm",
                        "disassemblyFile": dump_path.name,
                        "disassemblyBytes": len(dump),
                        "disassemblySha256": _sha256(dump),
                    }
                ],
            }
            dxbc_path.write_text(json.dumps(dxbc), encoding="utf-8")
            archive_path.write_text(json.dumps(archive), encoding="utf-8")
            legacy_path.write_text("{}\n", encoding="utf-8")
            dump_path.write_bytes(dump)
            base_manifest_path.write_text("{}\n", encoding="utf-8")

            def rec(path: Path) -> dict:
                raw = path.read_bytes()
                return {
                    "file": path.name,
                    "path": str(path),
                    "bytes": len(raw),
                    "sha256": _sha256(raw),
                }

            base = {
                "format": "t6-lightmap-shader-research-pipeline-manifest-v1",
                "inputs": {
                    "materialRoot": "materials",
                    "techsetRoot": "techsets",
                    "techniqueRoot": "techniques",
                    "shaderRoot": "shader_bin",
                    "disassembler": {"kind": "fxc", "sha256": "toolhash"},
                },
                "outputs": {
                    "shaderInventoryV2": {"file": "inventory", "path": "inventory", "bytes": 1, "sha256": "a"},
                    "shaderDxbcManifestV1": rec(dxbc_path),
                    "disassemblyArchiveV1": rec(archive_path),
                    "disassemblyEvidenceV1": {"file": "evidence", "path": "evidence", "bytes": 1, "sha256": "b"},
                    "dxbcLineageV1": rec(legacy_path),
                    "disassemblyArtifacts": [],
                },
                "validation": {"disassemblyRegenerationByteIdentical": True},
                "stats": {"lineage": {"provenanceTraceCount": 1}},
                "proofBoundary": {"stillNotClaimed": ["equation"]},
                "manifest": rec(base_manifest_path),
            }

            def fake_base(**kwargs):
                assert kwargs["output_dir"] == out
                return base

            def fake_lineage(dxbc_doc, archive_doc, *, disassembly_root):
                nonlocal lineage_calls
                lineage_calls += 1
                assert dxbc_doc["format"] == "t6-lightmap-shader-dxbc-manifest-v1"
                assert archive_doc["format"] == "t6-dxbc-disassembly-archive-v1"
                assert disassembly_root == disassembly
                return {
                    "format": "t6-lightmap-dxbc-lineage-v2",
                    "source": {"producer": "t6_lightmap_dxbc_lineage_v2.py"},
                    "stats": {
                        "provenanceTraceCount": 1,
                        "closureUsableStraightLineTraceCount": 1,
                        "unparsedInstructionCandidateCount": 0,
                    },
                    "provenance": [{"pixelShader": "world_lm"}],
                }

            pipe.run_pipeline_v1 = fake_base
            pipe.build_lineage_v2 = fake_lineage
            manifest = pipe.run_research_pipeline(
                material_root=root / "materials",
                techset_root=root / "techsets",
                technique_root=root / "techniques",
                shader_root=root / "shader_bin",
                disassembler=root / "fxc.exe",
                disassembler_kind="fxc",
                output_dir=out,
            )

            assert lineage_calls == 2
            assert manifest["format"] == "t6-lightmap-shader-research-pipeline-manifest-v2"
            assert manifest["validation"]["authoritativeLineageVersion"] == 2
            assert manifest["validation"]["lineageV2RegenerationCanonicalJsonIdentical"] is True
            assert "dxbcLineageV1" not in manifest["outputs"]
            assert "dxbcLineageV1Legacy" in manifest["outputs"]
            assert "dxbcLineageV2" in manifest["outputs"]
            assert manifest["proofBoundary"]["authoritativeLineage"] == "t6-lightmap-dxbc-lineage-v2"
            assert manifest["stats"]["lineageV1Legacy"] == {"provenanceTraceCount": 1}
            assert manifest["stats"]["lineageV2"]["unparsedInstructionCandidateCount"] == 0

            v2_path = out / "t6_lightmap_dxbc_lineage_v2.json"
            top_path = out / "t6_lightmap_shader_research_manifest_v2.json"
            assert v2_path.is_file()
            assert top_path.is_file()
            assert manifest["outputs"]["dxbcLineageV2"]["sha256"] == _sha256(v2_path.read_bytes())
            assert manifest["manifest"]["sha256"] == _sha256(top_path.read_bytes())

            # Non-deterministic v2 lineage is rejected rather than promoted.
            counter = {"n": 0}
            def unstable_lineage(*args, **kwargs):
                counter["n"] += 1
                doc = fake_lineage(*args, **kwargs)
                doc["unstable"] = counter["n"]
                return doc

            pipe.build_lineage_v2 = unstable_lineage
            try:
                pipe.run_research_pipeline(
                    material_root=root / "materials",
                    techset_root=root / "techsets",
                    technique_root=root / "techniques",
                    shader_root=root / "shader_bin",
                    disassembler=root / "fxc.exe",
                    disassembler_kind="fxc",
                    output_dir=out,
                )
            except pipe.LightmapShaderResearchPipelineError as exc:
                assert "lineage v2 regeneration" in str(exc)
            else:
                raise AssertionError("expected nondeterministic lineage v2 rejection")

    finally:
        pipe.run_pipeline_v1 = original_base
        pipe.build_lineage_v2 = original_lineage

    print("PASS t6_lightmap_shader_research_pipeline_v2 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
