#!/usr/bin/env python3
"""Corrected metadata wrapper for sphere-electric paired-VS resolution.

The v1 paired-VS resolver is retained as the implementation. V2 routes it through
the corrected ownership-only v2 packed-PS probe and records that paired-VS recovery
alone does not assign the pixel family; TC2/TEXCOORD0 classification remains the
responsibility of the corrected physical closure gate.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
V1=HERE/'t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py'
OWNER_V2=HERE/'t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v2.py'

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
_v1=load(V1,'sphere_paired_v1_impl')

def __getattr__(name):
 return getattr(_v1,name)

def build(root:Path,owner_probe_path:Path,base_path:Path,broad_path:Path,packed_vs_alias_path:Path):
 d=_v1.build(root,owner_probe_path,base_path,broad_path,packed_vs_alias_path)
 d['format']='t6-retail-reflection-probe-sphere-elec-paired-vs-probe-v2'
 d['producer']='tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v2.py'
 d['correction']={
  'supersedesMetadataFrom':'tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py',
  'implementation':'delegated unchanged to v1 paired-VS resolver',
  'reason':'v2 explicitly separates ownership/paired-VS recovery from downstream TC2/TEXCOORD0 pixel-family classification'}
 src=dict(d.get('sources',{}));src['pixelOwnerProbe']=str(owner_probe_path);src['requiredPhysicalClassifier']='tools/t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py';d['sources']=src
 d['proofBoundary']=(
  'Paired-vertex ownership resolution only. All v1 direct/cross-map/committed packed-VS '
  'alias logic is preserved, but the pixel owner source is the corrected ownership-only '
  'v2 probe. A resolved VS is evidence about the retained owner relation; no sphere '
  'reflection family is assigned here. The downstream v2 TC2/TC0 physical gate must '
  'independently classify each named PS payload and prove the required TC2 NORMAL0 and '
  'TC0 POSITION0 producers before closure is counted.')
 return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
 ap.add_argument('--owner-probe',type=Path,default=OWNER_V2)
 ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'))
 ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'))
 ap.add_argument('--packed-vs-alias',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 d=build(a.root,a.owner_probe,a.base_verifier,a.broad_verifier,a.packed_vs_alias);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
