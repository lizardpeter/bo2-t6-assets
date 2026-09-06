#!/usr/bin/env python3
"""Resolve strict inline T6 GfxImage keys for one audited Material texture table.

This extends t6_material_texturedef_audit_v1. For each inline MaterialTextureDef
image pointer it scans forward in source order for the next strict 80-byte T6
GfxImage fixed record whose inline name and stored GfxImage.hash agree exactly
under retail R_HashString. It records the first streamed-part CRC29 identity and
retail dimensions. Packed/alias image pointers remain unresolved here and must be
closed by a separate allocation/alias proof.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from t6_material_texturedef_audit_v1 import audit as audit_material

FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE
GFXIMAGE_FIXED=80

def r_hash_string(s:str,h:int=0)->int:
    for c in s.encode('latin1'):
        h=((33*h) ^ (c|0x20)) & 0xffffffff
    return h

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def ascii_cstring(data:bytes,pos:int,maxlen:int=512):
    e=data.find(b'\0',pos,min(len(data),pos+maxlen+1))
    if e<0 or e==pos:return None
    raw=data[pos:e]
    if any(c<32 or c>126 for c in raw):return None
    try:return raw.decode('ascii')
    except UnicodeDecodeError:return None

def strict_image_at(data:bytes,st:int):
    if st<0 or st+GFXIMAGE_FIXED+2>len(data):return None
    name_ptr=struct.unpack_from('<I',data,st+72)[0]
    if name_ptr not in (FOLLOWING,INSERT):return None
    name=ascii_cstring(data,st+80)
    if not name:return None
    name_hash=struct.unpack_from('<I',data,st+76)[0]
    if name_hash==0 or name_hash!=r_hash_string(name):return None
    width,height,depth=struct.unpack_from('<3H',data,st+20)
    if not(width and height and depth):return None
    data_hash=struct.unpack_from('<I',data,st+40)[0]&0x1fffffff
    return {'name':name,'fixedStart':st,'fixedBytes':GFXIMAGE_FIXED,'fixedSha256':sha(data[st:st+GFXIMAGE_FIXED]),
            'namePointerRaw':f'0x{name_ptr:08X}','nameHash':name_hash,'nameHashHex':f'0x{name_hash:08X}',
            'streamedPart0Hash29':data_hash,'streamedPart0Hash29Hex':f'0x{data_hash:08X}',
            'width':width,'height':height,'depth':depth,'nameEnd':st+GFXIMAGE_FIXED+len(name)+1}

def audit(data:bytes,start:int,expected_name:str|None=None,scan_limit:int=8192):
    mat=audit_material(data,start,expected_name)
    cursor=mat['source']['textureTableEnd'];found=[]
    for row in mat['textures']:
        kind=row['imagePointer']['kind']
        if kind not in ('following','insert'):
            found.append({'slot':row['slot'],'status':'packed-or-null','texture':row,'image':None});continue
        hit=None
        for st in range(cursor,min(len(data),cursor+scan_limit)):
            cand=strict_image_at(data,st)
            if cand:
                hit=cand;break
        if not hit:
            found.append({'slot':row['slot'],'status':'inline-image-not-strictly-located','texture':row,'image':None});continue
        found.append({'slot':row['slot'],'status':'inline-image-exact-key','texture':row,'image':hit});cursor=hit['nameEnd']
    mat['inlineImageResolution']=found
    mat['validation'].update({'exactInlineImageKeys':sum(x['image'] is not None for x in found),
                              'unresolvedInlineImageRows':sum(x['texture']['imagePointer']['kind'] in ('following','insert') and x['image'] is None for x in found)})
    return mat

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('expanded',type=Path);ap.add_argument('--material-start',required=True,type=lambda x:int(x,0));ap.add_argument('--expected-name');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    data=a.expanded.read_bytes();doc=audit(data,a.material_start,a.expected_name);doc['source']['expandedSha256']=sha(data)
    text=json.dumps(doc,indent=2,sort_keys=True)+'\n';a.out.write_text(text,encoding='utf-8')
    print(json.dumps({'out':str(a.out),'name':doc['identity']['name'],'textures':doc['material']['textureCount'],'exactImages':doc['validation']['exactInlineImageKeys'],'images':[x['image']['name'] if x['image'] else None for x in doc['inlineImageResolution']]},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
