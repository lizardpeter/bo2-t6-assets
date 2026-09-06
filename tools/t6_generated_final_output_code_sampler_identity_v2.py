#!/usr/bin/env python3
"""Resolve current-OAT final-output code samplers to exact T6 identities.

Consumes texture-resource binding v2 plus the pinned T6 sampler table.
Explicit `sampler.foo` (or legacy `code.foo`) bindings resolve directly. If a
sampled RDEF texture has no emitted `.tech` assignment, it resolves implicitly
only when its exact resource name is a pinned T6 code-sampler accessor. This is
OAT's source-closed DX11 AutoCreateMissingArgs rule.

Runtime resource selection/content and D3D11 sampling remain unresolved.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any
FORMAT='t6-generated-final-output-code-sampler-identity-v2'
BINDING_FORMAT='t6-generated-final-output-texture-resource-binding-v2'
TABLE_FORMAT='t6-code-sampler-source-table-v1'
class CodeSamplerIdentityV2Error(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _table(doc:dict)->dict:
 out={}
 for row in doc.get('rows',[]):
  name=str(row.get('accessor') or '')
  if not name or name in out:raise CodeSamplerIdentityV2Error(f'invalid/duplicate T6 code-sampler accessor {name!r}')
  out[name]=row
 if not out:raise CodeSamplerIdentityV2Error('pinned T6 code-sampler table has no rows')
 return out

def _identity(row:dict)->dict:return {k:copy.deepcopy(row.get(k)) for k in ('accessor','enumSymbol','enumValue','enumValueHex','enumAliases','updateFrequency','techFlags','customSamplerIndex')}

def build(binding_doc:dict,sampler_table:dict)->dict:
 if binding_doc.get('format')!=BINDING_FORMAT:raise CodeSamplerIdentityV2Error(f"unexpected texture-binding format {binding_doc.get('format')!r}")
 if sampler_table.get('format')!=TABLE_FORMAT:raise CodeSamplerIdentityV2Error(f"unexpected sampler-table format {sampler_table.get('format')!r}")
 by=_table(sampler_table);rows=[];explicit=implicit=unresolved=0;used=set();freq=Counter()
 for shader in binding_doc.get('shaders',[]):
  resources=[]
  for resource in shader.get('resources',[]):
   resource_name=str(resource.get('resource') or '');assignments=[]
   for assignment in resource.get('techniqueAssignments',[]):
    row=copy.deepcopy(assignment);cls=str(row.get('sourceClass') or '');kind=str(row.get('sourceKind') or '');name=str(row.get('sourceName') or '') if row.get('sourceName') is not None else ''
    match=None;mode=None
    if cls=='code' and kind in ('sampler','legacy_code'):
     namespace='sampler' if kind=='sampler' else 'code'
     if row.get('sourceExpression')!=f'{namespace}.{name}':raise CodeSamplerIdentityV2Error(f"{resource_name}: expression {row.get('sourceExpression')!r} disagrees with namespace/name")
     match=by.get(name)
     if match is None:raise CodeSamplerIdentityV2Error(f"{resource_name}: explicit code sampler accessor {name!r} absent from pinned T6 table")
     mode='explicitTechAssignment';explicit+=1
    elif cls=='unassigned' and resource_name in by:
     name=resource_name;match=by[name];mode='implicitSameAccessorAutoCreate';implicit+=1;row.update({'sourceClass':'code','sourceNamespace':'sampler','sourceKind':'sampler','sourceName':name})
    elif cls=='unassigned':
     unresolved+=1
    if match is not None:
     ident=_identity(match);row['codeSamplerIdentity']=ident;row['bindingMode']=mode;row['runtimeResourceResolved']=False;used.add(name);freq[str(ident['updateFrequency'])]+=1
    else:
     row['codeSamplerIdentity']=None;row['bindingMode']=row.get('assignmentEvidence');row['runtimeResourceResolved']=False
    assignments.append(row)
   resources.append({**{k:v for k,v in resource.items() if k!='techniqueAssignments'},'techniqueAssignments':assignments})
  rows.append({**{k:v for k,v in shader.items() if k!='resources'},'resources':resources})
 summary={'shaderCount':len(rows),'codeSamplerAssignmentCount':explicit+implicit,'explicitCodeSamplerAssignmentCount':explicit,'implicitSameAccessorCodeSamplerAssignmentCount':implicit,'unresolvedUnassignedSamplerBindingCount':unresolved,'uniqueCodeSamplerAccessorCount':len(used),'uniqueCodeSamplerAccessors':sorted(used),'codeSamplerUpdateFrequencyCounts':dict(sorted(freq.items())),'runtimeResourceResolvedCount':0}
 return {'format':FORMAT,'sourceTextureBindingFormat':BINDING_FORMAT,'sourceSamplerTableFormat':TABLE_FORMAT,'source':copy.deepcopy(sampler_table.get('source')),'shaders':rows,'summary':summary,'rowsSha256':_jhash(rows),'implicitBindingProof':{'oatRule':'CommonShaderArgCreator DX11 AutoCreateMissingArgs resolves each missing shader texture by exact resource name through GetCodeSamplerSourceForAccessor and fails when no matching code sampler exists'},'proofBoundary':'Exact explicit sampler.* (or legacy code.*) bindings plus source-closed same-accessor OAT auto-created code samplers joined to pinned T6 MaterialTextureSource metadata. Material/other bindings remain unchanged. Runtime resource instance/content and D3D11 sampling remain unresolved.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--texture-binding',type=Path,required=True);p.add_argument('--sampler-table',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.texture_binding.read_text()),json.loads(a.sampler_table.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
