#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

EXPECTED_SUMMARY={
 'retainedMapCount':5,
 'uniqueReflectionProbeShaderCount':5868,
 'affine4Minus4xFetchCount':4236,
 'sameXPackCheckCount':4236,
 'sameXPackFailureCount':0,
 'uniqueQPackPerFetchCount':4236,
 'allFourQLanesReachFactorCount':4236,
 'qFactorFormCount':2,
 'qFactorDominantFormCount':4216,
 'qFactorCommutedFormCount':20,
 'xSourceOriginCount':4236,
 'directTextureXSourceCount':2024,
 'shaderRowsSha256':'2f36fe08cf09364ddbf524686a2a387be6958ca86093d1366cd5ad1c75f8d506',
 'factorFormRowsSha256':'cf7d843e1c89a4c14e15af2f85a4297a4ec5cad90fe8fadc75761fcb8290bbe4',
 'xOriginRowsSha256':'36da72e458715345b02ad4cbe893f5f110e20b30e6aca6f9afada96b604df0f8',
 'directXSourceRowsSha256':'6d795b12d55076271bf9991df49866b92e5572282597657ce6d7d95858fbfc3f'
}
EXPECTED_FORMS={
 'a0daa888619bad43ca75c1b1f045cfed43f46ed608e0af417648dc2fd2d618b4':4216,
 'bcf4be739b61d581e495abf4ce4a58db9b1d8adabf687983d1e0ed1fb44d301c':20,
}
EXPECTED_ORIGINS={('constant_buffer','CB'):40,('temp','MAD'):1350,('temp','MUL'):822,('temp','SAMPLE'):2024}
EXPECTED_A=['3f855556','3ef33333','3c955567','3e800000']
EXPECTED_B=['00000000','00000000','bc800000','3f400000']

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def validate(d):
 assert d['format']=='t6-retail-reflection-probe-shared-parameter-v1'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['equation']['lod']=='4 - 4*x'
 assert [x['bits'] for x in d['equation']['A']]==EXPECTED_A
 assert [x['bits'] for x in d['equation']['B']]==EXPECTED_B
 assert d['equation']['C']=='min(E,Qy)'
 assert d['equation']['F']=='Qx*C + Qz'
 assert d['equation']['reflectionFactorRgb']=='saturate(P.rgb * (Qw - F) + F)'
 assert {x['formSha256']:x['count'] for x in d['factorForms']}==EXPECTED_FORMS
 assert {(x['sourceKind'],x['firstWriter']):x['count'] for x in d['xSourceOriginCounts']}==EXPECTED_ORIGINS
 assert sum(x['count'] for x in d['directTextureXSources'])==2024

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_SHARED_PARAMETER_V1.json'))
 ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 ap.add_argument('--root',type=Path)
 a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'shared').build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.guard)
  validate(got);assert got==d,'retail rerun differs from committed shared-parameter manifest'
 print('PASS: T6 retained reflectionProbeSampler shared mip/material parameter regression')
if __name__=='__main__':main()
