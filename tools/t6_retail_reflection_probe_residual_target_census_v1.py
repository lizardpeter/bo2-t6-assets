#!/usr/bin/env python3
"""Reconstruct and pin the two final direct-normal residual target populations.

This repairs a repository artifact gap without inventing identities. The later
TC2/TC1 broad verifier references a 75-SHA target-set JSON that was never committed.
The original exhaustive verifier remains able to reconstruct those 75 identities
from the five pinned retail worlds. This census reruns that classifier and requires
both independently committed digests:

  TC2/TC1 global row digest: 0d088b...e5f3
  TC2/TC1 sorted SHA-set digest: be9e44...cc0a0

The 42 TC3/TC1 identities are likewise reconstructed from their exhaustive verifier
and pinned by its committed global-row digest cf8651...59a4. The output is therefore
a deterministic target-set artifact generated from retained bytes, not a guessed or
manually copied list.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

TC2_COUNT=75
TC3_COUNT=42
TC2_GLOBAL_ROWS_SHA256='0d088b939b586ee46c7d69f7728046e0c377e12627f2883eba2786d25de5e5f3'
TC2_SHADER_SET_SHA256='be9e44e06742a56170b91ce5f94173fee63c3fbc8c91aaf690cf712b2f8cc0a0'
TC3_GLOBAL_ROWS_SHA256='cf865119d342260faae59ebd964fadcfe6ad40cfb6280e28fe5a4f3c19cb59a4'

def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sethash(xs):return hashlib.sha256(json.dumps(sorted(xs),separators=(',',':')).encode()).hexdigest()

def build(root:Path,base_path:Path,broad_path:Path):
 base=load(base_path,'residual_target_base');broad=load(broad_path,'residual_target_broad')
 tc2=base.global_target(root)
 if len(tc2)!=TC2_COUNT:raise ValueError(f'TC2/TC1 target count {len(tc2)}')
 tc2_rows=[{'sha256':h,'roles':tc2[h]} for h in sorted(tc2)]
 tc2_rows_sha=jhash(tc2_rows);tc2_set_sha=sethash(tc2)
 if tc2_rows_sha!=TC2_GLOBAL_ROWS_SHA256:raise ValueError(f'TC2/TC1 global row drift {tc2_rows_sha}')
 if tc2_set_sha!=TC2_SHADER_SET_SHA256:raise ValueError(f'TC2/TC1 target SHA-set drift {tc2_set_sha}')
 if sum(len(v) for v in tc2.values())!=TC2_COUNT:raise ValueError('TC2/TC1 fetch count is not 75')
 tc3,tc3_rows,tc3_fetches=broad.global_target(root,base)
 if len(tc3)!=TC3_COUNT or tc3_fetches!=TC3_COUNT:raise ValueError(f'TC3/TC1 target census {len(tc3)}/{tc3_fetches}')
 tc3_rows_sha=jhash(tc3_rows)
 if tc3_rows_sha!=TC3_GLOBAL_ROWS_SHA256:raise ValueError(f'TC3/TC1 global row drift {tc3_rows_sha}')
 if set(tc2)&set(tc3):raise ValueError('TC2/TC1 and TC3/TC1 target sets overlap')
 tc3_set_sha=sethash(tc3)
 summary={
  'tc2Texcoord1ShaderCount':len(tc2),'tc2Texcoord1FetchCount':sum(len(v) for v in tc2.values()),
  'tc2Texcoord1GlobalRowsSha256':tc2_rows_sha,'tc2Texcoord1ShaderSetSha256':tc2_set_sha,
  'tc3Texcoord1ShaderCount':len(tc3),'tc3Texcoord1FetchCount':tc3_fetches,
  'tc3Texcoord1GlobalRowsSha256':tc3_rows_sha,'tc3Texcoord1ShaderSetSha256':tc3_set_sha,
  'combinedShaderCount':len(tc2)+len(tc3),'combinedShaderSetSha256':sethash(set(tc2)|set(tc3))}
 return {
  'format':'t6-retail-reflection-probe-residual-target-census-v1',
  'producer':'tools/t6_retail_reflection_probe_residual_target_census_v1.py',
  'sources':{
   'tc2Classifier':str(base_path),'tc3Classifier':str(broad_path),
   'tc2CommittedProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_V1.json',
   'tc2BroadCommittedProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD2_TEXCOORD1_BROAD_V1.json',
   'tc3CommittedProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD3_TEXCOORD1_V1.json'},
  'targets':{
   'TEXCOORD2/TEXCOORD1':{'shaderSha256':sorted(tc2),'shaderSetSha256':tc2_set_sha,'globalRowsSha256':tc2_rows_sha},
   'TEXCOORD3/TEXCOORD1':{'shaderSha256':sorted(tc3),'shaderSetSha256':tc3_set_sha,'globalRowsSha256':tc3_rows_sha}},
  'summary':summary,
  'proofBoundary':'Exhaustive target identity reconstruction only. Both populations are regenerated from the five hash-pinned expanded retail worlds using the original committed pixel-family classifiers. TC2/TC1 must reproduce both its committed global-row digest and the later broad-stage sorted target-set digest; TC3/TC1 must reproduce its committed global-row digest. No pass ownership or vertex semantics are promoted by this census.'}

def write_tc2_compat(data:dict,path:Path):
 q=data['targets']['TEXCOORD2/TEXCOORD1'];compat={'format':'t6-retail-reflection-probe-texcoord2-texcoord1-target-set-compat-v1','shaderSha256':q['shaderSha256'],'summary':{'shaderCount':len(q['shaderSha256']),'shaderSetSha256':q['shaderSetSha256'],'globalRowsSha256':q['globalRowsSha256']},'generatedBy':'tools/t6_retail_reflection_probe_residual_target_census_v1.py'}
 path.write_text(json.dumps(compat,indent=2,sort_keys=True)+'\n')
 return compat

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
 ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'))
 ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'))
 ap.add_argument('--out',type=Path,required=True);ap.add_argument('--tc2-compat-out',type=Path);a=ap.parse_args()
 d=build(a.root,a.base_verifier,a.broad_verifier);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
 if a.tc2_compat_out:write_tc2_compat(d,a.tc2_compat_out)
 print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
