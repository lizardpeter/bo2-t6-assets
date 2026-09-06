#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v31 as v31
from t6_world_gltf_export_v1 import glb_bytes

def glb_fixture():
 recipe={'material':'*m','techniqueSet':'lit_sm_r0c0_b1c1s1','pixelShaderArchetype':'sha256:'+'a'*64,'worldVertFormats':[1],'proof':{'fixture':True},'generatedSpecularStateV1':{'material':'*m','pixelShaderArchetype':'sha256:'+'a'*64,'baseline':{'mode':'retail_fallback','alphaMode':'constantZero'},'steps':[{'layerIndex':1,'operator':'b'}]}}
 doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':0}],'materials':[{'name':'*m','extras':{'T6':{'generatedShaderRecipeV1':recipe}}}]}
 return glb_bytes(doc,b'')
def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v31_') as td:
  root=Path(td);old=root/'m_v30.glb';gb=glb_fixture();old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]});square=side('square.json',{'format':'t6-generated-final-output-rgb-square-anchor-v1','shaders':[]});spec=side('spec.json',{'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]})
  om=root/'old.json';om.write_text('{}')
  base={'format':v31.v30.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputRgbSquareAnchor':square,'generatedFinalOutputSpecularStateAnchor':spec},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v31.v30.run_oat_textured_pipeline;oldrgb=v31.rgb_anchor.build;oldjoin=v31.factor_join.build;calls=[]
  try:
   v31.v30.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fr(recipes,fd,sq,strict=True):
    calls.append(('rgb',strict,recipes['materials'][0]['material']))
    return {'format':v31.rgb_anchor.FORMAT,'materials':[{'material':'*m','steps':[{'layerIndex':1,'operation':'blend','sharedFactorSha256':'a'*64}]}],'summary':{'materialCount':1,'layerStepCount':1,'uniqueSharedFactorDagCount':1,'fullyMatchedMaterialCount':1,'strict':True},'rowsSha256':'r'*64}
   def fj(rgb,sp,strict=True):
    calls.append(('join',strict,rgb['materials'][0]['material']))
    return {'format':v31.factor_join.FORMAT,'materials':[{'material':'*m','allStepsMatch':True}],'summary':{'specularMaterialCount':1,'factorJoinCheckCount':1,'exactMatchCount':1,'mismatchCount':0,'fullyMatchedMaterialCount':1,'strict':True},'mismatches':[],'rowsSha256':'j'*64}
   v31.rgb_anchor.build=fr;v31.factor_join.build=fj
   result=v31.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v31.v30.run_oat_textured_pipeline=oldrun;v31.rgb_anchor.build=oldrgb;v31.factor_join.build=oldjoin
  assert calls==[('rgb',True,'*m'),('rgb',True,'*m'),('join',True,'*m'),('join',True,'*m')]
  assert result['format']==v31.FORMAT
  assert result['validation']['v31RgbFactorFullyMatchedMaterialCount']==1
  assert result['validation']['v31SpecularRgbFactorMismatchCount']==0
  assert result['validation']['v31SpecularRgbFullyMatchedMaterialCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputRgbFactorAnchor']['path']).read_text())['summary']['layerStepCount']==1
  assert json.loads(Path(result['outputs']['generatedFinalOutputSpecularRgbFactorJoin']['path']).read_text())['summary']['mismatchCount']==0
  assert not om.exists()
 print('PASS: production v31 exact RGB factor/specular cross-proof sidecars');return 0
if __name__=='__main__':raise SystemExit(main())
