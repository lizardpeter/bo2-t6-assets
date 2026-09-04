#!/usr/bin/env python3
"""Corrected metadata wrapper for the reusable sphere-electric packed-PS owner probe.

The v1 parser/ownership proof is retained byte-for-byte as the implementation. Its
only stale claim is metadata: it labeled the named sphere-electric bank with the
SHIFTED_TANGENT_BASIS_NORMAL mathematical proof. The named bank is now known to
require independent TC2/TEXCOORD0 classification by the corrected physical gate.

This wrapper delegates every parser/helper symbol to v1, overrides only build(), and
removes that stale family assertion from generated owner manifests.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
V1=HERE/'t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py'

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
_v1=load(V1,'sphere_owner_v1_impl')

def __getattr__(name):
 return getattr(_v1,name)

def build(root:Path,base_path:Path,broad_path:Path):
 d=_v1.build(root,base_path,broad_path)
 d['format']='t6-retail-reflection-probe-sphere-elec-packed-ps-probe-v2'
 d['producer']='tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v2.py'
 d['correction']={
  'supersedesMetadataFrom':'tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py',
  'implementation':'delegated unchanged to v1 ownership/parser code',
  'reason':'v1 target metadata pointed at the distinct already-closed shifted-TBN 24-fetch population; ownership evidence itself is reusable and family-agnostic'}
 target=dict(d.get('target',{}))
 target.pop('mathematicalProof',None)
 target['familyClassificationStatus']='not asserted by owner probe'
 target['requiredDownstreamClassifier']='tools/t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py'
 target['requiredPixelFamily']='A=normalize(TEXCOORD2.xyz), B=normalize(TEXCOORD0.xyz)'
 d['target']=target
 d['proofBoundary']=(
  'Ownership-only retained-byte proof for the 24 objects located by the '
  'pimp_shader_sw4_3d_zm_sphere_elec_ name prefix. All parser, structural alias, '
  'serializer-bound, and target-bank uniqueness logic is delegated unchanged to the '
  'v1 implementation. This wrapper intentionally makes no pixel-family semantic claim. '
  'A downstream gate must independently classify the actual PS payloads as TC2/TC0 '
  'before any reflection-normal closure is counted.')
 return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
 ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'))
 ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 d=build(a.root,a.base_verifier,a.broad_verifier);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
