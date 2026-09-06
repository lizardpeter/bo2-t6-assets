#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_specular_rgb_factor_join_v1 as j

def docs():
 h='a'*64
 rgb={'format':j.RGB_FORMAT,'materials':[{'material':'*m','steps':[{'layerIndex':1,'operation':'blend','sharedFactorSha256':h},{'layerIndex':2,'operation':'threshold','sharedFactorSha256':'b'*64}]}]}
 spec={'format':j.SPEC_FORMAT,'materials':[{'material':'*m','shaderSha256':'c'*64,'steps':[{'layerIndex':1,'operator':'b','sharedFactorSha256':h},{'layerIndex':2,'operator':'t','sharedFactorSha256':'b'*64}]}]}
 return rgb,spec

def main()->int:
 r,s=docs();got=j.build(r,s)
 assert got['summary']=={'specularMaterialCount':1,'factorJoinCheckCount':2,'exactMatchCount':2,'mismatchCount':0,'fullyMatchedMaterialCount':1,'strict':True}
 assert got['materials'][0]['allStepsMatch'] is True
 bad=copy.deepcopy(s);bad['materials'][0]['steps'][0]['sharedFactorSha256']='f'*64
 try:j.build(r,bad)
 except j.SpecularRgbFactorJoinError as exc:assert 'factor mismatches' in str(exc)
 else:raise AssertionError('factor hash mismatch accepted')
 relaxed=j.build(r,bad,strict=False);assert relaxed['summary']['mismatchCount']==1 and relaxed['materials'][0]['allStepsMatch'] is False
 bad=copy.deepcopy(s);bad['materials'][0]['steps'][0]['operator']='t'
 try:j.build(r,bad)
 except j.SpecularRgbFactorJoinError as exc:assert 'factor mismatches' in str(exc)
 else:raise AssertionError('operator-family mismatch accepted')
 missing=copy.deepcopy(r);missing['materials'][0]['steps']=missing['materials'][0]['steps'][:1]
 try:j.build(missing,s)
 except j.SpecularRgbFactorJoinError as exc:assert 'missing RGB layer step' in str(exc)
 else:raise AssertionError('missing RGB step accepted')
 print('PASS: exact generated specular/RGB final-output factor join v1');return 0
if __name__=='__main__':raise SystemExit(main())
