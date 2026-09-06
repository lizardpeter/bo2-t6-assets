#!/usr/bin/env python3
"""Resolve current-OAT final-output code constants to exact T6 identities.

Consumes cbuffer signature v2 plus the pinned T6 code-constant table.
- explicit `constant.foo` bindings are exact current OAT evidence;
- legacy `code.foo` remains accepted as compatibility evidence;
- an omitted assignment is auto-resolved only when the RDEF variable name
  exactly matches a scalar T6 code-constant accessor. This is the same-name
  auto-create rule implemented by OAT's CommonShaderArgCreator.

Implicit array bindings remain unresolved here because the current RDEF archive
does not retain enough type-element metadata to prove the exact element index.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any
import t6_generated_final_output_code_constant_identity_v1 as old
FORMAT='t6-generated-final-output-code-constant-identity-v2'
CBUFFER_FORMAT='t6-generated-final-output-cbuffer-signature-v2'
TABLE_FORMAT=old.TABLE_FORMAT
class FinalOutputCodeConstantIdentityV2Error(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _table(table:dict)->dict:
 out={}
 for row in table.get('rows',[]):
  name=str(row.get('accessor') or '')
  if not name or name in out:raise FinalOutputCodeConstantIdentityV2Error(f'invalid/duplicate code-constant accessor {name!r}')
  out[name]=row
 return out

def build(cbuffer_doc:dict,table_doc:dict)->dict:
 if cbuffer_doc.get('format')!=CBUFFER_FORMAT:raise FinalOutputCodeConstantIdentityV2Error(f"unexpected cbuffer format {cbuffer_doc.get('format')!r}")
 if table_doc.get('format')!=TABLE_FORMAT:raise FinalOutputCodeConstantIdentityV2Error(f"unexpected code-constant table format {table_doc.get('format')!r}")
 by=_table(table_doc);rows=[];explicit=implicit=0;unresolved_implicit_array=0;freq=Counter();access=Counter();enum_values=set()
 for shader in cbuffer_doc.get('shaders',[]):
  sha=str(shader.get('sha256') or '');assignments=[]
  if not sha:raise FinalOutputCodeConstantIdentityV2Error('cbuffer shader row lacks SHA')
  for item in shader.get('usedCbufferSymbols',[]):
   symbol=str(item.get('symbol') or '');variable=str((item.get('variable') or {}).get('name') or '')
   for assignment in item.get('techniqueAssignments',[]):
    cls=str(assignment.get('sourceClass') or '');kind=str(assignment.get('sourceKind') or '');ns=assignment.get('sourceNamespace');technique=str(assignment.get('techniqueSet') or '')
    identity=None;mode=None;source_name=None;source_expr=assignment.get('sourceExpression')
    if cls=='code' and kind in ('constant','legacy_code'):
     source_name=str(assignment.get('sourceName') or '')
     expected_prefix='constant' if kind=='constant' else 'code'
     if source_expr!=f'{expected_prefix}.{source_name}':raise FinalOutputCodeConstantIdentityV2Error(f"shader {sha} {symbol}: expression {source_expr!r} disagrees with namespace/name")
     try:identity=old.resolve_source_name(source_name,table_doc)
     except Exception as e:raise FinalOutputCodeConstantIdentityV2Error(str(e)) from e
     mode='explicitTechAssignment';explicit+=1
    elif cls=='unassigned' and variable in by:
     table_row=by[variable]
     if int(table_row.get('arrayCount',0))>0:
      unresolved_implicit_array+=1;continue
     source_name=variable
     try:identity=old.resolve_source_name(source_name,table_doc)
     except Exception as e:raise FinalOutputCodeConstantIdentityV2Error(str(e)) from e
     mode='implicitSameAccessorAutoCreate';implicit+=1;ns='constant'
    else:continue
    row={'symbol':symbol,'nodeIds':sorted(int(x) for x in item.get('nodeIds',[])),'buffer':copy.deepcopy(item.get('buffer')),'variable':copy.deepcopy(item.get('variable')),'techniqueSet':technique,'bindingMode':mode,'sourceNamespace':ns,'sourceExpression':source_expr,'sourceName':source_name,**identity,'runtimeValueResolved':False};assignments.append(row);freq[str(identity['updateFrequency'])]+=1;access[str(identity['accessor'])]+=1;enum_values.add(int(identity['resolvedEnumValue']))
  rows.append({'sha256':sha,'techniqueSets':sorted(str(x) for x in shader.get('techniqueSets',[])),'codeConstantAssignmentCount':len(assignments),'assignments':sorted(assignments,key=lambda r:(r['techniqueSet'],r['symbol'],r['sourceName']))})
 rows.sort(key=lambda r:r['sha256']);summary={'shaderCount':len(rows),'codeConstantAssignmentCount':explicit+implicit,'explicitCodeConstantAssignmentCount':explicit,'implicitSameAccessorCodeConstantAssignmentCount':implicit,'unresolvedImplicitArrayConstantOccurrenceCount':unresolved_implicit_array,'uniqueAccessorCount':len(access),'uniqueResolvedEnumValueCount':len(enum_values),'updateFrequencyAssignmentCounts':dict(sorted(freq.items())),'accessorAssignmentCounts':dict(sorted(access.items())),'rowsSha256':_jhash(rows)}
 return {'format':FORMAT,'sourceCbufferFormat':CBUFFER_FORMAT,'sourceCodeConstantTableFormat':TABLE_FORMAT,'codeConstantTableSource':copy.deepcopy(table_doc.get('source')),'shaders':rows,'summary':summary,'rowsSha256':summary['rowsSha256'],'implicitBindingProof':{'oatRule':'CommonShaderArgCreator AutoCreateMissingArgs resolves a missing DX11 constant by exact RDEF variable accessor through GetCodeConstSourceForAccessor; nonmatching nonignored variables fail','arrayPolicy':'explicit array bindings resolve; implicit array-valued bindings remain unresolved until RDEF type-element metadata is archived'},'proofBoundary':'Exact current-OAT constant.* (or legacy code.*) binding plus source-closed same-accessor scalar auto-create identity joined to pinned T6 MaterialConstantSource metadata. Runtime values and physical semantics remain unresolved; implicit arrays are not guessed.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--cbuffer-signature',type=Path,required=True);p.add_argument('--code-constant-table',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.cbuffer_signature.read_text()),json.loads(a.code_constant_table.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
