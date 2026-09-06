#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_unclassified_term_material_values_v1 as overlay

SHA='a'*64

def docs():
 census={'format':overlay.CENSUS_FORMAT,'terms':[
  {'sha256':SHA,'lane':'x','node':10,'cbufferEnrichedStructuralProfileSha256V3':'1'*64,'cbufferDependenciesV1':[{'symbol':'cb1[59].x'}]},
  {'sha256':SHA,'lane':'y','node':11,'cbufferEnrichedStructuralProfileSha256V3':'2'*64,'cbufferDependenciesV1':[{'symbol':'cb2[3].y'}]},
 ],'summary':{'unclassifiedLeafCount':2}}
 def resolved(material,value):
  return {'material':material,'pixelShaderSha256':SHA,'materialArchiveSha256':material*2,'resolvedMaterialBindings':[{'symbol':'cb1[59].x','sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1','materialConstant':{'scalarValue':value,'literal':[value,2.0,3.0,4.0],'literalComponentIndex':0,'serializedSha256':'b'*64,'nameHash':0x88befc31,'nameFragment':'alphaRevealP'}}],'unresolvedNonMaterialBindings':[{'symbol':'cb2[3].y','sourceClass':'code','sourceExpression':'code.sunColor','sourceName':'sunColor'}],'materialResolvedValueSignatureSha256':('3' if value<0.5 else '4')*64}
 values={'format':overlay.VALUES_FORMAT,'materials':[resolved('A',0.25),resolved('B',0.75)],'summary':{}}
 return census,values

def main()->int:
 census,values=docs();doc=overlay.build(census,values)
 assert doc['format']==overlay.FORMAT
 by_lane={row['lane']:row for row in doc['terms']}
 x=by_lane['x']['materialValueDependenciesV1'][0]
 assert x['resolvedMaterialOwnerCount']==2 and x['unresolvedMaterialOwnerCount']==0
 assert x['distinctResolvedScalarValueCount']==2
 assert x['distinctResolvedScalarFloat32Bits']==['0000403f','0000803e']
 assert x['variesAcrossMaterialOwners'] is True
 assert [row['scalarValue'] for row in x['owners']]==[0.25,0.75]
 assert by_lane['x']['hasMaterialValueVariation'] is True
 y=by_lane['y']['materialValueDependenciesV1'][0]
 assert y['resolvedMaterialOwnerCount']==0 and y['unresolvedMaterialOwnerCount']==2
 assert y['sourceClasses']==['code'] and y['variesAcrossMaterialOwners'] is False
 assert by_lane['y']['hasResolvedMaterialValue'] is False
 assert doc['summary']['termWithResolvedMaterialValueCount']==1
 assert doc['summary']['termWithMaterialValueVariationCount']==1
 assert doc['summary']['varyingMaterialDependencyCount']==1
 assert doc['summary']['sourceClassOwnerOccurrenceCounts']=={'code':2,'material':2}
 assert doc['summary']['materialOwnerCount']==2 and doc['summary']['shaderCount']==1
 assert len(doc['materialValuePatternGroups'])==2

 # When both owners have the same exact float32 scalar, variation must collapse.
 _,uniform_values=docs();uniform_values['materials'][1]['resolvedMaterialBindings'][0]['materialConstant']['scalarValue']=0.25;uniform_values['materials'][1]['resolvedMaterialBindings'][0]['materialConstant']['literal'][0]=0.25
 uniform=overlay.build(census,uniform_values);ux={r['lane']:r for r in uniform['terms']}['x']['materialValueDependenciesV1'][0]
 assert ux['distinctResolvedScalarValueCount']==1 and ux['variesAcrossMaterialOwners'] is False

 # A census dependency cannot be silently absent from an owning material's
 # exact cbuffer value/source table.
 bad=copy.deepcopy(values);bad['materials'][1]['resolvedMaterialBindings']=[]
 try:overlay.build(census,bad)
 except overlay.UnclassifiedTermMaterialValueError as exc:assert 'owner-state count' in str(exc)
 else:raise AssertionError('missing owner cbuffer state was accepted')
 print('PASS: exact material-value overlay for unclassified final RGB terms');return 0
if __name__=='__main__':raise SystemExit(main())
