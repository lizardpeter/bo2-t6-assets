#!/usr/bin/env python3
from __future__ import annotations
import t6_generated_final_output_specular_reflection_join_v1 as j

def add(n,k,**kw):i=len(n);n.append({'id':i,'kind':k,**kw});return i
def sym(n,name):return add(n,'symbol',name=name,args=[])
def sample(n,ch,at,*args):return add(n,'textureSample',resource=j.RESOURCE,channel=ch,sampler='s',opcode='sample_l',instructionDword=at,args=list(args))
def op(n,name,*args):return add(n,'op',op=name,args=list(args))
def main()->int:
 n=[];roots={ch:sym(n,'S'+ch) for ch in j.CHANNELS};rx=sample(n,'x',100);mx=op(n,'mul',roots['x'],rx);ry=sample(n,'y',200,roots['y'])
 final={'format':j.FINAL_FORMAT,'shaders':[{'sha256':'a'*64,'nodes':n,'outputs':[]}]}
 spec={'format':j.SPEC_FORMAT,'materials':[{'material':'*m','shaderSha256':'a'*64,'finalStateNodes':roots}]}
 empty={'rootNode':0,'allMixingSites':[]}
 frontier={'format':j.FRONTIER_FORMAT,'materials':[{'material':'*m','shaderSha256':'a'*64,'channels':{
  'x':{'rootNode':roots['x'],'allMixingSites':[{'distance':1,'node':mx,'kind':'op','operation':'mul','parentTextureResource':None,'externalChildNodes':[rx],'externalResources':[j.RESOURCE],'outputLanes':['x']}]},
  'y':{'rootNode':roots['y'],'allMixingSites':[{'distance':1,'node':ry,'kind':'textureSample','operation':'sample_l','parentTextureResource':j.RESOURCE,'externalChildNodes':[],'externalResources':[j.RESOURCE],'outputLanes':['y']}]},
  'z':{'rootNode':roots['z'],'allMixingSites':[]},'w':{'rootNode':roots['w'],'allMixingSites':[]}}}]}
 index={'format':j.REFLECTION_FORMAT,'shaders':[{'shaderSha256':'a'*64,'samples':[
  {'atDword':100,'opcode':'sample_l','sampleNodeIds':[rx],'sampleChannels':['x'],'coordinateNodes':[],'classification':{'known':True,'kind':'affine_lod','scaleFloat32Bits':'c0800000','offsetFloat32Bits':'40800000','sourceNode':roots['w']}},
  {'atDword':200,'opcode':'sample_l','sampleNodeIds':[ry],'sampleChannels':['y'],'coordinateNodes':[roots['y']],'classification':{'known':True,'kind':'literal_lod','lodFloat32Bits':'00000000'}},
 ]}]}
 got=j.build(final,spec,frontier,index);s=got['summary']
 assert s['materialCount']==1 and s['reflectionRelationCount']==2
 assert s['directSpecularTimesReflectionSampleCount']==1
 assert s['directReflectionCoordinateSpecularRootCount']==1
 assert s['directReflectionLodSourceSpecularRootCount']==1
 x=got['materials'][0]['channels']['x'][0];assert x['directSpecularTimesReflectionSample'] is True and x['directReflectionLodSourceSpecularChannels']==['w']
 y=got['materials'][0]['channels']['y'][0];assert y['directSpecularTimesReflectionSample'] is False and y['directReflectionCoordinateSpecularChannels']==['y']
 bad={'format':j.REFLECTION_FORMAT,'shaders':[{'shaderSha256':'a'*64,'samples':[]}]}
 try:j.build(final,spec,frontier,bad)
 except j.SpecularReflectionJoinError as exc:assert 'absent from v33 sample index' in str(exc)
 else:raise AssertionError('frontier reflection node without indexed sample accepted')
 print('PASS: exact generated specular/reflection sample instance join v1');return 0
if __name__=='__main__':raise SystemExit(main())
