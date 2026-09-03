#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED={
 'shaderCount':107,'rawVectorConstructionCheckCount':107,'rawVectorConstructionFailureCount':0,'basisPatternCount':1,
 'normalizationVectorCheckCount':107,'normalizationComponentCheckCount':321,'normalizationFailureCount':0,
 'signedSecondaryLightmapDotShaderCount':107,'signedSecondaryChannelDecodeCheckCount':321,'signedSecondaryChannelDecodeFailureCount':0,
 'texcoord5NormalizedDotShaderCount':101,'texcoord5NormalizedDotCount':202,'texcoord5NoDotShaderCount':6,
 'rowsSha256':'439ea8e76555fd8aedd5739cc5a08e729b3a99c55c24acc0e100478390dad622'}
EQ={'rawNormal':'TEXCOORD1.xyz + layeredNormalX * TEXCOORD3.xyz + layeredNormalY * TEXCOORD2.xyz','normalize':'rawNormal * rsq(dot(rawNormal, rawNormal))','secondaryDirection':'2 * lightmapSamplerSecondary.rgb - 1','secondaryDirectionalDot':'dot(secondaryDirection, normalizedNormal)'}
BASIS={'baseNormal':['TEXCOORD1.x','TEXCOORD1.y','TEXCOORD1.z'],'layeredXBasis':['TEXCOORD3.x','TEXCOORD3.y','TEXCOORD3.z'],'layeredYBasis':['TEXCOORD2.x','TEXCOORD2.y','TEXCOORD2.z']}
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-layered-normal-reconstruction-v1' and d['summary']==EXPECTED
 assert d['equations']==EQ and d['basis']==BASIS
 assert d['sourceSlot4ShaderSetSha256']=='f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799'
 assert len(d['examples'])==5
 for e in d['examples']:
  assert e['texcoord5NormalizedDotCount'] in (0,2)
  for k in ('sha256','rawVectorSha256','normalizedVectorSha256','signedSecondaryDotSha256'):assert len(e[k])==64
 assert 'downstream interpretation' in d['proofBoundary']
def negative_guards(v):
 class D:pass
 d=D();d.n=[{'kind':'lit','value':-1.0,'args':[]},{'kind':'sample','resource':'lightmapSamplerSecondary','channel':'x','args':[]},{'kind':'lit','value':2.0,'args':[]},{'kind':'mul','args':[1,2]},{'kind':'add','args':[0,3]}]
 assert v.signed_secondary_channel(d,4)=='x'
 d.n[2]={'kind':'lit','value':1.0,'args':[]};assert v.signed_secondary_channel(d,4) is None
 d.n[2]={'kind':'lit','value':2.0,'args':[]};d.n[1]['resource']='lightmapSamplerPrimary';assert v.signed_secondary_channel(d,4) is None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_NORMAL_RECONSTRUCTION_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_normal_reconstruction_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);v=load(a.verifier,'v');negative_guards(v)
 if a.root:
  got=v.build(a.root,Path('tools/t6_retail_special_shader_payload_census_v1.py'),Path('tools/t6_retail_world_formats_45_proof_v1.py'),Path('tools/t6_retail_layered_lmap_compositor_v1.py'),Path('tools/t6_retail_special_shdr_opcode_census_v1.py'),Path('tools/t6_retail_special_shdr_operand_census_v1.py'),Path('tools/t6_dxbc_inspect_v1.py'));validate(got);assert got==d,'retail rerun differs from committed normal reconstruction manifest'
 print('PASS: T6 retained layered normal reconstruction regression')
if __name__=='__main__':main()
