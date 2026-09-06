#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_unclassified_term_cbuffer_resolution_v1 as resolution

SHA='a'*64;TECH='lit_sm_fixture';MAT='*m'

def docs():
 census={'format':resolution.CENSUS_FORMAT,'terms':[
  {'sha256':SHA,'lane':'x','node':1,'cbufferDependenciesV1':[
   {'symbol':'cb1[59].x','techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1'}]},
   {'symbol':'cb2[3].y','techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'code','sourceExpression':'code.sunDiffuse','sourceName':'sunDiffuse'}]},
  ]},
  {'sha256':SHA,'lane':'y','node':2,'cbufferDependenciesV1':[{'symbol':'cb3[1].z','techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'other','sourceExpression':'literal.foo','sourceName':'foo'}]}]},
 ],'summary':{}}
 values={'format':resolution.VALUES_FORMAT,'materials':[{'material':MAT,'techniqueSet':TECH,'pixelShaderSha256':SHA,'materialArchiveSha256':'b'*64,'resolvedMaterialBindings':[{'symbol':'cb1[59].x','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1','materialConstant':{'scalarValue':0.25,'literal':[0.25,2,3,4],'literalComponentIndex':0,'serializedSha256':'c'*64}}],'unresolvedNonMaterialBindings':[{'symbol':'cb2[3].y','sourceClass':'code'}]}]}
 code={'format':resolution.CODE_FORMAT,'shaders':[{'sha256':SHA,'assignments':[{'symbol':'cb2[3].y','techniqueSet':TECH,'accessor':'sunDiffuse','arrayIndex':None,'arrayCount':0,'baseEnumSymbol':'CONST_SRC_CODE_SUN_DIFFUSE','baseEnumValue':0x23,'resolvedEnumValue':0x23,'resolvedEnumAliases':['CONST_SRC_CODE_SUN_DIFFUSE'],'updateFrequency':'CUSTOM','techFlags':None,'transposedMatrixEnumSymbol':None,'transposedMatrixEnumValue':None}]}]}
 return census,values,code

def main()->int:
 census,values,code=docs();doc=resolution.build(census,values,code)
 assert doc['format']==resolution.FORMAT
 by={row['lane']:row for row in doc['terms']}
 x=by['x'];assert x['allCbufferSourceIdentitiesResolved'] is True and x['allCbufferRuntimeValuesResolved'] is False
 material=x['cbufferResolutionV1'][0]['assignments'][0];assert material['resolutionKind']=='retail_material_constant' and material['identityResolved'] is True and material['runtimeValueResolved'] is True and material['materialOwners'][0]['scalarValue']==0.25
 code_row=x['cbufferResolutionV1'][1]['assignments'][0];assert code_row['resolutionKind']=='t6_code_constant_dynamic' and code_row['identityResolved'] is True and code_row['runtimeValueResolved'] is False and code_row['codeConstant']['resolvedEnumValue']==0x23
 y=by['y'];assert y['allCbufferSourceIdentitiesResolved'] is False and y['cbufferResolutionV1'][0]['assignments'][0]['resolutionKind']=='unresolved_source_class'
 s=doc['summary'];assert s['termCount']==2 and s['cbufferDependencyCount']==3
 assert s['termWithAllCbufferSourceIdentitiesResolvedCount']==1
 assert s['termWithAllCbufferRuntimeValuesResolvedCount']==0
 assert s['dependencyWithAllSourceIdentitiesResolvedCount']==2
 assert s['dependencyWithAllRuntimeValuesResolvedCount']==1
 assert s['resolutionKindAssignmentCounts']=={'retail_material_constant':1,'t6_code_constant_dynamic':1,'unresolved_source_class':1}

 # Missing optional proof inputs degrade explicitly instead of borrowing identity.
 no_code=resolution.build(census,values,None);nx={r['lane']:r for r in no_code['terms']}['x'];assert nx['cbufferResolutionV1'][1]['assignments'][0]['resolutionKind']=='code_identity_unavailable';assert nx['allCbufferSourceIdentitiesResolved'] is False
 no_values=resolution.build(census,None,code);nx2={r['lane']:r for r in no_values['terms']}['x'];assert nx2['cbufferResolutionV1'][0]['assignments'][0]['resolutionKind']=='material_values_unavailable'

 # Exact material source rows cannot silently lack the requested symbol.
 bad=copy.deepcopy(values);bad['materials'][0]['resolvedMaterialBindings']=[]
 try:resolution.build(census,bad,code)
 except resolution.CbufferResolutionError as exc:assert 'expected exactly one resolved material binding' in str(exc)
 else:raise AssertionError('missing exact material binding was accepted')
 print('PASS: unknown final RGB cbuffer source-resolution completeness v1');return 0
if __name__=='__main__':raise SystemExit(main())
