#!/usr/bin/env python3
"""Join final-output code.* texture bindings to exact pinned T6 sampler identities.

Consumes the exact texture-resource binding sidecar and the pinned T6
MaterialTextureSource/commonCodeSamplerSources table. Every `.tech` code.* RHS
must resolve to exactly one T6 accessor row. Material/other bindings are retained
unchanged and are not reinterpreted.

This proves engine sampler identity/index/update-frequency metadata only; it does
not select a runtime GfxImage/cubemap/lightmap instance or emulate D3D11 sampling.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-code-sampler-identity-v1'
BINDING_FORMAT='t6-generated-final-output-texture-resource-binding-v1'
TABLE_FORMAT='t6-code-sampler-source-table-v1'
class CodeSamplerIdentityError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def build(binding_doc:dict,sampler_table:dict)->dict:
 if binding_doc.get('format')!=BINDING_FORMAT:raise CodeSamplerIdentityError(f"unexpected texture-binding format {binding_doc.get('format')!r}")
 if sampler_table.get('format')!=TABLE_FORMAT:raise CodeSamplerIdentityError(f"unexpected sampler-table format {sampler_table.get('format')!r}")
 by={}
 for row in sampler_table.get('rows',[]):
  accessor=str(row.get('accessor') or '')
  if not accessor or accessor in by:raise CodeSamplerIdentityError(f'invalid/duplicate T6 code-sampler accessor {accessor!r}')
  by[accessor]=row
 rows=[];counts=Counter();used=set();code_count=0
 for shader in binding_doc.get('shaders',[]):
  resources=[]
  for resource in shader.get('resources',[]):
   assignments=[]
   for assignment in resource.get('techniqueAssignments',[]):
    row=dict(assignment);cls=str(row.get('sourceClass') or '')
    if cls=='code':
     name=str(row.get('sourceName') or '')
     match=by.get(name)
     if match is None:raise CodeSamplerIdentityError(f"{shader.get('sha256')} {resource.get('resource')} {row.get('techniqueSet')}: code sampler accessor {name!r} absent from pinned T6 table")
     identity={key:match.get(key) for key in ('accessor','enumSymbol','enumValue','enumValueHex','enumAliases','updateFrequency','techFlags','customSamplerIndex')}
     row['codeSamplerIdentity']=identity;row['runtimeResourceResolved']=False;used.add(name);code_count+=1;counts[str(identity['updateFrequency'])]+=1
    else:
     row['codeSamplerIdentity']=None;row['runtimeResourceResolved']=False
    assignments.append(row)
   resources.append({**{k:v for k,v in resource.items() if k!='techniqueAssignments'},'techniqueAssignments':assignments})
  rows.append({**{k:v for k,v in shader.items() if k!='resources'},'resources':resources})
 summary={'shaderCount':len(rows),'codeSamplerAssignmentCount':code_count,'uniqueCodeSamplerAccessorCount':len(used),'uniqueCodeSamplerAccessors':sorted(used),'codeSamplerUpdateFrequencyCounts':dict(sorted(counts.items())),'runtimeResourceResolvedCount':0}
 return {'format':FORMAT,'sourceTextureBindingFormat':BINDING_FORMAT,'sourceSamplerTableFormat':TABLE_FORMAT,'source':sampler_table.get('source'),'shaders':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Exact .tech code.* texture RHS -> pinned T6 commonCodeSamplerSources accessor -> MaterialTextureSource enum/index/update-frequency/customSampler/techFlags identity. Runtime resource instance/content and D3D11 sampler behavior remain unresolved; material.* and other bindings are retained without reinterpretation.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--texture-binding',type=Path,required=True);p.add_argument('--sampler-table',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.texture_binding.read_text()),json.loads(a.sampler_table.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
