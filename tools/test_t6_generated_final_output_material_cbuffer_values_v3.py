#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_material_cbuffer_values_v3 as v3

def main()->int:
 final={'format':'t6-generated-slot4-final-output-symbolic-v3'}
 cb={'format':v3.cb2.FORMAT,'shaders':[{'sha256':'a'*64,'usedCbufferSymbols':[{'symbol':'cb0[0].x','techniqueAssignments':[{'techniqueSet':'t','sourceClass':'material','sourceNamespace':'material','sourceKind':'material','sourceExpression':'material.foo','sourceName':'foo'}]}]}]}
 constants={'format':'t6-retail-world-material-constants-v1'}
 saved=v3.v2.build;seen=[]
 try:
  def fake(f,c,m):
   seen.append(copy.deepcopy(c));return {'format':v3.v2.FORMAT,'materials':[],'summary':{'shaderCountWithMaterialValueVariation':0},'proofBoundary':'exact'}
  v3.v2.build=fake
  out=v3.build(final,cb,constants)
 finally:v3.v2.build=saved
 assert seen[0]['format']==v3.cb1.FORMAT
 a=seen[0]['shaders'][0]['usedCbufferSymbols'][0]['techniqueAssignments'][0]
 assert a['sourceExpression']=='material.foo' and a['sourceNamespace']=='material'
 assert out['format']==v3.FORMAT and out['sourceCbufferFormat']==v3.cb2.FORMAT
 print('PASS: corrected cbuffer-v2 material cbuffer values v3');return 0
if __name__=='__main__':raise SystemExit(main())
