#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_code_constant_identity_v1 as identity

SHA='a'*64
TECH='lit_sm_fixture'

def docs():
 table={'format':identity.TABLE_FORMAT,'source':{'openAssetToolsCommit':'pinned'},'rows':[
  {'accessor':'sunDiffuse','enumSymbol':'CONST_SRC_CODE_SUN_DIFFUSE','enumValue':0x23,'enumValueHex':'0x23','enumAliases':['CONST_SRC_CODE_SUN_DIFFUSE'],'arrayCount':0,'updateFrequency':'CUSTOM','techFlags':None,'transposedMatrixEnumSymbol':None,'transposedMatrixEnumValue':None},
  {'accessor':'filterTap','enumSymbol':'CONST_SRC_CODE_FILTER_TAP_0','enumValue':0x30,'enumValueHex':'0x30','enumAliases':['CONST_SRC_CODE_FILTER_TAP_0'],'arrayCount':4,'updateFrequency':'RARELY','techFlags':'FLAG_X','transposedMatrixEnumSymbol':None,'transposedMatrixEnumValue':None},
  {'accessor':'worldMatrix','enumSymbol':'CONST_SRC_CODE_WORLD_MATRIX','enumValue':0xD3,'enumValueHex':'0xd3','enumAliases':['CONST_SRC_CODE_WORLD_MATRIX'],'arrayCount':0,'updateFrequency':'PER_PRIM','techFlags':None,'transposedMatrixEnumSymbol':'CONST_SRC_CODE_TRANSPOSE_WORLD_MATRIX','transposedMatrixEnumValue':0xD5},
 ],'enumAliasesByValue':{'35':['CONST_SRC_CODE_SUN_DIFFUSE'],'48':['CONST_SRC_CODE_FILTER_TAP_0'],'49':['CONST_SRC_CODE_FILTER_TAP_1'],'50':['CONST_SRC_CODE_FILTER_TAP_2'],'51':['CONST_SRC_CODE_FILTER_TAP_3'],'211':['CONST_SRC_CODE_WORLD_MATRIX']},'summary':{}}
 cbuffer={'format':identity.CBUFFER_FORMAT,'shaders':[{'sha256':SHA,'techniqueSets':[TECH],'usedCbufferSymbols':[
  {'symbol':'cb2[1].x','nodeIds':[4],'buffer':{'name':'PerCode'},'variable':{'name':'sunDiffuse'},'techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'code','sourceExpression':'code.sunDiffuse','sourceName':'sunDiffuse'}]},
  {'symbol':'cb2[2].y','nodeIds':[5],'buffer':{'name':'PerCode'},'variable':{'name':'filter'},'techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'code','sourceExpression':'code.filterTap[2]','sourceName':'filterTap[2]'}]},
  {'symbol':'cb1[59].x','nodeIds':[6],'buffer':{'name':'PerMaterial'},'variable':{'name':'alphaRevealParms1'},'techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1'}]},
 ]}]}
 return cbuffer,table

def main()->int:
 cbuffer,table=docs();doc=identity.build(cbuffer,table)
 assert doc['format']==identity.FORMAT
 assert doc['summary']['shaderCount']==1
 assert doc['summary']['codeConstantAssignmentCount']==2
 assert doc['summary']['arrayCodeConstantAssignmentCount']==1
 assert doc['summary']['uniqueAccessorCount']==2
 assert doc['summary']['uniqueResolvedEnumValueCount']==2
 assert doc['summary']['updateFrequencyAssignmentCounts']=={'CUSTOM':1,'RARELY':1}
 rows={row['sourceName']:row for row in doc['shaders'][0]['assignments']}
 sun=rows['sunDiffuse'];assert sun['baseEnumSymbol']=='CONST_SRC_CODE_SUN_DIFFUSE' and sun['resolvedEnumValue']==0x23 and sun['arrayIndex'] is None and sun['runtimeValueResolved'] is False
 tap=rows['filterTap[2]'];assert tap['accessor']=='filterTap' and tap['arrayIndex']==2 and tap['arrayCount']==4 and tap['resolvedEnumValue']==0x32 and tap['resolvedEnumAliases']==['CONST_SRC_CODE_FILTER_TAP_2'] and tap['techFlags']=='FLAG_X'

 # Scalar sources cannot be indexed and array sources cannot silently mean [0].
 for source,phrase in [('sunDiffuse[0]','scalar'),('filterTap','requires an explicit [index]'),('filterTap[4]','outside arrayCount')]:
  try:identity.resolve_source_name(source,table)
  except identity.FinalOutputCodeConstantIdentityError as exc:assert phrase in str(exc),str(exc)
  else:raise AssertionError(f'bad code source {source!r} was accepted')

 bad=copy.deepcopy(cbuffer);bad['shaders'][0]['usedCbufferSymbols'][0]['techniqueAssignments'][0]['sourceExpression']='code.other'
 try:identity.build(bad,table)
 except identity.FinalOutputCodeConstantIdentityError as exc:assert '!= code.sunDiffuse' in str(exc)
 else:raise AssertionError('mismatched code source expression/name was accepted')
 print('PASS: exact T6 final-output code constant identity v1');return 0
if __name__=='__main__':raise SystemExit(main())
