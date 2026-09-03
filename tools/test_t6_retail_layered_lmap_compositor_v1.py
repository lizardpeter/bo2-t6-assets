#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from collections import Counter
from pathlib import Path
EXPECTED={'retainedMapCount':5,'techniqueSetOccurrenceCount':273,'uniqueSlot4ShaderCount':173,'recurrenceMatchedShaderCount':173,'recurrenceFailureCount':0,'canonicalRgbWeightMismatchCount':0,'modeSignatureCount':23,'totalLayerOperationCount':301,'layerDispatchFailureCount':0,'operatorStepCounts':{'a':23,'b':177,'m':71,'t':30},'weightClassCounts':{'alpha_vertex':140,'height':50,'threshold_alpha_vertex':30,'vertex_only':81},'bWeightClassCounts':{'alpha_vertex':117,'height':50,'vertex_only':10},'uniqueHeightWeightDagCount':44,'heightLayerOperationCount':50,'crossModeShaderReuseCount':0,'crossTechniqueSetNameShaderReuseCount':0,'crossWorldVertFormatShaderReuseCount':0,'slot4ShaderSetSha256':'f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799','perShaderCompositorRowsSha256':'5c242506d0ca1dda9135a6d0030a4be4a63c23bc6a49621bff54da0e4ec25879','heightWeightDagSetSha256':'58f547861e2fe86526db62868137071d6c9803c4caaac60574263396dcfce8f1'}
def load(p,n='m'):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-layered-lmap-compositor-v1' and d['summary']==EXPECTED
 assert len(d['modeSignatureCoverage'])==23
 assert sum(x['layerOperationCount'] for x in d['dispatcherEvidence'])==301
 assert len(d['representativeShaders'])>=3
 o=Counter();c=Counter();b=Counter()
 for x in d['dispatcherEvidence']:
  o[x['mode']]+=x['layerOperationCount'];c[x['weightClass']]+=x['layerOperationCount']
  if x['mode']=='b':b[x['weightClass']]+=x['layerOperationCount']
 assert dict(sorted(o.items()))==EXPECTED['operatorStepCounts'] and dict(sorted(c.items()))==EXPECTED['weightClassCounts'] and dict(sorted(b.items()))==EXPECTED['bWeightClassCounts']
 assert any(r['techniqueSet']=='lit_sm_r0c0n0x0_b1c1' and r['steps'][0]['weightClass']=='alpha_vertex' for r in d['representativeShaders'])
 assert any(any(s['weightClass']=='height' and 'v' in s['flags'] for s in r['steps']) for r in d['representativeShaders'])
def pure(m):
 assert m.predict('b',[])=='alpha_vertex' and m.predict('b',['n','v'])=='height' and m.predict('b',['n','x'])=='vertex_only'
 assert m.predict('a',[])=='alpha_vertex' and m.predict('m',[])=='vertex_only' and m.predict('t',['n'])=='threshold_alpha_vertex'
 assert m.specs('lit_sm_r0c0n0x0_b1c1n1v1_a2c2_m3c3')==[(1,'b',['n','v']),(2,'a',[]),(3,'m',[])]
 d=m.Dag();p=d.add('sample',resource='colorMapSampler',channel='x',sampler='s0',instruction=1);l=d.add('sample',resource='colorMapSampler1',channel='x',sampler='s1',instruction=2);w=d.add('input',name='COLOR.y');one=d.add('lit',value='1');half=d.add('lit',value='0.5')
 diff=d.add('add',l,d.add('neg',p));bn=d.add('add',p,d.add('mul',diff,w));assert m.nextstep(d,bn,p,1,'b','x')==w
 an=d.add('add',p,d.add('mul',w,l));assert m.nextstep(d,an,p,1,'a','x') is not None
 lm1=d.add('add',l,d.add('lit',value='-1'));mn=d.add('mul',p,d.add('add',one,d.add('mul',lm1,w)));assert m.nextstep(d,mn,p,1,'m','x')==w
 cond=d.add('ge',d.add('mul',l,w),half);tn=d.add('select',cond,l,p);assert m.nextstep(d,tn,p,1,'t','x')==cond
def main():
 a=argparse.ArgumentParser();a.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_LMAP_COMPOSITOR_V1.json'));a.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_lmap_compositor_v1.py'));a.add_argument('--root',type=Path);a.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));a.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));a.add_argument('--opcode',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));a.add_argument('--operand',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));a.add_argument('--inspector',type=Path,default=Path('tools/t6_dxbc_inspect_v1.py'));x=a.parse_args();d=json.loads(x.manifest.read_text());validate(d);m=load(x.verifier);pure(m)
 if x.root:
  got=m.compact_manifest(m.build_manifest(x.root,x.parser,x.helper,x.opcode,x.operand,x.inspector));validate(got);assert got==d,'retail rerun differs from committed manifest'
 print('PASS: T6 retail layered layer_lmap compositor regression')
if __name__=='__main__':main()
