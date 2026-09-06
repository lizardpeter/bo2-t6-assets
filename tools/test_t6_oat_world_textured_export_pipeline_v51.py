#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v51 as v51

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v51_') as td:
  root=Path(td);old=root/'m_v50.glb';gb=b'UNCHANGED-V50';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':v51.replay.FINAL_FORMAT});cb=side('cb.json',{'format':v51.replay.CB_FORMAT});cc=side('cc.json',{'format':v51.replay.CODE_CONST_FORMAT});tex=side('tex.json',{'format':v51.replay.TEX_FORMAT});cs=side('cs.json',{'format':v51.replay.CODE_SAMPLER_FORMAT});ms=side('ms.json',{'format':v51.replay.MAT_SAMPLER_FORMAT});constants=side('constants.json',{'format':'t6-retail-world-material-constants-v1'});oldm=root/'old.json';oldm.write_text('{}')
  base={'format':v51.v50.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputCbufferSignatureV2':cb,'generatedFinalOutputCodeConstantIdentityV2':cc,'generatedFinalOutputTextureResourceBindingV2':tex,'generatedFinalOutputCodeSamplerIdentityV2':cs,'generatedFinalOutputMaterialSamplerBinding':ms,'generatedRetailMaterialConstants':constants},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(oldm)}}
  saved=(v51.v50.run_oat_textured_pipeline,v51.matvals.build,v51.replay.build);calls=[]
  try:
   v51.v50.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def mv(a,b,c):calls.append('mv');return {'format':v51.matvals.FORMAT,'materials':[],'summary':{'materialCount':120}}
   def rp(a,b,c,d,e,f,g):calls.append(('rp',g['format'] if g else None));return {'format':v51.replay.FORMAT,'programs':[],'materials':[],'summary':{'programCount':34,'materialCount':120,'replayIdentityCompleteMaterialCount':118,'materialStaticStateCompleteCount':118,'dynamicEngineInputIdentityCompleteCount':120,'materialRequiringRuntimeDynamicInputsCount':96,'blockerCounts':{'materialSamplerAmbiguous':2}}}
   v51.matvals.build=mv;v51.replay.build=rp
   result=v51.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v51.v50.run_oat_textured_pipeline,v51.matvals.build,v51.replay.build=saved
  assert calls==['mv','mv',('rp',v51.matvals.FORMAT),('rp',v51.matvals.FORMAT)]
  assert result['format']==v51.FORMAT and Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert result['validation']['v51ReplayContractGenerated'] is True and result['validation']['v51ReplayContractDeterministic'] is True
  assert result['validation']['v51CorrectedMaterialValuesGenerated'] is True
  assert result['validation']['v51ReplayProgramCount']==34 and result['validation']['v51ReplayMaterialCount']==120
  assert result['validation']['v51ReplayIdentityCompleteMaterialCount']==118
  assert result['validation']['v51ReplayBlockerCounts']=={'materialSamplerAmbiguous':2}
  assert 'generatedFinalOutputReplayContract' in result['outputs'] and 'generatedFinalOutputMaterialCbufferValuesV3' in result['outputs']
  assert not oldm.exists()

  # Without retained material constants, replay still emits and reports missing static values itself.
  old2=root/'n_v50.glb';old2.write_bytes(gb);om2=root/'old2.json';om2.write_text('{}');base2=copy.deepcopy(base);base2['outputs']['oatPortableTexturedGlb']['path']=str(old2);base2['outputs'].pop('generatedRetailMaterialConstants');base2['manifest']['path']=str(om2)
  saved=(v51.v50.run_oat_textured_pipeline,v51.replay.build);seen=[]
  try:
   v51.v50.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base2)
   v51.replay.build=lambda a,b,c,d,e,f,g:(seen.append(g) or {'format':v51.replay.FORMAT,'programs':[],'materials':[],'summary':{'programCount':34,'materialCount':120,'replayIdentityCompleteMaterialCount':0,'materialStaticStateCompleteCount':0,'dynamicEngineInputIdentityCompleteCount':120,'materialRequiringRuntimeDynamicInputsCount':96,'blockerCounts':{'materialConstantValueMissing':40}}})
   r2=v51.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v51.v50.run_oat_textured_pipeline,v51.replay.build=saved
  assert seen==[None,None] and r2['validation']['v51CorrectedMaterialValuesGenerated'] is False and r2['validation']['v51ReplayContractGenerated'] is True
 print('PASS: production v51 renderer-neutral final-output replay contract');return 0
if __name__=='__main__':raise SystemExit(main())
