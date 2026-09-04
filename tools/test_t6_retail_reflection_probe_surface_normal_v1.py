#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

EXPECTED={
 'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'reflectionCubeFetchCount':5888,
 'surfaceNormalRoleFetchCount':4086,'surfaceNormalRoleFailureCount':0,'surfaceNormalBasisCheckCount':4086,
 'normalNamedXAncestryCheckCount':4086,'normalNamedYAncestryCheckCount':4086,'texcoord5OpposingVectorCheckCount':4086,
 'formulaRoleRowsSha256':'bfc0117b363af7e6841efd41d7116eeb14ce95eda5020bf5ee6a6f093ffea8be',
 'normalResourceRowsSha256':'64be9edd007acd1b59d5fed645e946e46e8c48b9d802963a007aa265ace3d06f',
 'controlResourceRowsSha256':'9b691ff2dfb2ba06aa328e518c958d1fa5d4702859017e06dd5029554a312755',
 'shaderRowsSha256':'82be25ce964fe2a56fbe00ba81b01c3f931befd9d69cbd048e531f744761b0d5'}

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def validate(d):
 assert d['format']=='t6-retail-reflection-probe-surface-normal-v1'
 assert d['summary']==EXPECTED
 assert d['equation']['cubeCoord']=='viewCandidate - 2 * surfaceNormal * dot(surfaceNormal, viewCandidate)'
 assert d['equation']['surfaceNormalRaw']=='TEXCOORD1.xyz + normalX * TEXCOORD3.xyz + normalY * TEXCOORD2.xyz'
 assert sum(x['count'] for x in d['formulaRolePatterns'])==5888
 assert next(x['count'] for x in d['formulaRolePatterns'] if x['formulaA']=='TEMP_OP50' and x['formulaB']=='TEXCOORD5.xyz')==4086
 assert sum(x['ancestryOccurrenceCount'] for x in d['normalNamedResourceAncestry'])>0

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_SURFACE_NORMAL_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'));ap.add_argument('--root',type=Path)
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));ap.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'));ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'surface').build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.shared_verifier,a.guard);validate(got);assert got==d,'retail rerun differs from committed surface-normal manifest'
 print('PASS: T6 retained reflectionProbeSampler surface-normal role regression')
if __name__=='__main__':main()
