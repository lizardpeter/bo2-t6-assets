#!/usr/bin/env python3
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v40 as v40

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_v40_') as td:
  root=Path(td);old=root/'m_v39.glb';gb=b'UNCHANGED-V39';old.write_bytes(gb)
  def side(name,doc):p=root/name;p.write_text(json.dumps(doc));return {'path':str(p),'file':p.name,'bytes':p.stat().st_size,'sha256':'x'}
  cv2=side('census2.json',{'format':v40.census_v3.v2.FORMAT,'terms':[],'signatureGroups':[],'summary':{'unclassifiedLeafCount':2,'structuralSignatureCount':1}})
  final=side('final.json',{'format':v40.census_v3.FINAL_FORMAT,'shaders':[]})
  cb=side('cb.json',{'format':v40.census_v3.CBUFFER_FORMAT,'shaders':[]})
  om=root/'old.json';om.write_text('{}')
  base={'format':v40.v39.FORMAT,'outputs':{'oatPortableTexturedGlb':{'path':str(old),'file':old.name,'bytes':len(gb),'sha256':'g'},'generatedFinalOutputUnclassifiedTermCensus':cv2,'generatedSlot4FinalOutputSymbolic':final,'generatedFinalOutputCbufferSignature':cb},'stats':{},'validation':{},'policies':{},'manifest':{'path':str(om)}}
  oldrun=v40.v39.run_oat_textured_pipeline;oldbuild=v40.census_v3.build;calls=[]
  try:
   v40.v39.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(base)
   def fake(a,b,c):
    calls.append((a,b,c))
    return {'format':v40.census_v3.FORMAT,'terms':[],'signatureGroups':[],'cbufferEnrichedSignatureGroups':[{'count':2,'observedLanes':['x','y']}],'summary':{'shaderCount':1,'unclassifiedLeafCount':2,'structuralSignatureCount':1,'v2StructuralSignatureCount':1,'cbufferEnrichedStructuralSignatureCount':2,'termWithCbufferDependencyCount':2,'termCbufferDependencyOccurrenceCount':3,'immediateChildCbufferDependencyOccurrenceCount':2,'uniqueReflectedCbufferVariableCount':2,'cbufferAssignmentSourceClassCounts':{'material':2,'code':1}},'rowsSha256V3':'a'*64,'cbufferEnrichedSignatureGroupsSha256':'b'*64}
   v40.census_v3.build=fake
   result=v40.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
  finally:v40.v39.run_oat_textured_pipeline=oldrun;v40.census_v3.build=oldbuild
  assert len(calls)==2 and calls[0]==calls[1]
  assert result['format']==v40.FORMAT
  assert result['validation']['v40CbufferEnrichedUnclassifiedCensusGenerated'] is True
  assert result['validation']['v40CbufferEnrichedUnclassifiedCensusDeterministic'] is True
  assert result['validation']['v40UnclassifiedLeafCount']==2
  assert result['validation']['v40V2StructuralSignatureCount']==1
  assert result['validation']['v40CbufferEnrichedStructuralSignatureCount']==2
  assert result['validation']['v40TermWithCbufferDependencyCount']==2
  assert result['validation']['v40UniqueReflectedCbufferVariableCount']==2
  assert result['validation']['v40VisualGlbByteIdenticalToV39'] is True
  assert Path(result['outputs']['oatPortableTexturedGlb']['path']).read_bytes()==gb
  enriched=Path(result['outputs']['generatedFinalOutputUnclassifiedTermCensusCbufferEnriched']['path'])
  assert json.loads(enriched.read_text())['cbufferEnrichedSignatureGroups'][0]['observedLanes']==['x','y']
  # v38/v2 census remains present alongside the v3 enrichment.
  assert result['outputs']['generatedFinalOutputUnclassifiedTermCensus']['path']==cv2['path']
  assert not om.exists()

  # A v2 census cannot be enriched without both authoritative identity inputs.
  broken=copy.deepcopy(base);broken['outputs'].pop('generatedFinalOutputCbufferSignature')
  oldrun=v40.v39.run_oat_textured_pipeline
  try:
   v40.v39.run_oat_textured_pipeline=lambda **kw:copy.deepcopy(broken)
   try:v40.run_oat_textured_pipeline(output_dir=root,map_name='mp_nuketown_2020')
   except v40.OatTexturedPipelineV40Error as exc:assert 'final-output/cbuffer sidecar is missing' in str(exc)
   else:raise AssertionError('v40 accepted census enrichment without exact cbuffer identity sidecar')
  finally:v40.v39.run_oat_textured_pipeline=oldrun
 print('PASS: production v40 cbuffer-enriched unknown final RGB census');return 0
if __name__=='__main__':raise SystemExit(main())
