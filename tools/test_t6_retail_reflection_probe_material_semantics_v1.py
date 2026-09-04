#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

EXPECTED_SUMMARY={
 'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'targetFetchCount':4236,
 'squaredSpecularPathCount':4216,'sharedSpecGlossSampleCount':4116,'splitSpecGlossSampleCount':60,
 'constantSpecGlossVariableCount':40,'immediatePoint04GlossSampleCount':20,'semanticProvenanceFailureCount':0,
 'sharedPatternRowsSha256':'394cd29858a56c3254f4b0e5f5555635e0ec6f794e9b5937823f29cdf2125f6c',
 'splitPatternRowsSha256':'1e8292882fea92c9da8104dfd9c8088efa625cfd75034b86bac2a96f64e12a03',
 'constantPatternRowsSha256':'d4ed1f7df007d2fcd37ba563817d65531ade6a42fec172b81486a2da1a2763c6',
 'immediateGlossRowsSha256':'203fbc5f03f2b97cadde82473adfd758edb303a22cf6b6bfcaad02d077c4e735',
 'shaderRowsSha256':'0fec677b674e6c62f9e0140641c8014952b9bf64e1e866c3266ba8040d9b3543'}

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def validate(d):
 assert d['format']=='t6-retail-reflection-probe-material-semantics-v1'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['semanticPromotion']['x']=='gloss-path scalar (retail RDEF provenance)'
 assert d['semanticPromotion']['S.rgb']=='specular-color path (retail RDEF provenance)'
 assert sum(x['count'] for x in d['sharedNamedSamplePatterns'])==4116
 assert {(tuple(x['sResources']),tuple(x['xResources'])):x['count'] for x in d['splitNamedSamplePatterns']}=={
   (('Specular_Color_Map',),('Specular_Gloss_Map',)):20,(('specular_map',),('gloss_map',)):40}
 assert len(d['constantVariablePatterns'])==1 and d['constantVariablePatterns'][0]['count']==40
 c=d['constantVariablePatterns'][0]
 assert {x['variable'] for x in c['sVariables']}=={'SpecularColor'}
 assert c['xVariable']['variable']=='GlossAmount'
 assert d['immediatePoint04GlossSources']==[{'sourceKind':'SAMPLE','resourceName':'DiffuseAndGloss','resourceRegister':2,'channel':'w','opcode':'SAMPLE','count':20}]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_MATERIAL_SEMANTICS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));ap.add_argument('--material-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_color_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path)
 a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'sem').build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.shared_verifier,a.material_verifier,a.guard);validate(got);assert got==d,'retail rerun differs from committed material-semantics manifest'
 print('PASS: T6 retained reflectionProbeSampler material semantic provenance regression')
if __name__=='__main__':main()
