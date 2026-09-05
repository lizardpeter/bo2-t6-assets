#!/usr/bin/env python3
from __future__ import annotations
import argparse,base64,json,struct,zlib
from collections import defaultdict
from pathlib import Path

EXPECTED_STREAMED=421

def load_manifest(path:Path):
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))

def read_index(path:Path):
    b=path.read_bytes(); magic,ver,total,sc=struct.unpack_from('<4sIII',b,0)
    if magic!=b'KAPI' or ver!=0x50000 or total!=len(b): raise ValueError('invalid T6 IPAK')
    secs=[struct.unpack_from('<IIII',b,16+16*i) for i in range(sc)]
    idx=[s for s in secs if s[0]==1]
    if len(idx)!=1: raise ValueError('expected one IPAK index')
    _,off,size,count=idx[0]
    if count*16>size: raise ValueError('invalid IPAK index size')
    return total,[struct.unpack_from('<IIII',b,off+16*i) for i in range(count)]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',type=Path,required=True); ap.add_argument('--ipak',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    d=load_manifest(a.manifest)
    targets=[]
    for im in d['images']:
        p=im.get('streamedPart0')
        if p:
            targets.append({'image':im['image'],'nameHash':int(im['imageHash']),'dataHash29':int(p['hash29']),'width':int(im['width']),'height':int(im['height']),'depth':int(im['depth'])})
    if len(targets)!=EXPECTED_STREAMED: raise ValueError(f'targets {len(targets)} != {EXPECTED_STREAMED}')
    total,entries=read_index(a.ipak)
    by_pair=defaultdict(list); by_data=defaultdict(list); by_name=defaultdict(list)
    for e in entries:
        dh,nh,rel,size=e; by_pair[(nh,dh)].append(e); by_data[dh].append(e); by_name[nh].append(e)
    rows=[]; counts=defaultdict(int)
    for t in targets:
        exact=by_pair[(t['nameHash'],t['dataHash29'])]; data=by_data[t['dataHash29']]; name=by_name[t['nameHash']]
        if len(exact)==1: state='exact-pair'; chosen=exact[0]
        elif len(exact)>1: state='ambiguous-exact-pair'; chosen=None
        elif len(data)==1: state='unique-data-hash'; chosen=data[0]
        elif len(data)>1: state='ambiguous-data-hash'; chosen=None
        elif name: state='name-hash-only'; chosen=None
        else: state='absent'; chosen=None
        counts[state]+=1
        rows.append({**t,'state':state,'chosenEntry':list(chosen) if chosen else None,'exactPairCount':len(exact),'dataHashEntryCount':len(data),'nameHashEntryCount':len(name),'dataHashAvailableNameHashes':sorted({int(e[1]) for e in data})})
    report={'format':'t6-nuketown-live-world-local-ipak-census-v1','ipak':{'file':a.ipak.name,'bytes':total,'indexEntryCount':len(entries)},'targetStreamedImageCount':len(targets),'summary':dict(sorted(counts.items())),'rows':rows,'proofBoundary':'Targets are the 421 streamed GfxImages from the canonical frozen retail GfxWorld manifest. Census admission requires one exact nameHash+dataHash pair or one unique streamed-part dataHash. Name-hash-only hits are never promoted; payload extraction must still independently verify CRC29 and retained dimensions.'}
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps(report['summary'],indent=2))
if __name__=='__main__': main()
