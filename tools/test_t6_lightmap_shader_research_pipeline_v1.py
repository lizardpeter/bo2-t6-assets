#!/usr/bin/env python3
"""Orchestration regression for the one-command T6 lightmap shader research pipeline."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import t6_lightmap_shader_research_pipeline_v1 as pipe


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expect_pipeline_error(fn, needle: str) -> None:
    try:
        fn()
    except pipe.LightmapShaderResearchPipelineError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(
            f"expected LightmapShaderResearchPipelineError containing {needle!r}"
        )


def main() -> int:
    original = (
        pipe.build_inventory,
        pipe.build_dxbc_manifest,
        pipe.disassemble_manifest,
        pipe.build_evidence,
        pipe.build_lineage_manifest,
    )
    calls: list[tuple] = []

    inventory = {
        "format": "t6-lightmap-shader-inventory-v2",
        "source": {"producer": "test"},
        "stats": {
            "selectedProvenanceEdgeCount": 1,
            "uniqueLightmapPixelShaderCount": 1,
        },
        "uniqueLightmapPixelShaders": [
            {
                "pixelShader": "world_lm",
                "file": "ps_world_lm.cso",
                "present": True,
                "bytes": 8,
                "sha256": "shaderhash",
            }
        ],
        "provenance": [{"pixelShader": "world_lm"}],
    }
    dxbc = {
        "format": "t6-lightmap-shader-dxbc-manifest-v1",
        "stats": {
            "provenanceEdgeCount": 1,
            "presentPixelShaderCount": 1,
        },
        "pixelShaders": [
            {
                "pixelShader": "world_lm",
                "file": "ps_world_lm.cso",
                "present": True,
                "bytes": 8,
                "sha256": "shaderhash",
            }
        ],
        "provenance": [{"pixelShader": "world_lm", "shaderPresent": True}],
    }
    evidence = {
        "format": "t6-lightmap-disassembly-evidence-v1",
        "stats": {
            "provenanceEdgeCount": 1,
            "samplingInstructionCount": 2,
            "bindingsWithoutExecutableUseCount": 0,
        },
        "provenance": [{"pixelShader": "world_lm"}],
    }
    lineage = {
        "format": "t6-lightmap-dxbc-lineage-v1",
        "stats": {
            "provenanceTraceCount": 1,
            "closureUsableStraightLineTraceCount": 1,
            "sampledLightmapInstructionCount": 2,
        },
        "provenance": [{"pixelShader": "world_lm"}],
    }
    dump_bytes = b"ps_4_0\nsample r0.xyzw, v0.xyxx, t3.xyzw, s0\n"

    def fake_inventory(**kwargs):
        calls.append(("inventory", kwargs["material_root"], kwargs["shader_root"]))
        return inventory.copy() | {
            "stats": dict(inventory["stats"]),
            "uniqueLightmapPixelShaders": [dict(inventory["uniqueLightmapPixelShaders"][0])],
            "provenance": [dict(inventory["provenance"][0])],
        }

    def fake_dxbc(doc, **kwargs):
        calls.append(("dxbc", doc["format"], kwargs["shader_root"]))
        return dxbc.copy() | {
            "stats": dict(dxbc["stats"]),
            "pixelShaders": [dict(dxbc["pixelShaders"][0])],
            "provenance": [dict(dxbc["provenance"][0])],
        }

    def fake_disassemble(doc, **kwargs):
        out = kwargs["output_dir"]
        out.mkdir(parents=True, exist_ok=True)
        name = "ps_world_lm.fxc.dumpbin.txt"
        (out / name).write_bytes(dump_bytes)
        calls.append(("disassemble", doc["format"], kwargs["tool_kind"]))
        return {
            "format": "t6-dxbc-disassembly-archive-v1",
            "source": {"dxbcManifestFormat": doc["format"], "shaderRoot": str(kwargs["shader_root"])},
            "disassembler": {
                "kind": kwargs["tool_kind"],
                "path": str(kwargs["executable"]),
                "bytes": len(kwargs["executable"].read_bytes()),
                "sha256": _sha256(kwargs["executable"].read_bytes()),
            },
            "stats": {"disassembledPixelShaderCount": 1, "inputPixelShaderCount": 1},
            "shaders": [
                {
                    "pixelShader": "world_lm",
                    "shaderFile": "ps_world_lm.cso",
                    "shaderBytes": 8,
                    "shaderSha256": "shaderhash",
                    "command": [str(kwargs["executable"]), "/dumpbin", "shader"],
                    "returnCode": 0,
                    "disassemblyFile": name,
                    "disassemblyBytes": len(dump_bytes),
                    "disassemblySha256": _sha256(dump_bytes),
                    "stderrFile": None,
                    "stderrBytes": 0,
                    "stderrSha256": _sha256(b""),
                }
            ],
        }

    def fake_evidence(dxbc_doc, archive_doc, **kwargs):
        assert (kwargs["disassembly_root"] / archive_doc["shaders"][0]["disassemblyFile"]).is_file()
        calls.append(("evidence", kwargs["context_lines"], kwargs["require_executable_use"]))
        return evidence.copy() | {
            "stats": dict(evidence["stats"]),
            "provenance": [dict(evidence["provenance"][0])],
        }

    def fake_lineage(dxbc_doc, archive_doc, **kwargs):
        assert (kwargs["disassembly_root"] / archive_doc["shaders"][0]["disassemblyFile"]).is_file()
        calls.append(("lineage", dxbc_doc["format"], archive_doc["format"]))
        return lineage.copy() | {
            "stats": dict(lineage["stats"]),
            "provenance": [dict(lineage["provenance"][0])],
        }

    try:
        pipe.build_inventory = fake_inventory
        pipe.build_dxbc_manifest = fake_dxbc
        pipe.disassemble_manifest = fake_disassemble
        pipe.build_evidence = fake_evidence
        pipe.build_lineage_manifest = fake_lineage

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            materials = root / "materials"
            techsets = root / "techsets"
            techniques = root / "techniques"
            shaders = root / "shader_bin"
            out = root / "research"
            for directory in (materials, techsets, techniques, shaders):
                directory.mkdir()
            tool = root / "fxc.exe"
            tool.write_bytes(b"TEST-FXC")

            manifest = pipe.run_research_pipeline(
                material_root=materials,
                techset_root=techsets,
                technique_root=techniques,
                shader_root=shaders,
                disassembler=tool,
                disassembler_kind="fxc",
                output_dir=out,
                context_lines=5,
            )

            assert manifest["format"] == "t6-lightmap-shader-research-pipeline-manifest-v1"
            assert manifest["validation"] == {
                "inventoryRegenerationCanonicalJsonIdentical": True,
                "dxbcManifestRegenerationCanonicalJsonIdentical": True,
                "disassemblyRegenerationByteIdentical": True,
                "evidenceRegenerationCanonicalJsonIdentical": True,
                "lineageRegenerationCanonicalJsonIdentical": True,
                "requireExecutableLightmapRegisterUse": True,
                "allowMissingShaders": False,
                "allowEmpty": False,
            }
            # Deterministic stages run twice; the disassembler also runs twice by default.
            assert [x[0] for x in calls].count("inventory") == 2
            assert [x[0] for x in calls].count("dxbc") == 2
            assert [x[0] for x in calls].count("disassemble") == 2
            assert [x[0] for x in calls].count("evidence") == 2
            assert [x[0] for x in calls].count("lineage") == 2

            expected_files = [
                "t6_lightmap_shader_inventory_v2.json",
                "t6_lightmap_shader_dxbc_manifest_v1.json",
                "t6_dxbc_disassembly_archive_v1.json",
                "t6_lightmap_disassembly_evidence_v1.json",
                "t6_lightmap_dxbc_lineage_v1.json",
                "t6_lightmap_shader_research_manifest_v1.json",
                "disassembly/ps_world_lm.fxc.dumpbin.txt",
            ]
            for relative in expected_files:
                assert (out / relative).is_file(), relative

            for key in (
                "shaderInventoryV2",
                "shaderDxbcManifestV1",
                "disassemblyArchiveV1",
                "disassemblyEvidenceV1",
                "dxbcLineageV1",
            ):
                record = manifest["outputs"][key]
                raw = Path(record["path"]).read_bytes()
                assert record["bytes"] == len(raw)
                assert record["sha256"] == _sha256(raw)
            assert manifest["outputs"]["disassemblyArtifacts"][0]["disassembly"]["sha256"] == _sha256(dump_bytes)
            assert manifest["manifest"]["sha256"] == _sha256(
                Path(manifest["manifest"]["path"]).read_bytes()
            )

            # Empty inventory is a proof blocker unless explicitly allowed.
            def empty_inventory(**kwargs):
                doc = fake_inventory(**kwargs)
                doc["stats"]["uniqueLightmapPixelShaderCount"] = 0
                doc["uniqueLightmapPixelShaders"] = []
                doc["provenance"] = []
                return doc

            pipe.build_inventory = empty_inventory
            _expect_pipeline_error(
                lambda: pipe.run_research_pipeline(
                    material_root=materials,
                    techset_root=techsets,
                    technique_root=techniques,
                    shader_root=shaders,
                    disassembler=tool,
                    disassembler_kind="fxc",
                    output_dir=root / "empty",
                ),
                "zero selected lightmap pixel shaders",
            )

            # A supposedly deterministic producer that changes between calls is rejected.
            serial = {"value": 0}
            def unstable_inventory(**kwargs):
                serial["value"] += 1
                doc = fake_inventory(**kwargs)
                doc["unstableSerial"] = serial["value"]
                return doc

            pipe.build_inventory = unstable_inventory
            _expect_pipeline_error(
                lambda: pipe.run_research_pipeline(
                    material_root=materials,
                    techset_root=techsets,
                    technique_root=techniques,
                    shader_root=shaders,
                    disassembler=tool,
                    disassembler_kind="fxc",
                    output_dir=root / "unstable",
                ),
                "inventory v2 regeneration",
            )

    finally:
        (
            pipe.build_inventory,
            pipe.build_dxbc_manifest,
            pipe.disassemble_manifest,
            pipe.build_evidence,
            pipe.build_lineage_manifest,
        ) = original

    print("PASS t6_lightmap_shader_research_pipeline_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
