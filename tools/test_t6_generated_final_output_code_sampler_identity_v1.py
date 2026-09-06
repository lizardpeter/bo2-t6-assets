#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_code_sampler_identity_v1 as identity

def main()->int:
 binding={'format':identity.BINDING_FORMAT,'shaders':[{'sha256':'a'*64,'techniqueSets':['lit_sm_fixture'],'resources':[
  {'resource':'colorMapSampler','sampleNodeIds':[1],'techniqueAssignments':[{'techniqueSet':'lit_sm_fixture','sourceClass':'material','sourceExpression':'material.colorMap','sourceName':'colorMap'}]},
  {'resource':'reflectionProbeSampler','sampleNodeIds':[2],'techniqueAssignments':[{'techniqueSet':'lit_sm_fixture','sourceClass':'code','sourceExpression':'code.reflectionProbeSampler','sourceName':'reflectionProbeSampler'}]},
 ]}]}
 table={'format':identity.TABLE_FORMAT,'source':{'openAssetToolsCommit':'pinned'},'rows':[{'accessor':'reflectionProbeSampler','enumSymbol':'TEXTURE_SRC_CODE_REFLECTION_PROBE','enumValue':0x1A,'enumValueHex':'0x1a','enumAliases':['TEXTURE_SRC_CODE_REFLECTION_PROBE'],'updateFrequency':'CUSTOM','techFlags':None,'customSamplerIndex':'CUSTOM_SAMPLER_REFLECTION_PROBE'}]}
 doc=identity.build(binding,table)
 assert doc['format']==identity.FORMAT
 assert doc['summary']['codeSamplerAssignmentCount']==1
 assert doc['summary']['uniqueCodeSamplerAccessors']==['reflectionProbeSampler']
 rows={r['resource']:r for r in doc['shaders'][0]['resources']}
 probe=rows['reflectionProbeSampler']['techniqueAssignments'][0]
 assert probe['codeSamplerIdentity']['enumValue']==0x1A
 assert probe['codeSamplerIdentity']['customSamplerIndex']=='CUSTOM_SAMPLER_REFLECTION_PROBE'
 assert probe['runtimeResourceResolved'] is False
 color=rows['colorMapSampler']['techniqueAssignments'][0]
 assert color['codeSamplerIdentity'] is None and color['sourceClass']=='material'
 bad=copy.deepcopy(binding);bad['shaders'][0]['resources'][1]['techniqueAssignments'][0]['sourceName']='unknownSampler'
 try:identity.build(bad,table)
 except identity.CodeSamplerIdentityError as exc:assert 'absent from pinned T6 table' in str(exc)
 else:raise AssertionError('unknown code sampler accessor accepted')
 print('PASS: exact generated final-output T6 code sampler identity v1');return 0
if __name__=='__main__':raise SystemExit(main())
