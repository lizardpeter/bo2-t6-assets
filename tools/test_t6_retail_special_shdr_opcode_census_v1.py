#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,struct
from pathlib import Path
EXPECTED_SOURCE='aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7'
EXPECTED_LENSET='f1b242e93ec040bf5e824bfb04ede47da978925613b897c1f64feccf23ac1d2c'
EXPECTED_COUNTS={'shaderCount':176,'instructionCount':34695,'walkFailureCount':0,'opcodeTypeCount':39,'extendedOpcodeTokenCount':0,'customDataInstructionCount':0,'saturateInstructionCount':2088}
EXPECTED_FAMILY_INSTRUCTIONS={'default':6,'emissive_or_burning':13521,'rawnormal_special':4354,'tv_special':4484,'unlit':605,'water':11725}
EXPECTED_FAMILY_TYPES={'default':6,'emissive_or_burning':30,'rawnormal_special':29,'tv_special':30,'unlit':21,'water':34}
EXPECTED_CONTROL={'emissive_or_burning':33,'rawnormal_special':11,'tv_special':20,'water':14}
EXPECTED_OPCODES={'add':4032,'and':3,'dcl_constant_buffer':408,'dcl_input_ps':1298,'dcl_input_ps_siv':17,'dcl_output':176,'dcl_resource':1156,'dcl_sampler':1156,'dcl_temps':174,'discard':1,'div':1258,'dp2':225,'dp3':2089,'dp4':867,'else':75,'endif':175,'exp':655,'frc':240,'ge':95,'if':175,'log':273,'lt':146,'mad':6150,'max':26,'min':152,'mov':861,'movc':238,'mul':7629,'or':20,'ret':176,'round_ni':9,'rsq':830,'sample':1297,'sample_b':9,'sample_c_lz':1956,'sample_d':40,'sample_l':137,'sincos':9,'sqrt':462}
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-special-shdr-opcode-census-v1'
 assert d['sourcePixelShaderSetSha256']==EXPECTED_SOURCE
 assert d['instructionLengthVariantCount']==76 and d['instructionLengthVariantSetSha256']==EXPECTED_LENSET
 q=d['summary']
 for k,v in EXPECTED_COUNTS.items():assert q[k]==v,(k,q[k],v)
 assert q['familyInstructionCounts']==EXPECTED_FAMILY_INSTRUCTIONS
 assert q['familyOpcodeTypeCounts']==EXPECTED_FAMILY_TYPES
 assert q['familyControlFlowShaderCounts']==EXPECTED_CONTROL
 assert q['opcodeCounts']==EXPECTED_OPCODES
 assert 'unlit' not in q['familyControlFlowShaderCounts']
def malformed_walk_guards(m):
 # Declared program DWORD count disagrees with actual payload.
 bad=struct.pack('<III',0x40,4,0)
 try:m.walk(bad)
 except ValueError as e:assert 'program length mismatch' in str(e)
 else:raise AssertionError('program-length mismatch accepted')
 # Zero encoded instruction length must fail closed.
 bad=struct.pack('<III',0x40,3,0)
 try:m.walk(bad)
 except ValueError as e:assert 'bad instruction length' in str(e)
 else:raise AssertionError('zero-length instruction accepted')
 # Custom-data opcode requires its explicit length DWORD.
 bad=struct.pack('<III',0x40,3,53)
 try:m.walk(bad)
 except ValueError as e:assert 'truncated customdata' in str(e)
 else:raise AssertionError('truncated customdata accepted')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHDR_OPCODE_CENSUS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);m=load(a.verifier,'shdr');malformed_walk_guards(m)
 if a.root:
  got=m.build(a.root,a.family_manifest,a.parser,a.helper);validate(got);assert got==d,'retail rerun differs from committed SHDR opcode manifest'
 print('PASS: T6 retail special SHDR opcode census regression')
if __name__=='__main__':main()
