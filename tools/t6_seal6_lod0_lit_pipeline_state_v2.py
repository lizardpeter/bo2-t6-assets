#!/usr/bin/env python3
"""Close ordinary-lit technique-indexed D3D pipeline state for all 12 SEAL6 LOD0 Materials."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_shader_ir_v1 import TECHNIQUE_TYPES

FORMAT = "t6-seal6-lod0-ordinary-lit-pipeline-state-v2"
SHADER_PLAN_FORMAT = "t6-seal6-lod0-blender-shader-plan-v2"
CENSUS_FORMAT = "t6-seal6-native-material-conflict-report-v1"
LIT_INDEX = TECHNIQUE_TYPES.index("lit")
if LIT_INDEX != 4:
    raise RuntimeError(f"T6 lit TechniqueType index drift: {LIT_INDEX}")

OPAQUE_STATE = {
    "alphaTest":"disabled","blendOpAlpha":"disabled","blendOpRgb":"disabled",
    "colorWriteAlpha":True,"colorWriteRgb":True,"cullFace":"back","depthTest":"less_equal","depthWrite":True,
    "dstBlendAlpha":"zero","dstBlendRgb":"zero","polygonOffset":"offset0","polymodeLine":False,
    "srcBlendAlpha":"one","srcBlendRgb":"one",
}
CORNEA_STATE = {
    "alphaTest":"gt0","blendOpAlpha":"add","blendOpRgb":"add",
    "colorWriteAlpha":True,"colorWriteRgb":True,"cullFace":"back","depthTest":"less_equal","depthWrite":False,
    "dstBlendAlpha":"one","dstBlendRgb":"invsrcalpha","polygonOffset":"offset0","polymodeLine":False,
    "srcBlendAlpha":"invdestalpha","srcBlendRgb":"srcalpha",
}

class Lod0PipelineStateError(RuntimeError): pass

def _sha_obj(v: Any) -> str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def _selected(copy: dict[str,Any], material: str) -> dict[str,Any]:
    rec=copy.get("nativeMaterialRecord")
    if not isinstance(rec,dict): raise Lod0PipelineStateError(f"{material}: nativeMaterialRecord missing")
    entries=rec.get("stateBitsEntry"); states=rec.get("stateBits")
    if not isinstance(entries,list) or len(entries)!=len(TECHNIQUE_TYPES):
        raise Lod0PipelineStateError(f"{material}: stateBitsEntry length drift")
    if not isinstance(states,list): raise Lod0PipelineStateError(f"{material}: stateBits[] missing")
    idx=entries[LIT_INDEX]
    if not isinstance(idx,int) or idx<0 or idx>=len(states): raise Lod0PipelineStateError(f"{material}: invalid lit state index {idx!r}")
    return {"stateIndex":idx,"state":states[idx],"cameraRegion":rec.get("cameraRegion"),"sortKey":rec.get("sortKey"),"stateFlags":rec.get("stateFlags"),"surfaceFlags":rec.get("surfaceFlags"),"surfaceTypeBits":rec.get("surfaceTypeBits")}

def build(shader: dict[str,Any], census: dict[str,Any]) -> dict[str,Any]:
    if shader.get("format")!=SHADER_PLAN_FORMAT: raise Lod0PipelineStateError("wrong shader-plan format")
    if census.get("format")!=CENSUS_FORMAT: raise Lod0PipelineStateError("wrong census format")
    ss=shader.get("summary") or {}
    if int(ss.get("targetMaterials",-1))!=12 or ss.get("exactOrdinaryLitEquationsClosed") is not True:
        raise Lod0PipelineStateError("shader plan is not exact all-12 closure")
    plans={str(r.get("material") or ""):r for r in shader.get("materials",[])}
    natives={str(r.get("material") or ""):r for r in census.get("materials",[])}
    if len(plans)!=12 or set(plans)!=set(natives): raise Lod0PipelineStateError("Material set mismatch")
    rows=[]; opaque=trans=0; sigs=set()
    for material,plan in plans.items():
        copies=natives[material].get("copies")
        if not isinstance(copies,list) or not copies: raise Lod0PipelineStateError(f"{material}: no copies")
        sel=[_selected(c,material) for c in copies]
        first=sel[0]
        if any(x!=first for x in sel[1:]): raise Lod0PipelineStateError(f"{material}: selected lit state differs across copies")
        if material=="mc/mtl_gen_eye_cornea":
            expected=(0,"litTrans",40,21,7602176,CORNEA_STATE); trans+=1
        else:
            expected=(2,"litOpaque",4,121,7340032,OPAQUE_STATE); opaque+=1
        actual=(first["stateIndex"],first["cameraRegion"],first["sortKey"],first["stateFlags"],first["surfaceFlags"],first["state"])
        if actual!=expected: raise Lod0PipelineStateError(f"{material}: exact lit state drift")
        sha=_sha_obj(first["state"]); sigs.add(sha)
        rows.append({"material":material,"techniqueSet":plan.get("techniqueSet"),"shaderFamilyId":plan.get("shaderFamilyId"),"shaderIdentity":plan.get("shaderIdentity"),"techniqueType":"lit","techniqueTypeIndex":LIT_INDEX,"stateBitsEntryValue":first["stateIndex"],"selectedStateBits":first["state"],"selectedStateBitsSha256":sha,"cameraRegion":first["cameraRegion"],"sortKey":first["sortKey"],"stateFlags":first["stateFlags"],"surfaceFlags":first["surfaceFlags"],"surfaceTypeBits":first["surfaceTypeBits"],"physicalMaterialCopyCount":len(sel),"selectedStateInvariantAcrossPhysicalCopies":True,"activeRetailClientWholeMaterialOwnerResolved":bool(natives[material].get("activeRetailClientOwnerResolved"))})
    if (opaque,trans,len(sigs))!=(11,1,2): raise Lod0PipelineStateError(f"state census drift {(opaque,trans,len(sigs))}")
    return {"format":FORMAT,"summary":{"targetMaterials":12,"techniqueType":"lit","techniqueTypeIndex":4,"pipelineStatesClosed":12,"uniqueSelectedStatePayloads":2,"litOpaqueMaterials":11,"litTransMaterials":1,"allSelectedStatesInvariantAcrossPhysicalCopies":True,"headPipelineStateIndependentOfUnresolvedWholeMaterialOwner":True,"completeRetailPixelOutputInBlender":False},"materials":rows,"proofBoundary":"Ordinary-lit state is selected only by the pinned T6 TechniqueType index 4 and each exact native Material stateBitsEntry[4] -> stateBits[index]. Physical-copy invariance is mandatory. Blender viewport mappings are not asserted equivalent to D3D state."}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--shader-plan',type=Path,required=True); ap.add_argument('--native-census',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    d=build(json.loads(a.shader_plan.read_text(encoding='utf-8-sig')),json.loads(a.native_census.read_text(encoding='utf-8-sig')))
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(d['summary'],indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
