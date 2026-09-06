#!/usr/bin/env python3
"""Final-output texture-resource binding v2: current OAT namespaces + omissions.

For every RDEF texture resource actually sampled by the authoritative slot-4
DAG, v2 re-resolves the exact owning TechniqueSet/CSO and retains the exact
`.tech` RHS when one is emitted. A missing line is serialized as `unassigned`
instead of failing because OAT deliberately omits same-accessor code sampler
assignments in non-debug dumps.

No omitted binding is guessed here. The pinned T6 sampler table may close that
case in a separate proof.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any
import t6_generated_final_output_cbuffer_signature_v1 as techparse
from t6_oat_slot_shader_resolver_v2 import resolve_slot_shader
from t6_tech_argument_source_identity_v2 import source_identity
FORMAT='t6-generated-final-output-texture-resource-binding-v2'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
class TextureResourceBindingV2Error(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _sampled(shader:dict)->dict[str,dict]:
 out={}
 for node in shader.get('nodes',[]):
  if node.get('kind')!='textureSample':continue
  resource=str(node.get('resource') or '')
  if not resource:raise TextureResourceBindingV2Error(f"shader {shader.get('sha256')}: texture sample node {node.get('id')} lacks RDEF resource")
  row=out.setdefault(resource,{'resource':resource,'sampleNodeIds':[],'resourceRegisters':set(),'samplerNames':set(),'samplerRegisters':set(),'opcodes':set(),'channels':set()})
  row['sampleNodeIds'].append(int(node['id']))
  if node.get('resourceRegister') is not None:row['resourceRegisters'].add(int(node['resourceRegister']))
  if node.get('sampler'):row['samplerNames'].add(str(node['sampler']))
  if node.get('samplerRegister') is not None:row['samplerRegisters'].add(int(node['samplerRegister']))
  if node.get('opcode'):row['opcodes'].add(str(node['opcode']))
  if node.get('channel'):row['channels'].add(str(node['channel']))
 for row in out.values():
  for key in ('sampleNodeIds','resourceRegisters','samplerNames','samplerRegisters','opcodes','channels'):row[key]=sorted(row[key])
 return out

def _tech(root:Path,technique:str,sha:str,cache:dict)->dict:
 if technique in cache:return cache[technique]
 resolved=resolve_slot_shader(root,technique,slot_index=4);ps=resolved.get('pixelShaders',[])
 if len(ps)!=1:raise TextureResourceBindingV2Error(f"{technique!r}: slot-4 pixel shader count {len(ps)}")
 if str(ps[0].get('sha256') or '').lower()!=sha.lower():raise TextureResourceBindingV2Error(f"{technique!r}: slot-4 PS {ps[0].get('sha256')} != final-output {sha}")
 path=root/str(resolved['techniqueFile'])
 if not path.is_file():raise TextureResourceBindingV2Error(f"{technique!r}: technique file missing {path}")
 assignments=techparse.parse_tech_assignments(path.read_text(encoding='utf-8',errors='strict'))
 cache[technique]={**resolved,'assignmentMap':assignments};return cache[technique]

def build(final_doc:dict,*,oat_root:Path)->dict:
 if final_doc.get('format')!=FINAL_FORMAT:raise TextureResourceBindingV2Error(f"unexpected final-output format {final_doc.get('format')!r}")
 root=Path(oat_root);cache={};rows=[];classes=Counter();namespaces=Counter();sample_count=0;unassigned=0
 for shader in final_doc.get('shaders',[]):
  sha=str(shader.get('sha256') or '').lower();techniques=sorted(str(x) for x in shader.get('techniqueSets',[]))
  if not sha or not techniques:raise TextureResourceBindingV2Error('final-output shader lacks SHA/TechniqueSets')
  resources=_sampled(shader);sample_count+=sum(len(r['sampleNodeIds']) for r in resources.values());bound=[]
  for resource in sorted(resources):
   assignments=[]
   for technique in techniques:
    resolved=_tech(root,technique,sha,cache);expr=resolved['assignmentMap'].get(resource);identity=source_identity(expr)
    if expr is None:unassigned+=1
    classes[identity['sourceClass']]+=1;namespaces[str(identity['sourceNamespace']) if identity['sourceNamespace'] is not None else 'none']+=1
    assignments.append({'techniqueSet':technique,'techniqueAsset':resolved.get('techniqueAsset'),'techniqueFile':resolved.get('techniqueFile'),'assignmentEvidence':'explicitTechAssignment' if expr is not None else 'absentFromTechDump',**identity})
   bound.append({**resources[resource],'techniqueAssignments':assignments})
  rows.append({'sha256':sha,'techniqueSets':techniques,'sampledTextureResourceCount':len(bound),'textureSampleNodeCount':sum(len(r['sampleNodeIds']) for r in bound),'resources':bound})
 rows.sort(key=lambda r:r['sha256']);summary={'shaderCount':len(rows),'sampledTextureResourceCount':sum(r['sampledTextureResourceCount'] for r in rows),'textureSampleNodeCount':sample_count,'techniqueAssignmentSourceClassCounts':dict(sorted(classes.items())),'techniqueAssignmentSourceNamespaceCounts':dict(sorted(namespaces.items())),'unassignedTechniqueBindingCount':unassigned,'rowsSha256':_jhash(rows)}
 return {'format':FORMAT,'sourceFinalOutputFormat':FINAL_FORMAT,'shaders':rows,'summary':summary,'rowsSha256':summary['rowsSha256'],'proofBoundary':'Exact same-CSO/slot-4 .tech inspection for every RDEF texture resource sampled by the complete generated final-output DAG. Current OAT material./sampler./constant. namespaces are classified exactly when present. Missing lines remain explicit unassigned evidence because OAT can omit matching code-sampler accessors; no omitted binding is guessed here.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--oat-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),oat_root=a.oat_root);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
