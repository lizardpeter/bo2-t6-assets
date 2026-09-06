#!/usr/bin/env python3
"""Bind every sampled final-output texture resource through exact T6 `.tech` data.

Consumes the authoritative generated slot-4 final-output DAG and the exact OAT
shader dump root. For every RDEF-named texture resource actually sampled by the
DAG, each owning TechniqueSet is resolved back to the same slot-4 pass/CSO and
its `.tech` assignment is retained verbatim/classified syntactically as:
- material.*
- code.*
- other expression

Resource/sampler register evidence from every sample node is retained. This does
not yet join material RHS names to GfxImage objects or code RHS names to T6 code
sampler enums; it closes the exact shader-resource -> TechniqueSet source edge.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any

import t6_generated_final_output_cbuffer_signature_v1 as cb_sig
from t6_oat_slot_shader_resolver_v2 import resolve_slot_shader

FORMAT='t6-generated-final-output-texture-resource-binding-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
class TextureResourceBindingError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _sampled_resources(shader:dict)->dict[str,dict]:
 out={}
 for node in shader.get('nodes',[]):
  if node.get('kind')!='textureSample':continue
  resource=str(node.get('resource') or '')
  if not resource:raise TextureResourceBindingError(f"shader {shader.get('sha256')}: texture sample node {node.get('id')} lacks RDEF resource name")
  row=out.setdefault(resource,{'resource':resource,'sampleNodeIds':[],'resourceRegisters':set(),'samplerNames':set(),'samplerRegisters':set(),'opcodes':set(),'channels':set()})
  row['sampleNodeIds'].append(int(node['id']))
  if node.get('resourceRegister') is not None:row['resourceRegisters'].add(int(node['resourceRegister']))
  if node.get('sampler'):row['samplerNames'].add(str(node['sampler']))
  if node.get('samplerRegister') is not None:row['samplerRegisters'].add(int(node['samplerRegister']))
  if node.get('opcode'):row['opcodes'].add(str(node['opcode']))
  if node.get('channel'):row['channels'].add(str(node['channel']))
 for row in out.values():
  row['sampleNodeIds']=sorted(row['sampleNodeIds']);row['resourceRegisters']=sorted(row['resourceRegisters']);row['samplerNames']=sorted(row['samplerNames']);row['samplerRegisters']=sorted(row['samplerRegisters']);row['opcodes']=sorted(row['opcodes']);row['channels']=sorted(row['channels'])
 return out

def _resolve_technique(oat_root:Path,technique:str,sha:str,cache:dict)->tuple[str,dict]:
 if technique in cache:return cache[technique]
 resolved=resolve_slot_shader(oat_root,technique,slot_index=4);shaders=resolved.get('pixelShaders',[])
 if len(shaders)!=1:raise TextureResourceBindingError(f"{technique!r}: slot-4 resolves {len(shaders)} pixel shaders")
 ps=shaders[0]
 if str(ps.get('sha256') or '').lower()!=sha.lower():raise TextureResourceBindingError(f"{technique!r}: slot-4 PS {ps.get('sha256')} != final-output {sha}")
 path=Path(oat_root)/str(resolved['techniqueFile'])
 if not path.is_file():raise TextureResourceBindingError(f"{technique!r}: technique file missing {path}")
 text=path.read_text(encoding='utf-8',errors='strict');assign=cb_sig.parse_tech_assignments(text)
 cache[technique]=(text,{**resolved,'assignmentMap':assign});return cache[technique]

def build(final_doc:dict,*,oat_root:Path)->dict:
 if final_doc.get('format')!=FINAL_FORMAT:raise TextureResourceBindingError(f"unexpected final-output format {final_doc.get('format')!r}")
 root=Path(oat_root);cache={};rows=[];source_counts=Counter();resource_counts=Counter();sample_count=0
 for shader in final_doc.get('shaders',[]):
  sha=str(shader.get('sha256') or '').lower();techniques=sorted(str(x) for x in shader.get('techniqueSets',[]))
  if not sha or not techniques:raise TextureResourceBindingError('final-output shader lacks SHA/TechniqueSets')
  resources=_sampled_resources(shader);sample_count+=sum(len(row['sampleNodeIds']) for row in resources.values());bound=[]
  for resource in sorted(resources):
   evidence=resources[resource];assignments=[]
   for technique in techniques:
    _text,resolved=_resolve_technique(root,technique,sha,cache);expr=resolved['assignmentMap'].get(resource)
    if expr is None:raise TextureResourceBindingError(f"shader {sha} TechniqueSet {technique!r}: sampled resource {resource!r} has no exact .tech assignment")
    identity=cb_sig._source_identity(expr)
    source_class=str(identity['sourceClass']);source_name=identity.get('sourceName')
    assignments.append({'techniqueSet':technique,'techniqueAsset':resolved.get('techniqueAsset'),'techniqueFile':resolved.get('techniqueFile'),'sourceClass':source_class,'sourceExpression':identity.get('sourceExpression'),'sourceName':source_name})
    source_counts[source_class]+=1;resource_counts[resource]+=1
   bound.append({**evidence,'techniqueAssignments':assignments})
  rows.append({'sha256':sha,'techniqueSets':techniques,'sampledTextureResourceCount':len(bound),'textureSampleNodeCount':sum(len(row['sampleNodeIds']) for row in bound),'resources':bound})
 rows.sort(key=lambda row:row['sha256'])
 summary={'shaderCount':len(rows),'sampledTextureResourceCount':sum(row['sampledTextureResourceCount'] for row in rows),'textureSampleNodeCount':sample_count,'sourceClassAssignmentCounts':dict(sorted(source_counts.items())),'resourceAssignmentCounts':dict(sorted(resource_counts.items())),'rowsSha256':_jhash(rows)}
 return {'format':FORMAT,'sourceFinalOutputFormat':FINAL_FORMAT,'shaders':rows,'summary':summary,'rowsSha256':summary['rowsSha256'],'proofBoundary':'Exact same-CSO/slot-4 .tech binding for every RDEF-named texture resource actually sampled by the complete generated final-output DAG. RHS expressions are retained verbatim and classified syntactically only; material image ownership and code-sampler enum/runtime values remain separate.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--oat-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),oat_root=a.oat_root);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
