#!/usr/bin/env python3
"""Join exact generated specular consumer sites to exact reflection fetches.

This cross-proofs three forensic sidecars against the same full slot-4 DAG:
- completed generated specular XYZW state anchor;
- downstream specular consumer frontier;
- generated reflectionProbeSampler sample-instance index.

For every frontier site involving reflectionProbeSampler it identifies the exact
reflection sample instruction/node(s) and classifies only direct dataflow facts:

- whether the mixing node is exactly `specularRoot * reflectionSampleChannel`;
- whether a completed specular root is itself an exact reflection coordinate
  operand node;
- whether a completed specular root is itself the exact affine reflection LOD
  source x.

No physical names (roughness, gloss, F0, reflectivity) are assigned.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict,Counter
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-specular-reflection-join-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
SPEC_FORMAT='t6-generated-final-output-specular-state-anchor-v1'
FRONTIER_FORMAT='t6-generated-final-output-specular-consumer-frontier-v1'
REFLECTION_FORMAT='t6-generated-final-output-reflection-sample-index-v1'
RESOURCE='reflectionProbeSampler';CHANNELS='xyzw'
class SpecularReflectionJoinError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _map_rows(doc,key,label):
 out={}
 for row in doc.get(key,[]):
  name=str(row.get('material') or row.get('shaderSha256') or '')
  if not name or name in out:raise SpecularReflectionJoinError(f'{label}: invalid/duplicate key {name!r}')
  out[name]=row
 return out
def _nodes(shader):
 out={}
 for r in shader.get('nodes',[]):
  i=int(r.get('id',-1))
  if i<0 or i in out:raise SpecularReflectionJoinError(f'invalid/duplicate node {i}')
  out[i]=r
 return out
def _anc(nodes,root,memo):
 if root in memo:return memo[root]
 s=set()
 def w(i):
  if i in s:return
  if i not in nodes:raise SpecularReflectionJoinError(f'missing node {i}')
  s.add(i)
  for c in nodes[i].get('args',[]):w(int(c))
 w(root);memo[root]=s;return s
def _reflection_nodes(nodes,root):return sorted(i for i in _anc(nodes,root,{}) if nodes[i].get('kind')=='textureSample' and str(nodes[i].get('resource') or '')==RESOURCE)
def _sample_maps(index_doc):
 by_sha={}
 for row in index_doc.get('shaders',[]):
  sha=str(row.get('shaderSha256') or '');node_map={}
  for sample in row.get('samples',[]):
   for node in sample.get('sampleNodeIds',[]):
    node=int(node)
    if node in node_map:raise SpecularReflectionJoinError(f'shader {sha}: reflection sample node {node} belongs to multiple instructions')
    node_map[node]=sample
  by_sha[sha]=node_map
 return by_sha
def _direct_root_channels(sample,roots):
 cls=sample.get('classification',{});source=cls.get('sourceNode');lod=[]
 if source is not None:
  lod=[ch for ch,root in roots.items() if int(source)==int(root)]
 coords=set(map(int,sample.get('coordinateNodes',[])));coord=[ch for ch,root in roots.items() if int(root) in coords]
 return coord,lod

def build(final_output,spec_anchor,frontier,index_doc):
 if final_output.get('format')!=FINAL_FORMAT:raise SpecularReflectionJoinError(f'unexpected final-output format {final_output.get("format")!r}')
 if spec_anchor.get('format')!=SPEC_FORMAT:raise SpecularReflectionJoinError(f'unexpected specular format {spec_anchor.get("format")!r}')
 if frontier.get('format')!=FRONTIER_FORMAT:raise SpecularReflectionJoinError(f'unexpected frontier format {frontier.get("format")!r}')
 if index_doc.get('format')!=REFLECTION_FORMAT:raise SpecularReflectionJoinError(f'unexpected reflection index format {index_doc.get("format")!r}')
 shaders={str(s.get('sha256') or ''):s for s in final_output.get('shaders',[])};spec=_map_rows(spec_anchor,'materials','specular');front=_map_rows(frontier,'materials','frontier');samples_by_sha=_sample_maps(index_doc);rows=[];direct_products=direct_coord=direct_lod=relations=0;op_counts=Counter()
 for material,sr in sorted(spec.items()):
  fr=front.get(material)
  if fr is None:raise SpecularReflectionJoinError(f'{material!r}: missing consumer-frontier row')
  sha=str(sr.get('shaderSha256') or '');shader=shaders.get(sha)
  if shader is None:raise SpecularReflectionJoinError(f'{material!r}: missing final-output shader {sha}')
  nodes=_nodes(shader);sample_map=samples_by_sha.get(sha,{});roots={ch:int(sr.get('finalStateNodes',{}).get(ch,-1)) for ch in CHANNELS}
  if any(root not in nodes for root in roots.values()):raise SpecularReflectionJoinError(f'{material!r}: invalid specular roots')
  channels={};
  for ch in CHANNELS:
   fc=fr.get('channels',{}).get(ch)
   if not isinstance(fc,dict):raise SpecularReflectionJoinError(f'{material!r}: frontier lacks channel {ch}')
   if int(fc.get('rootNode',-1))!=roots[ch]:raise SpecularReflectionJoinError(f'{material!r} channel {ch}: frontier/specular root mismatch')
   rel=[]
   for site in fc.get('allMixingSites',[]):
    if RESOURCE not in site.get('externalResources',[]) and str(site.get('parentTextureResource') or '')!=RESOURCE:continue
    site_node=int(site['node']);sample_nodes=set()
    if str(site.get('parentTextureResource') or '')==RESOURCE:sample_nodes.add(site_node)
    for child in site.get('externalChildNodes',[]):sample_nodes.update(_reflection_nodes(nodes,int(child)))
    if not sample_nodes:raise SpecularReflectionJoinError(f'{material!r} channel {ch} site {site_node}: reflection resource reported but no exact sample node found')
    site_row=nodes[site_node];args=list(map(int,site_row.get('args',[])))
    for sample_node in sorted(sample_nodes):
     sample=sample_map.get(sample_node)
     if sample is None:raise SpecularReflectionJoinError(f'{material!r}: reflection node {sample_node} absent from v33 sample index')
     coord_channels,lod_channels=_direct_root_channels(sample,roots);direct_coord+=len(coord_channels);direct_lod+=len(lod_channels)
     direct_product=(site_row.get('kind')=='op' and site_row.get('op')=='mul' and len(args)==2 and roots[ch] in args and sample_node in args)
     if direct_product:direct_products+=1
     op=str(site.get('operation') or site.get('kind') or '');op_counts[op]+=1;relations+=1
     rel.append({'specularChannel':ch,'specularRootNode':roots[ch],'mixingSiteNode':site_node,'mixingSiteDistance':site.get('distance'),'mixingKind':site.get('kind'),'mixingOperation':site.get('operation'),'reflectionSampleNode':sample_node,'reflectionInstructionDword':sample.get('atDword'),'reflectionOpcode':sample.get('opcode'),'reflectionSampleChannels':sample.get('sampleChannels'),'reflectionLodBiasClassification':sample.get('classification'),'directSpecularTimesReflectionSample':direct_product,'directReflectionCoordinateSpecularChannels':coord_channels,'directReflectionLodSourceSpecularChannels':lod_channels,'outputLanes':site.get('outputLanes')})
   channels[ch]=rel
  rows.append({'material':material,'shaderSha256':sha,'channels':channels,'reflectionRelationCount':sum(len(v) for v in channels.values()),'hasReflectionRelation':any(channels.values())})
 summary={'materialCount':len(rows),'materialWithReflectionRelationCount':sum(1 for r in rows if r['hasReflectionRelation']),'reflectionRelationCount':relations,'directSpecularTimesReflectionSampleCount':direct_products,'directReflectionCoordinateSpecularRootCount':direct_coord,'directReflectionLodSourceSpecularRootCount':direct_lod,'mixingOperationCounts':dict(sorted(op_counts.items()))}
 return {'format':FORMAT,'materials':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Exact cross-join of completed specular roots, downstream consumer-frontier sites, and exact reflectionProbeSampler instruction instances in the same slot-4 DAG. Direct products, direct coordinate roots, and direct affine LOD source roots are reported only when node identity proves them. No physical semantic name is assigned to specular channels.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--frontier',type=Path,required=True);p.add_argument('--reflection-index',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.specular.read_text()),json.loads(a.frontier.read_text()),json.loads(a.reflection_index.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
