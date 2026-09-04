#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_ROWS_SHA='3a7c8ca9afc667a4fa72274ab787fc80ddb794f9533e76320abe7d04dc47df32'
EXPECTED_MAPS=[
 {'map':'mp_nuketown_2020','validDxbcCount':1972,'reflectionProbeShaderCount':1285},
 {'map':'mp_raid','validDxbcCount':3064,'reflectionProbeShaderCount':2063},
 {'map':'mp_hijacked','validDxbcCount':2299,'reflectionProbeShaderCount':1722},
 {'map':'zm_prison','validDxbcCount':3920,'reflectionProbeShaderCount':3158},
 {'map':'zm_tomb','validDxbcCount':2839,'reflectionProbeShaderCount':1979},]
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-reflection-probe-rdef-guard-v1';assert d['mapCoverage']==EXPECTED_MAPS
 assert d['binding']=={'name':'reflectionProbeSampler','texture':{'inputType':'TEXTURE','dimension':'TEXTURECUBE','bindPoint':15,'bindCount':1},'sampler':{'inputType':'SAMPLER','dimension':'UNKNOWN','bindPoint':15,'bindCount':1}}
 assert d['summary']=={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'bindingFailureCount':0,'textureBindPoint':15,'textureBindCount':1,'textureDimension':'TEXTURECUBE','samplerBindPoint':15,'samplerBindCount':1,'samplerDimension':'UNKNOWN','shaderRowsSha256':EXPECTED_ROWS_SHA}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_RDEF_GUARD_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_rdef_guard_v1.py'));ap.add_argument('--secondary-guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'reflection').build(a.root,a.secondary_guard);validate(got);assert got==d,'retail rerun differs from committed reflection-probe RDEF manifest'
 print('PASS: T6 retained reflectionProbeSampler RDEF guard regression')
if __name__=='__main__':main()
