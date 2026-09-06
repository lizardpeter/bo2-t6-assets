#!/usr/bin/env python3
"""Overlay exact per-material cbuffer values onto still-unclassified o0.rgb terms.

Consumes:
- cbuffer-enriched unknown-term census v3;
- exact per-material final-output cbuffer values v2.

For every cbuffer dependency in each unknown shader-level term, this records the
value/source state for every exact material owner of that pixel shader. Material
sources carry exact float32 scalar bits/value and the serialized MaterialConstantDef
identity. code.*, unassigned and other sources remain explicit unresolved rows.

This is an evidence overlay only. Numeric variation does not assign physical
meaning to a variable or promote a final-lighting equation.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,struct
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-unclassified-term-material-values-v1'
CENSUS_FORMAT='t6-generated-final-output-unclassified-term-census-v3'
VALUES_FORMAT='t6-generated-final-output-material-cbuffer-values-v2'
class UnclassifiedTermMaterialValueError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _f32bits(v:float)->str:return struct.pack('<f',float(v)).hex()

def _material_rows(doc:dict)->dict[str,list[dict]]:
 out=defaultdict(list);seen=set()
 for row in doc.get('materials',[]):
  material=str(row.get('material') or '');sha=str(row.get('pixelShaderSha256') or '')
  if not material or not sha or material in seen:raise UnclassifiedTermMaterialValueError(f'invalid/duplicate material row {material!r}')
  seen.add(material);out[sha].append(row)
 for sha in out:out[sha].sort(key=lambda r:str(r['material']))
 return dict(out)

def _symbol_owner_state(row:dict,symbol:str)->dict:
 resolved=[x for x in row.get('resolvedMaterialBindings',[]) if str(x.get('symbol') or '')==symbol]
 unresolved=[x for x in row.get('unresolvedNonMaterialBindings',[]) if str(x.get('symbol') or '')==symbol]
 if len(resolved)+len(unresolved)!=1:
  raise UnclassifiedTermMaterialValueError(f"{row.get('material')!r} symbol {symbol!r}: owner-state count {len(resolved)+len(unresolved)}, expected 1")
 if resolved:
  item=resolved[0];mc=item.get('materialConstant') or {};literal=[float(x) for x in mc.get('literal',[])]
  if len(literal)!=4:raise UnclassifiedTermMaterialValueError(f"{row.get('material')!r} {symbol}: resolved literal is not float4")
  scalar=float(mc['scalarValue']);component=int(mc['literalComponentIndex'])
  if not 0<=component<4 or scalar!=literal[component]:raise UnclassifiedTermMaterialValueError(f"{row.get('material')!r} {symbol}: scalar/literal component mismatch")
  return {'material':row['material'],'materialArchiveSha256':row.get('materialArchiveSha256'),'sourceClass':'material','sourceExpression':item.get('sourceExpression'),'sourceName':item.get('sourceName'),'resolved':True,'scalarValue':scalar,'scalarValueFloat32Bits':_f32bits(scalar),'literal':literal,'literalFloat32Bits':[_f32bits(x) for x in literal],'literalComponentIndex':component,'constantSerializedSha256':mc.get('serializedSha256'),'constantNameHash':mc.get('nameHash'),'constantNameFragment':mc.get('nameFragment')}
 item=unresolved[0]
 return {'material':row['material'],'materialArchiveSha256':row.get('materialArchiveSha256'),'sourceClass':item.get('sourceClass'),'sourceExpression':item.get('sourceExpression'),'sourceName':item.get('sourceName'),'resolved':False}

def build(census_doc:dict,values_doc:dict)->dict:
 if census_doc.get('format')!=CENSUS_FORMAT:raise UnclassifiedTermMaterialValueError(f"unexpected census format {census_doc.get('format')!r}")
 if values_doc.get('format')!=VALUES_FORMAT:raise UnclassifiedTermMaterialValueError(f"unexpected values format {values_doc.get('format')!r}")
 owners=_material_rows(values_doc)
 terms=copy.deepcopy(census_doc.get('terms',[]));rows=[];source_counts=Counter();varying_deps=0;uniform_material_deps=0;terms_with_values=0;terms_with_variation=0
 pattern_groups={}
 for term in terms:
  sha=str(term.get('sha256') or '');shader_owners=owners.get(sha,[])
  if not shader_owners:raise UnclassifiedTermMaterialValueError(f"unknown term shader {sha!r} has no material owners in value sidecar")
  dep_rows=[];term_has_values=False;term_varies=False
  for dep in term.get('cbufferDependenciesV1',[]):
   symbol=str(dep.get('symbol') or '');states=[_symbol_owner_state(owner,symbol) for owner in shader_owners]
   classes=sorted({str(x.get('sourceClass') or '') for x in states});resolved=[x for x in states if x['resolved']];bits=sorted({x['scalarValueFloat32Bits'] for x in resolved})
   for state in states:source_counts[str(state.get('sourceClass') or '')]+=1
   varies=len(resolved)>1 and len(bits)>1
   if varies:varying_deps+=1;term_varies=True
   if resolved and len(bits)==1:uniform_material_deps+=1
   term_has_values|=bool(resolved)
   dep_rows.append({'symbol':symbol,'materialOwnerCount':len(states),'sourceClasses':classes,'resolvedMaterialOwnerCount':len(resolved),'unresolvedMaterialOwnerCount':len(states)-len(resolved),'distinctResolvedScalarValueCount':len(bits),'distinctResolvedScalarFloat32Bits':bits,'variesAcrossMaterialOwners':varies,'owners':states})
  term['materialValueDependenciesV1']=dep_rows;term['hasResolvedMaterialValue']=term_has_values;term['hasMaterialValueVariation']=term_varies
  terms_with_values+=int(term_has_values);terms_with_variation+=int(term_varies)
  profile={'baseCbufferEnrichedStructuralProfileSha256':term.get('cbufferEnrichedStructuralProfileSha256V3'),'materialDependencies':[{'sourceClasses':d['sourceClasses'],'resolvedMaterialOwnerCount':d['resolvedMaterialOwnerCount'],'unresolvedMaterialOwnerCount':d['unresolvedMaterialOwnerCount'],'distinctResolvedScalarFloat32Bits':d['distinctResolvedScalarFloat32Bits'],'variesAcrossMaterialOwners':d['variesAcrossMaterialOwners']} for d in dep_rows]}
  sig=_jhash(profile);term['materialValuePatternSha256']=sig
  group=pattern_groups.get(sig)
  if group is None:pattern_groups[sig]={'materialValuePatternSha256':sig,'count':1,'profile':profile,'representative':{'sha256':sha,'lane':term.get('lane'),'node':term.get('node')},'observedLanes':[term.get('lane')]}
  else:
   group['count']+=1
   if term.get('lane') not in group['observedLanes']:group['observedLanes'].append(term.get('lane'))
 groups=sorted(pattern_groups.values(),key=lambda x:(-int(x['count']),x['materialValuePatternSha256']))
 for group in groups:group['observedLanes']=sorted(str(x) for x in group['observedLanes'] if x is not None)
 summary={'termCount':len(terms),'termWithResolvedMaterialValueCount':terms_with_values,'termWithMaterialValueVariationCount':terms_with_variation,'varyingMaterialDependencyCount':varying_deps,'uniformResolvedMaterialDependencyCount':uniform_material_deps,'materialValuePatternCount':len(groups),'sourceClassOwnerOccurrenceCounts':dict(sorted(source_counts.items())),'materialOwnerCount':sum(len(v) for v in owners.values()),'shaderCount':len(owners)}
 return {'format':FORMAT,'sourceCensusFormat':CENSUS_FORMAT,'sourceValuesFormat':VALUES_FORMAT,'terms':terms,'materialValuePatternGroups':groups,'summary':summary,'rowsSha256':_jhash(terms),'patternGroupsSha256':_jhash(groups),'proofBoundary':'Exact per-material owner overlay for cbuffer dependencies already present in the unclassified-term DAG census. material.* rows carry serialized MaterialConstantDef-backed float32 bits/value; non-material sources remain unresolved. Value patterns are evidence only and assign no physical semantics.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--census-v3',type=Path,required=True);p.add_argument('--material-values',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.census_v3.read_text()),json.loads(a.material_values.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
