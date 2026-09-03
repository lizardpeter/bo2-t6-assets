#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_ROWS_SHA='1b609b25f75a1630bee7c21670110ea74e871f973f029507e5f0e5d90bc735e3'
EXPECTED_SUMMARY={
 'retainedMapCount':5,'slot4TechniqueSetOccurrenceCount':273,'uniqueSlot4ShaderCount':173,
 'directionalEquationCount':331,'explicitEquationCount':316,'foldedEquationCount':15,
 'twoEquationShaderCount':158,'oneEquationShaderCount':15,'coordinateCheckCount':1986,
 'rgbFinalOutputAncestryCheckCount':993,'formatEquationCounts':{'1':67,'2':47,'3':56,'4':88,'5':41,'6':16,'7':16},
 'reflectionProbeShaderCount':158,'shaderFailureCount':0}
def load(path):
 s=importlib.util.spec_from_file_location('proof',path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-layered-directional-lightmap-v1'
 assert d['sourceSlot4ShaderSetSha256']=='f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799'
 assert d['shaderRowsSha256']==EXPECTED_ROWS_SHA
 assert d['summary']==EXPECTED_SUMMARY
 assert d['shaderRowSchema']==['sha256','techniqueSet','worldVertFormat','directionalEquationCount','encoding','coordinateCheckCount','rgbAncestryCheckCount']
 assert len(d['representativeShaderRows'])==2
 assert {r['encoding'] for r in d['representativeShaderRows']}=={'explicit','folded'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_DIRECTIONAL_LIGHTMAP_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_directional_lightmap_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier).build(a.root);validate(got);assert got==d,'retail rerun differs from committed directional-lightmap manifest'
 print('PASS: T6 retained layered directional lightmap regression')
if __name__=='__main__':main()
