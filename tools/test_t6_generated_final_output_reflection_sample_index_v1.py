#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_reflection_sample_index_v1 as r

def add(n,k,**kw):i=len(n);n.append({'id':i,'kind':k,**kw});return i
def op(n,name,*a):return add(n,'op',op=name,args=list(a))
def lit(n,b):return add(n,'literal32',bits=b)
def sym(n,name):return add(n,'symbol',name=name,args=[])
def ts(n,ch,at,*args):return add(n,'textureSample',resource=r.RESOURCE,channel=ch,sampler='reflectionProbeSampler_s',opcode='sample_l',instructionDword=at,args=list(args))

def fixture():
 n=[];roots={ch:sym(n,'S'+ch) for ch in r.CHANNELS};u=sym(n,'u');v=sym(n,'v')
 neg4=lit(n,'c0800000');four=lit(n,'40800000');lod=op(n,'add',op(n,'mul',roots['w'],neg4),four)
 coord=op(n,'add',u,roots['x']);nodes1=[ts(n,ch,100,coord,v,lod) for ch in 'xyz']
 bias=lit(n,r.BIAS_BITS);nodes2=[add(n,'textureSample',resource=r.RESOURCE,channel=ch,sampler='s',opcode='sample_b',instructionDword=200,args=[u,v,bias]) for ch in 'xy']
 lod08=lit(n,'3f4ccccd');nodes3=[ts(n,ch,300,u,v,lod08) for ch in 'x']
 final={'format':r.FINAL_FORMAT,'shaders':[{'sha256':'a'*64,'techniqueSets':['lit_sm_fixture'],'nodes':n,'outputs':[],'samples':[
  {'atDword':100,'opcode':'sample_l','resource':r.RESOURCE,'coordinateNodes':[coord,v],'extraOperandNodes':[lod]},
  {'atDword':200,'opcode':'sample_b','resource':r.RESOURCE,'coordinateNodes':[u,v],'extraOperandNodes':[bias]},
  {'atDword':300,'opcode':'sample_l','resource':r.RESOURCE,'coordinateNodes':[u,v],'extraOperandNodes':[lod08]},
 ]}]}
 spec={'format':r.SPEC_FORMAT,'materials':[{'material':'*m','shaderSha256':'a'*64,'finalStateNodes':roots}]}
 return final,spec

def main()->int:
 final,spec=fixture();got=r.build(final,spec)
 s=got['summary'];assert s['shaderCount']==1 and s['reflectionSampleCount']==3 and s['unknownFormCount']==0
 assert s['coordinateSpecularDependentSampleCount']==1 and s['lodBiasSpecularDependentSampleCount']==1
 rows=got['shaders'][0]['samples'];a=next(x for x in rows if x['atDword']==100)
 assert a['classification']['kind']=='affine_lod' and a['classification']['scaleFloat32Bits']=='c0800000' and a['classification']['offsetFloat32Bits']=='40800000'
 assert a['coordinateSpecularChannels']==['x'] and a['lodBiasSpecularChannels']==['w']
 b=next(x for x in rows if x['atDword']==200);assert b['classification']=={'known':True,'kind':'bias','biasFloat32Bits':r.BIAS_BITS}
 c=next(x for x in rows if x['atDword']==300);assert c['classification']['kind']=='literal_lod' and c['classification']['lodFloat32Bits']=='3f4ccccd'
 bad=copy.deepcopy(final);bad['shaders'][0]['samples'][2]['extraOperandNodes']=[bad['shaders'][0]['samples'][0]['coordinateNodes'][0]]
 try:r.build(bad,spec)
 except r.ReflectionSampleIndexError as exc:assert 'unrecognized retained reflection form' in str(exc)
 else:raise AssertionError('unknown reflection LOD form accepted in strict mode')
 relaxed=r.build(bad,spec,strict_known_forms=False);assert relaxed['summary']['unknownFormCount']==1
 print('PASS: generated reflection sample index + exact specular dependencies v1');return 0
if __name__=='__main__':raise SystemExit(main())
