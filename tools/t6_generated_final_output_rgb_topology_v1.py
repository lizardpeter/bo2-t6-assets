#!/usr/bin/env python3
"""Classify exact top-level o0.rgb expression topology by proven anchor membership.

This is a forensic topology view over the full generated slot-4 DAG.  For each
written o0 RGB lane it recursively descends only the *syntactic* ADD/NEG tree and
records each leaf with its original path/sign.  It does not reassociate ADDs or
MULs and therefore does not claim an algebraically normalized final formula.

Each leaf is tagged by exact node ancestry against already-proven anchors:
- v26 squared generated RGB;
- v28 directional-lightmap RGB equations;
- v30 completed generated specular XYZW roots;
- v33 exact reflectionProbeSampler sample nodes.

Immediate MUL children are additionally tagged so literal two-input product
shapes remain visible without multiplication flattening.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-rgb-topology-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
SQUARE_FORMAT='t6-generated-final-output-rgb-square-anchor-v1'
DIR_FORMAT='t6-generated-final-output-directional-lightmap-anchor-v2'
SPEC_FORMAT='t6-generated-final-output-specular-state-anchor-v1'
REFL_FORMAT='t6-generated-final-output-reflection-sample-index-v1'
RGB='xyz';RESOURCE='reflectionProbeSampler'
class FinalRgbTopologyError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _map(doc,key='shaders',field='sha256'):
 out={}
 for r in doc.get(key,[]):
  k=str(r.get(field) or '')
  if not k or k in out:raise FinalRgbTopologyError(f'invalid/duplicate {field} {k!r}')
  out[k]=r
 return out
def _nodes(shader):
 out={}
 for r in shader.get('nodes',[]):
  i=int(r.get('id',-1))
  if i<0 or i in out:raise FinalRgbTopologyError(f'invalid/duplicate node {i}')
  out[i]=r
 return out
def _anc(nodes,root,memo):
 if root in memo:return memo[root]
 s=set()
 def w(i):
  if i in s:return
  if i not in nodes:raise FinalRgbTopologyError(f'missing node {i}')
  s.add(i)
  for c in nodes[i].get('args',[]):w(int(c))
 w(root);memo[root]=s;return s
def _resources(nodes,root,memo):
 if root in memo:return set(memo[root])
 r=nodes[root];out={str(r.get('resource') or '')} if r.get('kind')=='textureSample' and str(r.get('resource') or '') else set()
 for c in r.get('args',[]):out.update(_resources(nodes,int(c),memo))
 memo[root]=frozenset(out);return out
def _o0(shader):
 q=[r for r in shader.get('outputs',[]) if int(r.get('register',-1))==0]
 if len(q)!=1:raise FinalRgbTopologyError(f"shader {shader.get('sha256')}: expected one o0")
 out={}
 for l in q[0].get('lanes',[]):
  ch=str(l.get('channel') or '')
  if ch in RGB and bool(l.get('written')):out[ch]=int(l['node'])
 if set(out)!=set(RGB):raise FinalRgbTopologyError(f"shader {shader.get('sha256')}: incomplete o0.rgb")
 return out
def _square(row):
 out={}
 for a in row.get('anchors',[]):
  ch=str(a.get('channel') or '')
  if ch in RGB and a.get('anchored') and int(a.get('candidateCount',0))==1:out[ch]=int(a['candidates'][0]['squareNode'])
 if set(out)!=set(RGB):raise FinalRgbTopologyError(f"shader {row.get('sha256')}: incomplete square anchors")
 return out
def _spec_by_sha(spec):
 out={}
 for r in spec.get('materials',[]):
  sha=str(r.get('shaderSha256') or '');roots={ch:int(r.get('finalStateNodes',{}).get(ch,-1)) for ch in 'xyzw'}
  if sha in out and out[sha]!=roots:raise FinalRgbTopologyError(f'shader {sha}: materials disagree on specular roots')
  out[sha]=roots
 return out
def _reflection_nodes(refl):
 out={}
 for r in refl.get('shaders',[]):
  sha=str(r.get('shaderSha256') or '');ids=set()
  for s in r.get('samples',[]):ids.update(map(int,s.get('sampleNodeIds',[])))
  out[sha]=ids
 return out
def _leaves(nodes,root,path='',sign=1):
 r=nodes[root]
 if r.get('kind')=='op' and r.get('op')=='add' and len(r.get('args',[]))==2:
  a,b=map(int,r['args']);return _leaves(nodes,a,path+'L',sign)+_leaves(nodes,b,path+'R',sign)
 if r.get('kind')=='op' and r.get('op')=='neg' and len(r.get('args',[]))==1:return _leaves(nodes,int(r['args'][0]),path+'N',-sign)
 return [(root,path or 'ROOT',sign)]
def _anchor_tags(anc,square_node,dir_nodes,spec_roots,refl_nodes):
 tags=[]
 if square_node in anc:tags.append('squareRgb')
 for idx,node in sorted(dir_nodes.items()):
  if node in anc:tags.append(f'directional:{idx}')
 for ch,node in sorted(spec_roots.items()):
  if node in anc:tags.append(f'specular:{ch}')
 if anc & refl_nodes:tags.append('reflectionProbe')
 return tags
def build(final,square,directional,specular,reflection):
 for doc,fmt,label in ((final,FINAL_FORMAT,'final'),(square,SQUARE_FORMAT,'square'),(directional,DIR_FORMAT,'directional'),(specular,SPEC_FORMAT,'specular'),(reflection,REFL_FORMAT,'reflection')):
  if doc.get('format')!=fmt:raise FinalRgbTopologyError(f'unexpected {label} format {doc.get("format")!r}')
 shaders=_map(final);sq=_map(square);dr=_map(directional);spec=_spec_by_sha(specular);refl=_reflection_nodes(reflection)
 if set(shaders)!=set(sq) or set(shaders)!=set(dr):raise FinalRgbTopologyError('shader sets disagree across final/square/directional inputs')
 rows=[];sig=Counter();leaf_count=0;direct_mul=0
 for sha in sorted(shaders):
  shader=shaders[sha];nodes=_nodes(shader);outs=_o0(shader);squares=_square(sq[sha]);spec_roots=spec.get(sha,{});refl_nodes=refl.get(sha,set());lanes={};amemo={};rmemo={}
  eqs=dr[sha].get('equations',[])
  for ch in RGB:
   dir_nodes={idx:int(eq.get('rgbNodes',{}).get(ch,-1)) for idx,eq in enumerate(eqs)}
   if any(i not in nodes for i in dir_nodes.values()):raise FinalRgbTopologyError(f'shader {sha} {ch}: invalid directional RGB node')
   lr=[]
   for node,path,sign in _leaves(nodes,outs[ch]):
    anc=_anc(nodes,node,amemo);tags=_anchor_tags(anc,squares[ch],dir_nodes,spec_roots,refl_nodes);r=nodes[node];children=[]
    if r.get('kind')=='op' and r.get('op')=='mul' and len(r.get('args',[]))==2:
     for child in map(int,r['args']):
      ca=_anc(nodes,child,amemo);children.append({'node':child,'tags':_anchor_tags(ca,squares[ch],dir_nodes,spec_roots,refl_nodes),'resources':sorted(_resources(nodes,child,rmemo))})
     if any(c['tags'] for c in children):direct_mul+=1
    signature='+'.join(tags) if tags else 'unanchored';sig[signature]+=1;leaf_count+=1
    lr.append({'path':path,'sign':sign,'node':node,'kind':r.get('kind'),'operation':r.get('op') if r.get('kind')=='op' else r.get('opcode') if r.get('kind')=='textureSample' else None,'anchorTags':tags,'anchorSignature':signature,'resources':sorted(_resources(nodes,node,rmemo)),'immediateMulChildren':children})
   lanes[ch]={'outputRootNode':outs[ch],'syntacticAdditiveLeafCount':len(lr),'leaves':lr}
  rows.append({'sha256':sha,'techniqueSets':shader.get('techniqueSets',[]),'lanes':lanes})
 summary={'shaderCount':len(rows),'rgbLaneCount':3*len(rows),'syntacticAdditiveLeafCount':leaf_count,'anchoredImmediateMulLeafCount':direct_mul,'leafAnchorSignatureCounts':dict(sorted(sig.items()))}
 return {'format':FORMAT,'shaders':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Syntactic top-level ADD/NEG descent of exact o0.rgb DAGs with original path/sign retained. Leaves are tagged only by exact ancestry from already-proven square RGB, directional-lightmap, completed specular, and reflection sample nodes. MULs are not flattened and ADD association is not promoted as a normalized floating-point formula.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--rgb-square',type=Path,required=True);p.add_argument('--directional',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--reflection-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.rgb_square.read_text()),json.loads(a.directional.read_text()),json.loads(a.specular.read_text()),json.loads(a.reflection_index.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
