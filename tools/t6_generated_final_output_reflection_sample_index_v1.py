#!/usr/bin/env python3
"""Index exact reflectionProbeSampler instances in generated slot-4 output DAGs.

This generated-shader sidecar joins exact reflection sample instructions to the
completed generated specular state without relying on aggregate retained counts.
For every reflectionProbeSampler instruction it records:

- exact instruction DWORD/opcode and symbolic sample channel nodes;
- exact coordinate and extra LOD/bias operand nodes from the final-output parser;
- whether coordinate operands depend on completed specular X/Y/Z/W roots;
- whether LOD/bias operands depend on completed specular X/Y/Z/W roots;
- exact retained LOD/bias form classification when structurally matched.

Accepted retained forms:
- SAMPLE_B bias -3 (0xc0400000);
- SAMPLE_L literal LOD 0, 0.8, 2.4, 4;
- SAMPLE_L affine LOD scale*x+offset with exact pairs:
    -4*x+4, 0.475*x, 0.25*x+0.75, 0*x+0.

This proves dataflow relationships only.  It does not name a specular channel as
roughness/gloss or assign a physical meaning to affine source x.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict,Counter
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-reflection-sample-index-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
SPEC_FORMAT='t6-generated-final-output-specular-state-anchor-v1'
RESOURCE='reflectionProbeSampler';CHANNELS='xyzw'
BIAS_BITS='c0400000';LITERAL_LOD_BITS={'00000000','3f4ccccd','4019999a','40800000'}
AFFINE_BITS={('c0800000','40800000'),('3ef33333','00000000'),('3e800000','3f400000'),('00000000','00000000')}
ZERO='00000000'
class ReflectionSampleIndexError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _nodes(shader):
 rows=shader.get('nodes');
 if not isinstance(rows,list):raise ReflectionSampleIndexError('shader has no nodes')
 out={}
 for r in rows:
  i=int(r.get('id',-1))
  if i<0 or i in out:raise ReflectionSampleIndexError(f'invalid/duplicate node {i}')
  out[i]=r
 return out
def _anc(nodes,root,memo):
 if root in memo:return memo[root]
 seen=set()
 def w(i):
  if i in seen:return
  if i not in nodes:raise ReflectionSampleIndexError(f'missing node {i}')
  seen.add(i)
  for c in nodes[i].get('args',[]):w(int(c))
 w(root);memo[root]=seen;return seen
def _lit(nodes,i):
 r=nodes[i]
 return str(r.get('bits') or '').lower() if r.get('kind')=='literal32' else None
def _mul_source_literal(nodes,i):
 r=nodes[i]
 if r.get('kind')!='op' or r.get('op')!='mul' or len(r.get('args',[]))!=2:return None
 for source,literal in (r['args'],r['args'][::-1]):
  source=int(source);literal=int(literal);bits=_lit(nodes,literal)
  if bits is not None:return source,bits
 return None
def _affine(nodes,i):
 # scale*x + offset, allowing exact zero offset to be omitted by the compiler.
 r=nodes[i]
 if r.get('kind')=='op' and r.get('op')=='add' and len(r.get('args',[]))==2:
  for term,offset in (r['args'],r['args'][::-1]):
   term=int(term);offset=int(offset);ob=_lit(nodes,offset);q=_mul_source_literal(nodes,term)
   if ob is not None and q is not None:return q[1],ob,q[0]
 q=_mul_source_literal(nodes,i)
 if q is not None:return q[1],ZERO,q[0]
 return None
def _deps(nodes,operand_nodes,spec_roots,memo):
 out=[]
 for ch,root in spec_roots.items():
  if any(root in _anc(nodes,int(node),memo) for node in operand_nodes):out.append(ch)
 return out
def _spec_roots(spec):
 by={}
 for row in spec.get('materials',[]):
  sha=str(row.get('shaderSha256') or '');roots={ch:int(row.get('finalStateNodes',{}).get(ch,-1)) for ch in CHANNELS}
  if sha in by and by[sha]!=roots:raise ReflectionSampleIndexError(f'shader {sha}: materials disagree on completed specular roots')
  by[sha]=roots
 return by
def _classify(nodes,sample):
 op=str(sample.get('opcode') or '').lower();extra=[int(x) for x in sample.get('extraOperandNodes',[])]
 if op=='sample_b':
  if len(extra)!=1 or _lit(nodes,extra[0])!=BIAS_BITS:return {'known':False,'kind':'sample_b','reason':'bias is not exact -3'}
  return {'known':True,'kind':'bias','biasFloat32Bits':BIAS_BITS}
 if op=='sample_l':
  if len(extra)!=1:return {'known':False,'kind':'sample_l','reason':f'extra operand count {len(extra)}'}
  bits=_lit(nodes,extra[0])
  if bits is not None:return {'known':bits in LITERAL_LOD_BITS,'kind':'literal_lod','lodFloat32Bits':bits}
  q=_affine(nodes,extra[0])
  if q is None:return {'known':False,'kind':'affine_lod','reason':'operand is not structural scale*x+offset'}
  scale,offset,source=q
  return {'known':(scale,offset) in AFFINE_BITS,'kind':'affine_lod','scaleFloat32Bits':scale,'offsetFloat32Bits':offset,'sourceNode':source}
 return {'known':False,'kind':'unsupported_opcode','opcode':op}
def build(final_output,spec_anchor,*,strict_known_forms=True):
 if final_output.get('format')!=FINAL_FORMAT:raise ReflectionSampleIndexError(f"unexpected final-output format {final_output.get('format')!r}")
 if spec_anchor.get('format')!=SPEC_FORMAT:raise ReflectionSampleIndexError(f"unexpected specular format {spec_anchor.get('format')!r}")
 roots_by_sha=_spec_roots(spec_anchor);rows=[];form_counts=Counter();coord_dep=lod_dep=unknown=0
 for shader in final_output.get('shaders',[]):
  sha=str(shader.get('sha256') or '');samples=[s for s in shader.get('samples',[]) if str(s.get('resource') or '')==RESOURCE]
  if not samples:continue
  nodes=_nodes(shader);spec_roots=roots_by_sha.get(sha);memo={};sr=[]
  for s in samples:
   at=int(s.get('atDword',-1));node_ids=sorted(i for i,r in nodes.items() if r.get('kind')=='textureSample' and str(r.get('resource') or '')==RESOURCE and int(r.get('instructionDword',-2))==at)
   if not node_ids:raise ReflectionSampleIndexError(f'shader {sha} DWORD {at}: no symbolic reflection sample nodes')
   coords=[int(x) for x in s.get('coordinateNodes',[])];extra=[int(x) for x in s.get('extraOperandNodes',[])];classification=_classify(nodes,s)
   if not classification['known']:unknown+=1
   if strict_known_forms and not classification['known']:raise ReflectionSampleIndexError(f'shader {sha} DWORD {at}: unrecognized retained reflection form {classification}')
   cdep=[];ldep=[]
   if spec_roots is not None:
    if any(root not in nodes for root in spec_roots.values()):raise ReflectionSampleIndexError(f'shader {sha}: invalid specular roots')
    cdep=_deps(nodes,coords,spec_roots,memo);ldep=_deps(nodes,extra,spec_roots,memo)
   if cdep:coord_dep+=1
   if ldep:lod_dep+=1
   key=classification['kind']
   if key=='affine_lod':key+=f":{classification.get('scaleFloat32Bits')}:{classification.get('offsetFloat32Bits')}"
   elif key=='literal_lod':key+=f":{classification.get('lodFloat32Bits')}"
   elif key=='bias':key+=f":{classification.get('biasFloat32Bits')}"
   form_counts[key]+=1
   sr.append({'atDword':at,'opcode':s.get('opcode'),'sampleNodeIds':node_ids,'sampleChannels':sorted(str(nodes[i].get('channel') or '') for i in node_ids),'coordinateNodes':coords,'extraOperandNodes':extra,'classification':classification,'coordinateSpecularChannels':cdep,'lodBiasSpecularChannels':ldep,'specularRootJoinAvailable':spec_roots is not None})
  rows.append({'shaderSha256':sha,'techniqueSets':sorted(str(x) for x in shader.get('techniqueSets',[])),'reflectionSampleCount':len(sr),'samples':sr})
 summary={'shaderCount':len(rows),'reflectionSampleCount':sum(r['reflectionSampleCount'] for r in rows),'unknownFormCount':unknown,'coordinateSpecularDependentSampleCount':coord_dep,'lodBiasSpecularDependentSampleCount':lod_dep,'formCounts':dict(sorted(form_counts.items())),'strictKnownForms':bool(strict_known_forms)}
 return {'format':FORMAT,'shaders':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Exact generated slot-4 reflectionProbeSampler instruction instances indexed from final-output symbolic sample metadata. Coordinate and LOD/bias operands are tested for direct ancestry from completed specular XYZW roots. LOD/bias classification is restricted to the already retained exact finite forms. Dependency does not assign roughness/gloss or other physical semantics to any specular channel.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--relaxed-forms',action='store_true');a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.specular.read_text()),strict_known_forms=not a.relaxed_forms);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
