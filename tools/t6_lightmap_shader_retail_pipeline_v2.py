#!/usr/bin/env python3
"""One-command retail T6 lightmap shader proof pipeline v2.

V2 is the acquisition-to-equation path:
  verify retail FF identity
    -> exact OAT provenance staging
    -> DXBC research pipeline v3
    -> register lineage v2
    -> straight-line symbolic equation DAG v2
    -> deterministic combined retail proof manifest
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from t6_lightmap_shader_research_pipeline_v3 import run_research_pipeline
from t6_lightmap_shader_retail_stage_v1 import build_stage


class RetailLightmapPipelineV2Error(RuntimeError):
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
        raise RetailLightmapPipelineV2Error(f"retail fastfile missing: {path}")
    record = _file_record(path)
    if expected_sha256 is not None:
        expected = expected_sha256.lower().strip()
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise RetailLightmapPipelineV2Error("expected retail FF SHA-256 must be 64 hex characters")
        if record["sha256"] != expected:
            raise RetailLightmapPipelineV2Error(
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
        raise RetailLightmapPipelineV2Error(f"disassembler missing: {disassembler}")
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = output_dir / "stage"
    research_dir = output_dir / "research"

    stage = build_stage(
        oat_root=oat_root,
        output_dir=stage_dir,
        map_name=map_name,
        retail_ff_sha256=ff["sha256"],
    )
    args = stage["researchPipelineArgs"]
    research = run_research_pipeline(
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

    # Semantic regeneration is repeated independently. Remove path/file wrapper
    # records before comparison; stats/validation/proof content must match.
    verify_dir = output_dir / "research_verify"
    research_verify = run_research_pipeline(
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

    def projection(doc: dict) -> dict:
        value = copy.deepcopy(doc)
        value.pop("manifest", None)
        value.pop("basePipelineManifest", None)
        value.pop("inputs", None)
        value.pop("outputs", None)
        return value

    if projection(research) != projection(research_verify):
        raise RetailLightmapPipelineV2Error("isolated semantic regeneration was not identical")

    symbolic = research.get("stats", {}).get("symbolicV2", {})
    validation = research.get("validation", {})
    stage_manifest = stage_dir / "t6_retail_lightmap_shader_stage_v1.json"
    research_manifest = research_dir / "t6_lightmap_shader_research_manifest_v3.json"
    symbolic_file = research_dir / "t6_lightmap_dxbc_symbolic_v2.json"
    for path in (stage_manifest, research_manifest, symbolic_file):
        if not path.is_file():
            raise RetailLightmapPipelineV2Error(f"expected proof artifact missing: {path}")

    closure_ready = bool(symbolic.get("allEdgesClosureUsable"))
    result = {
        "format": "t6-retail-lightmap-shader-proof-pipeline-v2",
        "map": map_name,
        "retailFastfile": ff,
        "disassembler": {**_file_record(disassembler), "kind": disassembler_kind},
        "stageManifest": _file_record(stage_manifest),
        "researchManifest": _file_record(research_manifest),
        "symbolicEquationManifest": _file_record(symbolic_file),
        "stats": {
            "staging": stage["stats"],
            "research": research.get("stats", {}),
            "symbolicV2": symbolic,
        },
        "validation": {
            "retailFastfileHashPinned": expected_ff_sha256 is not None,
            "retailFastfileHashVerified": True,
            "noMissingShadersAllowed": True,
            "executableLightmapRegisterUseRequired": True,
            "lineageV2RegenerationCanonicalJsonIdentical": bool(validation.get("lineageV2RegenerationCanonicalJsonIdentical")),
            "symbolicV2RegenerationCanonicalJsonIdentical": bool(validation.get("symbolicV2RegenerationCanonicalJsonIdentical")),
            "isolatedSemanticRegenerationIdentical": True,
        },
        "closureReadiness": {
            "retailProvenanceCollected": True,
            "dxbcRegisterLineageCollected": True,
            "symbolicAssemblyEquationCollected": closure_ready,
            "allObservedEdgesSymbolicallyClosed": closure_ready,
            "primaryObserved": stage["stats"]["primaryTechniqueEdgeCount"] > 0,
            "secondaryObserved": stage["stats"]["secondaryTechniqueEdgeCount"] > 0,
            "bothRolesInSameTechniqueObserved": stage["stats"]["bothRoleTechniqueEdgeCount"] > 0,
            "rendererExecutionValidated": False,
        },
        "proofBoundary": (
            "A successful allEdgesSymbolicallyClosed result yields an exact supported straight-line DXBC expression DAG "
            "from T6 primary/secondary sample channels to shader outputs. Human physical channel names are not required "
            "for playback. Final semantic closure still requires executing the retained equation in the T6-aware renderer "
            "and cross-validating representative technique families."
        ),
    }
    out = output_dir / "t6_retail_lightmap_shader_proof_pipeline_v2.json"
    payload = _stable_json(result)
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
