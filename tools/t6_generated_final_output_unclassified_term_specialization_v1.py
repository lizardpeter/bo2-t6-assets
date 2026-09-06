#!/usr/bin/env python3
"""Per-material symbolic specialization of still-unclassified final-RGB terms.

Consumes:
- authoritative full final-output DAG v3;
- cbuffer replay-completeness sidecar v1.

For every unknown term and every exact material owner of its pixel shader, the
term subtree is serialized again with cbuffer leaves specialized only where
source evidence is closed:
- material.* -> exact float32 literal bits/value for that material;
- code.* -> exact T6 enum/index/update-frequency identity, runtime-dynamic;
- unresolved -> original raw cbN[R].component identity.

No arithmetic is evaluated, folded, reordered, associated, or simplified. The
result is a deterministic source-specialized expression profile, not a guessed
lighting equation.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-unclassified-term-specialization-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
RESOLUTION_FORMAT='t6-generated-final-output-unclassified-term-cbuffer-resolution-v1'
class UnclassifiedTermSpecializationError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _f32bits(v:float)->str:return struct.pack('<f',float(v)).hex()

def _shader_rows(doc:dict)->dict[str,dict]:
 out={}
 for row in doc.get('shaders',[]):
  sha=str(row.get('sha256') or '')
  if not sha or sha in out:raise UnclassifiedTermSpecializationError(f'invalid/duplicate shader {sha!r}')
  out[sha]=row
 return out

def _material_owners(doc:dict)->dict[str,list[dict]]:
 out={};seen=set()
 for row in doc.get('materials',[]):
  material=str(row.get('material') or '');sha=str(row.get('pixelShaderSha256') or '');tech=str(row.get('techniqueSet') or '')
  if not material or not sha or not tech or material in seen:raise UnclassifiedTermSpecializationError(f'invalid/duplicate material owner {material!r}')
  seen.add(material);out.setdefault(sha,[]).append({'material':material,'techniqueSet':tech})
 for sha in out:out[sha].sort(key=lambda x:x['material'])
 return out

def _node_table(shader:dict)->dict[int,dict]:
 out={}
 for row in shader.get('nodes',[]):
  node=int(row.get('id',-1))
  if node<0 or node in out:raise UnclassifiedTermSpecializationError(f'invalid/duplicate DAG node {node}')
  out[node]=row
 return out

def _resolution_by_symbol(term:dict)->dict[str,dict]:
 out={}
 for row in term.get('cbufferResolutionV1',[]):
  symbol=str(row.get('symbol') or '')
  if not symbol or symbol in out:raise UnclassifiedTermSpecializationError(f'invalid/duplicate term resolution symbol {symbol!r}')
  out[symbol]=row
 return out

def _assignment_for_owner(resolution:dict,owner:dict)->dict|None:
 technique=owner['techniqueSet'];matches=[row for row in resolution.get('assignments',[]) if str(row.get('techniqueSet') or '')==technique]
 if len(matches)>1:raise UnclassifiedTermSpecializationError(f"{resolution.get('symbol')} TechniqueSet {technique!r}: multiple resolution assignments")
 return matches[0] if matches else None

def _replacement(symbol:str,resolution:dict|None,owner:dict)->dict:
 if resolution is None:return {'kind':'unresolvedCbuffer','symbol':symbol,'reason':'dependency_not_in_resolution_sidecar'}
 assignment=_assignment_for_owner(resolution,owner)
 if assignment is None:return {'kind':'unresolvedCbuffer','symbol':symbol,'reason':'owner_technique_assignment_absent','techniqueSet':owner['techniqueSet']}
 kind=str(assignment.get('resolutionKind') or '')
 if kind=='retail_material_constant':
  states=[row for row in assignment.get('materialOwners',[]) if str(row.get('material') or '')==owner['material']]
  if len(states)!=1:raise UnclassifiedTermSpecializationError(f"{owner['material']!r} {symbol}: material value owner count {len(states)}, expected 1")
  state=states[0];value=float(state['scalarValue'])
  return {'kind':'retailMaterialConstant','symbol':symbol,'techniqueSet':owner['techniqueSet'],'sourceExpression':assignment.get('sourceExpression'),'sourceName':assignment.get('sourceName'),'scalarFloat32Bits':_f32bits(value),'scalarValue':value,'materialArchiveSha256':state.get('materialArchiveSha256'),'constantSerializedSha256':state.get('constantSerializedSha256')}
 if kind=='t6_code_constant_dynamic':
  code=assignment.get('codeConstant') or {}
  return {'kind':'t6CodeConstantDynamic','symbol':symbol,'techniqueSet':owner['techniqueSet'],'sourceExpression':assignment.get('sourceExpression'),'sourceName':assignment.get('sourceName'),'accessor':code.get('accessor'),'arrayIndex':code.get('arrayIndex'),'resolvedEnumValue':code.get('resolvedEnumValue'),'updateFrequency':code.get('updateFrequency'),'techFlags':code.get('techFlags'),'transposedMatrixEnumValue':code.get('transposedMatrixEnumValue')}
 return {'kind':'unresolvedCbuffer','symbol':symbol,'techniqueSet':owner['techniqueSet'],'sourceClass':assignment.get('sourceClass'),'sourceExpression':assignment.get('sourceExpression'),'sourceName':assignment.get('sourceName'),'reason':kind or 'unresolved'}

def _profile(nodes:dict[int,dict],root:int,replacements:dict[str,dict],memo:dict[int,Any])->Any:
 if root in memo:return memo[root]
 if root not in nodes:raise UnclassifiedTermSpecializationError(f'DAG references missing node {root}')
 row=nodes[root]
 if row.get('kind')=='symbol' and str(row.get('name') or '').startswith('cb'):
  symbol=str(row['name']);result=replacements.get(symbol,{'kind':'unresolvedCbuffer','symbol':symbol,'reason':'no_replacement'})
 else:
  result={key:value for key,value in row.items() if key not in ('id','args','instructionDword')}
  result['args']=[_profile(nodes,int(child),replacements,memo) for child in row.get('args',[])]
 memo[root]=result;return result

def build(final_doc:dict,resolution_doc:dict)->dict:
 if final_doc.get('format')!=FINAL_FORMAT:raise UnclassifiedTermSpecializationError(f"unexpected final-output format {final_doc.get('format')!r}")
 if resolution_doc.get('format')!=RESOLUTION_FORMAT:raise UnclassifiedTermSpecializationError(f"unexpected resolution format {resolution_doc.get('format')!r}")
 shaders=_shader_rows(final_doc);owners=_material_owners(final_doc);rows=[];variant_count=0;term_variation=0;fully_literal_material_variants=0;dynamic_code_variants=0;unresolved_variants=0;groups={}
 for term in resolution_doc.get('terms',[]):
  sha=str(term.get('sha256') or '');root=int(term.get('node',-1));shader=shaders.get(sha)
  if shader is None:raise UnclassifiedTermSpecializationError(f'term shader {sha!r} absent from final DAG')
  shader_owners=owners.get(sha,[])
  if not shader_owners:raise UnclassifiedTermSpecializationError(f'term shader {sha!r} has no material owners')
  nodes=_node_table(shader);resolutions=_resolution_by_symbol(term);variants=[]
  for owner in shader_owners:
   replacements={symbol:_replacement(symbol,resolution,owner) for symbol,resolution in resolutions.items()}
   profile=_profile(nodes,root,replacements,{})
   signature=_jhash(profile);kinds=Counter(row['kind'] for row in replacements.values())
   fully_literal=bool(replacements) and set(kinds)<= {'retailMaterialConstant'}
   has_code=kinds.get('t6CodeConstantDynamic',0)>0;has_unresolved=kinds.get('unresolvedCbuffer',0)>0
   fully_literal_material_variants+=int(fully_literal);dynamic_code_variants+=int(has_code);unresolved_variants+=int(has_unresolved);variant_count+=1
   variant={'material':owner['material'],'techniqueSet':owner['techniqueSet'],'profileSha256':signature,'replacementKindCounts':dict(sorted(kinds.items())),'fullyMaterialLiteralCbufferState':fully_literal,'hasDynamicCodeConstant':has_code,'hasUnresolvedCbuffer':has_unresolved,'profile':profile};variants.append(variant)
   group=groups.get(signature)
   if group is None:groups[signature]={'profileSha256':signature,'count':1,'profile':profile,'representative':{'sha256':sha,'material':owner['material'],'lane':term.get('lane'),'node':root},'materials':[owner['material']]}
   else:
    group['count']+=1
    if owner['material'] not in group['materials']:group['materials'].append(owner['material'])
  distinct=len({row['profileSha256'] for row in variants});term_variation+=int(distinct>1)
  rows.append({'sha256':sha,'lane':term.get('lane'),'node':root,'materialOwnerCount':len(variants),'distinctSpecializedProfileCount':distinct,'variesAcrossMaterialOwners':distinct>1,'variants':variants})
 profile_groups=sorted(groups.values(),key=lambda x:(-int(x['count']),x['profileSha256']))
 for group in profile_groups:group['materials']=sorted(group['materials'])
 summary={'termCount':len(rows),'materialVariantCount':variant_count,'termWithMaterialSpecializationVariationCount':term_variation,'uniqueSpecializedProfileCount':len(profile_groups),'fullyMaterialLiteralCbufferVariantCount':fully_literal_material_variants,'variantWithDynamicCodeConstantCount':dynamic_code_variants,'variantWithUnresolvedCbufferCount':unresolved_variants}
 return {'format':FORMAT,'sourceFinalOutputFormat':FINAL_FORMAT,'sourceResolutionFormat':RESOLUTION_FORMAT,'terms':rows,'specializedProfileGroups':profile_groups,'summary':summary,'rowsSha256':_jhash(rows),'profileGroupsSha256':_jhash(profile_groups),'proofBoundary':'Exact source-specialized expression serialization of unknown final-RGB term subtrees per material owner. Only source-closed material cbuffer values are substituted as exact float32 bits and code constants as exact dynamic T6 identities. Arithmetic/resource/input topology is preserved verbatim and never evaluated or algebraically normalized.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer-resolution',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.cbuffer_resolution.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
