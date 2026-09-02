#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_SOURCE='aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7'
EXPECTED_SHAPES='8dd3ff19322530bd181b49a5ab8611ee1b6d66136d4ac1a241fee644e9b79ad9'
EXPECTED_TYPES={'constant_buffer':7228,'immediate32':6793,'input':6084,'output':526,'resource':4595,'sampler':4595,'temp':72369}
EXPECTED_FAMILY={'default':{'instructionCount':6,'operandCount':8,'shaderCount':1},'emissive_or_burning':{'instructionCount':13521,'operandCount':40075,'shaderCount':60},'rawnormal_special':{'instructionCount':4354,'operandCount':12946,'shaderCount':20},'tv_special':{'instructionCount':4484,'operandCount':13056,'shaderCount':20},'unlit':{'instructionCount':605,'operandCount':1449,'shaderCount':16},'water':{'instructionCount':11725,'operandCount':34656,'shaderCount':59}}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-special-shdr-operand-census-v1'
 assert d['sourcePixelShaderSetSha256']==EXPECTED_SOURCE and d['operandShapeSetSha256']==EXPECTED_SHAPES
 assert len(d['operandShapes'])==24 and sum(x['count'] for x in d['operandShapes'])==102190
 q=d['summary'];assert q['shaderCount']==176 and q['instructionCount']==34695 and q['operandCount']==102190 and q['operandDecodeFailureCount']==0 and q['operandShapeCount']==24
 assert q['operandTypeCounts']==EXPECTED_TYPES and q['indexDimensionCounts']=={'0':6793,'1':88169,'2':7228}
 assert q['indexRepresentationCounts']=={'imm32':102625} and q['relativeIndexOperandCount']==0
 assert q['modifierCounts']=={'abs':195,'neg':2308} and q['immediateLiteralCounts']=={'immediate32:1':3139,'immediate32:4':3654}
 assert q['componentSelectionModeCounts']=={'mask':34862,'none':8890,'select1':19757,'swizzle':38681}
 assert q['familyCounts']==EXPECTED_FAMILY
def guards(m):
 # Unknown operand type 14.
 try:m.parse_operand([(14<<12)],0,1)
 except m.OperandDecodeError as e:assert 'unknown operand type' in str(e)
 else:raise AssertionError('unknown operand type accepted')
 # 1D operand with invalid 3-bit index representation 5.
 tok=1 | (0<<12) | (1<<20) | (5<<22)
 try:m.parse_operand([tok],0,1)
 except m.OperandDecodeError as e:assert 'unknown index representation' in str(e)
 else:raise AssertionError('invalid index representation accepted')
 # Chained extended operand token is rejected rather than skipped.
 tok=1 | (0<<12) | 0x80000000
 try:m.parse_operand([tok,0x80000041],0,2)
 except m.OperandDecodeError as e:assert 'chained extended operand' in str(e)
 else:raise AssertionError('extended operand chain accepted')
 # Scalar immediate32 with missing literal payload.
 tok=1 | (4<<12)
 try:m.parse_operand([tok],0,1)
 except m.OperandDecodeError as e:assert 'literal outside instruction' in str(e)
 else:raise AssertionError('truncated immediate literal accepted')
 # RET encodes zero operands; an extra DWORD must not be silently consumed.
 try:m.parse_instruction([2<<24|62,0],0,['x']*62+['ret'])
 except m.OperandDecodeError as e:assert 'decoded end' in str(e)
 else:raise AssertionError('instruction trailing token accepted')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHDR_OPERAND_CENSUS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--opcode-tool',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);m=load(a.verifier,'operand');guards(m)
 if a.root:
  got=m.build(a.root,a.family_manifest,a.opcode_tool);validate(got);assert got==d,'retail rerun differs from committed operand census manifest'
 print('PASS: T6 retail special SHDR operand census regression')
if __name__=='__main__':main()
