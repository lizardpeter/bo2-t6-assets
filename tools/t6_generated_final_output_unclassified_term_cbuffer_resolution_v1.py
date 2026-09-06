#!/usr/bin/env python3
"""Classify source/value completeness of cbuffer dependencies in unknown o0.rgb terms.

Consumes the cbuffer-enriched unknown census plus, when available:
- exact per-material cbuffer values v2;
- exact pinned T6 code-constant identities v1.

Resolution is performed per shader/symbol/TechniqueSet assignment from the v39
census evidence:
- material.* -> exact generated-material MaterialConstantDef-backed values for
  every owner using that TechniqueSet;
- code.* -> exact T6 MaterialConstantSource enum/index/update-frequency identity,
  with runtime value deliberately marked dynamic/unresolved;
- other/unassigned -> unresolved.

This produces a precise replay boundary. It does not infer runtime code values or
physical semantics from names.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-unclassified-term-cbuffer-resolution-v1'
CENSUS_FORMAT='t6-generated-final-output-unclassified-term-census-v3'
VALUES_FORMAT='t6-generated-final-output-material-cbuffer-values-v2'
CODE_FORMAT='t6-generated-final-output-code-constant-identity-v1'
class CbufferResolutionError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _material_index(doc:dict|None):
 out=defaultdict(list)
 if doc is None:return out
 if doc.get('format')!=VALUES_FORMAT:raise CbufferResolutionError(f"unexpected material-values format {doc.get('format')!r}")
 for row in doc.get('materials',[]):
  sha=str(row.get('pixelShaderSha256') or '');tech=str(row.get('techniqueSet') or '');material=str(row.get('material') or '')
  if not sha or not tech or not material:raise CbufferResolutionError('material-values row lacks shader/TechniqueSet/material identity')
  out[(sha,tech)].append(row)
 for key in out:out[key].sort(key=lambda r:str(r['material']))
 return out

def _code_index(doc:dict|None):
 out={}
 if doc is None:return out
 if doc.get('format')!=CODE_FORMAT:raise CbufferResolutionError(f"unexpected code-identity format {doc.get('format')!r}")
 for shader in doc.get('shaders',[]):
  sha=str(shader.get('sha256') or '')
  for row in shader.get('assignments',[]):
   key=(sha,str(row.get('symbol') or ''),str(row.get('techniqueSet') or ''))
   if not all(key) or key in out:raise CbufferResolutionError(f'invalid/duplicate code identity {key!r}')
   out[key]=row
 return out

def _material_state(owner:dict,symbol:str)->dict:
 resolved=[x for x in owner.get('resolvedMaterialBindings',[]) if str(x.get('symbol') or '')==symbol]
 unresolved=[x for x in owner.get('unresolvedNonMaterialBindings',[]) if str(x.get('symbol') or '')==symbol]
 if len(resolved)!=1 or unresolved:
  raise CbufferResolutionError(f"{owner.get('material')!r} {symbol}: expected exactly one resolved material binding")
 item=resolved[0];mc=item.get('materialConstant') or {}
 return {'material':owner['material'],'materialArchiveSha256':owner.get('materialArchiveSha256'),'sourceExpression':item.get('sourceExpression'),'sourceName':item.get('sourceName'),'scalarValue':mc.get('scalarValue'),'literal':copy.deepcopy(mc.get('literal')),'literalComponentIndex':mc.get('literalComponentIndex'),'constantSerializedSha256':mc.get('serializedSha256'),'valueResolved':True}

def build(census_doc:dict,material_values_doc:dict|None=None,code_identity_doc:dict|None=None)->dict:
 if census_doc.get('format')!=CENSUS_FORMAT:raise CbufferResolutionError(f"unexpected census format {census_doc.get('format')!r}")
 materials=_material_index(material_values_doc);codes=_code_index(code_identity_doc)
 terms=copy.deepcopy(census_doc.get('terms',[]));assignment_counts=Counter();resolution_counts=Counter();terms_identity_complete=terms_value_complete=0;dependencies_identity_complete=dependencies_value_complete=0;dependency_count=0
 for term in terms:
  sha=str(term.get('sha256') or '');dep_out=[];term_identity=True;term_values=True
  for dep in term.get('cbufferDependenciesV1',[]):
   dependency_count+=1;symbol=str(dep.get('symbol') or '');assignments=[];dep_identity=True;dep_values=True
   source_rows=dep.get('techniqueAssignments',[])
   if not source_rows:dep_identity=False;dep_values=False
   for source in source_rows:
    technique=str(source.get('techniqueSet') or '');source_class=str(source.get('sourceClass') or '');expr=source.get('sourceExpression');name=source.get('sourceName');assignment_counts[source_class]+=1
    base={'techniqueSet':technique,'sourceClass':source_class,'sourceExpression':expr,'sourceName':name}
    if source_class=='material':
     owners=materials.get((sha,technique),[])
     if not owners:
      row={**base,'identityResolved':False,'runtimeValueResolved':False,'resolutionKind':'material_values_unavailable','materialOwners':[]};dep_identity=False;dep_values=False
     else:
      states=[_material_state(owner,symbol) for owner in owners]
      bits={json.dumps(state.get('scalarValue'),sort_keys=True) for state in states}
      row={**base,'identityResolved':True,'runtimeValueResolved':True,'resolutionKind':'retail_material_constant','materialOwners':states,'materialOwnerCount':len(states),'distinctScalarValueCount':len(bits)}
    elif source_class=='code':
     item=codes.get((sha,symbol,technique))
     if item is None:
      row={**base,'identityResolved':False,'runtimeValueResolved':False,'resolutionKind':'code_identity_unavailable'};dep_identity=False;dep_values=False
     else:
      row={**base,'identityResolved':True,'runtimeValueResolved':False,'resolutionKind':'t6_code_constant_dynamic','codeConstant':{key:copy.deepcopy(item.get(key)) for key in ('accessor','arrayIndex','arrayCount','baseEnumSymbol','baseEnumValue','resolvedEnumValue','resolvedEnumAliases','updateFrequency','techFlags','transposedMatrixEnumSymbol','transposedMatrixEnumValue')}};dep_values=False
    else:
     row={**base,'identityResolved':False,'runtimeValueResolved':False,'resolutionKind':'unresolved_source_class'};dep_identity=False;dep_values=False
    resolution_counts[row['resolutionKind']]+=1;assignments.append(row)
   dep_out.append({'symbol':symbol,'assignmentCount':len(assignments),'assignments':assignments,'allSourceIdentitiesResolved':dep_identity,'allRuntimeValuesResolved':dep_values})
   dependencies_identity_complete+=int(dep_identity);dependencies_value_complete+=int(dep_values);term_identity&=dep_identity;term_values&=dep_values
  term['cbufferResolutionV1']=dep_out;term['allCbufferSourceIdentitiesResolved']=term_identity;term['allCbufferRuntimeValuesResolved']=term_values
  terms_identity_complete+=int(term_identity);terms_value_complete+=int(term_values)
 summary={'termCount':len(terms),'cbufferDependencyCount':dependency_count,'termWithAllCbufferSourceIdentitiesResolvedCount':terms_identity_complete,'termWithAllCbufferRuntimeValuesResolvedCount':terms_value_complete,'dependencyWithAllSourceIdentitiesResolvedCount':dependencies_identity_complete,'dependencyWithAllRuntimeValuesResolvedCount':dependencies_value_complete,'sourceClassAssignmentCounts':dict(sorted(assignment_counts.items())),'resolutionKindAssignmentCounts':dict(sorted(resolution_counts.items())),'materialValuesInputAvailable':material_values_doc is not None,'codeIdentityInputAvailable':code_identity_doc is not None}
 return {'format':FORMAT,'sourceCensusFormat':CENSUS_FORMAT,'sourceMaterialValuesFormat':None if material_values_doc is None else VALUES_FORMAT,'sourceCodeIdentityFormat':None if code_identity_doc is None else CODE_FORMAT,'terms':terms,'summary':summary,'rowsSha256':_jhash(terms),'proofBoundary':'Per-TechniqueSet source-resolution completeness for cbuffer dependencies already proven in unknown final-RGB terms. material.* can carry exact retained MaterialConstantDef values; code.* can carry exact T6 enum/update-frequency identity while remaining runtime-dynamic; other/unavailable sources remain unresolved. No runtime code values or physical semantics are inferred.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--census-v3',type=Path,required=True);p.add_argument('--material-values',type=Path);p.add_argument('--code-identity',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.census_v3.read_text()),None if a.material_values is None else json.loads(a.material_values.read_text()),None if a.code_identity is None else json.loads(a.code_identity.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
