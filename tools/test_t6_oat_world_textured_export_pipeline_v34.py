#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v34 as v34

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v34_') as td:
  root=Path(td);old=root/'m_v33.glb';gb=b'UNCHANGED-V33';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  final=side('final.json',{'format':'t6-generated-slot4-final-output-symbolic-v3','shaders':[]});spec=side('spec.json',{'format':'t6-generated-final-output-specular-state-anchor-v1','materials':[]});front=side('front.json',{'format':'t6-generated-final-output-specular-consumer-frontier-v1','materials':[]});refl=side('refl.json',{'format':'t6-generated-final-output-reflection-sample-index-v1','shaders':[]})
  om=root/'old.json';om.write_text('{}')
  base={'format':v34.v33.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputSpecularStateAnchor':spec,'generatedFinalOutputSpecularConsumerFrontier':front,'generatedFinalOutputReflectionSampleIndex':refl},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v34.v33.run_oat_textured_pipeline;oldbuild=v34.sr_join.build;calls=[]
  try:
   v34.v33.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(fd,sp,fr,ri):
    calls.append((fd['format'],sp['format'],fr['format'],ri['format']))
    return {'format':v34.sr_join.FORMAT,'materials':[{'material':'*m'}],'summary':{'materialCount':1,'materialWithReflectionRelationCount':1,'reflectionRelationCount':3,'directSpecularTimesReflectionSampleCount':1,'directReflectionCoordinateSpecularRootCount':1,'directReflectionLodSourceSpecularRootCount':1,'mixingOperationCounts':{'mul':1,'sample_l':2}},'rowsSha256':'a'*64}
   v34.sr_join.build=fake
   result=v34.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v34.v33.run_oat_textured_pipeline=oldrun;v34.sr_join.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v34.FORMAT
  assert result['validation']['v34SpecularReflectionJoinGenerated'] is True
  assert result['validation']['v34DirectSpecularTimesReflectionSampleCount']==1
  assert result['validation']['v34DirectReflectionCoordinateSpecularRootCount']==1
  assert result['validation']['v34DirectReflectionLodSourceSpecularRootCount']==1
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  assert json.loads(Path(result['outputs']['generatedFinalOutputSpecularReflectionJoin']['path']).read_text())['summary']['reflectionRelationCount']==3
  assert not om.exists()
 print('PASS: production v34 exact specular/reflection sample join sidecar');return 0
if __name__=='__main__':raise SystemExit(main())
