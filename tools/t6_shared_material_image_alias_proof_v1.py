#!/usr/bin/env python3
"""Prove a shared T6 MaterialTextureDef image alias from its first inline use."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
F=0xffffffff;I=0xfffffffe;MASK=(1<<29)-1

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def rhash0(s):
 h=0
 for c in s.encode('latin1'):h=((h*33)^(c|0x20))&0xffffffff
 return h
def ptr(v):
 if v==F:return {'kind':'following','rawHex':'0xffffffff'}
 if v==I:return {'kind':'insert','rawHex':'0xfffffffe'}
 if v==0:return {'kind':'null','rawHex':'0x00000000'}
 e=(v-1)&0xffffffff;return {'kind':'packed','rawHex':f'0x{v:08x}','block':e>>29,'offset':e&MASK}
def cstr(d,p):
 e=d.find(b'\0',p,p+8192)
 if e<0:raise ValueError('unterminated string')
 return d[p:e].decode('latin1'),e+1
def image(d,p):
 load=struct.unpack_from('<I',d,p)[0];np=struct.unpack_from('<I',d,p+72)[0]
 if np not in(F,I):raise ValueError('GfxImage name is not inline')
 name,q=cstr(d,p+80)
 if load in(F,I):
  rs=struct.unpack_from('<i',d,q+8)[0]
  if rs<0 or q+12+rs>len(d):raise ValueError('bad GfxImageLoadDef')
  q+=12+rs
 return {'rawStart':p,'rawEnd':q,'name':name,'fixedSha256':hashlib.sha256(d[p:p+80]).hexdigest(),'loadDefPointer':ptr(load)}
def material(d,name):
 nb=name.encode('latin1')+b'\0';at=d.find(nb)
 if at<0 or d.find(nb,at+1)>=0:raise ValueError('source material name must occur exactly once')
 st=at-112
 if struct.unpack_from('<I',d,st)[0] not in(F,I):raise ValueError('bad Material fixed record')
 tc=d[st+84];tp=struct.unpack_from('<I',d,st+96)[0]
 if not(0<tc<=64 and tp in(F,I)):raise ValueError('source Material texture table not inline')
 table=at+len(nb);q=table+16*tc;slots=[]
 for i in range(tc):
  o=table+i*16;nh=struct.unpack_from('<I',d,o)[0];ns,ne,samp,sem=d[o+4:o+8];ip=struct.unpack_from('<I',d,o+12)[0]
  slots.append({'index':i,'rawOffset':o,'nameHash':nh,'nameHashHex':f'0x{nh:08x}','nameStart':chr(ns),'nameEnd':chr(ne),'samplerStateRaw':samp,'semanticRaw':sem,'imagePointer':ptr(ip)})
 for s in slots:
  if s['imagePointer']['kind'] in ('following','insert'):
   s['inlineImage']=image(d,q);q=s['inlineImage']['rawEnd']
 return {'name':name,'rawStart':st,'rawNameOffset':at,'textureCount':tc,'textureTableRawStart':table,'slots':slots}
def rows(path):
 x=json.loads(Path(path).read_text(encoding='utf-8-sig'))
 if isinstance(x,list):return x
 return sum([v for v in x.values() if isinstance(v,list)],[])
def main():
 a=argparse.ArgumentParser();a.add_argument('--expanded',type=Path,required=True);a.add_argument('--catalog',type=Path,required=True);a.add_argument('--source-material',required=True);a.add_argument('--source-slot',type=int,required=True);a.add_argument('--binding-name',required=True);a.add_argument('--expected-image',required=True);a.add_argument('--alias-pointer',type=lambda x:int(x,0),required=True);a.add_argument('--required-later-material',required=True);a.add_argument('--required-later-slot',type=int,required=True);a.add_argument('--out',type=Path,required=True);q=a.parse_args()
 d=q.expanded.read_bytes();m=material(d,q.source_material);s=m['slots'][q.source_slot];bh=rhash0(q.binding_name)
 if s['nameHash']!=bh or s['nameStart'].lower()!=q.binding_name[0].lower() or s['nameEnd'].lower()!=q.binding_name[-1].lower():raise SystemExit('binding identity mismatch')
 if s.get('inlineImage',{}).get('name')!=q.expected_image:raise SystemExit('inline image identity mismatch')
 alias=ptr(q.alias_pointer)
 if alias.get('block')!=5:raise SystemExit('alias is not VIRTUAL')
 uses=[]
 for r in rows(q.catalog):
  for t in r.get('textures',[]):
   try:nh=int(str(t.get('nameHash')),0)
   except:continue
   if nh!=bh:continue
   raw=(t.get('imagePointer') or {}).get('raw')
   if raw is None:continue
   rv=int(raw,0) if isinstance(raw,str) else int(raw)
   uses.append({'material':r.get('name'),'materialRawStart':r.get('start'),'slotIndex':int(t.get('index',-1)),'imagePointerRaw':f'0x{rv:08x}','matchesAliasPointer':rv==q.alias_pointer})
 if not uses or any(not x['matchesAliasPointer'] for x in uses):raise SystemExit('later binding uses are not uniform to alias')
 req=next((x for x in uses if x['material']==q.required_later_material and x['slotIndex']==q.required_later_slot),None)
 if not req:raise SystemExit('required later use not found')
 if any((x.get('materialRawStart') or 0)<=m['rawStart'] for x in uses):raise SystemExit('alias use predates inline source')
 out={'format':'t6-shared-material-image-alias-proof-v1','authority':'expanded retail T6 Material/GfxImage serialization','source':{'expandedBytes':len(d),'expandedSha256':sha(q.expanded),'catalogSha256':sha(q.catalog)},'binding':{'name':q.binding_name,'R_HashStringSeed':0,'nameHashHex':f'0x{bh:08x}','sourceMaterial':m,'sourceSlot':s},'alias':{'pointerRaw':f'0x{q.alias_pointer:08x}','decoded':alias,'laterUniformUseCount':len(uses),'requiredLaterUse':req,'firstLaterUse':uses[0],'lastLaterUse':uses[-1]},'exactImageIdentity':q.expected_image,'exactAliasIdentityProven':True,'proofBoundary':'Exact packed alias identity is proven from the earlier inline retail GfxImage plus the exact T6 texture-binding hash/name. Upstream full GfxImage metadata remains separate for comma-prefixed imports.'}
 q.out.parent.mkdir(parents=True,exist_ok=True);q.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'image':q.expected_image,'binding':q.binding_name,'laterUniformUseCount':len(uses),'exactAliasIdentityProven':True},indent=2))
if __name__=='__main__':main()
