#!/usr/bin/env python3
"""Attach exact ordinary-lit T6/D3D pipeline state metadata to all 12 SEAL6 LOD0 Materials."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from typing import Any
try:
    import bpy  # type: ignore
except ImportError:
    bpy=None
import t6_blender_seal6_pipeline_state_v1 as v1

FORMAT="t6-blender-seal6-lod0-pipeline-state-v2"
PIPELINE_FORMAT="t6-seal6-lod0-ordinary-lit-pipeline-state-v2"
class Lod0PipelineBackendError(RuntimeError): pass

def _require_bpy():
    if bpy is None: raise Lod0PipelineBackendError('bpy unavailable; run inside Blender')

def validate(report:dict[str,Any])->None:
    if report.get('format')!=PIPELINE_FORMAT: raise Lod0PipelineBackendError(f"unsupported pipeline {report.get('format')!r}")
    s=report.get('summary') or {}
    expected={'targetMaterials':12,'techniqueTypeIndex':4,'pipelineStatesClosed':12,'uniqueSelectedStatePayloads':2,'litOpaqueMaterials':11,'litTransMaterials':1}
    for k,v in expected.items():
        if s.get(k)!=v: raise Lod0PipelineBackendError(f"pipeline {k}={s.get(k)!r} != {v!r}")
    if s.get('techniqueType')!='lit' or s.get('allSelectedStatesInvariantAcrossPhysicalCopies') is not True or s.get('completeRetailPixelOutputInBlender') is not False:
        raise Lod0PipelineBackendError('pipeline proof-boundary drift')
    rows=report.get('materials')
    if not isinstance(rows,list) or len(rows)!=12: raise Lod0PipelineBackendError('pipeline materials[] malformed')

def compile_report(report:dict[str,Any])->dict[str,Any]:
    _require_bpy(); validate(report)
    rows=[]
    for row in report['materials']:
        material=v1._material_exact(str(row.get('material') or ''))
        rows.append(v1.compile_material(material,row))
        material['t6_pipeline_state_backend']=FORMAT
    opaque=sum(1 for r in rows if r['cameraRegion']=='litOpaque'); trans=sum(1 for r in rows if r['cameraRegion']=='litTrans')
    if (opaque,trans)!=(11,1): raise Lod0PipelineBackendError(f'camera-region census drift {opaque}/{trans}')
    return {'format':FORMAT,'summary':{'materialsCompiled':12,'exactD3DPipelineStatesPreserved':12,'litOpaqueMaterials':11,'litTransMaterials':1,'allBlenderPipelineMappingsExplicitlyAuthoringOnly':True,'completeRetailPixelOutput':False},'materials':rows,'proofBoundary':'Exact T6 selected stateBits payloads are stored verbatim for all 12 LOD0 Materials. Blender culling/transparency settings remain explicitly authoring-only and are not asserted equivalent to D3D blend/depth/destination-alpha behavior.'}

def _args(argv): return argv[argv.index('--')+1:] if '--' in argv else argv[1:]
def main()->int:
    _require_bpy(); ap=argparse.ArgumentParser(); ap.add_argument('--pipeline',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); a=ap.parse_args(_args(sys.argv)); d=compile_report(json.loads(a.pipeline.read_text(encoding='utf-8-sig'))); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print('T6_SEAL6_LOD0_PIPELINE_STATE_V2='+json.dumps(d['summary'],sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
