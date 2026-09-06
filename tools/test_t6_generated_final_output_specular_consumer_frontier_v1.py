#!/usr/bin/env python3
from __future__ import annotations
import t6_generated_final_output_specular_consumer_frontier_v1 as f

def add(n,k,**kw):i=len(n);n.append({'id':i,'kind':k,**kw});return i
def op(n,name,*args):return add(n,'op',op=name,args=list(args))
def sample(n,res,ch,*args):return add(n,'textureSample',resource=res,channel=ch,sampler=res+'_s',opcode='sample',args=list(args))
def sym(n,name):return add(n,'symbol',name=name,args=[])
def main()->int:
 n=[];sx={ch:sym(n,'S'+ch) for ch in f.CHANNELS}
 refl=sample(n,'reflectionProbeSampler','x');light=sample(n,'lightmapSamplerSecondary','y')
 ox=op(n,'mul',sx['x'],refl);oy=op(n,'add',sx['y'],light)
 two=add(n,'literal32',bits='40000000');oz=op(n,'mul',sx['z'],two)
 # W is used as a coordinate to a texture sample: resource lives on parent.
 ow=sample(n,'reflectionProbeSampler','w',sx['w'])
 final={'format':f.FINAL_FORMAT,'shaders':[{'sha256':'a'*64,'nodes':n,'outputs':[{'register':0,'lanes':[{'channel':'x','written':True,'node':ox},{'channel':'y','written':True,'node':oy},{'channel':'z','written':True,'node':oz},{'channel':'w','written':True,'node':ow}]}]}]}
 spec={'format':f.SPEC_FORMAT,'materials':[{'material':'*m','shaderSha256':'a'*64,'finalStateNodes':sx,'downstreamOutputLanes':{ch:[ch] for ch in f.CHANNELS}}]}
 got=f.build(final,spec);assert got['summary']['materialCount']==1 and got['summary']['channelCount']==4
 row=got['materials'][0];x=row['channels']['x'];y=row['channels']['y'];z=row['channels']['z'];w=row['channels']['w']
 assert x['nearestResourceMixDistance']==1 and x['nearestResourceMixingSites'][0]['externalResources']==['reflectionProbeSampler']
 assert y['nearestResourceMixingSites'][0]['externalResources']==['lightmapSamplerSecondary']
 assert z['resourceMixingSiteCount']==0 and z['nearestMixDistance']==1
 assert w['nearestResourceMixDistance']==1 and w['nearestResourceMixingSites'][0]['parentTextureResource']=='reflectionProbeSampler'
 assert got['summary']['channelWithResourceMixCount']==3
 assert got['summary']['materialWithAnyResourceMixCount']==1
 assert got['summary']['nearestResourceNameCounts']=={'lightmapSamplerSecondary':1,'reflectionProbeSampler':2}
 # Other specular channels are owned siblings, not external dependencies.
 n2=[];roots={ch:sym(n2,'S'+ch) for ch in f.CHANNELS};mix=op(n2,'add',roots['x'],roots['y']);z=op(n2,'add',mix,roots['z']);w=op(n2,'add',z,roots['w'])
 final2={'format':f.FINAL_FORMAT,'shaders':[{'sha256':'b'*64,'nodes':n2,'outputs':[{'register':0,'lanes':[{'channel':'x','written':True,'node':w},{'channel':'y','written':False},{'channel':'z','written':False},{'channel':'w','written':False}]}]}]}
 spec2={'format':f.SPEC_FORMAT,'materials':[{'material':'*m2','shaderSha256':'b'*64,'finalStateNodes':roots,'downstreamOutputLanes':{}}]}
 got2=f.build(final2,spec2);assert all(got2['materials'][0]['channels'][ch]['resourceMixingSiteCount']==0 for ch in f.CHANNELS)
 print('PASS: exact generated specular downstream consumer frontier v1');return 0
if __name__=='__main__':raise SystemExit(main())
