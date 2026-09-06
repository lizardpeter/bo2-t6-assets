#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_material_cbuffer_values_v2 as v2

SHA='a'*64
TECH='lit_sm_fixture'
MAT_A='*mat_a(base:layer)'
MAT_B='*mat_b(base:layer)'
NAME='alphaRevealParms1'
HASH=v2.v1.t6_r_hash_string(NAME,0)

def docs(two_materials=True):
 materials=[{'material':MAT_A,'techniqueSet':TECH,'pixelShaderSha256':SHA}]
 if two_materials:materials.append({'material':MAT_B,'techniqueSet':TECH,'pixelShaderSha256':SHA})
 final={'format':v2.v1.FINAL_FORMAT,'materials':materials,'shaders':[{'sha256':SHA,'techniqueSets':[TECH]}]}
 cbuffer={'format':v2.v1.CBUFFER_FORMAT,'shaders':[{'sha256':SHA,'techniqueSets':[TECH],'usedCbufferSymbols':[
  {'symbol':'cb1[59].x','nodeIds':[7],'buffer':{'name':'PerMaterial'},'variable':{'name':NAME,'relativeScalarIndex':0},'techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'material','sourceExpression':'material.'+NAME,'sourceName':NAME}]},
  {'symbol':'cb2[3].y','nodeIds':[8],'buffer':{'name':'PerCode'},'variable':{'name':'sunColor','relativeScalarIndex':1},'techniqueAssignments':[{'techniqueSet':TECH,'sourceClass':'code','sourceExpression':'code.sunColor','sourceName':'sunColor'}]},
 ]}]}
 def row(material,index,value):
  return {'material':material,'materialIndex':index,'materialStart':1000+index*100,'materialArchiveSha256':str(index+1)*64,'constantCount':1,'constants':[{'index':0,'fileOffset':2000+index*32,'nameHash':HASH,'nameHashHex':f'0x{HASH:08x}','nameFragment':NAME[:12],'literal':[value,2.0,3.0,4.0],'serializedSha256':chr(98+index)*64}]}
 rows=[row(MAT_A,0,0.25)]
 if two_materials:rows.append(row(MAT_B,1,0.75))
 constants={'format':v2.v1.MATERIAL_CONSTANT_FORMAT,'map':'mp_nuketown_2020','generatedOnly':True,'materials':rows}
 return final,cbuffer,constants

def main()->int:
 final,cb,constants=docs(True);doc=v2.build(final,cb,constants)
 assert doc['format']==v2.FORMAT and doc['baseFormat']==v2.v1.FORMAT
 rows={row['material']:row for row in doc['materials']}
 assert rows[MAT_A]['resolvedMaterialBindings'][0]['materialConstant']['scalarValue']==0.25
 assert rows[MAT_B]['resolvedMaterialBindings'][0]['materialConstant']['scalarValue']==0.75
 assert rows[MAT_A]['resolvedMaterialBindings'][0]['materialConstant']['nameHash']==HASH
 assert rows[MAT_A]['unresolvedNonMaterialBindings'][0]['sourceClass']=='code'
 assert doc['summary']['materialSourceBindingOccurrenceCount']==2
 assert doc['summary']['resolvedMaterialSourceBindingOccurrenceCount']==2
 assert doc['summary']['unresolvedNonMaterialSourceBindingOccurrenceCount']==2
 assert doc['summary']['shaderCountWithMaterialValueVariation']==1
 assert doc['summary']['shaderCountWithMultipleMaterialOwners']==1
 var=doc['shaderMaterialValueVariation'][0]
 assert var['materialOwnerCount']==2 and var['distinctMaterialValueSignatureCount']==2 and var['variesAcrossMaterialOwners'] is True

 # One material can use multiple distinct binding values without constituting
 # cross-material variation. Exercise v2 promotion independently of v1's old stat.
 single={'format':v2.v1.FORMAT,'materials':[{'material':MAT_A,'pixelShaderSha256':SHA,'materialResolvedValueSignatureSha256':'1'*64}], 'summary':{'shaderCountWithMaterialValueVariation':1},'proofBoundary':'fixture'}
 promoted=v2.promote(single)
 assert promoted['summary']['v1BindingValueDiversityStatistic']==1
 assert promoted['summary']['shaderCountWithMaterialValueVariation']==0
 assert promoted['summary']['shaderCountWithMultipleMaterialOwners']==0

 # Hash identity alone is insufficient: the serialized 12-byte fragment must
 # also match the full reflected material constant name.
 bad=copy.deepcopy(constants);bad['materials'][0]['constants'][0]['nameFragment']='alphaRevealX'
 try:v2.build(final,cb,bad)
 except v2.v1.FinalOutputMaterialCbufferValueError as exc:assert 'fragment' in str(exc)
 else:raise AssertionError('material constant hash collision/fragment mismatch was accepted')

 missing=copy.deepcopy(constants);missing['materials']=missing['materials'][:1]
 try:v2.build(final,cb,missing)
 except v2.v1.FinalOutputMaterialCbufferValueError as exc:assert 'absent from retail constant archive' in str(exc)
 else:raise AssertionError('missing per-material retail constant archive row was accepted')
 print('PASS: exact final-output per-material cbuffer values v2');return 0
if __name__=='__main__':raise SystemExit(main())
