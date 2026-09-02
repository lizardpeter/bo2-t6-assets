#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED_SOURCE='aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7'
EXPECTED_DAG='ffc6c894a767aa4563e67d05b8f1911d6f09e3b4f3b288148d86fd65c43bb30c'
EXPECTED_ROWS='646419b3f90fdd16a6be584cd994b6d00bd0e6daf923f1d2de4b9a07d2882d81'
EXPECTED_SUMMARY={'branchFreeLightmappedShaderCount':76,'symbolicBlockerCount':0,'lightmapSampleCount':211,'lightmapDependentOutputCount':228,'nodeCount':43108,'uniqueDagCount':76,'familyCounts':{'emissive_or_burning':{'shaderCount':27,'sampleCount':81,'nodeCount':14463,'outputCount':81},'rawnormal_special':{'shaderCount':9,'sampleCount':27,'nodeCount':4535,'outputCount':27},'water':{'shaderCount':40,'sampleCount':103,'nodeCount':24110,'outputCount':120}},'outputDependencyPatternCount':5,'lightmapDependentSampleInputCount':0,'lightmapDependentDiscardCount':0}

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def row_projection(rows):return [{k:r[k] for k in ('sha256','family','sampleCount','nodeCount','outputCount','dagSha256')} for r in rows]
def row_digest(rows):return hashlib.sha256(json.dumps(row_projection(rows),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def validate_manifest(d):
 assert d['format']=='t6-retail-special-shdr-symbolic-v1'
 assert d['sourcePixelShaderSetSha256']==EXPECTED_SOURCE and d['dagSetSha256']==EXPECTED_DAG and d['shaderRowSetSha256']==EXPECTED_ROWS
 assert d['summary']==EXPECTED_SUMMARY and len(d['outputDependencyPatterns'])==5 and sum(x['count'] for x in d['outputDependencyPatterns'])==76
 assert [(x['family'],x['count']) for x in d['outputDependencyPatterns']]==[('emissive_or_burning',27),('rawnormal_special',9),('water',24),('water',9),('water',7)]
 assert len(d['shaderRowExamples'])==3

def project_full(got):
 return {'format':got['format'],'sourcePixelShaderSetSha256':got['sourcePixelShaderSetSha256'],'dagSetSha256':got['dagSetSha256'],'shaderRowSetSha256':row_digest(got['shaderRows']),'summary':got['summary'],'outputDependencyPatterns':got['outputDependencyPatterns']}

def negatives(mod):
 dag=mod.Dag();a=dag.add('lightmapSample',role='secondary',channel='x',textureRegister=13,samplerRegister=13,opcode='sample',instructionDword=10,args=[]);b=dag.add('lightmapSample',role='secondary',channel='x',textureRegister=13,samplerRegister=13,opcode='sample',instructionDword=20,args=[])
 assert a!=b and dag.deps(a)=={'secondary.x'} and dag.deps(b)=={'secondary.x'}
 blockers=[];temp={'type':'temp','component':{'numComponents':2,'selectionMode':'swizzle','swizzle':[0,1,2,3]},'indices':[{'immediate32':0}],'extensions':[],'literalDwords':[]}
 mod.source_nodes(temp,[0],{},mod.Dag(),blockers,7);assert blockers and blockers[0]['reason']=='read-before-write'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHDR_SYMBOLIC_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_shdr_symbolic_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--opcode-tool',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));ap.add_argument('--operand-tool',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));a=ap.parse_args();manifest=json.loads(a.manifest.read_text());validate_manifest(manifest);mod=load(a.verifier,'sym');negatives(mod)
 if a.root:
  got=mod.build(a.root,a.family_manifest,a.opcode_tool,a.operand_tool);p=project_full(got);assert p['sourcePixelShaderSetSha256']==manifest['sourcePixelShaderSetSha256'];assert p['dagSetSha256']==manifest['dagSetSha256'];assert p['shaderRowSetSha256']==manifest['shaderRowSetSha256'];assert p['summary']==manifest['summary'];assert p['outputDependencyPatterns']==manifest['outputDependencyPatterns']
 print('PASS: T6 retail special straight-line SHDR symbolic regression')
if __name__=='__main__':main()
