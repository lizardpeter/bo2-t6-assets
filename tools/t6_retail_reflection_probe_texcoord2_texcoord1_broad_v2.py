#!/usr/bin/env python3
"""Rerunnable TC2/TC1 broad ownership proof without the missing target-set artifact.

V1's ownership/VS proof is preserved unchanged. V2 reconstructs the exact 75-SHA
target set from the pinned corpus through residual_target_census_v1, verifies both
committed target digests, emits a temporary compatibility target-set JSON, and then
runs the v1 broad proof against that generated set.
"""
from __future__ import annotations
import argparse, importlib.util, json, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
V1=HERE/'t6_retail_reflection_probe_texcoord2_texcoord1_broad_v1.py'
CENSUS=HERE/'t6_retail_reflection_probe_residual_target_census_v1.py'

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
_v1=load(V1,'tc2_broad_v1_impl');_c=load(CENSUS,'residual_target_census_impl')

def __getattr__(name):return getattr(_v1,name)

def build(root:Path,base_path:Path,broad_path:Path,prior_alias_path:Path,prior_family_path:Path):
 census=_c.build(root,base_path,broad_path)
 with tempfile.TemporaryDirectory(prefix='t6_tc2_target_') as td:
  target=Path(td)/'T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_TARGET_SET_COMPAT.json'
  _c.write_tc2_compat(census,target)
  d=_v1.build(root,base_path,broad_path,prior_alias_path,prior_family_path,target)
 d['format']='t6-retail-reflection-probe-texcoord2-texcoord1-broad-v2'
 d['producer']='tools/t6_retail_reflection_probe_texcoord2_texcoord1_broad_v2.py'
 src=dict(d.get('sources',{}));src['targetSet']='generated in-memory from tools/t6_retail_reflection_probe_residual_target_census_v1.py';src['targetCensus']='tools/t6_retail_reflection_probe_residual_target_census_v1.py';d['sources']=src
 d['targetCensusSummary']=census['summary']
 d['correction']={'supersedesExecutionDependencyFrom':'tools/t6_retail_reflection_probe_texcoord2_texcoord1_broad_v1.py','reason':'v1 references a 75-SHA target-set JSON that was never committed; v2 reconstructs and digest-pins the same set from the five retained worlds before delegating to v1 ownership logic'}
 return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
 ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'))
 ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'))
 ap.add_argument('--prior-alias',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'))
 ap.add_argument('--prior-family',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_V1.json'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.base_verifier,a.broad_verifier,a.prior_alias,a.prior_family);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
