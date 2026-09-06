#!/usr/bin/env python3
from __future__ import annotations

import copy
import t6_generated_final_output_rgb_factor_anchor_v1 as a


def add(nodes,kind,**kw):i=len(nodes);nodes.append({'id':i,'kind':kind,**kw});return i
def sample(nodes,res,ch):return add(nodes,'textureSample',resource=res,channel=ch,sampler=res+'_s',args=[])
def lit(nodes,bits):return add(nodes,'literal32',bits=bits)
def op(nodes,name,*args):return add(nodes,'op',op=name,args=list(args))

def fixture(operation='blend',bad_shared=False,mismatch=False):
 nodes=[];one=lit(nodes,a.ONE_BITS);negone=lit(nodes,a.NEG_ONE_BITS)
 base={ch:sample(nodes,'colorMapSampler',ch) for ch in a.RGB};layer={ch:sample(nodes,'colorMapSampler1',ch) for ch in a.RGB}
 factor=sample(nodes,'colorMapSampler1','w');factor2=sample(nodes,'colorMapSampler1','x') if bad_shared else factor;state={}
 for ch in a.RGB:
  f=factor2 if bad_shared and ch=='z' else factor
  if operation=='add':state[ch]=op(nodes,'add',base[ch],op(nodes,'mul',layer[ch],f))
  elif operation=='blend':state[ch]=op(nodes,'add',base[ch],op(nodes,'mul',op(nodes,'add',layer[ch],op(nodes,'neg',base[ch])),f))
  elif operation=='multiply':state[ch]=op(nodes,'mul',base[ch],op(nodes,'add',one,op(nodes,'mul',op(nodes,'add',layer[ch],negone),f)))
  elif operation=='threshold':state[ch]=op(nodes,'select',f,layer[ch],base[ch])
  else:raise ValueError(operation)
 sha='a'*64;opchar={'add':'a','blend':'b','multiply':'m','threshold':'t'}[operation]
 recipe={'material':'*fixture','techniqueSet':f'lit_sm_r0c0_{opchar}1c1','pixelShaderArchetype':'sha256:'+sha,'worldVertFormats':[1],'proof':{'fixture':True}}
 recipes={'format':'t6-generated-world-shader-recipe-manifest-v1','materials':[recipe]}
 final={'format':a.FINAL_FORMAT,'shaders':[{'sha256':sha,'nodes':nodes,'outputs':[]} ]}
 anchors=[]
 for ch in a.RGB:
  h=a._h(a._nodes(final['shaders'][0]),state[ch])
  if mismatch and ch=='z':h='f'*64
  anchors.append({'channel':ch,'anchored':True,'candidateCount':1,'candidates':[{'encodedRgbNode':state[ch],'encodedRgbSha256':h}]})
 square={'format':a.SQUARE_FORMAT,'shaders':[{'sha256':sha,'anchors':anchors}]}
 return recipes,final,square

def main()->int:
 for operation in ('add','blend','multiply','threshold'):
  r,f,s=fixture(operation);got=a.build(r,f,s)
  assert got['summary']['materialCount']==1 and got['summary']['layerStepCount']==1
  assert got['summary']['fullyMatchedMaterialCount']==1
  row=got['materials'][0];assert row['allChannelsMatch'] is True
  st=row['steps'][0];assert st['operation']==operation and len(st['sharedFactorSha256'])==64
  assert len(set(st['stateSha256'].values()))==3
 r,f,s=fixture('blend',bad_shared=True)
 try:a.build(r,f,s)
 except a.RgbFactorAnchorError as exc:assert 'shared blend factor/condition count' in str(exc)
 else:raise AssertionError('RGB channels with different factors were accepted')
 r,f,s=fixture('blend',mismatch=True)
 try:a.build(r,f,s)
 except a.RgbFactorAnchorError as exc:assert 'does not equal pre-square anchor' in str(exc)
 else:raise AssertionError('RGB recurrence not ending at square anchor was accepted')
 relaxed=a.build(r,f,s,strict=False);assert relaxed['materials'][0]['allChannelsMatch'] is False
 print('PASS: exact generated RGB factor anchors for A/B/M/T')
 return 0
if __name__=='__main__':raise SystemExit(main())
