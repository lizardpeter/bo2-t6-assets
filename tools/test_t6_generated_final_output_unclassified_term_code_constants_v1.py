#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_unclassified_term_code_constants_v1 as overlay

SHA='a'*64
T0='lit_sm_a';T1='lit_sm_b'

def docs():
 census={'format':overlay.CENSUS_FORMAT,'terms':[
  {'sha256':SHA,'lane':'x','node':10,'cbufferEnrichedStructuralProfileSha256V3':'1'*64,'cbufferDependenciesV1':[
   {'symbol':'cb2[3].y','techniqueAssignments':[{'techniqueSet':T0,'sourceClass':'code','sourceExpression':'code.sunDiffuse','sourceName':'sunDiffuse'},{'techniqueSet':T1,'sourceClass':'code','sourceExpression':'code.sunDiffuse','sourceName':'sunDiffuse'}]},
   {'symbol':'cb1[59].x','techniqueAssignments':[{'techniqueSet':T0,'sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1'}]},
  ]},
  {'sha256':SHA,'lane':'y','node':11,'cbufferEnrichedStructuralProfileSha256V3':'2'*64,'cbufferDependenciesV1':[{'symbol':'cb2[4].x','techniqueAssignments':[{'techniqueSet':T0,'sourceClass':'code','sourceExpression':'code.filterTap[2]','sourceName':'filterTap[2]'}]}]},
 ],'summary':{}}
 def row(symbol,tech,source,accessor,array_index,value,freq):
  return {'symbol':symbol,'nodeIds':[1],'buffer':{'name':'PerCode'},'variable':{'name':'v'},'techniqueSet':tech,'sourceExpression':'code.'+source,'sourceName':source,'accessor':accessor,'arrayIndex':array_index,'arrayCount':4 if array_index is not None else 0,'baseEnumSymbol':'BASE','baseEnumValue':value-(array_index or 0),'baseEnumValueHex':hex(value-(array_index or 0)),'resolvedEnumValue':value,'resolvedEnumValueHex':hex(value),'resolvedEnumAliases':['ENUM'],'updateFrequency':freq,'techFlags':None,'transposedMatrixEnumSymbol':None,'transposedMatrixEnumValue':None,'runtimeValueResolved':False}
 identity={'format':overlay.IDENTITY_FORMAT,'shaders':[{'sha256':SHA,'assignments':[row('cb2[3].y',T0,'sunDiffuse','sunDiffuse',None,0x23,'CUSTOM'),row('cb2[3].y',T1,'sunDiffuse','sunDiffuse',None,0x23,'CUSTOM'),row('cb2[4].x',T0,'filterTap[2]','filterTap',2,0x32,'RARELY')]}],'summary':{}}
 return census,identity

def main()->int:
 census,identity=docs();doc=overlay.build(census,identity)
 assert doc['format']==overlay.FORMAT
 by={row['lane']:row for row in doc['terms']}
 x=by['x'];assert x['hasCodeConstantDependency'] is True and x['codeConstantDependencyCount']==1
 dep=x['codeConstantIdentitiesV1'][0];assert dep['symbol']=='cb2[3].y' and dep['techniqueAssignmentCount']==2
 assert {r['techniqueSet'] for r in dep['assignments']}=={T0,T1}
 assert {r['resolvedEnumValue'] for r in dep['assignments']}=={0x23}
 # material dependency was not misclassified as code.
 assert all(d['symbol']!='cb1[59].x' for d in x['codeConstantIdentitiesV1'])
 y=by['y']['codeConstantIdentitiesV1'][0]['assignments'][0];assert y['accessor']=='filterTap' and y['arrayIndex']==2 and y['resolvedEnumValue']==0x32
 assert doc['summary']['termWithCodeConstantDependencyCount']==2
 assert doc['summary']['codeConstantAssignmentOccurrenceCount']==3
 assert doc['summary']['arrayCodeConstantAssignmentOccurrenceCount']==1
 assert doc['summary']['uniqueCodeConstantAccessorCount']==2
 assert doc['summary']['updateFrequencyAssignmentCounts']=={'CUSTOM':2,'RARELY':1}

 bad=copy.deepcopy(identity);bad['shaders'][0]['assignments']=[r for r in bad['shaders'][0]['assignments'] if not (r['symbol']=='cb2[3].y' and r['techniqueSet']==T1)]
 try:overlay.build(census,bad)
 except overlay.UnclassifiedTermCodeConstantError as exc:assert 'absent from exact identity sidecar' in str(exc)
 else:raise AssertionError('missing code identity for one owning TechniqueSet was accepted')

 bad_runtime=copy.deepcopy(identity);bad_runtime['shaders'][0]['assignments'][0]['runtimeValueResolved']=True
 try:overlay.build(census,bad_runtime)
 except overlay.UnclassifiedTermCodeConstantError as exc:assert 'unexpectedly claims runtime value resolution' in str(exc)
 else:raise AssertionError('identity-only sidecar falsely claiming runtime values was accepted')
 print('PASS: exact code-constant overlay for unclassified final RGB terms');return 0
if __name__=='__main__':raise SystemExit(main())
