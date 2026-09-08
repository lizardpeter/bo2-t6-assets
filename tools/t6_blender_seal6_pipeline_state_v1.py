#!/usr/bin/env python3
"""Attach exact SEAL6 ordinary-lit T6/D3D pipeline state to Blender materials.

The input is ``t6-seal6-ordinary-lit-pipeline-state-v1``.  Exact T6 state is
stored verbatim as material metadata.  A very small authoring-only Blender
mapping is applied where safe for viewport inspection (back-face culling and a
transparency mode for the cornea).  That mapping is *not* claimed to reproduce
arbitrary D3D blend/depth/destination-alpha behavior.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import bpy  # type: ignore
except ImportError:
    bpy = None

FORMAT = "t6-blender-seal6-pipeline-state-v1"
PIPELINE_FORMAT = "t6-seal6-ordinary-lit-pipeline-state-v1"


class Seal6BlenderPipelineStateError(RuntimeError):
    pass


def _require_bpy() -> None:
    if bpy is None:
        raise Seal6BlenderPipelineStateError("bpy is unavailable; run inside Blender")


def _material_exact(name: str):
    material = bpy.data.materials.get(name)
    if material is not None:
        return material
    matches = [m for m in bpy.data.materials if m.name == name or m.name.startswith(name + ".")]
    if len(matches) != 1:
        raise Seal6BlenderPipelineStateError(f"exact SEAL6 Material {name!r} is not uniquely present")
    return matches[0]


def validate_pipeline(report: dict[str, Any]) -> None:
    if report.get("format") != PIPELINE_FORMAT:
        raise Seal6BlenderPipelineStateError(f"unsupported pipeline report {report.get('format')!r}")
    summary = report.get("summary") or {}
    expected = {
        "targetMaterials": 5,
        "techniqueTypeIndex": 4,
        "pipelineStatesClosed": 5,
        "uniqueSelectedStatePayloads": 2,
        "litOpaqueMaterials": 4,
        "litTransMaterials": 1,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise Seal6BlenderPipelineStateError(f"pipeline summary {key}={summary.get(key)!r}, expected {value!r}")
    if summary.get("techniqueType") != "lit":
        raise Seal6BlenderPipelineStateError("pipeline report is not for ordinary lit")
    if summary.get("allSelectedStatesInvariantAcrossPhysicalCopies") is not True:
        raise Seal6BlenderPipelineStateError("pipeline state is not invariant across physical copies")
    if summary.get("completeRetailPixelOutputInBlender") is not False:
        raise Seal6BlenderPipelineStateError("pipeline report incorrectly claims complete Blender retail output")
    rows = report.get("materials")
    if not isinstance(rows, list) or len(rows) != 5:
        raise Seal6BlenderPipelineStateError("pipeline report materials[] malformed")


def _authoring_mapping(material, state: dict[str, Any]) -> dict[str, Any]:
    cull = state.get("cullFace")
    if cull == "back" and hasattr(material, "use_backface_culling"):
        material.use_backface_culling = True
        cull_mapping = "use_backface_culling=true"
    elif cull == "none" and hasattr(material, "use_backface_culling"):
        material.use_backface_culling = False
        cull_mapping = "use_backface_culling=false"
    else:
        cull_mapping = "metadata-only"

    blended = state.get("blendOpRgb") != "disabled"
    if not blended:
        blend_mapping = "opaque-authoring"
    else:
        blend_mapping = "metadata-only"
        # Blender 4.x changed Eevee transparency APIs.  Try known authoring
        # controls but retain exact T6 state separately regardless of outcome.
        if hasattr(material, "surface_render_method"):
            for candidate in ("DITHERED", "BLENDED"):
                try:
                    material.surface_render_method = candidate
                    blend_mapping = f"surface_render_method={candidate}"
                    break
                except Exception:
                    pass
        if blend_mapping == "metadata-only" and hasattr(material, "blend_method"):
            try:
                material.blend_method = "BLEND"
                blend_mapping = "blend_method=BLEND"
            except Exception:
                pass
    return {"cull": cull_mapping, "blend": blend_mapping}


def compile_material(material, row: dict[str, Any]) -> dict[str, Any]:
    _require_bpy()
    if material.get("t6_exact_material_local_nodes_compiled") is not True:
        raise Seal6BlenderPipelineStateError(
            f"{material.name}: exact SEAL6 lit material-local nodes must be compiled before pipeline state"
        )
    if material.get("t6_complete_retail_pixel_output") is not False:
        raise Seal6BlenderPipelineStateError(f"{material.name}: unexpected complete-retail claim")
    if row.get("techniqueType") != "lit" or row.get("techniqueTypeIndex") != 4:
        raise Seal6BlenderPipelineStateError(f"{material.name}: pipeline row is not exact ordinary lit index 4")
    if row.get("selectedStateInvariantAcrossPhysicalCopies") is not True:
        raise Seal6BlenderPipelineStateError(f"{material.name}: selected state not invariant")
    state = row.get("selectedStateBits")
    if not isinstance(state, dict):
        raise Seal6BlenderPipelineStateError(f"{material.name}: missing selectedStateBits")

    mapping = _authoring_mapping(material, state)
    material["t6_ordinary_lit_technique_type"] = "lit"
    material["t6_ordinary_lit_technique_type_index"] = 4
    material["t6_ordinary_lit_state_bits_entry_value"] = int(row["stateBitsEntryValue"])
    material["t6_ordinary_lit_pipeline_state_json"] = json.dumps(state, sort_keys=True)
    material["t6_ordinary_lit_pipeline_state_sha256"] = str(row.get("selectedStateBitsSha256") or "")
    material["t6_camera_region"] = str(row.get("cameraRegion") or "")
    material["t6_sort_key"] = int(row.get("sortKey"))
    material["t6_state_flags"] = int(row.get("stateFlags"))
    material["t6_surface_flags"] = int(row.get("surfaceFlags"))
    material["t6_pipeline_state_exact_metadata"] = True
    material["t6_blender_pipeline_authoring_mapping_json"] = json.dumps(mapping, sort_keys=True)
    material["t6_blender_pipeline_authoring_mapping_exact"] = False
    material["t6_complete_retail_pixel_output"] = False
    return {
        "material": row.get("material"),
        "cameraRegion": row.get("cameraRegion"),
        "stateBitsEntryValue": row.get("stateBitsEntryValue"),
        "selectedStateBitsSha256": row.get("selectedStateBitsSha256"),
        "authoringMapping": mapping,
        "exactD3DPipelineStatePreserved": True,
        "blenderPipelineMappingClaimedExact": False,
        "completeRetailPixelOutput": False,
    }


def compile_report(report: dict[str, Any]) -> dict[str, Any]:
    _require_bpy()
    validate_pipeline(report)
    rows = []
    for pipeline_row in report["materials"]:
        material = _material_exact(str(pipeline_row.get("material") or ""))
        rows.append(compile_material(material, pipeline_row))
    opaque = sum(1 for row in rows if row["cameraRegion"] == "litOpaque")
    trans = sum(1 for row in rows if row["cameraRegion"] == "litTrans")
    if (opaque, trans) != (4, 1):
        raise Seal6BlenderPipelineStateError(f"compiled camera-region census drift: {opaque}/{trans}")
    return {
        "format": FORMAT,
        "summary": {
            "materialsCompiled": 5,
            "exactD3DPipelineStatesPreserved": 5,
            "litOpaqueMaterials": 4,
            "litTransMaterials": 1,
            "allBlenderPipelineMappingsExplicitlyAuthoringOnly": True,
            "completeRetailPixelOutput": False,
        },
        "materials": rows,
        "proofBoundary": (
            "Exact T6 ordinary-lit selected stateBits payloads are stored verbatim. Blender cull/transparency "
            "settings are authoring-only mappings and are not claimed to reproduce D3D destination-alpha, "
            "depth-write, alpha-test or blend semantics exactly."
        ),
    }


def _script_args(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args(_script_args(sys.argv))
    pipeline = json.loads(args.pipeline.read_text(encoding="utf-8-sig"))
    out = compile_report(pipeline)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
