#!/usr/bin/env python3
"""Scan expanded retail T6 bytes for exact serialized GfxImage identities/keys.

A strong streamed-image hit requires all of:
- exact NUL-terminated serialized image identity;
- an 80-byte PC32 GfxImage fixed record immediately before the name;
- inline GfxImage name pointer at fixed +72;
- stored GfxImage.hash at +76 equals retail R_HashString(serialized name);
- nonzero width/height/depth at +20/+22/+24.

A zero-metadata alias shell is retained separately when the fixed record is
zero-filled apart from its inline-name pointer/hash area. It is not promoted to
an IPAK key.

Important: the byte before an inline GfxImage name is part of GfxImage.hash and
is *not* required to be NUL. Exactness is established by the terminating NUL plus
the validated 80-byte fixed record immediately preceding the string.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

GFXIMAGE_FIXED=80
FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE

def r_hash_string(s:str,h:int=0)->int:
    for c in s.encode('latin1'):
        h=((33*h) ^ (c|0x20)) & 0xffffffff
    return h

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def _exact_cstring(data:bytes,pos:int,name:str)->bool:
    b=name.encode('latin1')
    return data[pos:pos+len(b)]==b and pos+len(b)<len(data) and data[pos+len(b)]==0

def classify_at(data:bytes,name_start:int,name:str):
    st=name_start-GFXIMAGE_FIXED
    if st<0:return None
    name_ptr=struct.unpack_from('<I',data,st+72)[0]
    if name_ptr not in (FOLLOWING,INSERT):return None
    stored_hash=struct.unpack_from('<I',data,st+76)[0]
    width,height,depth=struct.unpack_from('<3H',data,st+20)
    data_hash=struct.unpack_from('<I',data,st+40)[0]&0x1fffffff
    fixed=data[st:st+GFXIMAGE_FIXED]
    if stored_hash==r_hash_string(name) and width and height and depth:
        return {'status':'exact-streamed-key','serializedName':name,'fixedStart':st,'fixedSha256':sha(fixed),
                'nameHash':stored_hash,'nameHashHex':f'0x{stored_hash:08X}','dataHash29':data_hash,'dataHash29Hex':f'0x{data_hash:08X}',
                'dimensions':[width,height,depth],'namePointerRaw':f'0x{name_ptr:08X}'}
    # Retail alias shells observed in faction zones have zero metadata, an inline
    # name pointer, and stored hash 0. Keep the exact name but do not invent a key.
    if stored_hash==0 and width==0 and height==0 and depth==0 and data_hash==0 and all(x==0 for x in fixed[:72]):
        return {'status':'exact-named-alias-shell','serializedName':name,'fixedStart':st,'fixedSha256':sha(fixed),
                'nameHash':0,'nameHashHex':'0x00000000','dataHash29':0,'dataHash29Hex':'0x00000000','dimensions':[0,0,0],
                'namePointerRaw':f'0x{name_ptr:08X}'}
    return None

def scan_one(data:bytes,name:str):
    b=name.encode('latin1');pos=0;hits=[]
    while True:
        p=data.find(b,pos)
        if p<0:break
        if _exact_cstring(data,p,name):
            row=classify_at(data,p,name)
            if row:hits.append(row)
        pos=p+1
    strong=[h for h in hits if h['status']=='exact-streamed-key']
    shells=[h for h in hits if h['status']=='exact-named-alias-shell']
    strong_keys={(h['nameHash'],h['dataHash29'],tuple(h['dimensions'])) for h in strong}
    if len(strong_keys)>1:
        raise RuntimeError(f'{name}: conflicting exact streamed GfxImage keys: {sorted(strong_keys)}')
    return {'requestedName':name,'exactStreamedKey':strong[0] if strong else None,'aliasShells':shells,
            'summary':{'strongHits':len(strong),'aliasShells':len(shells),'resolved':bool(strong)}}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('expanded',type=Path);ap.add_argument('--name',action='append',default=[]);ap.add_argument('--names-json',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    names=list(a.name)
    if a.names_json:
        obj=json.loads(a.names_json.read_text())
        if isinstance(obj,list):names.extend(str(x) for x in obj)
        elif isinstance(obj,dict) and isinstance(obj.get('names'),list):names.extend(str(x) for x in obj['names'])
        else:raise ValueError('names JSON must be a list or {"names": [...]}')
    names=list(dict.fromkeys(names))
    if not names:raise ValueError('no image names supplied')
    data=a.expanded.read_bytes();rows=[scan_one(data,n) for n in names]
    doc={'format':'t6-gfximage-exact-key-scan-v1','source':{'expandedBytes':len(data),'expandedSha256':sha(data)},'rows':rows,
         'summary':{'requested':len(rows),'resolved':sum(r['summary']['resolved'] for r in rows),'aliasShellOnly':sum((not r['summary']['resolved']) and bool(r['aliasShells']) for r in rows),'absent':sum((not r['summary']['resolved']) and not r['aliasShells'] for r in rows)}}
    text=json.dumps(doc,indent=2,sort_keys=True)+'\n';a.out.write_text(text,encoding='utf-8');print(json.dumps(doc['summary'],indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
