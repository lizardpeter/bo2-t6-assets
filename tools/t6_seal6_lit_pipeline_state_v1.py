#!/usr/bin/env python3
"""Close exact technique-indexed ordinary-lit pipeline state for SEAL6 materials.

T6 Material render state is not material-global.  The exact selected state for a
TechniqueType is:

    stateBits[stateBitsEntry[techniqueTypeIndex]]

The technique-type order is imported from ``t6_shader_ir_v1`` which is pinned to
OpenAssetTools ``TechsetConstantsT6.h``.  Ordinary ``lit`` is index 4.  This
adapter joins the already-closed SEAL6 shader plan to the physical native OAT
Material copies and requires the selected ordinary-lit state to be invariant
across copies before emitting it.

No Blender mapping is performed here.  The output is authoritative T6/D3D state
metadata only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_shader_ir_v1 import TECHNIQUE_TYPES

FORMAT = "t6-seal6-ordinary-lit-pipeline-state-v1"
SHADER_PLAN_FORMAT = "t6-seal6-blender-shader-plan-v1"
CONFLICT_FORMAT = "t6-seal6-native-material-conflict-report-v1"
LIT_TYPE = "lit"
LIT_TYPE_INDEX = TECHNIQUE_TYPES.index(LIT_TYPE)
if LIT_TYPE_INDEX != 4:
    raise RuntimeError(f"pinned T6 ordinary lit technique index drifted: {LIT_TYPE_INDEX}")

OPAQUE_STATE = {
    "alphaTest": "disabled",
    "blendOpAlpha": "disabled",
    "blendOpRgb": "disabled",
    "colorWriteAlpha": True,
    "colorWriteRgb": True,
    "cullFace": "back",
    "depthTest": "less_equal",
    "depthWrite": True,
    "dstBlendAlpha": "zero",
    "dstBlendRgb": "zero",
    "polygonOffset": "offset0",
    "polymodeLine": False,
    "srcBlendAlpha": "one",
    "srcBlendRgb": "one",
}
CORNEA_STATE = {
    "alphaTest": "gt0",
    "blendOpAlpha": "add",
    "blendOpRgb": "add",
    "colorWriteAlpha": True,
    "colorWriteRgb": True,
    "cullFace": "back",
    "depthTest": "less_equal",
    "depthWrite": False,
    "dstBlendAlpha": "one",
    "dstBlendRgb": "invsrcalpha",
    "polygonOffset": "offset0",
    "polymodeLine": False,
    "srcBlendAlpha": "invdestalpha",
    "srcBlendRgb": "srcalpha",
}

TARGETS = {
    "mc/mtl_c_usa_milcas_mcknight_head_camo": {
        "stateIndex": 2, "cameraRegion": "litOpaque", "sortKey": 4,
        "stateFlags": 121, "surfaceFlags": 7340032, "state": OPAQUE_STATE,
    },
    "mc/mtl_c_usa_mp_seal6_smg_arms": {
        "stateIndex": 2, "cameraRegion": "litOpaque", "sortKey": 4,
        "stateFlags": 121, "surfaceFlags": 7340032, "state": OPAQUE_STATE,
    },
    "mc/mtl_gen_eye_cornea": {
        "stateIndex": 0, "cameraRegion": "litTrans", "sortKey": 40,
        "stateFlags": 21, "surfaceFlags": 7602176, "state": CORNEA_STATE,
    },
    "mc/mtl_gen_eye_iris_green": {
        "stateIndex": 2, "cameraRegion": "litOpaque", "sortKey": 4,
        "stateFlags": 121, "surfaceFlags": 7340032, "state": OPAQUE_STATE,
    },
    "mc/mtl_c_gen_insidemouth": {
        "stateIndex": 2, "cameraRegion": "litOpaque", "sortKey": 4,
        "stateFlags": 121, "surfaceFlags": 7340032, "state": OPAQUE_STATE,
    },
}


class Seal6PipelineStateError(RuntimeError):
    pass


def _sha_obj(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _copies(material: dict[str, Any]) -> list[dict[str, Any]]:
    rows = material.get("copies")
    if not isinstance(rows, list) or not rows:
        raise Seal6PipelineStateError(f"{material.get('material')}: no physical native Material copies")
    return rows


def _selected(copy: dict[str, Any], material: str) -> dict[str, Any]:
    rec = copy.get("nativeMaterialRecord")
    if not isinstance(rec, dict):
        raise Seal6PipelineStateError(f"{material}: physical copy lacks nativeMaterialRecord")
    entries = rec.get("stateBitsEntry")
    states = rec.get("stateBits")
    if not isinstance(entries, list) or len(entries) != len(TECHNIQUE_TYPES):
        raise Seal6PipelineStateError(
            f"{material}: stateBitsEntry length {0 if not isinstance(entries, list) else len(entries)} != {len(TECHNIQUE_TYPES)}"
        )
    if not isinstance(states, list):
        raise Seal6PipelineStateError(f"{material}: native Material lacks stateBits[]")
    state_index = entries[LIT_TYPE_INDEX]
    if not isinstance(state_index, int) or state_index < 0 or state_index >= len(states):
        raise Seal6PipelineStateError(
            f"{material}: stateBitsEntry[{LIT_TYPE_INDEX}]={state_index!r} does not select a valid state"
        )
    state = states[state_index]
    if not isinstance(state, dict):
        raise Seal6PipelineStateError(f"{material}: selected stateBits[{state_index}] is not an object")
    return {
        "stateIndex": state_index,
        "state": state,
        "cameraRegion": rec.get("cameraRegion"),
        "sortKey": rec.get("sortKey"),
        "stateFlags": rec.get("stateFlags"),
        "surfaceFlags": rec.get("surfaceFlags"),
        "surfaceTypeBits": rec.get("surfaceTypeBits"),
    }


def build(shader_plan: dict[str, Any], conflict: dict[str, Any]) -> dict[str, Any]:
    if shader_plan.get("format") != SHADER_PLAN_FORMAT:
        raise Seal6PipelineStateError(f"unsupported shader plan {shader_plan.get('format')!r}")
    if conflict.get("format") != CONFLICT_FORMAT:
        raise Seal6PipelineStateError(f"unsupported native report {conflict.get('format')!r}")
    ss = shader_plan.get("summary") or {}
    if ss.get("allOrdinaryLitMaterialArgumentsClosed") is not True or ss.get("exactOrdinaryLitEquationsClosed") is not True:
        raise Seal6PipelineStateError("input shader plan has not closed exact ordinary-lit Material arguments/equations")
    if ss.get("completeRetailPixelOutputInBlender") is not False:
        raise Seal6PipelineStateError("pipeline state closure must not inherit a complete-retail Blender claim")

    plans = {str(r.get("material") or ""): r for r in shader_plan.get("materials", [])}
    natives = {str(r.get("material") or ""): r for r in conflict.get("materials", [])}
    if set(plans) != set(TARGETS):
        raise Seal6PipelineStateError(f"shader plan Material set drift: {sorted(plans)}")
    if set(TARGETS) - set(natives):
        raise Seal6PipelineStateError(f"native report missing Materials: {sorted(set(TARGETS)-set(natives))}")

    rows = []
    signatures = set()
    opaque = 0
    translucent = 0
    for material, expected in TARGETS.items():
        plan = plans[material]
        native = natives[material]
        selected = [_selected(copy, material) for copy in _copies(native)]
        first = selected[0]
        if any(row != first for row in selected[1:]):
            raise Seal6PipelineStateError(f"{material}: selected ordinary-lit pipeline state differs across physical copies")
        for key in ("stateIndex", "cameraRegion", "sortKey", "stateFlags", "surfaceFlags"):
            if first[key] != expected[key]:
                raise Seal6PipelineStateError(f"{material}: {key}={first[key]!r} != exact expected {expected[key]!r}")
        if first["state"] != expected["state"]:
            raise Seal6PipelineStateError(f"{material}: selected ordinary-lit stateBits payload drift")
        if first["cameraRegion"] == "litOpaque":
            opaque += 1
        elif first["cameraRegion"] == "litTrans":
            translucent += 1
        else:
            raise Seal6PipelineStateError(f"{material}: unexpected cameraRegion {first['cameraRegion']!r}")
        state_sha = _sha_obj(first["state"])
        signatures.add(state_sha)
        rows.append({
            "material": material,
            "techniqueSet": plan.get("techniqueSet"),
            "shaderFamilyId": plan.get("shaderFamilyId"),
            "shaderIdentity": plan.get("shaderIdentity"),
            "techniqueType": LIT_TYPE,
            "techniqueTypeIndex": LIT_TYPE_INDEX,
            "stateBitsEntryValue": first["stateIndex"],
            "selectedStateBits": first["state"],
            "selectedStateBitsSha256": state_sha,
            "cameraRegion": first["cameraRegion"],
            "sortKey": first["sortKey"],
            "stateFlags": first["stateFlags"],
            "surfaceFlags": first["surfaceFlags"],
            "surfaceTypeBits": first["surfaceTypeBits"],
            "physicalMaterialCopyCount": len(selected),
            "selectedStateInvariantAcrossPhysicalCopies": True,
            "activeRetailClientWholeMaterialOwnerResolved": bool(native.get("activeRetailClientOwnerResolved")),
        })

    if (opaque, translucent, len(signatures)) != (4, 1, 2):
        raise Seal6PipelineStateError(
            f"SEAL6 ordinary-lit state census drift opaque={opaque} translucent={translucent} unique={len(signatures)}"
        )
    return {
        "format": FORMAT,
        "summary": {
            "targetMaterials": 5,
            "techniqueType": LIT_TYPE,
            "techniqueTypeIndex": LIT_TYPE_INDEX,
            "pipelineStatesClosed": 5,
            "uniqueSelectedStatePayloads": 2,
            "litOpaqueMaterials": 4,
            "litTransMaterials": 1,
            "allSelectedStatesInvariantAcrossPhysicalCopies": True,
            "headPipelineStateIndependentOfUnresolvedWholeMaterialOwner": True,
            "completeRetailPixelOutputInBlender": False,
        },
        "materials": rows,
        "proofBoundary": (
            "Ordinary-lit state is selected only through the pinned T6 TechniqueType order and exact native "
            "Material.stateBitsEntry[4] -> stateBits[index] lookup. Physical-copy invariance is required. "
            "No material-global blend inference and no Blender render-state equivalence are asserted."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shader-plan", type=Path, required=True)
    ap.add_argument("--native-conflicts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    shader_plan = json.loads(args.shader_plan.read_text(encoding="utf-8-sig"))
    conflict = json.loads(args.native_conflicts.read_text(encoding="utf-8-sig"))
    result = build(shader_plan, conflict)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
