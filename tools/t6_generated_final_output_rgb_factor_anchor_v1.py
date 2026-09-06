#!/usr/bin/env python3
"""Recover exact generated RGB layer factors inside full slot-4 final-output DAGs.

The v26 RGB-square anchor identifies the exact encoded RGB roots immediately
before the proven per-channel square.  This verifier reconstructs the canonical
A/B/M/T generated layer program from exact colorMapSampler* samples and requires
that the completed RGB state equals those pre-square roots.

Each non-threshold step must expose one scalar factor DAG shared by x/y/z;
threshold steps must expose one condition DAG shared by x/y/z.  No attempt is
made here to reinterpret that factor physically or to rederive vN height math.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path
from typing import Any
from t6_generated_shader_recipe_contract_v1 import validate_manifest

FORMAT='t6-generated-final-output-rgb-factor-anchor-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
SQUARE_FORMAT='t6-generated-final-output-rgb-square-anchor-v1'
RGB='xyz';ONE_BITS='3f800000';NEG_ONE_BITS='bf800000'
class RgbFactorAnchorError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _nodes(shader):
 rows=shader.get('nodes');
 if not isinstance(rows,list):raise RgbFactorAnchorError('shader has no nodes')
 out={}
 for r in rows:
  i=int(r.get('id',-1))
  if i<0 or i in out:raise RgbFactorAnchorError(f'invalid/duplicate node {i}')
  out[i]=r
 return out

def _canon(nodes,i,m=None):
 m={} if m is None else m
 if i in m:return m[i]
 r=nodes[i];k=str(r.get('kind') or '')
 if k=='op':
  op=str(r.get('op') or '');a=[_canon(nodes,int(x),m) for x in r.get('args',[])]
  if op in {'add','mul','min','max','eq','ne','and','or','and_bool'}:a=sorted(a,key=lambda x:json.dumps(x,sort_keys=True,separators=(',',':')))
  v=('op',op,tuple(a))
 elif k=='textureSample':v=('sample',str(r.get('resource') or ''),str(r.get('channel') or ''),str(r.get('sampler') or ''),tuple(_canon(nodes,int(x),m) for x in r.get('args',[])))
 elif k=='literal32':v=('literal32',str(r.get('bits') or '').lower())
 else:v=(k,tuple(sorted((q,r[q]) for q in r if q not in {'id','args'})),tuple(_canon(nodes,int(x),m) for x in r.get('args',[])))
 m[i]=v;return v
def _h(nodes,i):return _jhash(_canon(nodes,i))
def _anc(nodes,root):
 s=set()
 def w(i):
  if i in s:return
  if i not in nodes:raise RgbFactorAnchorError(f'missing node {i}')
  s.add(i)
  for x in nodes[i].get('args',[]):w(int(x))
 w(root);return s
def _sample(nodes,res,ch):return sorted(i for i,r in nodes.items() if r.get('kind')=='textureSample' and str(r.get('resource') or '')==res and str(r.get('channel') or '')==ch)
def _lit(nodes,bits):return sorted(i for i,r in nodes.items() if r.get('kind')=='literal32' and str(r.get('bits') or '').lower()==bits)
def _neg(nodes,cand,target):
 r=nodes[cand]
 if r.get('kind')=='op' and r.get('op')=='neg' and len(r.get('args',[]))==1:return _h(nodes,int(r['args'][0]))==_h(nodes,target)
 if r.get('kind')=='op' and r.get('op')=='mul' and len(r.get('args',[]))==2:
  for a,b in (r['args'],r['args'][::-1]):
   a=int(a);b=int(b);br=nodes[b]
   if _h(nodes,a)==_h(nodes,target) and br.get('kind')=='literal32' and str(br.get('bits') or '').lower()==NEG_ONE_BITS:return True
 return False
def _diff(nodes,i,layer,prev):
 r=nodes[i]
 if r.get('kind')!='op' or r.get('op')!='add' or len(r.get('args',[]))!=2:return False
 return any(_h(nodes,int(a))==_h(nodes,layer) and _neg(nodes,int(b),prev) for a,b in (r['args'],r['args'][::-1]))
def _layer_minus_one(nodes,i,layer):
 r=nodes[i]
 if r.get('kind')!='op' or r.get('op')!='add' or len(r.get('args',[]))!=2:return False
 for a,b in (r['args'],r['args'][::-1]):
  a=int(a);b=int(b);br=nodes[b]
  if _h(nodes,a)==_h(nodes,layer) and br.get('kind')=='literal32' and str(br.get('bits') or '').lower()==NEG_ONE_BITS:return True
 return False
def _candidates(nodes,prev,layer,operation,allowed):
 hp=_h(nodes,prev);hl=_h(nodes,layer);out=[]
 for root,r in nodes.items():
  if root not in allowed:continue
  if operation=='threshold':
   if r.get('kind')=='op' and r.get('op')=='select' and len(r.get('args',[]))==3:
    c,y,n=map(int,r['args'])
    if _h(nodes,y)==hl and _h(nodes,n)==hp:out.append((root,c))
   continue
  if operation in {'add','blend'}:
   if r.get('kind')!='op' or r.get('op')!='add' or len(r.get('args',[]))!=2:continue
   for base,term in (r['args'],r['args'][::-1]):
    base=int(base);term=int(term)
    if _h(nodes,base)!=hp:continue
    tr=nodes[term]
    if tr.get('kind')!='op' or tr.get('op')!='mul' or len(tr.get('args',[]))!=2:continue
    for value,factor in (tr['args'],tr['args'][::-1]):
     value=int(value);factor=int(factor)
     ok=_h(nodes,value)==hl if operation=='add' else _diff(nodes,value,layer,prev)
     if ok:out.append((root,factor))
   continue
  if operation=='multiply':
   if r.get('kind')!='op' or r.get('op')!='mul' or len(r.get('args',[]))!=2:continue
   for base,inner in (r['args'],r['args'][::-1]):
    base=int(base);inner=int(inner)
    if _h(nodes,base)!=hp:continue
    ir=nodes[inner]
    if ir.get('kind')!='op' or ir.get('op')!='add' or len(ir.get('args',[]))!=2:continue
    for one,term in (ir['args'],ir['args'][::-1]):
     one=int(one);term=int(term);orr=nodes[one]
     if orr.get('kind')!='literal32' or str(orr.get('bits') or '').lower()!=ONE_BITS:continue
     tr=nodes[term]
     if tr.get('kind')!='op' or tr.get('op')!='mul' or len(tr.get('args',[]))!=2:continue
     for diff,factor in (tr['args'],tr['args'][::-1]):
      if _layer_minus_one(nodes,int(diff),layer):out.append((root,int(factor)))
   continue
  raise RgbFactorAnchorError(f'unsupported operation {operation!r}')
 return sorted(set(out))
def _choose(nodes,per,material,layer,op):
 common=None;groups={}
 for ch in RGB:
  g=defaultdict(list)
  for root,f in per[ch]:g[_h(nodes,f)].append((root,f))
  groups[ch]=g;common=set(g) if common is None else common & set(g)
 if not common or len(common)!=1:raise RgbFactorAnchorError(f'{material!r} layer {layer}: shared {op} factor/condition count {0 if common is None else len(common)}')
 fh=next(iter(common));roots={};fids=[]
 for ch in RGB:
  rh=defaultdict(list)
  for root,f in groups[ch][fh]:rh[_h(nodes,root)].append((root,f))
  if len(rh)!=1:raise RgbFactorAnchorError(f'{material!r} layer {layer} channel {ch}: ambiguous RGB recurrence roots')
  root,f=sorted(next(iter(rh.values())))[0];roots[ch]=root;fids.append(f)
 return roots,min(fids),fh
def _square_rows(square):
 out={}
 for r in square.get('shaders',[]):
  sha=str(r.get('sha256') or '');a={}
  for row in r.get('anchors',[]):
   ch=str(row.get('channel') or '')
   if row.get('anchored') and int(row.get('candidateCount',0))==1:a[ch]=row['candidates'][0]
  out[sha]=a
 return out

def build(recipes,final_output,square_anchor,*,strict=True):
 if final_output.get('format')!=FINAL_FORMAT:raise RgbFactorAnchorError(f"unexpected final-output format {final_output.get('format')!r}")
 if square_anchor.get('format')!=SQUARE_FORMAT:raise RgbFactorAnchorError(f"unexpected square-anchor format {square_anchor.get('format')!r}")
 rr=validate_manifest(recipes);shaders={str(s.get('sha256') or ''):s for s in final_output.get('shaders',[])};sq=_square_rows(square_anchor);rows=[];steps=0;fhs=set()
 for material,recipe in sorted(rr.items()):
  arch=str(recipe.get('pixelShaderArchetype') or '')
  if not arch.startswith('sha256:'):raise RgbFactorAnchorError(f'{material!r}: invalid shader archetype')
  sha=arch.split(':',1)[1];shader=shaders.get(sha);anchors=sq.get(sha)
  if shader is None or anchors is None:raise RgbFactorAnchorError(f'{material!r}: missing shader/square anchor {sha}')
  if set(anchors)!=set(RGB):raise RgbFactorAnchorError(f'{material!r}: incomplete RGB square anchors')
  nodes=_nodes(shader);state={}
  for ch in RGB:
   base=_sample(nodes,'colorMapSampler',ch)
   if len(base)!=1:raise RgbFactorAnchorError(f'{material!r}: base colorMapSampler.{ch} sample count {len(base)}')
   state[ch]=base[0]
  target={ch:int(anchors[ch]['encodedRgbNode']) for ch in RGB};allowed={ch:_anc(nodes,target[ch]) for ch in RGB};step_rows=[]
  for step in recipe['layerProgram']:
   layer=int(step['layerIndex']);op=str(step['operation']);ls={}
   for ch in RGB:
    q=_sample(nodes,f'colorMapSampler{layer}',ch)
    if len(q)!=1:raise RgbFactorAnchorError(f'{material!r} layer {layer}: colorMapSampler{layer}.{ch} sample count {len(q)}')
    ls[ch]=q[0]
   per={ch:_candidates(nodes,state[ch],ls[ch],op,allowed[ch]) for ch in RGB}
   state,fid,fh=_choose(nodes,per,material,layer,op);fhs.add(fh);steps+=1
   step_rows.append({'layerIndex':layer,'operation':op,'weightClass':step.get('weightClass'),'stateNodes':dict(state),'stateSha256':{ch:_h(nodes,state[ch]) for ch in RGB},'sharedFactorNode':fid,'sharedFactorSha256':fh})
  match={ch:_h(nodes,state[ch])==str(anchors[ch]['encodedRgbSha256']) for ch in RGB}
  if strict and not all(match.values()):raise RgbFactorAnchorError(f'{material!r}: reconstructed RGB state does not equal pre-square anchor {match}')
  rows.append({'material':material,'techniqueSet':recipe['techniqueSet'],'shaderSha256':sha,'steps':step_rows,'finalStateNodes':dict(state),'preSquareAnchorMatch':match,'allChannelsMatch':all(match.values())})
 summary={'materialCount':len(rows),'layerStepCount':steps,'uniqueSharedFactorDagCount':len(fhs),'fullyMatchedMaterialCount':sum(1 for r in rows if r['allChannelsMatch']),'strict':bool(strict)}
 return {'format':FORMAT,'materials':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Canonical generated A/B/M/T RGB recurrence matched from exact colorMapSampler* samples inside the full slot-4 DAG and required to terminate at the v26 pre-square RGB anchors. Every layer exposes one factor/condition DAG shared by RGB. Physical interpretation of the scalar remains unassigned.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--recipes',type=Path,required=True);p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--relaxed',action='store_true');a=p.parse_args();d=build(json.loads(a.recipes.read_text()),json.loads(a.final_output.read_text()),json.loads(a.rgb_square.read_text()),strict=not a.relaxed);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
