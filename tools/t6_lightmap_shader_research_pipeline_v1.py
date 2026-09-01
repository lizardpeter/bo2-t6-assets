#!/usr/bin/env python3
"""One-command proof-driven retail T6 lightmap shader research pipeline.

This orchestration deliberately composes already-independent stages instead of
adding new shader assumptions:

  OAT material/techset/technique/shader dump
    -> lightmap shader inventory v2
    -> exact DXBC/RDEF register manifest v1
    -> hashed fxc/dxc dumpbin archive v1
    -> bounded lightmap-register evidence v1
    -> conservative component lineage v1

Every intermediate manifest is retained with SHA-256. Deterministic in-process
stages are regenerated and compared. By default the external disassembler is
also run twice and every archived stdout/stderr artifact must be byte-identical.

The final output is a research/provenance bundle. It does NOT claim the physical
meaning of primary/secondary channels or reconstruct the final combine equation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from t6_dxbc_disassemble_v1 import disassemble_manifest
from t6_lightmap_disassembly_evidence_v1 import build_evidence
from t6_lightmap_dxbc_lineage_v1 import build_lineage_manifest
from t6_lightmap_shader_dxbc_manifest_v1 import build_manifest as build_dxbc_manifest
from t6_lightmap_shader_inventory_v2 import build_inventory


class LightmapShaderResearchPipelineError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _stable_json(document: dict) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _file_record(path: Path, payload: bytes | None = None) -> dict:
    raw = path.read_bytes() if payload is None else payload
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(raw),
        "sha256": _sha256(raw),
    }


def _write_json(path: Path, document: dict) -> dict:
    payload = _json_bytes(document)
    path.write_bytes(payload)
    return _file_record(path, payload)


def _require_deterministic(label: str, first: dict, second: dict) -> None:
    if _stable_json(first) != _stable_json(second):
        raise LightmapShaderResearchPipelineError(
            f"{label} regeneration was not byte-identical as canonical JSON"
        )


def _verify_disassembly_artifacts(
    first: dict,
    second: dict,
    *,
    first_root: Path,
    second_root: Path,
) -> None:
    _require_deterministic("DXBC disassembly archive manifest", first, second)
    first_by_shader = {str(x["pixelShader"]): x for x in first.get("shaders", [])}
    second_by_shader = {str(x["pixelShader"]): x for x in second.get("shaders", [])}
    if set(first_by_shader) != set(second_by_shader):
        raise LightmapShaderResearchPipelineError(
            "DXBC disassembly regeneration changed shader identity set"
        )
    for shader_name in sorted(first_by_shader):
        a = first_by_shader[shader_name]
        b = second_by_shader[shader_name]
        for key in ("disassemblyFile", "stderrFile"):
            a_name = a.get(key)
            b_name = b.get(key)
            if a_name != b_name:
                raise LightmapShaderResearchPipelineError(
                    f"DXBC disassembly regeneration changed {key} for {shader_name!r}"
                )
            if not a_name:
                continue
            a_raw = (first_root / str(a_name)).read_bytes()
            b_raw = (second_root / str(b_name)).read_bytes()
            if a_raw != b_raw:
                raise LightmapShaderResearchPipelineError(
                    f"DXBC disassembly artifact was not byte-identical for {shader_name!r}: {key}"
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
    output_dir.mkdir(parents=True, exist_ok=True)
    disassembly_dir = output_dir / "disassembly"
    disassembly_dir.mkdir(parents=True, exist_ok=True)

    inventory1 = build_inventory(
        material_root=material_root,
        techset_root=techset_root,
        technique_root=technique_root,
        shader_root=shader_root,
        allow_missing_shaders=allow_missing_shaders,
    )
    inventory2 = build_inventory(
        material_root=material_root,
        techset_root=techset_root,
        technique_root=technique_root,
        shader_root=shader_root,
        allow_missing_shaders=allow_missing_shaders,
    )
    _require_deterministic("lightmap shader inventory v2", inventory1, inventory2)
    unique_shader_count = int(
        inventory1.get("stats", {}).get("uniqueLightmapPixelShaderCount", 0)
    )
    if unique_shader_count == 0 and not allow_empty:
        raise LightmapShaderResearchPipelineError(
            "OAT dump contains zero selected lightmap pixel shaders; refusing empty retail proof"
        )
    inventory_path = output_dir / "t6_lightmap_shader_inventory_v2.json"
    inventory_record = _write_json(inventory_path, inventory1)

    dxbc1 = build_dxbc_manifest(
        inventory1,
        shader_root=shader_root,
        allow_missing_shaders=allow_missing_shaders,
    )
    dxbc2 = build_dxbc_manifest(
        inventory1,
        shader_root=shader_root,
        allow_missing_shaders=allow_missing_shaders,
    )
    _require_deterministic("lightmap shader DXBC manifest v1", dxbc1, dxbc2)
    dxbc_path = output_dir / "t6_lightmap_shader_dxbc_manifest_v1.json"
    dxbc_record = _write_json(dxbc_path, dxbc1)

    archive1 = disassemble_manifest(
        dxbc1,
        shader_root=shader_root,
        executable=disassembler,
        tool_kind=disassembler_kind,
        output_dir=disassembly_dir,
    )
    disassembly_regeneration_identical = None
    if verify_disassembly_regeneration:
        with tempfile.TemporaryDirectory(prefix="t6_dxbc_verify_") as td:
            verify_root = Path(td)
            archive2 = disassemble_manifest(
                dxbc1,
                shader_root=shader_root,
                executable=disassembler,
                tool_kind=disassembler_kind,
                output_dir=verify_root,
            )
            _verify_disassembly_artifacts(
                archive1,
                archive2,
                first_root=disassembly_dir,
                second_root=verify_root,
            )
        disassembly_regeneration_identical = True
    archive_path = output_dir / "t6_dxbc_disassembly_archive_v1.json"
    archive_record = _write_json(archive_path, archive1)

    evidence1 = build_evidence(
        dxbc1,
        archive1,
        disassembly_root=disassembly_dir,
        context_lines=context_lines,
        require_executable_use=require_executable_use,
    )
    evidence2 = build_evidence(
        dxbc1,
        archive1,
        disassembly_root=disassembly_dir,
        context_lines=context_lines,
        require_executable_use=require_executable_use,
    )
    _require_deterministic("lightmap disassembly evidence v1", evidence1, evidence2)
    evidence_path = output_dir / "t6_lightmap_disassembly_evidence_v1.json"
    evidence_record = _write_json(evidence_path, evidence1)

    lineage1 = build_lineage_manifest(
        dxbc1,
        archive1,
        disassembly_root=disassembly_dir,
    )
    lineage2 = build_lineage_manifest(
        dxbc1,
        archive1,
        disassembly_root=disassembly_dir,
    )
    _require_deterministic("lightmap DXBC lineage v1", lineage1, lineage2)
    lineage_path = output_dir / "t6_lightmap_dxbc_lineage_v1.json"
    lineage_record = _write_json(lineage_path, lineage1)

    disassembly_records = []
    for item in archive1.get("shaders", []):
        disassembly_records.append(
            {
                "pixelShader": item["pixelShader"],
                "shaderSha256": item["shaderSha256"],
                "disassembly": _file_record(
                    disassembly_dir / str(item["disassemblyFile"])
                ),
                "stderr": (
                    None
                    if not item.get("stderrFile")
                    else _file_record(disassembly_dir / str(item["stderrFile"]))
                ),
            }
        )

    manifest = {
        "format": "t6-lightmap-shader-research-pipeline-manifest-v1",
        "inputs": {
            "materialRoot": str(material_root),
            "techsetRoot": str(techset_root),
            "techniqueRoot": str(technique_root),
            "shaderRoot": str(shader_root),
            "disassembler": archive1.get("disassembler"),
        },
        "outputs": {
            "shaderInventoryV2": inventory_record,
            "shaderDxbcManifestV1": dxbc_record,
            "disassemblyArchiveV1": archive_record,
            "disassemblyEvidenceV1": evidence_record,
            "dxbcLineageV1": lineage_record,
            "disassemblyArtifacts": disassembly_records,
        },
        "validation": {
            "inventoryRegenerationCanonicalJsonIdentical": True,
            "dxbcManifestRegenerationCanonicalJsonIdentical": True,
            "disassemblyRegenerationByteIdentical": disassembly_regeneration_identical,
            "evidenceRegenerationCanonicalJsonIdentical": True,
            "lineageRegenerationCanonicalJsonIdentical": True,
            "requireExecutableLightmapRegisterUse": require_executable_use,
            "allowMissingShaders": allow_missing_shaders,
            "allowEmpty": allow_empty,
        },
        "stats": {
            "inventory": inventory1.get("stats", {}),
            "dxbc": dxbc1.get("stats", {}),
            "disassembly": archive1.get("stats", {}),
            "evidence": evidence1.get("stats", {}),
            "lineage": lineage1.get("stats", {}),
        },
        "proofBoundary": {
            "closedByThisPipeline": [
                "Material/TechniqueSet/Technique/Pass -> exact pixel shader identity",
                "T6 primary/secondary code sampler -> shader resource accessor",
                "shader resource accessor -> exact DXBC RDEF texture bind point",
                "exact shader/disassembler hashes -> retained dumpbin text",
                "exact t# references -> bounded instruction evidence",
                "conservative sampled-channel dependency lineage for supported straight-line writes",
            ],
            "stillNotClaimed": [
                "physical RGB/A meaning of primary lightmap",
                "physical RGB/A meaning of secondary lightmap",
                "exact algebraic primary/secondary combine equation",
                "CFG/SSA-correct lineage across shader control flow",
                "retail proof unless inputs are retained retail T6 OAT dumps and shader binaries",
            ],
        },
    }
    manifest_payload = _json_bytes(manifest)
    manifest_path = output_dir / "t6_lightmap_shader_research_manifest_v1.json"
    manifest_path.write_bytes(manifest_payload)
    manifest["manifest"] = _file_record(manifest_path, manifest_payload)
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
