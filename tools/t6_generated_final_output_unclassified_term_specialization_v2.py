#!/usr/bin/env python3
"""Unknown final-RGB specialization v2: authoritative cbuffer-coverage preflight.

v1 specializes exact term subtrees per material owner. v2 first walks each term
root in the authoritative final-output DAG and requires the set of reachable
`cbN[R].component` leaves to equal the cbuffer-resolution symbol set exactly.
Only then is v1 specialization allowed.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from pathlib import Path
from typing import Any
import t6_generated_final_output_unclassified_term_specialization_v1 as v1

FORMAT='t6-generated-final-output-unclassified-term-specialization-v2'
class UnclassifiedTermSpecializationV2Error(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _shader_rows(doc:dict)->dict[str,dict]:
 out={}
 for row in doc.get('shaders',[]):
  sha=str(row.get('sha256') or '')
  if not sha or sha in out:raise UnclassifiedTermSpecializationV2Error(f'invalid/duplicate shader {sha!r}')
  out[sha]=row
 return out

def _nodes(shader:dict)->dict[int,dict]:
 out={}
 for row in shader.get('nodes',[]):
  node=int(row.get('id',-1))
  if node<0 or node in out:raise UnclassifiedTermSpecializationV2Error(f'invalid/duplicate DAG node {node}')
  out[node]=row
 return out

def _cb_symbols(nodes:dict[int,dict],root:int)->set[str]:
 seen=set();symbols=set()
 def walk(node:int):
  if node in seen:return
  if node not in nodes:raise UnclassifiedTermSpecializationV2Error(f'DAG references missing node {node}')
  seen.add(node);row=nodes[node]
  if row.get('kind')=='symbol' and str(row.get('name') or '').startswith('cb'):symbols.add(str(row['name']))
  for child in row.get('args',[]):walk(int(child))
 walk(root);return symbols

def preflight(final_doc:dict,resolution_doc:dict)->dict:
 if final_doc.get('format')!=v1.FINAL_FORMAT:raise UnclassifiedTermSpecializationV2Error('unsupported final-output format')
 if resolution_doc.get('format')!=v1.RESOLUTION_FORMAT:raise UnclassifiedTermSpecializationV2Error('unsupported resolution format')
 shaders=_shader_rows(final_doc);rows=[]
 for term in resolution_doc.get('terms',[]):
  sha=str(term.get('sha256') or '');root=int(term.get('node',-1));shader=shaders.get(sha)
  if shader is None:raise UnclassifiedTermSpecializationV2Error(f'term shader {sha!r} absent from final-output DAG')
  actual=sorted(_cb_symbols(_nodes(shader),root));declared=sorted(str(row.get('symbol') or '') for row in term.get('cbufferResolutionV1',[]))
  if any(not x for x in declared) or len(declared)!=len(set(declared)):raise UnclassifiedTermSpecializationV2Error(f'shader {sha} node {root}: invalid/duplicate resolution symbols')
  if actual!=declared:raise UnclassifiedTermSpecializationV2Error(f'shader {sha} node {root}: reachable cbuffer symbols {actual} != resolution symbols {declared}')
  rows.append({'sha256':sha,'lane':term.get('lane'),'node':root,'reachableCbufferSymbols':actual,'resolutionCbufferSymbols':declared,'exactCoverage':True})
 return {'termCount':len(rows),'rows':rows,'rowsSha256':_jhash(rows)}
def promote(base:dict,preflight_doc:dict)->dict:
 if base.get('format')!=v1.FORMAT:raise UnclassifiedTermSpecializationV2Error(f"unexpected v1 specialization format {base.get('format')!r}")
 out=copy.deepcopy(base);out['format']=FORMAT;out['baseFormat']=v1.FORMAT;out['cbufferCoveragePreflight']=preflight_doc;summary=copy.deepcopy(out.get('summary',{}));summary['exactCbufferCoverageTermCount']=int(preflight_doc['termCount']);summary['cbufferCoverageRowsSha256']=preflight_doc['rowsSha256'];out['summary']=summary;out['proofBoundary']=str(base.get('proofBoundary') or '')+' v2 additionally requires exact equality between every reachable cbuffer symbol in the authoritative term subtree and the resolution sidecar before specialization.';return out
def build(final_doc:dict,resolution_doc:dict)->dict:
 pf=preflight(final_doc,resolution_doc);return promote(v1.build(final_doc,resolution_doc),pf)
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer-resolution',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.cbuffer_resolution.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
