#!/usr/bin/env python3
"""Probe SHA-pinned retail bytes for exact GfxWorld reflection-image identities.

Ownership comes only from the independently recovered GfxWorld v3 catalog. This
probe then requires a unique serialized GfxImage object for each exact identity
before hashing any inline loadDef payload. It does not use name similarity.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
FOLLOW=0xffffffff; INSERT=0xfffffffe; SOURCE_SHA='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'
def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def h(b): return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--expanded',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();data=a.expanded.read_bytes()
 if len(data)!=154653476 or h(data)!=SOURCE_SHA: raise ValueError('expanded retail source drift')
 cat=json.loads(a.catalog.read_text()); rows=cat.get('reflectionProbes') or []
 if cat.get('reflectionProbeCount')!=25 or len(rows)!=25: raise ValueError('reflection ownership catalog drift')
 out=[]
 for r in rows:
  name=r['reflectionImage']; needle=name.encode()+b'\0'; hits=[]; p=0
  while True:
   p=data.find(needle,p)
   if p<0: break
   hits.append(p);p+=1
  candidates=[]
  for name_start in hits:
   fixed=name_start-80
   if fixed<0 or u32(data,fixed+72)!=FOLLOW: continue
   load=u32(data,fixed); name_end=name_start+len(needle); item={'nameStart':name_start,'fixedStart':fixed,'loadDefPointer':f'0x{load:08x}'}
   if load in (FOLLOW,INSERT) and name_end+12<=len(data):
    size=u32(data,name_end+8); ds=name_end+12; de=ds+size
    if de<=len(data): item.update({'inline':True,'resourceSize':size,'dataStart':ds,'dataEnd':de,'payloadSha256':h(data[ds:de])})
   else: item['inline']=False
   candidates.append(item)
  out.append({'index':r['index'],'image':name,'stringOccurrenceCount':len(hits),'serializedGfxImageCandidateCount':len(candidates),'candidates':candidates})
 exact=[x for x in out if x['serializedGfxImageCandidateCount']==1 and x['candidates'][0].get('inline')]
 doc={'format':'t6-nuketown-reflection-inline-payload-probe-v1','map':'mp_nuketown_2020','source':{'expandedBytes':len(data),'expandedSha256':h(data)},'ownership':{'catalog':a.catalog.name,'reflectionProbeCount':25},'rows':out,'summary':{'identityCount':25,'uniqueSerializedGfxImageCount':sum(x['serializedGfxImageCandidateCount']==1 for x in out),'uniqueInlinePayloadCount':len(exact),'ambiguousOrAbsentCount':sum(x['serializedGfxImageCandidateCount']!=1 for x in out)},'proofBoundary':'GfxWorld ownership is imported only from the exact v3 catalog. Payload promotion requires exactly one byte-level serialized GfxImage candidate with exact identity, inline name pointer, inline/insert loadDef pointer, bounded resource size, and SHA-pinned expanded source. Rows failing uniqueness remain unresolved; no nearest-name or adjacency inference is admitted.'}
 b=(json.dumps(doc,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(b);print(json.dumps({'sha256':h(b),**doc['summary'],'inline':[(x['image'],x['candidates'][0]['resourceSize']) for x in exact]},indent=2))
if __name__=='__main__': main()
