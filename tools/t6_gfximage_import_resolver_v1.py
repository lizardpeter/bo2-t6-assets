#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
F=0xffffffff;I=0xfffffffe

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rhash(s):
 h=5381
 for c in s.encode('latin1'):h=(((h<<5)+h)^(c|0x20))&0xffffffff
 return h
def parse(data,st,name):
 if st<0 or st+80>len(data):return None
 if struct.unpack_from('<I',data,st+72)[0] not in(F,I):return None
 if data[st+4] not in range(0,7):return None
 w,h,d=struct.unpack_from('<HHH',data,st+20)
 stream=data[st+27];pc=data[st+60]
 end=data.find(b'\0',st+80,min(len(data),st+80+512))
 if end<0:return None
 try:n=data[st+80:end].decode('latin1')
 except:return None
 if n!=name:return None
 word,dh=struct.unpack_from('<II',data,st+36)
 return {'structOffset':st,'fixedSha256':hashlib.sha256(data[st:st+80]).hexdigest(),'nameOffset':st+80,'name':n,'nameHash':rhash(n),'nameHashHex':f'0x{rhash(n):08x}','mapType':data[st+4],'semantic':data[st+5],'category':data[st+6],'width':w,'height':h,'depth':d,'levelCount':data[st+26],'streaming':stream,'baseSize':struct.unpack_from('<I',data,st+28)[0],'streamedPartCount':pc,'streamedPart0':{'levelCount':word&15,'levelSize':word>>4,'dataHash':dh&0x1fffffff,'dataHashHex':f'0x{dh&0x1fffffff:08x}'},'runtimeHashRaw':struct.unpack_from('<I',data,st+76)[0]}
def main():
 a=argparse.ArgumentParser();a.add_argument('--manifest',type=Path,required=True);a.add_argument('--source',action='append',nargs=2,metavar=('ZONE','EXPANDED'),required=True);a.add_argument('--out',type=Path,required=True);q=a.parse_args()
 doc=json.loads(q.manifest.read_text());stubs=doc.get('inlineImageStubs',[]); sources=[]; loaded=[]
 for zone,p in q.source:
  pp=Path(p);loaded.append((zone,pp,pp.read_bytes()));sources.append({'zone':zone,'expanded':str(pp),'expandedSha256':sha(pp),'expandedBytes':pp.stat().st_size})
 promotions=[];unresolved=[]
 for stub in stubs:
  raw=stub['name']; target=raw[1:] if raw.startswith(',') else raw; candidates=[]
  for zone,p,data in loaded:
   needle=target.encode('latin1')+b'\0';pos=0
   while True:
    at=data.find(needle,pos)
    if at<0:break
    r=parse(data,at-80,target)
    if r:candidates.append({'sourceZone':zone,**r})
    pos=at+1
  unique={(x['sourceZone'],x['structOffset']):x for x in candidates}
  if len(unique)!=1:
   unresolved.append({'stub':stub,'targetName':target,'candidateCount':len(unique),'candidates':list(unique.values())});continue
  r=next(iter(unique.values()))
  if not (r['streaming'] and r['streamedPartCount']==1 and r['width'] and r['height'] and r['streamedPart0']['dataHash']):
   unresolved.append({'stub':stub,'targetName':target,'candidateCount':1,'reason':'unique candidate lacks complete stream key','candidate':r});continue
  promotions.append({'stub':stub,'targetName':target,'resolution':'exact-import-name-to-unique-retail-gfximage','image':r})
 existing={(x['sourceZone'],x['name'],x['structOffset']) for x in doc.get('exactStreamKeyImages',[])}
 for p in promotions:
  im=p['image'];k=(im['sourceZone'],im['name'],im['structOffset'])
  if k not in existing:doc.setdefault('exactStreamKeyImages',[]).append(im);existing.add(k)
 doc['imageImportResolution']={'format':'t6-gfximage-import-resolution-v1','sources':sources,'promotionCount':len(promotions),'unresolvedCount':len(unresolved),'promotions':promotions,'unresolved':unresolved,'rule':'Only a comma-prefixed imported GfxImage is promoted when the exact stripped name resolves to one structurally valid full GfxImage fixed record in the supplied retail zone set.'}
 doc['summary']['exactStreamKeys']=len(doc['exactStreamKeyImages']);doc['summary']['resolvedInlineImageImports']=len(promotions);doc['summary']['unresolvedInlineImageStubs']=len(unresolved)
 q.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
