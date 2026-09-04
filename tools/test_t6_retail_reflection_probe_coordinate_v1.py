#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_ROWS_SHA='6c2bbd4e5fe92d4e9a05a1debdac0904d870809cb17a292a4205bb7bea2861b3'
EXPECTED_SUMMARY={
 'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'reflectionCubeSampleCount':5888,
 'oneSampleShaderCount':5848,'twoSampleShaderCount':20,'sampleOpcodeCounts':{'SAMPLE_B':9,'SAMPLE_L':5879},
 'resourceSamplerPairFailureCount':0,'coordinateMadCheckCount':5888,'doubleDotCheckCount':5888,
 'normalizedVectorCheckCount':11776,'reflectFormulaFailureCount':0,
 'coordinateStorageCounts':{'xyw':725,'xyz':4896,'xzw':8,'yzw':259},
 'rawVectorKindPairCounts':{'INPUT+INPUT':768,'INPUT+TEMP':5120},'shaderRowsSha256':EXPECTED_ROWS_SHA}
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-reflection-probe-coordinate-v1'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['equation']=={
  'normalizedA':'rawA * rsq(dot(rawA,rawA))','normalizedB':'rawB * rsq(dot(rawB,rawB))',
  'cubeCoordinate':'normalizedB - 2 * normalizedA * dot(normalizedA, normalizedB)'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--rdef-guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'coord').build(a.root,a.rdef_guard);validate(got);assert got==d,'retail rerun differs from committed reflection-coordinate manifest'
 print('PASS: T6 retained reflectionProbeSampler coordinate regression')
if __name__=='__main__':main()
