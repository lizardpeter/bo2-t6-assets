#!/usr/bin/env python3
from __future__ import annotations
import t6_generated_final_output_diffuse_directional_product_probe_v1 as p

def add(n,k,**kw):i=len(n);n.append({'id':i,'kind':k,**kw});return i
def sym(n,name):return add(n,'symbol',name=name,args=[])
def op(n,name,*args):return add(n,'op',op=name,args=list(args))
def fixture(two=False,normal_index=0,direct_on=(0,)):
 n=[];sq={ch:sym(n,'sq'+ch) for ch in p.RGB};eqs=[]
 count=2 if two else 1
 for i in range(count):eqs.append({ch:sym(n,f'e{i}{ch}') for ch in p.RGB})
 out={}
 for ch in p.RGB:
  terms=[]
  for i in range(count):
   if i in direct_on:terms.append(op(n,'mul',sq[ch],eqs[i][ch]))
   else:terms.append(eqs[i][ch])
  root=terms[0]
  for t in terms[1:]:root=op(n,'add',root,t)
  out[ch]=root
 sha='a'*64
 final={'format':p.FINAL_FORMAT,'shaders':[{'sha256':sha,'techniqueSets':['lit_sm_fixture'],'nodes':n,'outputs':[{'register':0,'lanes':[{'channel':'x','written':True,'node':out['x']},{'channel':'y','written':True,'node':out['y']},{'channel':'z','written':True,'node':out['z']},{'channel':'w','written':False}]}]}]}
 square={'format':p.SQUARE_FORMAT,'shaders':[{'sha256':sha,'anchors':[{'channel':ch,'anchored':True,'candidateCount':1,'candidates':[{'squareNode':sq[ch]}]} for ch in p.RGB]}]}
 directional={'format':p.DIRECTIONAL_FORMAT,'shaders':[{'sha256':sha,'equations':[{'rgbNodes':eqs[i]} for i in range(count)]}]}
 normal={'format':p.NORMAL_FORMAT,'shaders':[{'sha256':sha,'matches':[{'directionalEquationIndex':normal_index}] if normal_index is not None else []}]}
 return final,square,directional,normal

def main()->int:
 got=p.build(*fixture(False,0,(0,)));s=got['summary'];assert s['directProductCount']==3 and s['layeredNormalEquationDirectRgbLaneCount']==3 and s['layeredNormalEquationAllRgbDirectProductCount']==1
 row=got['shaders'][0]['equations'][0];assert row['isLayeredNormalEquation'] is True and row['allRgbDirectProducts'] is True
 got=p.build(*fixture(True,1,(0,)));eq0,eq1=got['shaders'][0]['equations'];assert eq0['allRgbDirectProducts'] is True and eq0['isLayeredNormalEquation'] is False;assert eq1['allRgbDirectProducts'] is False and eq1['isLayeredNormalEquation'] is True
 assert got['summary']['layeredNormalEquationDirectRgbLaneCount']==0
 # Ambiguous duplicate direct products are rejected rather than choosing one.
 f,sq,d,norm=fixture(False,0,(0,));nodes=f['shaders'][0]['nodes'];orig=f['shaders'][0]['outputs'][0]['lanes'][0]['node'];dup=op(nodes,'mul',sq['shaders'][0]['anchors'][0]['candidates'][0]['squareNode'],d['shaders'][0]['equations'][0]['rgbNodes']['x']);f['shaders'][0]['outputs'][0]['lanes'][0]['node']=op(nodes,'add',orig,dup)
 try:p.build(f,sq,d,norm)
 except p.DiffuseDirectionalProductProbeError as exc:assert 'ambiguous direct product count' in str(exc)
 else:raise AssertionError('ambiguous direct diffuse-directional product accepted')
 print('PASS: direct squared-RGB directional-lightmap product probe v1');return 0
if __name__=='__main__':raise SystemExit(main())
