#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, struct
from pathlib import Path
EXPECTED_SUMMARY={'retainedMapCount':5,'specialDistinctTechniqueSetCount':31,'specialTechniqueSetOccurrenceCount':52,'techniqueSetBlocksStructurallyExact':True,'totalTechniqueSetCount':411,'totalInlineTechniqueCount':8434,'totalInlineShaderObjectCount':8296,'specialTechniqueSetsWithDirectPixelShaderPayload':30,'specialTechniqueSetsWithoutDirectPixelShaderPayload':1,'directPixelShaderPayloadCount':203,'uniqueDirectPixelShaderCount':176,'directPixelShaderBytes':2168064,'directVertexShaderPayloadCount':44,'uniqueDirectVertexShaderCount':31,'directVertexShaderBytes':254208,'directDxbcValidationFailureCount':0}
STRUCT={'mp_nuketown_2020':(59,1232,1209,63150420),'mp_raid':(96,1989,1984,66275632),'mp_hijacked':(71,1417,1408,58846527),'zm_prison':(128,2666,2586,82099460),'zm_tomb':(57,1130,1109,78964845)}
HOLDOUT='wpc_shadowcaster_wj6w5j60'
def load(path,name='m'):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-special-shader-payload-census-v1' and d['summary']==EXPECTED_SUMMARY
 assert len(d['specialTechniqueSetCoverage'])==31
 cov={x['techniqueSet']:x for x in d['specialTechniqueSetCoverage']};assert [k for k,v in cov.items() if not v['hasDirectPixelShaderPayload']]==[HOLDOUT]
 h=cov[HOLDOUT];assert h['occurrenceCount']==5 and h['nonnullTechniqueRefCount']==30 and h['packedTechniqueRefCount']==25 and h['packedPixelShaderRefCountWithinInlineTechniques']==5
 assert len(d['directPixelShaderExamples'])==4 and len({x['sha256'] for x in d['directPixelShaderExamples']})==4
 assert len(d['directVertexShaderExamples'])==2 and len({x['sha256'] for x in d['directVertexShaderExamples']})==2
 assert len(d['uniqueDirectPixelShaderSetSha256'])==64 and len(d['uniqueDirectVertexShaderSetSha256'])==64
 for x in d['structuralValidation']:
  exp=STRUCT[x['map']];assert (x['techniqueSetCount'],x['inlineTechniqueCount'],x['inlineShaderObjectCount'],x['end'])==exp and x['end']==x['gfxWorldStart']
def negatives(mod,helper):
 blocks=(1024,)*8;b=bytearray(26);struct.pack_into('<IIII',b,0,0xffffffff,0,0xffffffff,8);b[16:18]=b'x\0';b[18:26]=b'NOTDXBC!'
 try:mod.parse_shader(bytes(b),0,blocks,helper,'ps')
 except ValueError as e:assert 'not DXBC' in str(e)
 else:raise AssertionError('malformed direct program accepted')
 b=bytearray(16);struct.pack_into('<IIII',b,0,0,1,0,0)
 try:mod.parse_shader(bytes(b),0,blocks,helper,'ps')
 except ValueError as e:assert 'runtime pointer nonzero' in str(e)
 else:raise AssertionError('runtime pointer accepted')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHADER_PAYLOAD_CENSUS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--special-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);mod=load(a.verifier,'specialshader');helper=load(a.helper,'helper');negatives(mod,helper)
 if a.root:
  got=mod.build(a.root,a.special_manifest,a.helper);validate(got);assert got==d,'retail rerun differs from committed manifest'
 print('PASS: T6 retail special shader payload census regression')
if __name__=='__main__':main()
