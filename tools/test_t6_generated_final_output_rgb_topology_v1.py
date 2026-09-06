#!/usr/bin/env python3
from __future__ import annotations
import t6_generated_final_output_rgb_topology_v1 as t

def add(n,k,**kw):i=len(n);n.append({'id':i,'kind':k,**kw});return i
def sym(n,name):return add(n,'symbol',name=name,args=[])
def op(n,name,*args):return add(n,'op',op=name,args=list(args))
def sample(n,ch,at):return add(n,'textureSample',resource=t.RESOURCE,channel=ch,sampler='s',opcode='sample_l',instructionDword=at,args=[])
def main()->int:
 n=[];sq={ch:sym(n,'sq'+ch) for ch in t.RGB};dr={ch:sym(n,'d'+ch) for ch in t.RGB};sp={ch:sym(n,'s'+ch) for ch in 'xyzw'};rf={ch:sample(n,ch,100+i) for i,ch in enumerate(t.RGB)}
 x1=op(n,'mul',sq['x'],dr['x']);x2=op(n,'mul',sp['x'],rf['x']);ox=op(n,'add',x1,x2)
 oy=op(n,'mul',sq['y'],dr['y']);oz=op(n,'add',rf['z'],sq['z']);sha='a'*64
 final={'format':t.FINAL_FORMAT,'shaders':[{'sha256':sha,'techniqueSets':['lit_sm_fixture'],'nodes':n,'outputs':[{'register':0,'lanes':[{'channel':'x','written':True,'node':ox},{'channel':'y','written':True,'node':oy},{'channel':'z','written':True,'node':oz},{'channel':'w','written':False}]}]}]}
 square={'format':t.SQUARE_FORMAT,'shaders':[{'sha256':sha,'anchors':[{'channel':ch,'anchored':True,'candidateCount':1,'candidates':[{'squareNode':sq[ch]}]} for ch in t.RGB]}]}
 directional={'format':t.DIR_FORMAT,'shaders':[{'sha256':sha,'equations':[{'rgbNodes':dr}]}]}
 spec={'format':t.SPEC_FORMAT,'materials':[{'material':'*m','shaderSha256':sha,'finalStateNodes':sp}]}
 refl={'format':t.REFL_FORMAT,'shaders':[{'shaderSha256':sha,'samples':[{'sampleNodeIds':[rf[ch]]} for ch in t.RGB]}]}
 got=t.build(final,square,directional,spec,refl);s=got['summary'];assert s['shaderCount']==1 and s['rgbLaneCount']==3 and s['syntacticAdditiveLeafCount']==5
 assert s['anchoredImmediateMulLeafCount']==3
 c=s['leafAnchorSignatureCounts'];assert c['squareRgb+directional:0']==2 and c['specular:x+reflectionProbe']==1 and c['reflectionProbe']==1 and c['squareRgb']==1
 row=got['shaders'][0];xl=row['lanes']['x']['leaves'];assert [q['path'] for q in xl]==['L','R'];assert xl[0]['immediateMulChildren'][0]['tags'] or xl[0]['immediateMulChildren'][1]['tags']
 assert row['lanes']['y']['leaves'][0]['path']=='ROOT'
 print('PASS: exact top-level generated o0 RGB topology v1');return 0
if __name__=='__main__':raise SystemExit(main())
