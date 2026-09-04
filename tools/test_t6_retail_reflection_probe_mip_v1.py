#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_SUMMARY={
 'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'reflectionCubeFetchCount':5888,
 'sampleLOpcodeCount':5879,'sampleBOpcodeCount':9,'literalLodCount':227,'affineLodCount':5652,'literalBiasCount':9,
 'affine4Minus4xCount':4236,'affine0475xCount':1327,'affine025xPlus075Count':30,'compiledZeroAffineCount':59,
 'literalLod0Count':99,'literalLod08Count':48,'literalLod24Count':40,'literalLod4Count':40,'literalBiasMinus3Count':9,
 'mipFormFailureCount':0,'shaderRowsSha256':'d057e0b75023d981fd12f72bc01abc8e668695bbaba6b757e4c7ebfe03441df1',
 'directSourceSampleRowsSha256':'17d7dac80c5e8bc7afe5adfc58a3a82d8337f8c9169036977d32a7609afe1801'}
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-reflection-probe-mip-v1'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['forms']['sampleB']['literalBiasBits']=='c0400000'
 assert d['forms']['sampleL']['affinePairsBits']==[['c0800000','40800000'],['3ef33333','00000000'],['3e800000','3f400000'],['00000000','00000000']]
 assert len(d['directAffineSourceSamples'])==18
 assert len(d['affineSourceOriginCounts'])==13
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_MIP_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'mip').build(a.root,a.coordinate_verifier,a.guard);validate(got);assert got==d,'retail rerun differs from committed reflection mip manifest'
 print('PASS: T6 retained reflectionProbeSampler mip regression')
if __name__=='__main__':main()
