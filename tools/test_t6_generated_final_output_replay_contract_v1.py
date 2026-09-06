#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_replay_contract_v1 as replay

def docs():
 sha='a'*64;tech='lit_sm_fixture';mat='*fixture'
 final={'format':replay.FINAL_FORMAT,'materials':[{'material':mat,'techniqueSet':tech,'pixelShaderSha256':sha}],'shaders':[{'sha256':sha,'shaderModel':'4.0','techniqueSets':[tech],'nodes':[{'id':0,'kind':'symbol','name':'cb0[0].x'},{'id':1,'kind':'symbol','name':'cb0[1].x'},{'id':2,'kind':'symbol','name':'v0.x'},{'id':3,'kind':'textureSample','resource':'colorMapSampler','channel':'x','args':[2]},{'id':4,'kind':'textureSample','resource':'reflectionProbeSampler','channel':'x','args':[2]},{'id':5,'kind':'op','op':'add','args':[0,1]},{'id':6,'kind':'op','op':'add','args':[3,4]},{'id':7,'kind':'op','op':'mul','args':[5,6]}],'outputs':[{'register':0,'lanes':[{'channel':'x','written':True,'node':7}]}],'samples':[],'branches':[],'discards':[]}]}
 cb={'format':replay.CB_FORMAT,'shaders':[{'sha256':sha,'usedCbufferSymbols':[
  {'symbol':'cb0[0].x','nodeIds':[0],'buffer':{'name':'B'},'variable':{'name':'foo'},'techniqueAssignments':[{'techniqueSet':tech,'sourceClass':'material','sourceNamespace':'material','sourceKind':'material','sourceExpression':'material.foo','sourceName':'foo'}]},
  {'symbol':'cb0[1].x','nodeIds':[1],'buffer':{'name':'B'},'variable':{'name':'sunDiffuse'},'techniqueAssignments':[{'techniqueSet':tech,'sourceClass':'code','sourceNamespace':'constant','sourceKind':'constant','sourceExpression':'constant.sunDiffuse','sourceName':'sunDiffuse'}]},
 ]}]}
 cc={'format':replay.CODE_CONST_FORMAT,'shaders':[{'sha256':sha,'assignments':[{'symbol':'cb0[1].x','techniqueSet':tech,'sourceName':'sunDiffuse','accessor':'sunDiffuse','resolvedEnumValue':35,'arrayIndex':None,'updateFrequency':'CUSTOM','runtimeValueResolved':False}]}]}
 tex={'format':replay.TEX_FORMAT,'shaders':[{'sha256':sha,'resources':[]}]}
 cs={'format':replay.CODE_SAMPLER_FORMAT,'shaders':[{'sha256':sha,'resources':[
  {'resource':'colorMapSampler','sampleNodeIds':[3],'resourceRegisters':[0],'samplerNames':['s0'],'samplerRegisters':[0],'opcodes':['sample'],'channels':['x'],'techniqueAssignments':[{'techniqueSet':tech,'sourceClass':'material','sourceNamespace':'material','sourceKind':'material','sourceExpression':'material.colorMap','sourceName':'colorMap','codeSamplerIdentity':None}]},
  {'resource':'reflectionProbeSampler','sampleNodeIds':[4],'resourceRegisters':[15],'samplerNames':['s15'],'samplerRegisters':[15],'opcodes':['sample_l'],'channels':['x'],'techniqueAssignments':[{'techniqueSet':tech,'sourceClass':'code','sourceNamespace':'sampler','sourceKind':'sampler','sourceExpression':None,'sourceName':'reflectionProbeSampler','codeSamplerIdentity':{'accessor':'reflectionProbeSampler','enumSymbol':'TEXTURE_SRC_CODE_REFLECTION_PROBE','enumValue':26,'enumValueHex':'0x1a','updateFrequency':'CUSTOM','customSamplerIndex':'CUSTOM_SAMPLER_REFLECTION_PROBE'}}]},
 ]}]}
 # Texture proof must cover same shader set, even though replay takes authoritative resource rows from code-sampler v2.
 tex['shaders'][0]['resources']=copy.deepcopy(cs['shaders'][0]['resources'])
 ms={'format':replay.MAT_SAMPLER_FORMAT,'materials':[{'material':mat,'bindings':[{'resource':'colorMapSampler','status':'unique','resolvedTexture':{'imageAsset':'img_color','sourceTexture':'img_color.png','propertyHash':123}}]}]}
 mv={'format':replay.MAT_VALUES_FORMAT,'materials':[{'material':mat,'resolvedMaterialBindings':[{'symbol':'cb0[0].x','materialConstant':{'name':'foo','scalarValue':0.25,'literal':[0.25,0,0,0]}}]}]}
 return final,cb,cc,tex,cs,ms,mv

def main()->int:
 d=docs();out=replay.build(*d)
 assert out['format']==replay.FORMAT and out['summary']['programCount']==1 and out['summary']['materialCount']==1
 m=out['materials'][0];assert m['replayIdentityComplete'] is True and m['runtimeDynamicInputsStillRequired'] is True and m['blockerCount']==0
 assert out['summary']['uniqueDynamicCodeConstantSlotCount']==1 and out['summary']['uniqueDynamicCodeSamplerSlotCount']==1
 assert out['summary']['resolvedStaticMaterialCbufferBindingCount']==1 and out['summary']['resolvedStaticMaterialTextureBindingCount']==1
 assert out['programs'][0]['externalNonCbufferSymbols']==['v0.x']
 kinds={r['bindingKind'] for r in m['cbufferInputs']};assert kinds=={'retailMaterialConstant','t6CodeConstantDynamic'}
 tk={r['bindingKind'] for r in m['textureInputs']};assert tk=={'retailMaterialTexture','t6CodeSamplerDynamic'}

 bad=list(d);bad[5]=copy.deepcopy(d[5]);binding=bad[5]['materials'][0]['bindings'][0];binding['status']='ambiguous';binding['resolvedTexture']=None;binding['candidates']=[{'imageAsset':'a'},{'imageAsset':'b'}]
 out2=replay.build(*bad);m2=out2['materials'][0];assert m2['replayIdentityComplete'] is False and m2['blockerCount']==1 and out2['summary']['blockerCounts']['materialSamplerAmbiguous']==1

 noval=list(d);noval[6]=None;out3=replay.build(*noval);assert out3['materials'][0]['materialStaticStateComplete'] is False and out3['summary']['blockerCounts']['materialConstantValueMissing']==1
 print('PASS: renderer-neutral exact generated final-output replay contract v1');return 0
if __name__=='__main__':raise SystemExit(main())
