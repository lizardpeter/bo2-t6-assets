#!/usr/bin/env python3
"""Trace downstream consumer frontiers of completed generated specular XYZW state.

Inputs:
- exact full slot-4 final-output symbolic DAG v3;
- exact completed specular-state anchor v1.

For each canonical material/channel this tool walks upward from the completed
specular root toward written o0.  The four XYZW roots are treated as one owned
state: siblings whose subtrees contain any specular root are not considered
external inputs.

At each downstream mixing node it records:
- graph distance from the completed state;
- operation/kind;
- exact external sibling texture-resource ancestry;
- the sampled resource itself when a textureSample node consumes specular state
  as coordinate/LOD/gradient input;
- output lanes reachable through that site.

This is forensic dependency tracing only.  It does not rename channels or infer
roughness/F0/reflection meaning from proximity to a resource.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict,deque,Counter
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-specular-consumer-frontier-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
SPEC_FORMAT='t6-generated-final-output-specular-state-anchor-v1'
CHANNELS='xyzw'
class SpecularConsumerFrontierError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _nodes(shader):
 rows=shader.get('nodes');
 if not isinstance(rows,list):raise SpecularConsumerFrontierError('shader has no nodes')
 out={}
 for r in rows:
  i=int(r.get('id',-1))
  if i<0 or i in out:raise SpecularConsumerFrontierError(f'invalid/duplicate node id {i}')
  out[i]=r
 return out
def _parents(nodes):
 p=defaultdict(set)
 for i,r in nodes.items():
  for c in r.get('args',[]):
   c=int(c)
   if c not in nodes:raise SpecularConsumerFrontierError(f'node {i} references missing child {c}')
   p[c].add(i)
 return p
def _anc(nodes,root,memo=None):
 memo={} if memo is None else memo
 if root in memo:return memo[root]
 seen=set()
 def w(i):
  if i in seen:return
  seen.add(i)
  for c in nodes[i].get('args',[]):w(int(c))
 w(root);memo[root]=seen;return seen
def _resources(nodes,root,memo=None):
 memo={} if memo is None else memo
 if root in memo:return set(memo[root])
 out=set();r=nodes[root]
 if r.get('kind')=='textureSample':out.add(str(r.get('resource') or ''))
 for c in r.get('args',[]):out.update(_resources(nodes,int(c),memo))
 memo[root]=frozenset(out);return out
def _outputs(shader):
 rows=[r for r in shader.get('outputs',[]) if int(r.get('register',-1))==0]
 if len(rows)!=1:raise SpecularConsumerFrontierError(f"shader {shader.get('sha256')}: expected exactly one o0")
 out={}
 for lane in rows[0].get('lanes',[]):
  ch=str(lane.get('channel') or '')
  if ch in CHANNELS and bool(lane.get('written')):out[ch]=int(lane['node'])
 return out
def _canon(nodes,i,m=None):
 m={} if m is None else m
 if i in m:return m[i]
 r=nodes[i];k=str(r.get('kind') or '')
 if k=='op':
  op=str(r.get('op') or '');a=[_canon(nodes,int(c),m) for c in r.get('args',[])]
  if op in {'add','mul','min','max','eq','ne','and','or','and_bool'}:a=sorted(a,key=lambda x:json.dumps(x,sort_keys=True,separators=(',',':')))
  v=('op',op,tuple(a))
 elif k=='textureSample':v=('sample',str(r.get('resource') or ''),str(r.get('channel') or ''),str(r.get('sampler') or ''),tuple(_canon(nodes,int(c),m) for c in r.get('args',[])))
 elif k=='literal32':v=('literal32',str(r.get('bits') or '').lower())
 else:v=(k,tuple(sorted((q,r[q]) for q in r if q not in {'id','args','instructionDword'})),tuple(_canon(nodes,int(c),m) for c in r.get('args',[])))
 m[i]=v;return v
def _h(nodes,i):return _jhash(_canon(nodes,i))
def _contains_spec(nodes,root,spec_roots,amemo):return bool(_anc(nodes,root,amemo)&spec_roots)
def _reachable_outputs(nodes,site,output_anc):return sorted(ch for ch,anc in output_anc.items() if site in anc)

def _frontier_for_root(nodes,parents,root,spec_roots,output_anc):
 union=set().union(*output_anc.values()) if output_anc else set();q=deque([(root,0)]);seen={root};mix=[];amemo={};rmemo={}
 while q:
  current,d=q.popleft()
  for parent in sorted(parents.get(current,())):
   if parent not in union:continue
   if parent not in seen:seen.add(parent);q.append((parent,d+1))
   row=nodes[parent];external_children=[];ext_resources=set()
   for child in map(int,row.get('args',[])):
    if _contains_spec(nodes,child,spec_roots,amemo):continue
    external_children.append(child);ext_resources.update(_resources(nodes,child,rmemo))
   parent_resource=None
   if row.get('kind')=='textureSample':
    parent_resource=str(row.get('resource') or '')
    if parent_resource:ext_resources.add(parent_resource)
   if not external_children and parent_resource is None:continue
   mix.append({'distance':d+1,'node':parent,'nodeSha256':_h(nodes,parent),'kind':row.get('kind'),'operation':row.get('op') if row.get('kind')=='op' else row.get('opcode') if row.get('kind')=='textureSample' else None,'parentTextureResource':parent_resource,'externalChildNodes':external_children,'externalResources':sorted(x for x in ext_resources if x),'outputLanes':_reachable_outputs(nodes,parent,output_anc)})
 mix.sort(key=lambda r:(r['distance'],r['node']))
 any_distance=None if not mix else mix[0]['distance'];resource_rows=[r for r in mix if r['externalResources']];resource_distance=None if not resource_rows else resource_rows[0]['distance']
 return {'rootNode':root,'rootSha256':_h(nodes,root),'mixingSiteCount':len(mix),'nearestMixDistance':any_distance,'nearestMixingSites':[r for r in mix if r['distance']==any_distance] if any_distance is not None else [],'resourceMixingSiteCount':len(resource_rows),'nearestResourceMixDistance':resource_distance,'nearestResourceMixingSites':[r for r in resource_rows if r['distance']==resource_distance] if resource_distance is not None else [],'allMixingSites':mix}

def build(final_output,spec_anchor):
 if final_output.get('format')!=FINAL_FORMAT:raise SpecularConsumerFrontierError(f"unexpected final-output format {final_output.get('format')!r}")
 if spec_anchor.get('format')!=SPEC_FORMAT:raise SpecularConsumerFrontierError(f"unexpected specular anchor format {spec_anchor.get('format')!r}")
 shaders={str(s.get('sha256') or ''):s for s in final_output.get('shaders',[])};rows=[];resource_counts=Counter();resource_mix_channels=0
 for sr in spec_anchor.get('materials',[]):
  material=str(sr.get('material') or '');sha=str(sr.get('shaderSha256') or '');shader=shaders.get(sha)
  if shader is None:raise SpecularConsumerFrontierError(f'{material!r}: missing final-output shader {sha}')
  nodes=_nodes(shader);parents=_parents(nodes);outputs=_outputs(shader);output_anc={ch:_anc(nodes,root,{}) for ch,root in outputs.items()};roots={ch:int(sr.get('finalStateNodes',{}).get(ch,-1)) for ch in CHANNELS}
  if any(i not in nodes for i in roots.values()):raise SpecularConsumerFrontierError(f'{material!r}: invalid completed specular roots {roots}')
  spec_roots=set(roots.values());channels={}
  for ch in CHANNELS:
   q=_frontier_for_root(nodes,parents,roots[ch],spec_roots,output_anc);channels[ch]=q
   if q['resourceMixingSiteCount']>0:resource_mix_channels+=1
   for site in q['nearestResourceMixingSites']:
    for res in site['externalResources']:resource_counts[res]+=1
  rows.append({'material':material,'shaderSha256':sha,'channels':channels,'downstreamOutputLanes':sr.get('downstreamOutputLanes'),'anyResourceMix':any(q['resourceMixingSiteCount']>0 for q in channels.values())})
 summary={'materialCount':len(rows),'channelCount':4*len(rows),'channelWithResourceMixCount':resource_mix_channels,'materialWithAnyResourceMixCount':sum(1 for r in rows if r['anyResourceMix']),'nearestResourceNameCounts':dict(sorted(resource_counts.items()))}
 return {'format':FORMAT,'materials':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Exact upward dataflow trace from completed specular XYZW roots already proven to reach o0. The four roots are treated as one owned state; nearest downstream mixing operations and exact external texture resource ancestry are reported. Resource proximity is not promoted to physical channel meaning or a final lighting equation.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.specular.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
