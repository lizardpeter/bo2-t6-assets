#!/usr/bin/env python3
"""T6 lightmap shader research pipeline v2.

V2 deliberately builds on the fully retained v1 bundle, then promotes the
lineage stage to `t6-lightmap-dxbc-lineage-v2`, which understands real fxc/dxc
dumpbin opcode decorations and source modifiers. The v1 lineage file remains in
the bundle as a legacy comparison artifact; v2 is authoritative.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from t6_lightmap_dxbc_lineage_v2 import build_lineage_manifest as build_lineage_v2
from t6_lightmap_shader_research_pipeline_v1 import (
    LightmapShaderResearchPipelineError,
    _file_record,
    _json_bytes,
    _stable_json,
    run_research_pipeline as run_pipeline_v1,
)


def run_research_pipeline(
    *,
    material_root: Path,
    techset_root: Path,
    technique_root: Path,
    shader_root: Path,
    disassembler: Path,
    disassembler_kind: str,
    output_dir: Path,
    context_lines: int = 3,
    require_executable_use: bool = True,
    allow_missing_shaders: bool = False,
    allow_empty: bool = False,
    verify_disassembly_regeneration: bool = True,
) -> dict:
    base = run_pipeline_v1(
        material_root=material_root,
        techset_root=techset_root,
        technique_root=technique_root,
        shader_root=shader_root,
        disassembler=disassembler,
        disassembler_kind=disassembler_kind,
        output_dir=output_dir,
        context_lines=context_lines,
        require_executable_use=require_executable_use,
        allow_missing_shaders=allow_missing_shaders,
        allow_empty=allow_empty,
        verify_disassembly_regeneration=verify_disassembly_regeneration,
    )

    dxbc_record = base["outputs"]["shaderDxbcManifestV1"]
    archive_record = base["outputs"]["disassemblyArchiveV1"]
    dxbc = json.loads(Path(dxbc_record["path"]).read_text(encoding="utf-8"))
    archive = json.loads(Path(archive_record["path"]).read_text(encoding="utf-8"))
    disassembly_root = output_dir / "disassembly"

    lineage1 = build_lineage_v2(dxbc, archive, disassembly_root=disassembly_root)
    lineage2 = build_lineage_v2(
        copy.deepcopy(dxbc), copy.deepcopy(archive), disassembly_root=disassembly_root
    )
    if _stable_json(lineage1) != _stable_json(lineage2):
        raise LightmapShaderResearchPipelineError(
            "lightmap DXBC lineage v2 regeneration was not byte-identical as canonical JSON"
        )

    lineage_path = output_dir / "t6_lightmap_dxbc_lineage_v2.json"
    lineage_payload = _json_bytes(lineage1)
    lineage_path.write_bytes(lineage_payload)
    lineage_record = _file_record(lineage_path, lineage_payload)

    outputs = copy.deepcopy(base["outputs"])
    legacy = outputs.pop("dxbcLineageV1")
    outputs["dxbcLineageV1Legacy"] = legacy
    outputs["dxbcLineageV2"] = lineage_record

    validation = copy.deepcopy(base["validation"])
    validation["lineageV2RegenerationCanonicalJsonIdentical"] = True
    validation["authoritativeLineageVersion"] = 2

    stats = copy.deepcopy(base["stats"])
    if "lineage" in stats:
        stats["lineageV1Legacy"] = stats.pop("lineage")
    stats["lineageV2"] = lineage1.get("stats", {})

    manifest = {
        "format": "t6-lightmap-shader-research-pipeline-manifest-v2",
        "basePipelineManifest": base["manifest"],
        "inputs": copy.deepcopy(base["inputs"]),
        "outputs": outputs,
        "validation": validation,
        "stats": stats,
        "proofBoundary": {
            "authoritativeLineage": "t6-lightmap-dxbc-lineage-v2",
            "legacyLineageRetained": "t6-lightmap-dxbc-lineage-v1",
            "v2SyntaxClosure": [
                "decorated sample/gather/ld opcode syntax such as sample_indexable(texture2d)(...) is parsed",
                "optional numeric dumpbin instruction prefixes are parsed",
                "absolute-value temp modifiers |r#| and -|r#| preserve dependency lineage",
                "discard/control-flow instructions downgrade closure usability",
                "plausible unparsed r#/o#/t# instruction lines are explicit blockers",
            ],
            "stillNotClaimed": [
                "physical RGB/A meaning of primary lightmap",
                "physical RGB/A meaning of secondary lightmap",
                "exact algebraic primary/secondary combine equation",
                "CFG/SSA-correct lineage across shader control flow",
                "retail proof unless all inputs are retained retail T6 OAT dumps and shader binaries",
            ],
        },
    }
    payload = _json_bytes(manifest)
    manifest_path = output_dir / "t6_lightmap_shader_research_manifest_v2.json"
    manifest_path.write_bytes(payload)
    manifest["manifest"] = _file_record(manifest_path, payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-root", type=Path, required=True)
    parser.add_argument("--techset-root", type=Path, required=True)
    parser.add_argument("--technique-root", type=Path, required=True)
    parser.add_argument("--shader-root", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--tool-kind", choices=("fxc", "dxc"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--context-lines", type=int, default=3)
    parser.add_argument("--allow-missing-shaders", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--allow-no-executable-use", action="store_true")
    parser.add_argument("--no-verify-disassembly-regeneration", action="store_true")
    args = parser.parse_args()

    manifest = run_research_pipeline(
        material_root=args.material_root,
        techset_root=args.techset_root,
        technique_root=args.technique_root,
        shader_root=args.shader_root,
        disassembler=args.tool,
        disassembler_kind=args.tool_kind,
        output_dir=args.out_dir,
        context_lines=args.context_lines,
        require_executable_use=not args.allow_no_executable_use,
        allow_missing_shaders=args.allow_missing_shaders,
        allow_empty=args.allow_empty,
        verify_disassembly_regeneration=not args.no_verify_disassembly_regeneration,
    )
    print(
        json.dumps(
            {
                "manifest": manifest["manifest"],
                "validation": manifest["validation"],
                "stats": manifest["stats"],
                "proofBoundary": manifest["proofBoundary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
