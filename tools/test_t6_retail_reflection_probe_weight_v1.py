#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_SUMMARY={
 'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'reflectionCubeFetchCount':5888,
 'sampleLOpcodeCount':5879,'sampleBOpcodeCount':9,'firstRgbConsumerMulCount':5888,'firstRgbConsumerFailureCount':0,
 'alphaBiasBits':'358637bd','reciprocalNumeratorBits':'3f800000','firstMulDistance3Count':5858,'firstMulDistance4Count':30,
 'finalAlignedRgbAncestryCheckCount':17664,'finalAlignedRgbAncestryFailureCount':0,
 'shaderRowsSha256':'813f05f52beb2edd114a45400e84743e5ac20f85e3cb97f9a48be3394c1d9753',
 'firstMulPackingRowsSha256':'2baf4e7a9ddf32c909db5c38b011acaa94343ef06b11130c4cdff982c1f5810f',
 'outputTagCardinalityRowsSha256':'9a53f4e61a1a6c6c829fe5ed50bacc78813a4e6427b877c0e17650f01076247f'}
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-reflection-probe-weight-v1'
 assert d['equation']=={'decodedProbeRgb':'probe.rgb / (probe.a + 1e-6)','alphaBiasBits':'358637bd','reciprocalNumeratorBits':'3f800000'}
 assert d['summary']==EXPECTED_SUMMARY
 assert len(d['firstMulPackingPatterns'])==12
 assert len(d['outputTagCardinalityPatterns'])==5
 assert sum(x['count'] for x in d['firstMulPackingPatterns'])==5888
 assert sum(x['shaderCount'] for x in d['outputTagCardinalityPatterns'])==5868
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_WEIGHT_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'weight').build(a.root,a.coordinate_verifier,a.guard);validate(got);assert got==d,'retail rerun differs from committed reflection weight manifest'
 print('PASS: T6 retained reflectionProbeSampler RGB decode/final ancestry regression')
if __name__=='__main__':main()
