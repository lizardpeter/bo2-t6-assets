#!/usr/bin/env python3
"""Overlay exact T6 code-constant identities onto unclassified final-RGB terms.

Consumes:
- cbuffer-enriched unknown-term census v3;
- final-output code-constant identity v1.

For each unknown-term cbuffer dependency whose `.tech` source class is `code`,
this joins every owning TechniqueSet to the exact pinned T6 accessor/base enum,
numeric MaterialConstantSource value (including array element offset), update
frequency, optional tech flags and matrix-pair metadata.

The existing cbuffer dependency rows remain unchanged. Runtime values stay
unresolved; accessor/enum names are identities only and are not physical labels.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-unclassified-term-code-constants-v1'
CENSUS_FORMAT='t6-generated-final-output-unclassified-term-census-v3'
IDENTITY_FORMAT='t6-generated-final-output-code-constant-identity-v1'
class UnclassifiedTermCodeConstantError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _identity_by_shader(doc:dict)->dict[str,dict[tuple[str,str],dict]]:
 out={}
 for shader in doc.get('shaders',[]):
  sha=str(shader.get('sha256') or '')
  if not sha or sha in out:raise UnclassifiedTermCodeConstantError(f'invalid/duplicate identity shader {sha!r}')
  rows={}
  for item in shader.get('assignments',[]):
   key=(str(item.get('symbol') or ''),str(item.get('techniqueSet') or ''))
   if not all(key) or key in rows:raise UnclassifiedTermCodeConstantError(f'shader {sha}: invalid/duplicate code identity key {key!r}')
   rows[key]=item
  out[sha]=rows
 return out

def _code_techniques(dep:dict)->list[str]:
 return sorted({str(row.get('techniqueSet') or '') for row in dep.get('techniqueAssignments',[]) if str(row.get('sourceClass') or '')=='code' and str(row.get('techniqueSet') or '')})

def build(census_doc:dict,identity_doc:dict)->dict:
 if census_doc.get('format')!=CENSUS_FORMAT:raise UnclassifiedTermCodeConstantError(f"unexpected census format {census_doc.get('format')!r}")
 if identity_doc.get('format')!=IDENTITY_FORMAT:raise UnclassifiedTermCodeConstantError(f"unexpected identity format {identity_doc.get('format')!r}")
 identities=_identity_by_shader(identity_doc);terms=copy.deepcopy(census_doc.get('terms',[]));source_occurrences=0;terms_with_code=0;array_occurrences=0;frequency=Counter();accessors=Counter();enum_values=set();patterns={}
 for term in terms:
  sha=str(term.get('sha256') or '');shader_identities=identities.get(sha)
  if shader_identities is None:raise UnclassifiedTermCodeConstantError(f'unknown term shader {sha!r} absent from code identity sidecar')
  overlays=[]
  for dep in term.get('cbufferDependenciesV1',[]):
   symbol=str(dep.get('symbol') or '');techniques=_code_techniques(dep)
   if not techniques:continue
   rows=[]
   for technique in techniques:
    item=shader_identities.get((symbol,technique))
    if item is None:raise UnclassifiedTermCodeConstantError(f'shader {sha} {symbol} TechniqueSet {technique!r}: code assignment absent from exact identity sidecar')
    row={key:copy.deepcopy(item.get(key)) for key in ('symbol','nodeIds','buffer','variable','techniqueSet','sourceExpression','sourceName','accessor','arrayIndex','arrayCount','baseEnumSymbol','baseEnumValue','baseEnumValueHex','resolvedEnumValue','resolvedEnumValueHex','resolvedEnumAliases','updateFrequency','techFlags','transposedMatrixEnumSymbol','transposedMatrixEnumValue','runtimeValueResolved')}
    if row['runtimeValueResolved'] is not False:raise UnclassifiedTermCodeConstantError(f'shader {sha} {symbol}: v1 identity unexpectedly claims runtime value resolution')
    rows.append(row);source_occurrences+=1;array_occurrences+=int(row['arrayIndex'] is not None);frequency[str(row['updateFrequency'])]+=1;accessors[str(row['accessor'])]+=1;enum_values.add(int(row['resolvedEnumValue']))
   overlays.append({'symbol':symbol,'techniqueAssignmentCount':len(rows),'assignments':rows})
  term['codeConstantIdentitiesV1']=overlays;term['codeConstantDependencyCount']=len(overlays);term['hasCodeConstantDependency']=bool(overlays);terms_with_code+=int(bool(overlays))
  profile={'baseCbufferEnrichedStructuralProfileSha256':term.get('cbufferEnrichedStructuralProfileSha256V3'),'codeConstants':[
   {'symbol':row['symbol'],'assignments':[{'accessor':x['accessor'],'arrayIndex':x['arrayIndex'],'resolvedEnumValue':x['resolvedEnumValue'],'updateFrequency':x['updateFrequency'],'techFlags':x['techFlags'],'transposedMatrixEnumValue':x['transposedMatrixEnumValue']} for x in row['assignments']]} for row in overlays]}
  sig=_jhash(profile);term['codeConstantPatternSha256']=sig
  group=patterns.get(sig)
  if group is None:patterns[sig]={'codeConstantPatternSha256':sig,'count':1,'profile':profile,'representative':{'sha256':sha,'lane':term.get('lane'),'node':term.get('node')},'observedLanes':[term.get('lane')]}
  else:
   group['count']+=1
   if term.get('lane') not in group['observedLanes']:group['observedLanes'].append(term.get('lane'))
 groups=sorted(patterns.values(),key=lambda x:(-int(x['count']),x['codeConstantPatternSha256']))
 for group in groups:group['observedLanes']=sorted(str(x) for x in group['observedLanes'] if x is not None)
 summary={'termCount':len(terms),'termWithCodeConstantDependencyCount':terms_with_code,'codeConstantAssignmentOccurrenceCount':source_occurrences,'arrayCodeConstantAssignmentOccurrenceCount':array_occurrences,'uniqueCodeConstantAccessorCount':len(accessors),'uniqueResolvedCodeEnumValueCount':len(enum_values),'updateFrequencyAssignmentCounts':dict(sorted(frequency.items())),'accessorAssignmentCounts':dict(sorted(accessors.items())),'codeConstantPatternCount':len(groups)}
 return {'format':FORMAT,'sourceCensusFormat':CENSUS_FORMAT,'sourceIdentityFormat':IDENTITY_FORMAT,'terms':terms,'codeConstantPatternGroups':groups,'summary':summary,'rowsSha256':_jhash(terms),'patternGroupsSha256':_jhash(groups),'proofBoundary':'Exact code.* identity overlay on cbuffer dependencies already present in the unclassified-term census. Numeric MaterialConstantSource enum identity/array offset/update frequency/flags are retained from the pinned T6 table. Runtime values and physical semantics remain unresolved.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--census-v3',type=Path,required=True);p.add_argument('--code-constant-identity',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.census_v3.read_text()),json.loads(a.code_constant_identity.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
