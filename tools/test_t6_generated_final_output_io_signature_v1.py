#!/usr/bin/env python3
from __future__ import annotations

import hashlib,tempfile
from pathlib import Path
import t6_generated_final_output_io_signature_v1 as binder
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3


def io(mask=7):
 return {'format':'t6-dxbc-io-signatures-v1','input':{'format':'t6-dxbc-signature-v1','tag':'ISGN','headerUnknown':0,'entryCount':2,'entries':[{'entryIndex':0,'register':1,'semanticName':'TEXCOORD','semanticIndex':1,'semantic':'TEXCOORD1','systemValue':0,'componentType':3,'mask':mask,'readWriteMask':mask},{'entryIndex':1,'register':3,'semanticName':'TEXCOORD','semanticIndex':3,'semantic':'TEXCOORD3','systemValue':0,'componentType':3,'mask':7,'readWriteMask':7}],'registerMap':{'1':'TEXCOORD1','3':'TEXCOORD3'}},'output':{'format':'t6-dxbc-signature-v1','tag':'OSGN','headerUnknown':0,'entryCount':1,'entries':[{'entryIndex':0,'register':0,'semanticName':'SV_Target','semanticIndex':0,'semantic':'SV_Target0','systemValue':0,'componentType':3,'mask':15,'readWriteMask':15}],'registerMap':{'0':'SV_Target0'}}}

def manifest(rel,sha):
 return {'format':symbolic_v3.FORMAT,'shaders':[{'sha256':sha,'relativeFile':rel,'techniqueSets':['lit_sm_x'],'nodes':[{'id':0,'kind':'symbol','name':'v1.x'},{'id':1,'kind':'symbol','name':'v1.z'},{'id':2,'kind':'symbol','name':'v3.y'},{'id':3,'kind':'symbol','name':'cb1[2].x'}],'outputs':[{'register':0,'lanes':[{'channel':'x','written':True,'node':0,'resources':[]},{'channel':'y','written':True,'node':2,'resources':[]},{'channel':'z','written':True,'node':1,'resources':[]},{'channel':'w','written':False,'node':None,'resources':[]}]}]}]}

def main():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);p=root/'shader_bin/ps_x.cso';p.parent.mkdir();p.write_bytes(b'fixture-cso');sha=hashlib.sha256(p.read_bytes()).hexdigest();doc=manifest('shader_bin/ps_x.cso',sha);old=binder.signatures.parse_io_signatures
  try:
   binder.signatures.parse_io_signatures=lambda blob:io();r=binder.build(doc,oat_root=root)
  finally:binder.signatures.parse_io_signatures=old
  assert r['format']==binder.FORMAT and r['summary']['shaderCount']==1
  row=r['shaders'][0];assert row['usedInputRegisters']==[1,3];assert row['usedInputComponents']==['v1.x','v1.z','v3.y'];assert row['usedInputSemantics']==['TEXCOORD1','TEXCOORD3'];assert row['usedOutputRegisters']==[0]
  assert r['summary']['inputSymbolCheckCount']==3 and r['summary']['outputRegisterCheckCount']==1
  bad=manifest('shader_bin/ps_x.cso','0'*64)
  try:binder.build(bad,oat_root=root)
  except binder.GeneratedFinalOutputIoSignatureError as e:assert 'exact OAT file SHA changed' in str(e)
  else:raise AssertionError('SHA mismatch accepted')
  old=binder.signatures.parse_io_signatures
  try:
   binder.signatures.parse_io_signatures=lambda blob:io(mask=1)
   try:binder.build(doc,oat_root=root)
   except binder.GeneratedFinalOutputIoSignatureError as e:assert 'outside ISGN mask' in str(e)
   else:raise AssertionError('masked input component accepted')
  finally:binder.signatures.parse_io_signatures=old
  old=binder.signatures.parse_io_signatures
  try:
   q=io();q['input']['entries']=q['input']['entries'][1:];q['input']['registerMap']={'3':'TEXCOORD3'};binder.signatures.parse_io_signatures=lambda blob:q
   try:binder.build(doc,oat_root=root)
   except binder.GeneratedFinalOutputIoSignatureError as e:assert 'absent from ISGN' in str(e)
   else:raise AssertionError('missing ISGN register accepted')
  finally:binder.signatures.parse_io_signatures=old
 print('PASS: generated final-output exact I/O signature binder')
 return 0
if __name__=='__main__':raise SystemExit(main())
