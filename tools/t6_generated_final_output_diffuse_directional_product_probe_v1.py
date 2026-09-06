#!/usr/bin/env python3
"""Probe exact direct products between squared generated RGB and directional RGB.

Consumes:
- full final-output DAG v3;
- v26 RGB-square anchors;
- v28 directional-lightmap anchors;
- v29 layered-normal directional-equation join.

For every shader/output RGB lane this tool searches only for a literal DAG node:

    mul(squareNode, directionalRgbNode)

(or reversed argument order) that is reachable from the matching written o0
lane.  No multiplication reassociation or other algebraic normalization is used.
The v29 sidecar labels which directional equation, if any, is the exact generated
layered-normal equation.

This is diagnostic evidence.  Missing direct products are not treated as proof
that no diffuse/lightmap relationship exists; they only mean the exact relation
is not this direct two-input MUL shape.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-diffuse-directional-product-probe-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
SQUARE_FORMAT='t6-generated-final-output-rgb-square-anchor-v1'
DIRECTIONAL_FORMAT='t6-generated-final-output-directional-lightmap-anchor-v2'
NORMAL_FORMAT='t6-generated-final-output-layered-normal-anchor-v1'
RGB='xyz'
class DiffuseDirectionalProductProbeError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _nodes(shader):
 rows=shader.get('nodes');
 if not isinstance(rows,list):raise DiffuseDirectionalProductProbeError('shader has no nodes')
 out={}
 for r in rows:
  i=int(r.get('id',-1))
  if i<0 or i in out:raise DiffuseDirectionalProductProbeError(f'invalid/duplicate node {i}')
  out[i]=r
 return out
def _anc(nodes,root):
 s=set()
 def w(i):
  if i in s:return
  if i not in nodes:raise DiffuseDirectionalProductProbeError(f'missing node {i}')
  s.add(i)
  for c in nodes[i].get('args',[]):w(int(c))
 w(root);return s
def _o0(shader):
 rows=[r for r in shader.get('outputs',[]) if int(r.get('register',-1))==0]
 if len(rows)!=1:raise DiffuseDirectionalProductProbeError(f"shader {shader.get('sha256')}: expected one o0")
 out={}
 for l in rows[0].get('lanes',[]):
  ch=str(l.get('channel') or '')
  if ch in RGB and bool(l.get('written')):out[ch]=int(l['node'])
 if set(out)!=set(RGB):raise DiffuseDirectionalProductProbeError(f"shader {shader.get('sha256')}: incomplete written o0.rgb")
 return out
def _rowmap(doc,key='shaders'):
 out={}
 for r in doc.get(key,[]):
  sha=str(r.get('sha256') or '')
  if not sha or sha in out:raise DiffuseDirectionalProductProbeError(f'invalid/duplicate shader {sha!r}')
  out[sha]=r
 return out
def _square_nodes(row):
 out={}
 for a in row.get('anchors',[]):
  ch=str(a.get('channel') or '')
  if ch in RGB and bool(a.get('anchored')) and int(a.get('candidateCount',0))==1:out[ch]=int(a['candidates'][0]['squareNode'])
 if set(out)!=set(RGB):raise DiffuseDirectionalProductProbeError(f"shader {row.get('sha256')}: incomplete square anchors")
 return out
def _layered_normal_equation_indices(normal_row):
 return sorted(int(m['directionalEquationIndex']) for m in normal_row.get('matches',[]))
def _direct_mul(nodes,allowed,a,b):
 out=[]
 for i,r in nodes.items():
  if i not in allowed or r.get('kind')!='op' or r.get('op')!='mul' or len(r.get('args',[]))!=2:continue
  x,y=map(int,r['args'])
  if (x==a and y==b) or (x==b and y==a):out.append(i)
 return sorted(out)
def build(final_output,square_doc,directional_doc,normal_doc):
 if final_output.get('format')!=FINAL_FORMAT:raise DiffuseDirectionalProductProbeError('unsupported final-output format')
 if square_doc.get('format')!=SQUARE_FORMAT:raise DiffuseDirectionalProductProbeError('unsupported square-anchor format')
 if directional_doc.get('format')!=DIRECTIONAL_FORMAT:raise DiffuseDirectionalProductProbeError('unsupported directional format')
 if normal_doc.get('format')!=NORMAL_FORMAT:raise DiffuseDirectionalProductProbeError('unsupported layered-normal format')
 shaders=_rowmap(final_output);sq=_rowmap(square_doc);dr=_rowmap(directional_doc);nr=_rowmap(normal_doc)
 if set(shaders)!=set(sq) or set(shaders)!=set(dr) or set(shaders)!=set(nr):raise DiffuseDirectionalProductProbeError('shader sets disagree across inputs')
 rows=[];total=0;normal_direct=0;normal_all_rgb=0;any_direct_shaders=0
 for sha in sorted(shaders):
  shader=shaders[sha];nodes=_nodes(shader);outs=_o0(shader);squares=_square_nodes(sq[sha]);normal_indices=set(_layered_normal_equation_indices(nr[sha]));equations=[];shader_any=False
  for idx,eq in enumerate(dr[sha].get('equations',[])):
   rgb=eq.get('rgbNodes',{})
   if set(rgb)!=set(RGB):raise DiffuseDirectionalProductProbeError(f'shader {sha} equation {idx}: incomplete rgbNodes')
   lanes={};all3=True
   for ch in RGB:
    allowed=_anc(nodes,outs[ch]);matches=_direct_mul(nodes,allowed,squares[ch],int(rgb[ch]));direct=len(matches)==1
    if len(matches)>1:raise DiffuseDirectionalProductProbeError(f'shader {sha} equation {idx} channel {ch}: ambiguous direct product count {len(matches)}')
    lanes[ch]={'squareNode':squares[ch],'directionalRgbNode':int(rgb[ch]),'directProductCount':len(matches),'directProductNode':matches[0] if direct else None,'directProduct':direct}
    total+=int(direct);all3=all3 and direct;shader_any=shader_any or direct
   is_normal=idx in normal_indices
   if is_normal:normal_direct+=sum(1 for x in lanes.values() if x['directProduct']);normal_all_rgb+=int(all3)
   equations.append({'directionalEquationIndex':idx,'isLayeredNormalEquation':is_normal,'channels':lanes,'allRgbDirectProducts':all3})
  any_direct_shaders+=int(shader_any);rows.append({'sha256':sha,'techniqueSets':shader.get('techniqueSets',[]),'layeredNormalEquationIndices':sorted(normal_indices),'directionalEquationCount':len(equations),'equations':equations,'hasAnyDirectProduct':shader_any})
 summary={'shaderCount':len(rows),'directionalEquationCount':sum(r['directionalEquationCount'] for r in rows),'directProductCount':total,'shaderWithAnyDirectProductCount':any_direct_shaders,'layeredNormalEquationDirectRgbLaneCount':normal_direct,'layeredNormalEquationAllRgbDirectProductCount':normal_all_rgb}
 return {'format':FORMAT,'shaders':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Literal same-DAG search for direct two-input MUL nodes between v26 squared generated RGB and exact v28 directional-lightmap RGB, with v29 identifying the layered-normal directional equation. No reassociation or fallback formula is used; absence of a direct MUL is diagnostic only.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--directional',type=Path,required=True);p.add_argument('--layered-normal',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.rgb_square.read_text()),json.loads(a.directional.read_text()),json.loads(a.layered_normal.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
