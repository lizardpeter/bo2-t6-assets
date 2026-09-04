#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED_ROWS_SHA='9272dc76dc3ca5c5577a146bfe7b662d78f4c42ff707c69f16ee3713f96ba3eb'
EXPECTED_MAPS=[
 {'map':'mp_nuketown_2020','validDxbcCount':1972,'secondaryShaderCount':1185},
 {'map':'mp_raid','validDxbcCount':3064,'secondaryShaderCount':1961},
 {'map':'mp_hijacked','validDxbcCount':2299,'secondaryShaderCount':1380},
 {'map':'zm_prison','validDxbcCount':3920,'secondaryShaderCount':2522},
 {'map':'zm_tomb','validDxbcCount':2839,'secondaryShaderCount':1061},
]
def load(path):
 s=importlib.util.spec_from_file_location('guard',path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-lightmap-secondary-rdef-guard-v1'
 assert d['mapCoverage']==EXPECTED_MAPS
 s=d['summary'];assert s=={
  'retainedMapCount':5,'uniqueSecondaryShaderCount':4531,'bindingFailureCount':0,
  'textureBindPoint':13,'textureBindCount':1,'textureDimension':'TEXTURE2D',
  'samplerBindPoint':13,'samplerBindCount':1,'samplerDimension':'UNKNOWN','shaderRowsSha256':EXPECTED_ROWS_SHA}
 assert d['binding']=={
  'name':'lightmapSamplerSecondary',
  'texture':{'inputType':'TEXTURE','dimension':'TEXTURE2D','bindPoint':13,'bindCount':1},
  'sampler':{'inputType':'SAMPLER','dimension':'UNKNOWN','bindPoint':13,'bindCount':1}}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LIGHTMAP_SECONDARY_RDEF_GUARD_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier).build(a.root);validate(got);assert got==d,'retail rerun differs from committed secondary-RDEF guard manifest'
 print('PASS: T6 retained lightmapSamplerSecondary RDEF guard regression')
if __name__=='__main__':main()
