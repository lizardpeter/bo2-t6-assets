#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_unclassified_term_specialization_v2 as v2

SHA='a'*64;TECH='lit_sm_fixture';A='*a';B='*b'

def docs():
 final={'format':v2.v1.FINAL_FORMAT,'materials':[{'material':A,'techniqueSet':TECH,'pixelShaderSha256':SHA},{'material':B,'techniqueSet':TECH,'pixelShaderSha256':SHA}],'shaders':[{'sha256':SHA,'nodes':[
  {'id':0,'kind':'symbol','name':'cb1[59].x'},
  {'id':1,'kind':'symbol','name':'cb2[3].y'},
  {'id':2,'kind':'op','op':'mul','args':[0,1]},
  {'id':3,'kind':'textureSample','resource':'colorMapSampler','channel':'x','opcode':'sample','args':[]},
  {'id':4,'kind':'op','op':'add','args':[2,3]},
 ]}]}
 material_assignment={'techniqueSet':TECH,'sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1','resolutionKind':'retail_material_constant','identityResolved':True,'runtimeValueResolved':True,'materialOwners':[{'material':A,'materialArchiveSha256':'1'*64,'scalarValue':0.25,'constantSerializedSha256':'3'*64},{'material':B,'materialArchiveSha256':'2'*64,'scalarValue':0.75,'constantSerializedSha256':'4'*64}]}
 code_assignment={'techniqueSet':TECH,'sourceClass':'code','sourceExpression':'code.sunDiffuse','sourceName':'sunDiffuse','resolutionKind':'t6_code_constant_dynamic','identityResolved':True,'runtimeValueResolved':False,'codeConstant':{'accessor':'sunDiffuse','arrayIndex':None,'resolvedEnumValue':0x23,'updateFrequency':'CUSTOM','techFlags':None,'transposedMatrixEnumValue':None}}
 resolution={'format':v2.v1.RESOLUTION_FORMAT,'terms':[{'sha256':SHA,'lane':'x','node':4,'cbufferResolutionV1':[{'symbol':'cb1[59].x','assignments':[material_assignment]},{'symbol':'cb2[3].y','assignments':[code_assignment]}]}],'summary':{}}
 return final,resolution

def main()->int:
 final,resolution=docs();doc=v2.build(final,resolution)
 assert doc['format']==v2.FORMAT and doc['baseFormat']==v2.v1.FORMAT
 assert doc['summary']['exactCbufferCoverageTermCount']==1
 assert doc['cbufferCoveragePreflight']['rows'][0]['reachableCbufferSymbols']==['cb1[59].x','cb2[3].y']
 term=doc['terms'][0];assert term['materialOwnerCount']==2 and term['distinctSpecializedProfileCount']==2 and term['variesAcrossMaterialOwners'] is True
 variants={row['material']:row for row in term['variants']}
 pa=variants[A]['profile'];pb=variants[B]['profile']
 # add(mul(materialLiteral, dynamicCode), texture) topology and operand order stay exact.
 mul_a=pa['args'][0];mul_b=pb['args'][0]
 assert mul_a['op']=='mul' and mul_a['args'][0]['kind']=='retailMaterialConstant' and mul_a['args'][1]['kind']=='t6CodeConstantDynamic'
 assert mul_a['args'][0]['scalarFloat32Bits']=='0000803e' and mul_a['args'][0]['scalarValue']==0.25
 assert mul_b['args'][0]['scalarFloat32Bits']=='0000403f' and mul_b['args'][0]['scalarValue']==0.75
 assert mul_a['args'][1]['resolvedEnumValue']==0x23 and mul_b['args'][1]['resolvedEnumValue']==0x23
 assert pa['args'][1]['kind']=='textureSample' and pa['args'][1]['resource']=='colorMapSampler'
 assert variants[A]['hasDynamicCodeConstant'] is True and variants[B]['hasDynamicCodeConstant'] is True
 assert variants[A]['hasUnresolvedCbuffer'] is False
 assert doc['summary']['termWithMaterialSpecializationVariationCount']==1
 assert doc['summary']['materialVariantCount']==2
 assert doc['summary']['variantWithDynamicCodeConstantCount']==2
 assert doc['summary']['variantWithUnresolvedCbufferCount']==0

 # If both exact material values are identical, the specialized expression hashes collapse.
 final2,res2=docs();res2['terms'][0]['cbufferResolutionV1'][0]['assignments'][0]['materialOwners'][1]['scalarValue']=0.25
 same=v2.build(final2,res2);assert same['terms'][0]['distinctSpecializedProfileCount']==1 and same['terms'][0]['variesAcrossMaterialOwners'] is False

 # Every reachable cbuffer symbol must be represented in the resolution sidecar.
 bad=copy.deepcopy(resolution);bad['terms'][0]['cbufferResolutionV1']=bad['terms'][0]['cbufferResolutionV1'][:1]
 try:v2.build(final,bad)
 except v2.UnclassifiedTermSpecializationV2Error as exc:assert 'reachable cbuffer symbols' in str(exc)
 else:raise AssertionError('specialization accepted incomplete cbuffer resolution coverage')
 print('PASS: exact per-material unknown final RGB specialization v2');return 0
if __name__=='__main__':raise SystemExit(main())
