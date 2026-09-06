#!/usr/bin/env python3
from __future__ import annotations
import struct
import t6_dxbc_rdef_cbuffer_types_v2 as v2

def main()->int:
 payload=bytearray(64);struct.pack_into('<HHHHHHI',payload,8,1,3,1,4,4,0,0)
 dxbc=b'PADDING!'+bytes(payload)
 base={'format':'t6-dxbc-rdef-cbuffers-v1','dxbcSha256':'x','shaderModel':'4.0','constantBufferCount':1,'constantBuffers':[{'name':'Globals','bindPoint':0,'size':64,'type':0,'flags':0,'variables':[{'index':0,'name':'filterTap','startOffset':0,'size':64,'endOffset':64,'flags':2,'typeOffset':8,'defaultValueOffset':0}]}]}
 saved_base=v2.v1.parse_rdef_constant_buffers;saved_inspect=v2.inspect.inspect_dxbc
 try:
  v2.v1.parse_rdef_constant_buffers=lambda blob:base
  v2.inspect.inspect_dxbc=lambda blob:{'chunks':[{'tag':'RDEF','payloadOffset':8,'payloadBytes':64}]}
  out=v2.parse(dxbc)
 finally:v2.v1.parse_rdef_constant_buffers=saved_base;v2.inspect.inspect_dxbc=saved_inspect
 typ=out['constantBuffers'][0]['variables'][0]['type']
 assert out['format']==v2.FORMAT and out['typeRecordCount']==1
 assert typ['className']=='VECTOR' and typ['rowCount']==1 and typ['columnCount']==4
 assert typ['elementCount']==4 and typ['effectiveElementCount']==4 and typ['fieldCount']==0
 bad=bytearray(payload);struct.pack_into('<HHHHHHI',bad,8,1,3,0,4,4,0,0)
 try:
  v2.v1.parse_rdef_constant_buffers=lambda blob:base;v2.inspect.inspect_dxbc=lambda blob:{'chunks':[{'tag':'RDEF','payloadOffset':8,'payloadBytes':64}]};v2.parse(b'PADDING!'+bytes(bad))
 except v2.RdefCbufferTypeError as exc:assert 'rows/columns' in str(exc)
 else:raise AssertionError('zero-row RDEF type accepted')
 finally:v2.v1.parse_rdef_constant_buffers=saved_base;v2.inspect.inspect_dxbc=saved_inspect
 print('PASS: exact DXBC RDEF cbuffer type metadata v2');return 0
if __name__=='__main__':raise SystemExit(main())
