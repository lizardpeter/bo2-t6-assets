#!/usr/bin/env python3
"""Enrich exact T6 DXBC RDEF cbuffer metadata with variable type records.

The existing cbuffer parser preserves each variable's `typeOffset` but not the
16-byte RDEF type record. This v2 companion parses the exact SM4/SM5 layout used
by OAT's D3D11ShaderAnalyser:

  uint16 class, baseType, rows, columns, elements, fields;
  uint32 fieldsOffset;

This supplies the element count required to reproduce OAT's missing-argument
auto-create behavior without inferring arrays from byte spans.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,struct
from pathlib import Path
from typing import Any
import t6_dxbc_material_constant_binding_v1 as v1
import t6_dxbc_inspect_v1 as inspect
FORMAT='t6-dxbc-rdef-cbuffers-v2'
TYPE_SIZE=16
CLASS_NAMES={0:'SCALAR',1:'VECTOR',2:'MATRIX_ROWS',3:'MATRIX_COLUMNS',4:'OBJECT',5:'STRUCT',6:'INTERFACE_CLASS',7:'INTERFACE_POINTER',8:'SCALAR',9:'VECTOR',10:'MATRIX_ROWS',11:'MATRIX_COLUMNS',12:'OBJECT',13:'STRUCT',14:'INTERFACE_CLASS',15:'INTERFACE_POINTER'}
class RdefCbufferTypeError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def parse(dxbc:bytes)->dict:
 base=v1.parse_rdef_constant_buffers(dxbc);ins=inspect.inspect_dxbc(dxbc);chunks=[c for c in ins.get('chunks',[]) if c.get('tag')=='RDEF']
 if len(chunks)!=1:raise RdefCbufferTypeError(f'expected exactly one RDEF chunk, got {len(chunks)}')
 start=int(chunks[0]['payloadOffset']);size=int(chunks[0]['payloadBytes']);payload=dxbc[start:start+size]
 if len(payload)!=size:raise RdefCbufferTypeError('RDEF payload truncated')
 out=copy.deepcopy(base);types={}
 for buffer in out.get('constantBuffers',[]):
  for variable in buffer.get('variables',[]):
   off=int(variable.get('typeOffset',-1))
   if off<0 or off+TYPE_SIZE>len(payload):raise RdefCbufferTypeError(f"{buffer.get('name')}.{variable.get('name')}: typeOffset {off} outside RDEF payload")
   cls,base_type,rows,cols,elements,fields,fields_off=struct.unpack_from('<HHHHHHI',payload,off)
   if rows==0 or cols==0:raise RdefCbufferTypeError(f"{buffer.get('name')}.{variable.get('name')}: invalid RDEF type rows/columns {rows}/{cols}")
   if fields and (fields_off<=0 or fields_off>=len(payload)):raise RdefCbufferTypeError(f"{buffer.get('name')}.{variable.get('name')}: field table offset {fields_off} outside RDEF")
   typ={'typeOffset':off,'classRaw':cls,'className':CLASS_NAMES.get(cls,'UNKNOWN'),'baseTypeRaw':base_type,'rowCount':rows,'columnCount':cols,'elementCount':elements,'effectiveElementCount':max(elements,1),'fieldCount':fields,'fieldsOffset':fields_off}
   variable['type']=typ;types.setdefault(off,typ)
 out['format']=FORMAT;out['baseFormat']=base['format'];out['typeRecordCount']=len(types);out['typeRecordsSha256']=_jhash([types[k] for k in sorted(types)]);out['proofBoundary']=str(base.get('proofBoundary') or '')+' v2 adds exact 16-byte RDEF type records at each retained typeOffset, matching OAT D3D11ShaderAnalyser FileRdefType; no type semantics beyond reflected fields are inferred.'
 return out

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('dxbc',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=parse(a.dxbc.read_bytes());a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps({'constantBufferCount':d['constantBufferCount'],'typeRecordCount':d['typeRecordCount']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
