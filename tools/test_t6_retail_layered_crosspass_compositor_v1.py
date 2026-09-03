#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_SUMMARY={'retainedMapCount':5,'straightLineSlotCount':10,'baselineSlot':4,'targetSlotCount':9,'techniqueSetOccurrenceCount':273,'uniqueShaderCountPerSlot':173,'shaderOccurrenceComparisonCount':2457,'layerWeightComparisonCount':3879,'semanticMismatchOccurrenceCount':0,'semanticWeightMismatchCount':0,'targetSemanticAmbiguityCount':0,'byteIdenticalToSlot4OccurrenceCount':0,'crossTechniqueSetNameShaderReuseCount':0,'multiVariantTechniqueSetNameCount':8,'allTargetSlotsEquivalent':True}
EXPECTED_SLOTS=[4,5,7,8,9,10,11,12,13,14]
EXPECTED_SHA='9928947c22ff49dd8d37688a6a72cd39e9868c54eff8461b189afe9182612233'
EXPECTED_MULTI=['lit_sm_r0c0n0_b1c1n1s1v1','lit_sm_r0c0n0_b1c1n1v1','lit_sm_r0c0n0s0_b1c1n1s1v1','lit_sm_r0c0n0s0_b1c1n1v1','lit_sm_r0c0n0s0_b1c1n1v1_m2c2','lit_sm_r0c0n0x0_b1c1n1s1v1','lit_sm_r0c0n0x0_b1c1n1s1v1_b2c2n2s2v2','lit_sm_r0c0n0x0_b1c1n1v1']
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-layered-crosspass-compositor-v1'
 assert d['summary']==EXPECTED_SUMMARY and d['slots']==EXPECTED_SLOTS and d['comparisonSetSha256']==EXPECTED_SHA
 assert d['multiVariantTechniqueSetNames']==EXPECTED_MULTI
 assert d['mapCoverage']=={'mp_hijacked':46,'mp_nuketown_2020':34,'mp_raid':66,'zm_prison':94,'zm_tomb':33}
 assert d['worldVertFormatCoverage']=={'1':78,'2':54,'3':46,'4':52,'5':26,'6':9,'7':8}
 assert [x['slot'] for x in d['slotCoverage']]==EXPECTED_SLOTS[1:]
 for x in d['slotCoverage']:
  assert x['techniqueSetOccurrenceCount']==273 and x['uniquePixelShaderCount']==173
  assert x['semanticMatchOccurrenceCount']==273 and x['semanticMismatchOccurrenceCount']==0
  assert x['layerWeightComparisonCount']==431 and x['byteIdenticalToSlot4OccurrenceCount']==0
  assert len(x['comparisonSetSha256'])==64
 c=d['semanticCanonicalization'];assert c['sampleInstructionPosition']=='omitted for cross-shader comparison only' and c['sampleResource']=='retained' and c['sampleChannel']=='retained' and c['sampleSampler']=='retained'
def semantic_negative_guards(v):
 class D:pass
 a=D();a.n=[{'kind':'sample','args':[],'resource':'colorMapSampler1','channel':'w','sampler':'colorMapSampler1','instruction':100}]
 b=D();b.n=[{'kind':'sample','args':[],'resource':'colorMapSampler1','channel':'w','sampler':'colorMapSampler1','instruction':900}]
 assert v.semantic_canon(a,0)==v.semantic_canon(b,0)
 for field,value in [('resource','colorMapSampler2'),('channel','x'),('sampler','otherSampler')]:
  c=D();n=dict(a.n[0]);n[field]=value;c.n=[n];assert v.semantic_canon(a,0)!=v.semantic_canon(c,0)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_CROSSPASS_COMPOSITOR_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_crosspass_compositor_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);v=load(a.verifier,'v');semantic_negative_guards(v)
 if a.root:
  got=v.build(a.root,Path('tools/t6_retail_special_shader_payload_census_v1.py'),Path('tools/t6_retail_world_formats_45_proof_v1.py'),Path('tools/t6_retail_layered_lmap_compositor_v1.py'),Path('tools/t6_retail_special_shdr_opcode_census_v1.py'),Path('tools/t6_retail_special_shdr_operand_census_v1.py'),Path('tools/t6_dxbc_inspect_v1.py'),a.jobs);validate(got);assert got==d,'retail rerun differs from committed cross-pass manifest'
 print('PASS: T6 retained layered cross-pass compositor regression')
if __name__=='__main__':main()
