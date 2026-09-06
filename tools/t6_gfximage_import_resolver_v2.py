#!/usr/bin/env python3
"""Resolve comma-prefixed T6 GfxImage import identities to unique full retail images.

Input identities may come from direct inline image stubs or from a separately
proven packed-alias ledger. A leading comma is treated as the serialized import
marker; the stripped identity must resolve to exactly one structurally valid
full GfxImage fixed record across the supplied retail expanded zones.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
F=0xffffffff;I=0xfffffffe

def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def rhash(s:str)->int:
 h=5381
 for c in s.encode('latin1'):h=(((h<<5)+h)^(c|0x20))&0xffffffff
 return h
def parse_image(data:bytes,st:int,name:str):
 if st<0 or st+80>len(data):return None
 load=struct.unpack_from('<I',data,st)[0]
 if struct.unpack_from('<I',data,st+72)[0] not in (F,I):return None
 if data[st+4] not in range(0,7):return None
 end=data.find(b'\0',st+80,min(len(data),st+592))
 if end<0:return None
 try:n=data[st+80:end].decode('latin1')
 except UnicodeDecodeError:return None
 if n!=name:return None
 w,h,d=struct.unpack_from('<HHH',data,st+20);word,rawhash=struct.unpack_from('<II',data,st+36);sizeword=struct.unpack_from('<I',data,st+52)[0]
 return {'structOffset':st,'fixedSha256':hashlib.sha256(data[st:st+80]).hexdigest(),'name':n,'nameHash':rhash(n),'nameHashHex':f'0x{rhash(n):08x}','mapType':data[st+4],'semantic':data[st+5],'category':data[st+6],'width':w,'height':h,'depth':d,'levelCount':data[st+26],'streaming':data[st+27],'baseSize':struct.unpack_from('<I',data,st+28)[0],'streamedPartCount':data[st+60],'streamedPart0':{'levelCount':word&0xf,'levelSize':word>>4,'dataHash':rawhash&0x1fffffff,'dataHashHex':f'0x{rawhash&0x1fffffff:08x}','ipakIndex':(sizeword>>28)&0xf,'size':sizeword&0x0fffffff},'loadDefPointerRaw':f'0x{load:08x}'}
def collect_identities(manifest:dict|None,alias:dict|None):
 out=[]
 if manifest:
  for s in manifest.get('inlineImageStubs',[]):
   raw=s.get('image') or s.get('name')
   if isinstance(raw,str) and raw.startswith(','):out.append({'importIdentity':raw,'uses':[s],'sourceKind':'inline-image-stub'})
 if alias:
  for p in alias.get('proofs',[]):
   raw=p.get('exactIdentity')
   if isinstance(raw,str) and raw.startswith(','):
    out.append({'importIdentity':raw,'uses':[p.get('laterUse') or {}],'sourceKind':'packed-alias-proof','aliasProof':{'sourceOwner':p.get('sourceOwner'),'sourceImageFieldVirtualOffset':p.get('sourceImageFieldVirtualOffset')}})
 by={}
 for r in out:
  k=r['importIdentity'];x=by.setdefault(k,{'importIdentity':k,'uses':[],'sourceKinds':[],'aliasProofs':[]});x['uses']+=r['uses'];x['sourceKinds'].append(r['sourceKind'])
  if r.get('aliasProof'):x['aliasProofs'].append(r['aliasProof'])
 return list(by.values())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path);ap.add_argument('--alias-proof',type=Path);ap.add_argument('--source',action='append',nargs=2,metavar=('ZONE','EXPANDED'),required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 manifest=json.loads(a.manifest.read_text(encoding='utf-8-sig')) if a.manifest else None;alias=json.loads(a.alias_proof.read_text(encoding='utf-8-sig')) if a.alias_proof else None
 identities=collect_identities(manifest,alias)
 if not identities:raise SystemExit('no comma-prefixed import identities supplied')
 sources=[];loaded=[]
 for zone,p in a.source:
  pp=Path(p);data=pp.read_bytes();sources.append({'zone':zone,'path':str(pp),'bytes':len(data),'sha256':sha256_file(pp)});loaded.append((zone,data))
 promotions=[];unresolved=[]
 for item in identities:
  raw=item['importIdentity'];target=raw[1:];candidates=[]
  for zone,data in loaded:
   needle=target.encode('latin1')+b'\0';pos=0
   while True:
    at=data.find(needle,pos)
    if at<0:break
    r=parse_image(data,at-80,target)
    if r:candidates.append({'sourceZone':zone,**r})
    pos=at+1
  unique={(x['sourceZone'],x['structOffset']):x for x in candidates}
  if len(unique)!=1:
   unresolved.append({**item,'targetName':target,'candidateCount':len(unique),'candidates':list(unique.values())});continue
  im=next(iter(unique.values()))
  sp=im['streamedPart0']
  if not (im['streaming'] and im['streamedPartCount']==1 and im['width'] and im['height'] and sp['dataHash']):
   unresolved.append({**item,'targetName':target,'candidateCount':1,'reason':'unique full image lacks complete stream key','candidate':im});continue
  promotions.append({**item,'targetName':target,'resolution':'exact-comma-import-to-unique-retail-gfximage','image':im})
 out={'format':'t6-gfximage-import-resolution-v2','authority':'exact serialized comma-prefixed image identity + unique structurally valid full retail GfxImage fixed record','sources':sources,'summary':{'requestedImportIdentities':len(identities),'promoted':len(promotions),'unresolved':len(unresolved),'baseIpakPromotions':sum(p['image']['streamedPart0']['ipakIndex']==0 for p in promotions)},'promotions':promotions,'unresolved':unresolved,'rules':{'importMarker':'leading comma is stripped only for exact asset identity resolution','uniqueness':'exact stripped name must have exactly one structurally valid full GfxImage fixed record across supplied retail sources','streamKey':'streaming != 0, streamedPartCount == 1, nonzero width/height/dataHash required','noFilenameFallback':True},'proofBoundary':'This proves full GfxImage identity/stream metadata for comma imports. Pixel bytes remain an IPAK extraction/decompression stage.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(out['summary'],indent=2,sort_keys=True));return 2 if unresolved else 0
if __name__=='__main__':raise SystemExit(main())
