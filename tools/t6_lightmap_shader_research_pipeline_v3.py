#!/usr/bin/env python3
"""T6 lightmap shader research pipeline v3.

V3 promotes the v2 provenance/DXBC/disassembly/lineage chain and adds
`t6-lightmap-dxbc-symbolic-v2`, producing an exact straight-line assembly
expression DAG for every lineage-v2 closure-usable lightmap shader edge.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from t6_lightmap_dxbc_symbolic_v2 import build_manifest as build_symbolic
from t6_lightmap_shader_research_pipeline_v1 import _file_record, _json_bytes, _stable_json
from t6_lightmap_shader_research_pipeline_v2 import (
    LightmapShaderResearchPipelineError,
    run_research_pipeline as run_pipeline_v2,
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
    base = run_pipeline_v2(
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

    lineage_record = base["outputs"]["dxbcLineageV2"]
    archive_record = base["outputs"]["disassemblyArchiveV1"]
    lineage = json.loads(Path(lineage_record["path"]).read_text(encoding="utf-8"))
    archive = json.loads(Path(archive_record["path"]).read_text(encoding="utf-8"))
    disassembly_root = output_dir / "disassembly"

    symbolic1 = build_symbolic(lineage, archive, disassembly_root=disassembly_root)
    symbolic2 = build_symbolic(copy.deepcopy(lineage), copy.deepcopy(archive), disassembly_root=disassembly_root)
    if _stable_json(symbolic1) != _stable_json(symbolic2):
        raise LightmapShaderResearchPipelineError(
            "lightmap DXBC symbolic v2 regeneration was not byte-identical as canonical JSON"
        )

    symbolic_path = output_dir / "t6_lightmap_dxbc_symbolic_v2.json"
    symbolic_payload = _json_bytes(symbolic1)
    symbolic_path.write_bytes(symbolic_payload)

    outputs = copy.deepcopy(base["outputs"])
    outputs["dxbcSymbolicV2"] = _file_record(symbolic_path, symbolic_payload)
    validation = copy.deepcopy(base["validation"])
    validation.update({
        "symbolicV2RegenerationCanonicalJsonIdentical": True,
        "symbolicV2AllEdgesClosureUsable": bool(symbolic1.get("stats", {}).get("allEdgesClosureUsable")),
    })
    stats = copy.deepcopy(base["stats"])
    stats["symbolicV2"] = symbolic1.get("stats", {})

    manifest = {
        "format": "t6-lightmap-shader-research-pipeline-manifest-v3",
        "basePipelineManifest": base["manifest"],
        "inputs": copy.deepcopy(base["inputs"]),
        "outputs": outputs,
        "validation": validation,
        "stats": stats,
        "proofBoundary": {
            "authoritativeLineage": "t6-lightmap-dxbc-lineage-v2",
            "authoritativeSymbolicEquation": "t6-lightmap-dxbc-symbolic-v2",
            "symbolicClosureMeans": (
                "mapped primary/secondary sample channels reach output through a straight-line instruction path "
                "whose consumed lightmap operations are all explicitly modeled in the expression DAG"
            ),
            "hardBlockers": [
                "shader control flow",
                "lineage-v2 syntax/write blocker",
                "unknown opcode that consumes a lightmap-derived value",
                "read-before-symbolic-write on a required register component",
            ],
            "stillNotClaimed": [
                "human physical names for primary/secondary RGB/A quantities",
                "visual equivalence until the expression is executed in the T6-aware renderer",
                "retail proof unless inputs are retained hash-pinned retail T6 OAT/shader artifacts",
            ],
            "importantDistinction": (
                "human physical channel labels are descriptive, not required for bytecode-equivalent playback; "
                "the renderer can consume the exact sampled channels and symbolic operation DAG directly"
            ),
        },
    }
    payload = _json_bytes(manifest)
    manifest_path = output_dir / "t6_lightmap_shader_research_manifest_v3.json"
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
    print(json.dumps({
        "manifest": manifest["manifest"],
        "validation": manifest["validation"],
        "symbolicStats": manifest["stats"]["symbolicV2"],
        "proofBoundary": manifest["proofBoundary"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
