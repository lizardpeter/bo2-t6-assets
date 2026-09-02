#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
SUMMARY={'shaderCount':176,'inspectionFailureCount':0,'shaderModelCounts':{'4.0':176},'programTypeCounts':{'pixel':176},'chunkSequenceCounts':{'RDEF|ISGN|OSGN|SHDR|STAT':176},'creatorCounts':{'Microsoft (R) HLSL Shader Compiler 9.29.952.3111':176},'resourceInputTypeCounts':{'CBUFFER':408,'SAMPLER':1156,'TEXTURE':1156},'resourceDimensionCounts':{'TEXTURE2D':1000,'TEXTURECUBE':156,'UNKNOWN':1564},'distinctResourceNameCount':40,'lightmapShaderCount':154,'lightmapPrimaryShaderCount':0,'lightmapSecondaryShaderCount':154}
FAMILY={'default':(1,0,1),'emissive_or_burning':(60,60,0),'rawnormal_special':(20,20,0),'shadowcaster':(0,0,0),'tv_special':(20,20,0),'unlit':(16,0,16),'water':(59,54,5)}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-special-dxbc-inspection-v1' and d['summary']==SUMMARY
 assert d['sourcePixelShaderSetSha256']=='aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7'
 assert d['inspectionSetSha256']=='eee22681e48fdc599f2fe3e2f2303a658302d048bc37e514c6244d2f21f702b5'
 assert {k:(v['uniqueShaderCount'],v['lightmapShaderCount'],v['nonLightmapShaderCount']) for k,v in d['familyCoverage'].items()}==FAMILY
 assert d['lightmapBindingSignatures']==[
  {'name':'lightmapSamplerSecondary','inputType':'SAMPLER','dimension':'UNKNOWN','bindPoint':13,'bindCount':1,'shaderCount':154},
  {'name':'lightmapSamplerSecondary','inputType':'TEXTURE','dimension':'TEXTURE2D','bindPoint':13,'bindCount':1,'shaderCount':154},]
 assert 'lightmapSamplerPrimary' not in d['resourceNameCounts'] and d['resourceNameCounts']['lightmapSamplerSecondary']==308 and len(d['resourceNameCounts'])==40
 assert len(d['examples'])==4
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_DXBC_INSPECTION_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_dxbc_inspection_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--payload-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHADER_PAYLOAD_CENSUS_V1.json'));ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--inspector',type=Path,default=Path('tools/t6_dxbc_inspect_v1.py'));a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  m=load(a.verifier,'v');got=m.build(a.root,a.family_manifest,a.payload_manifest,a.parser,a.helper,a.inspector);validate(got);assert got==d,'retail rerun differs from committed DXBC inspection manifest'
 print('PASS: T6 retail special DXBC inspection regression')
if __name__=='__main__':main()
