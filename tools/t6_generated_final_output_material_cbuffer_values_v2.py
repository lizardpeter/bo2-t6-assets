#!/usr/bin/env python3
"""Material cbuffer value proof v2: correct per-owner variation accounting.

v1 resolves exact values correctly but its summary statistic named
``shaderCountWithMaterialValueVariation`` counted distinct individual binding
value signatures within a shader. A shader using two different constant bindings
could therefore be marked as varying even with only one material owner.

v2 leaves every material/binding row untouched and recomputes variation from the
complete ``materialResolvedValueSignatureSha256`` of each material owner sharing
one exact pixel shader.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import defaultdict
from pathlib import Path
from typing import Any
import t6_generated_final_output_material_cbuffer_values_v1 as v1

FORMAT='t6-generated-final-output-material-cbuffer-values-v2'
class FinalOutputMaterialCbufferValueV2Error(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def promote(base:dict)->dict:
 if base.get('format')!=v1.FORMAT:raise FinalOutputMaterialCbufferValueV2Error(f"unexpected v1 format {base.get('format')!r}")
 owners=defaultdict(list)
 for row in base.get('materials',[]):
  sha=str(row.get('pixelShaderSha256') or '');material=str(row.get('material') or '');sig=str(row.get('materialResolvedValueSignatureSha256') or '')
  if not sha or not material or not sig:raise FinalOutputMaterialCbufferValueV2Error('material row lacks shader/material/value-signature identity')
  owners[sha].append({'material':material,'materialResolvedValueSignatureSha256':sig})
 variation=[]
 for sha,rows in sorted(owners.items()):
  signatures=sorted({row['materialResolvedValueSignatureSha256'] for row in rows})
  variation.append({'pixelShaderSha256':sha,'materialOwnerCount':len(rows),'distinctMaterialValueSignatureCount':len(signatures),'variesAcrossMaterialOwners':len(rows)>1 and len(signatures)>1,'owners':sorted(rows,key=lambda x:x['material'])})
 out=copy.deepcopy(base);out['format']=FORMAT;out['baseFormat']=v1.FORMAT;out['shaderMaterialValueVariation']=variation
 summary=copy.deepcopy(base.get('summary',{}));summary['v1BindingValueDiversityStatistic']=summary.get('shaderCountWithMaterialValueVariation');summary['shaderCountWithMaterialValueVariation']=sum(1 for row in variation if row['variesAcrossMaterialOwners']);summary['shaderCountWithMultipleMaterialOwners']=sum(1 for row in variation if row['materialOwnerCount']>1);summary['shaderMaterialValueVariationRowsSha256']=_jhash(variation);out['summary']=summary
 out['proofBoundary']=str(base.get('proofBoundary') or '')+' v2 changes only variation accounting: a shader varies iff multiple material owners have distinct complete resolved-value signatures.'
 return out

def build(final_doc:dict,cbuffer_doc:dict,material_constants_doc:dict)->dict:return promote(v1.build(final_doc,cbuffer_doc,material_constants_doc))
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer-signature',type=Path,required=True);p.add_argument('--material-constants',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.cbuffer_signature.read_text()),json.loads(a.material_constants.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
