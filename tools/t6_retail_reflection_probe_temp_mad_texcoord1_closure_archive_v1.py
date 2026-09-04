#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path

def load(p:Path):
 s=importlib.util.spec_from_file_location('base',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def compact(d):
 s=d['summary']; rr=d['resourceRoleRows']
 resource_summary={
  'resourceNames':sorted({x['resourceName'] for x in rr}),
  'classes':sorted({x['class'] for x in rr}),
  'roleRowCount':len(rr),
  'coefficientRoles':sorted({x['coefficient'] for x in rr}),
  'sampleOpcodes':sorted({x['opcode'] for x in rr}),
 }
 return {
  'format':'t6-retail-reflection-probe-temp-mad-texcoord1-closure-archive-v1',
  'producer':'tools/t6_retail_reflection_probe_temp_mad_texcoord1_closure_archive_v1.py',
  'sources':d['sources'],'equations':d['equations'],'classSemantics':d['classSemantics'],
  'resourceRoleSummary':resource_summary,
  'examples':{k:v[:1] for k,v in d['examples'].items()},
  'forensicDigests':{
   'allShaderRowsSha256':s['shaderRowsSha256'],
   'allResourceRoleRowsSha256':s['resourceRoleRowsSha256'],
   'classCountsSha256':s['classCountsSha256'],
  },
  'summary':s,
  'proofBoundary':d['proofBoundary']+' This archival wrapper omits full resource-role row arrays while retaining their deterministic SHA-256 digests; the exhaustive verifier remains tools/t6_retail_reflection_probe_temp_mad_texcoord1_closure_v1.py.'
 }

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--base-verifier',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
 for n in ('tangent-verifier','coordinate-verifier','weight-verifier','shared-verifier','surface-verifier','guard','mip-verifier','angular-verifier','semantic-verifier'):a.add_argument('--'+n,type=Path,required=True)
 q=a.parse_args();m=load(q.base_verifier);d=m.build(q.root,q.tangent_verifier,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);o=compact(d);q.out.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n');print(json.dumps(o['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
