#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED={
 'retainedMapCount':5,'surfaceNormalTargetShaderCount':4086,'surfaceNormalTargetFetchCount':4086,
 'targetPixelShaderMappedCount':3410,'targetPixelShaderUnmappedCount':676,'targetPassOccurrenceCount':5676,
 'directVertexShaderOccurrenceCount':64,'packedVertexShaderOccurrenceCount':5612,'uniqueDirectVertexShaderCount':16,
 'directTexcoord5ProducerProofCount':64,'directTexcoord5ProducerFailureCount':0,'worldMatrixProducerOccurrenceCount':64,
 'positionHomogeneousInputCheckCount':192,
 'producerRowsSha256':'f1f71ab4f04f794f3a055361ad5c81274968b1bad3800eec111056cde6300743',
 'directOccurrenceRowsSha256':'8508fc87dd1d0b1467c597c053f0650889aea78bfbf3dfd313248d6562a99639',
 'mapCoverageRowsSha256':'29127e72b64c03a9a65e3d40ee0260a054d3a2fdf1489f61b2a72bc3d42e7d19',
 'formatCoverageRowsSha256':'ad888b84a51da3a0aef79ae8f5676d6cf09972e24d528d258035f27d2c102d00',
 'unmappedPixelShaderSetSha256':'6db3e1b6f8e69f33524946acac524e9a53855b245b2d064b90ba12da17e76f91'}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-reflection-probe-texcoord5-producer-v1'
 assert d['summary']==EXPECTED
 assert d['equation']=={'directProducer':'TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz','rdefVariable':'dlights.worldMatrix','constantBufferRegister':3,'matrixRows':[0,1,2]}
 assert len(d['directVertexShaderRows'])==16
 assert sum(x['directPassOccurrenceCount'] for x in d['directVertexShaderRows'])==64
 assert all(x['equation']==d['equation']['directProducer'] and x['inputSemantic']=='POSITION0' and x['constantBuffer']=='dlights' and x['variable']=='worldMatrix' and x['rowElements']==[0,1,2] and x['rowByteOffsets']==[0,16,32] for x in d['directVertexShaderRows'])
 assert sum(x['targetPassOccurrenceCount'] for x in d['mapCoverage'])==5676
 assert sum(x['directVertexShaderOccurrenceCount'] for x in d['mapCoverage'])==64
 assert sum(x['packedVertexShaderOccurrenceCount'] for x in d['mapCoverage'])==5612
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD5_PRODUCER_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord5_producer_v1.py'));ap.add_argument('--root',type=Path)
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));ap.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'));ap.add_argument('--surface-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'));ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'prod').build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.surface_verifier,a.shared_verifier,a.guard);validate(got);assert got==d,'retail rerun differs from committed TEXCOORD5-producer manifest'
 print('PASS: T6 retained reflection TEXCOORD5 direct vertex-producer regression')
if __name__=='__main__':main()
