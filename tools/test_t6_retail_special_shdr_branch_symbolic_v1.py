#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_SOURCE='aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7'
EXPECTED_DAG='b46197488dd9ef523158a4488a4fab8fe0ced793ffdbf44e34f2283f5327586b'
EXPECTED_ROWS='e4ce7309c2a84449c830eb232b3c7a34317f2a2d27f56d5668b501420b469f7d'
EXPECTED_SUMMARY={'controlFlowLightmappedShaderCount':78,'ifCount':175,'elseCount':75,'endifCount':175,'maxNestingDepth':2,'ifTestModeCounts':{'nonzero':175},'conditionLightmapDependentCount':0,'lightmapDependentSampleInputCount':0,'discardCount':0,'symbolicBlockerCount':0,'lightmapSampleCount':232,'lightmapDependentOutputCount':234,'nodeCount':71736,'uniqueDagCount':78,'familyCounts':{'emissive_or_burning':{'shaderCount':33,'ifCount':78,'elseCount':36,'sampleCount':99,'outputCount':99,'nodeCount':33251,'conditionLightmapDependentCount':0},'rawnormal_special':{'shaderCount':11,'ifCount':26,'elseCount':12,'sampleCount':33,'outputCount':33,'nodeCount':10788,'conditionLightmapDependentCount':0},'tv_special':{'shaderCount':20,'ifCount':36,'elseCount':12,'sampleCount':60,'outputCount':60,'nodeCount':13333,'conditionLightmapDependentCount':0},'water':{'shaderCount':14,'ifCount':35,'elseCount':15,'sampleCount':40,'outputCount':42,'nodeCount':14364,'conditionLightmapDependentCount':0}},'outputDependencyPatternCount':6}

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def validate(d):
 assert d['format']=='t6-retail-special-shdr-branch-symbolic-v1' and d['sourcePixelShaderSetSha256']==EXPECTED_SOURCE
 assert d['dagSetSha256']==EXPECTED_DAG and d['shaderRowSetSha256']==EXPECTED_ROWS and d['summary']==EXPECTED_SUMMARY
 assert len(d['outputDependencyPatterns'])==6 and sum(x['count'] for x in d['outputDependencyPatterns'])==78
 assert [(x['family'],x['count']) for x in d['outputDependencyPatterns']]==[('emissive_or_burning',33),('rawnormal_special',11),('tv_special',20),('water',2),('water',11),('water',1)]
 assert len(d['shaderRowExamples'])==3

def negatives(mod):
 assert mod.if_mode(0)=='zero' and mod.if_mode(1<<18)=='nonzero'
 class D:
  def __init__(self):self.nodes=[]
  def add(self,kind,**kw):self.nodes.append((kind,kw));return len(self.nodes)-1
 dag=D();merged=mod.merge_state(dag,7,{('temp',0,0):1},{('temp',0,0):2});assert merged[('temp',0,0)]==0 and dag.nodes[0][0]=='op' and dag.nodes[0][1]['op']=='select'
 try:mod.merge_state(dag,7,{('temp',0,0):1},{})
 except Exception as e:raise AssertionError(f'merge should represent missing branch, not fail: {e}')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHDR_BRANCH_SYMBOLIC_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_shdr_branch_symbolic_v1.py'));ap.add_argument('--root',type=Path);ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--opcode-tool',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));ap.add_argument('--operand-tool',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));ap.add_argument('--straight-tool',type=Path,default=Path('tools/t6_retail_special_shdr_symbolic_v1.py'));a=ap.parse_args();manifest=json.loads(a.manifest.read_text());validate(manifest);mod=load(a.verifier,'branchsym');negatives(mod)
 if a.root:
  got=mod.build(a.root,a.family_manifest,a.opcode_tool,a.operand_tool,a.straight_tool);validate(got)
 print('PASS: T6 retail special branch-aware SHDR symbolic regression')
if __name__=='__main__':main()
