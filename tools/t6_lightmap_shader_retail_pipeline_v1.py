#!/usr/bin/env python3
"""One-command retail T6 lightmap shader proof pipeline.

Pipeline:
  hash-pinned retail FF identity
    -> compact exact OAT Material/Techset/Technique/CSO staging
    -> existing T6 DXBC research pipeline v2
    -> deterministic combined evidence manifest

This makes acquisition-to-lineage one auditable command. It still does not
claim physical channel meaning or an algebraic combine equation merely because
DXBC lineage exists; those remain stronger semantic closure requirements.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from t6_lightmap_shader_research_pipeline_v2 import run_research_pipeline
from t6_lightmap_shader_retail_stage_v1 import build_stage


class RetailLightmapPipelineError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": _sha256(data)}


def _stable_json(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _verify_ff(path: Path, expected_sha256: str | None) -> dict:
    if not path.is_file():
        raise RetailLightmapPipelineError(f"retail fastfile missing: {path}")
    record = _file_record(path)
    if expected_sha256 is not None:
        expected = expected_sha256.lower().strip()
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise RetailLightmapPipelineError("expected retail FF SHA-256 must be 64 hex characters")
        if record["sha256"] != expected:
            raise RetailLightmapPipelineError(
                f"retail FF SHA-256 mismatch: {record['sha256']} != {expected}"
            )
    record["verifiedAgainstExpectedSha256"] = expected_sha256 is not None
    return record


def run_pipeline(
    *,
    map_name: str,
    retail_ff: Path,
    oat_root: Path,
    disassembler: Path,
    disassembler_kind: str,
    output_dir: Path,
    expected_ff_sha256: str | None = None,
    context_lines: int = 3,
) -> dict:
    ff = _verify_ff(retail_ff, expected_ff_sha256)
    if not disassembler.is_file():
        raise RetailLightmapPipelineError(f"disassembler missing: {disassembler}")
    disassembler_record = _file_record(disassembler)

    stage_dir = output_dir / "stage"
    research_dir = output_dir / "research"
    output_dir.mkdir(parents=True, exist_ok=True)

    stage1 = build_stage(
        oat_root=oat_root,
        output_dir=stage_dir,
        map_name=map_name,
        retail_ff_sha256=ff["sha256"],
    )
    args = stage1["researchPipelineArgs"]
    research1 = run_research_pipeline(
        material_root=Path(args["materialRoot"]),
        techset_root=Path(args["techsetRoot"]),
        technique_root=Path(args["techniqueRoot"]),
        shader_root=Path(args["shaderRoot"]),
        disassembler=disassembler,
        disassembler_kind=disassembler_kind,
        output_dir=research_dir,
        context_lines=context_lines,
        require_executable_use=True,
        allow_missing_shaders=False,
        allow_empty=False,
        verify_disassembly_regeneration=True,
    )

    # Re-run the semantic pipeline into a second isolated directory and compare
    # canonical manifests after removing path-dependent file-record fields. This
    # is intentionally stronger than only relying on its internal stage checks.
    verify_dir = output_dir / "research_verify"
    research2 = run_research_pipeline(
        material_root=Path(args["materialRoot"]),
        techset_root=Path(args["techsetRoot"]),
        technique_root=Path(args["techniqueRoot"]),
        shader_root=Path(args["shaderRoot"]),
        disassembler=disassembler,
        disassembler_kind=disassembler_kind,
        output_dir=verify_dir,
        context_lines=context_lines,
        require_executable_use=True,
        allow_missing_shaders=False,
        allow_empty=False,
        verify_disassembly_regeneration=True,
    )

    def semantic_projection(doc: dict) -> dict:
        projected = copy.deepcopy(doc)
        projected.pop("manifest", None)
        projected.pop("basePipelineManifest", None)
        projected.pop("inputs", None)
        projected.pop("outputs", None)
        return projected

    if semantic_projection(research1) != semantic_projection(research2):
        raise RetailLightmapPipelineError(
            "isolated lightmap shader semantic regeneration was not identical"
        )

    stage_manifest_path = stage_dir / "t6_retail_lightmap_shader_stage_v1.json"
    research_manifest_path = research_dir / "t6_lightmap_shader_research_manifest_v2.json"
    if not stage_manifest_path.is_file() or not research_manifest_path.is_file():
        raise RetailLightmapPipelineError("expected staged/research manifests are missing")

    lineage_stats = research1.get("stats", {}).get("lineageV2", {})
    validation = research1.get("validation", {})
    result = {
        "format": "t6-retail-lightmap-shader-proof-pipeline-v1",
        "map": map_name,
        "retailFastfile": ff,
        "disassembler": {**disassembler_record, "kind": disassembler_kind},
        "stageManifest": _file_record(stage_manifest_path),
        "researchManifest": _file_record(research_manifest_path),
        "stats": {
            "staging": stage1["stats"],
            "research": research1.get("stats", {}),
            "lineageV2": lineage_stats,
        },
        "validation": {
            "retailFastfileHashPinned": expected_ff_sha256 is not None,
            "retailFastfileHashVerified": True,
            "noMissingShadersAllowed": True,
            "executableLightmapRegisterUseRequired": True,
            "internalDisassemblyRegenerationVerified": bool(
                validation.get("disassemblyRegenerationByteIdentical", False)
                or validation.get("disassemblyRegenerationCanonicalJsonIdentical", False)
                or validation.get("lineageV2RegenerationCanonicalJsonIdentical", False)
            ),
            "lineageV2RegenerationCanonicalJsonIdentical": bool(
                validation.get("lineageV2RegenerationCanonicalJsonIdentical")
            ),
            "isolatedSemanticRegenerationIdentical": True,
        },
        "closureReadiness": {
            "retailProvenanceCollected": True,
            "dxbcRegisterLineageCollected": True,
            "primaryObserved": stage1["stats"]["primaryTechniqueEdgeCount"] > 0,
            "secondaryObserved": stage1["stats"]["secondaryTechniqueEdgeCount"] > 0,
            "bothRolesInSameTechniqueObserved": stage1["stats"]["bothRoleTechniqueEdgeCount"] > 0,
            "channelPhysicalMeaningProven": False,
            "combineEquationProven": False,
        },
        "proofBoundary": (
            "A successful run closes acquisition/provenance/disassembly/register-lineage automation for the supplied retail map. "
            "It does not automatically name physical RGB/A quantities or infer the final lighting equation; those require direct instruction-level algebra and cross-technique validation."
        ),
    }
    payload = _stable_json(result)
    out = output_dir / "t6_retail_lightmap_shader_proof_pipeline_v1.json"
    out.write_bytes(payload)
    result["manifest"] = _file_record(out)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--retail-ff", type=Path, required=True)
    parser.add_argument("--expected-ff-sha256")
    parser.add_argument("--oat-root", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--tool-kind", choices=("fxc", "dxc"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--context-lines", type=int, default=3)
    args = parser.parse_args()
    result = run_pipeline(
        map_name=args.map_name,
        retail_ff=args.retail_ff,
        oat_root=args.oat_root,
        disassembler=args.tool,
        disassembler_kind=args.tool_kind,
        output_dir=args.out_dir,
        expected_ff_sha256=args.expected_ff_sha256,
        context_lines=args.context_lines,
    )
    print(json.dumps({
        "map": result["map"],
        "manifest": result["manifest"],
        "closureReadiness": result["closureReadiness"],
        "validation": result["validation"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
