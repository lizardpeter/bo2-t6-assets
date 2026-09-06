#!/usr/bin/env python3
"""Collect exact T6 IPAK entry slices without decompressing image payloads.

Purpose: make large retail IPAKs unnecessary to transfer for targeted proofs.
The collector reads only the KAPI header/index plus matched raw data spans. A
target is selected by the exact pair:
    (GfxImage.hash/nameHash, GfxImage.streamedParts[0].hash & 0x1fffffff)

No filename similarity is used. The raw span is preserved byte-for-byte so a
later machine with the T6 IPAK/LZO decoder can reconstruct the IWI and validate
CRC29/dimensions before promotion.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, struct
from pathlib import Path

IPAK_MAGIC=b'KAPI'
IPAK_VERSION=0x50000
IPAK_INDEX=1
IPAK_DATA=2

def sha_file(path:Path,chunk:int=8*1024*1024)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b=f.read(chunk)
            if not b:break
            h.update(b)
    return h.hexdigest()

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def u32(v):
    if isinstance(v,int):return v&0xffffffff
    s=str(v).strip();return int(s,16) if s.lower().startswith('0x') else int(s)

def safe_name(s:str)->str:
    s=re.sub(r'[^A-Za-z0-9._-]+','_',s).strip('._')
    return s[:100] or 'image'

def normalize_targets(obj):
    rows=obj.get('targets',obj) if isinstance(obj,dict) else obj
    if not isinstance(rows,list):raise ValueError('targets JSON must be list or {"targets": [...]}')
    out=[]
    for i,r in enumerate(rows):
        if not isinstance(r,dict):raise ValueError(f'target {i} is not an object')
        nh=r.get('nameHash',r.get('nameHashHex'));dh=r.get('dataHash29',r.get('dataHash29Hex',r.get('dataHash')))
        if nh is None or dh is None:raise ValueError(f'target {i} missing nameHash/dataHash29')
        out.append({'id':r.get('id',r.get('name',f'target_{i}')),'name':r.get('name'),'nameHash':u32(nh),'dataHash29':u32(dh)&0x1fffffff,
                    'dimensions':r.get('dimensions'),'semantic':r.get('semantic'),'source':r.get('source')})
    pairs=[(r['nameHash'],r['dataHash29']) for r in out]
    if len(set(pairs))!=len(pairs):raise ValueError('duplicate target exact pairs')
    return out

class IPakIndex:
    def __init__(self,path:Path):
        self.path=path;self.size=path.stat().st_size
        with path.open('rb') as f:
            hdr=f.read(16)
            if len(hdr)!=16:raise ValueError('truncated IPAK header')
            magic,ver,size,sc=struct.unpack('<4sIII',hdr)
            if magic!=IPAK_MAGIC or ver!=IPAK_VERSION or size!=self.size:raise ValueError('invalid T6 IPAK header')
            secraw=f.read(sc*16)
            if len(secraw)!=sc*16:raise ValueError('truncated IPAK section table')
        self.sections=[struct.unpack_from('<IIII',secraw,i*16) for i in range(sc)]
        ds=[s for s in self.sections if s[0]==IPAK_DATA];ix=[s for s in self.sections if s[0]==IPAK_INDEX]
        if len(ds)!=1 or len(ix)!=1:raise ValueError('missing/ambiguous data/index section')
        self.data_sec=ds[0];self.index_sec=ix[0]
        _,ioff,isz,icount=self.index_sec
        if icount*16>isz or ioff+icount*16>self.size:raise ValueError('invalid IPAK index bounds')
    def find_pairs(self,pairs:set[tuple[int,int]]):
        found=[];_,ioff,_,icount=self.index_sec
        with self.path.open('rb') as f:
            f.seek(ioff)
            for i in range(icount):
                raw=f.read(16)
                if len(raw)!=16:raise ValueError('truncated IPAK index row')
                data_hash,name_hash,rel_off,span=struct.unpack('<IIII',raw);key=(name_hash,data_hash&0x1fffffff)
                if key in pairs:
                    data_abs=self.data_sec[1]+rel_off
                    if data_abs<self.data_sec[1] or data_abs+span>self.data_sec[1]+self.data_sec[2] or data_abs+span>self.size:
                        raise ValueError(f'index {i}: target span outside data section')
                    found.append({'index':i,'nameHash':name_hash,'dataHash29':data_hash&0x1fffffff,'relativeOffset':rel_off,'span':span,'absoluteOffset':data_abs})
        return found
    def read_span(self,row):
        with self.path.open('rb') as f:f.seek(row['absoluteOffset']);b=f.read(row['span'])
        if len(b)!=row['span']:raise ValueError('short IPAK data span')
        return b

def discover_archives(root:Path,names:list[str]):
    wanted={x.lower() for x in names};hits=[]
    for p in root.rglob('*.ipak'):
        if not wanted or p.name.lower() in wanted:hits.append(p)
    order={n.lower():i for i,n in enumerate(names)}
    return sorted(hits,key=lambda p:(order.get(p.name.lower(),9999),str(p).lower()))

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('targets',type=Path);ap.add_argument('output_dir',type=Path)
    g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--game-root',type=Path);g.add_argument('--archive',type=Path,action='append')
    ap.add_argument('--archive-name',action='append',default=['patch_mp.ipak','mp.ipak','base.ipak']);ap.add_argument('--hash-hit-archives',action='store_true')
    a=ap.parse_args();targets=normalize_targets(json.loads(a.targets.read_text()));pairs={(r['nameHash'],r['dataHash29']) for r in targets};by_pair={(r['nameHash'],r['dataHash29']):r for r in targets}
    archives=a.archive or discover_archives(a.game_root,a.archive_name)
    if not archives:raise SystemExit('no IPAK archives found')
    a.output_dir.mkdir(parents=True,exist_ok=True);slice_dir=a.output_dir/'slices';slice_dir.mkdir(exist_ok=True)
    results=[];archive_rows=[]
    for rank,path in enumerate(archives):
        idx=IPakIndex(path);found=idx.find_pairs(pairs);ar={'path':str(path),'basename':path.name,'bytes':path.stat().st_size,'precedenceRank':rank,'matchedEntries':len(found)}
        if found and a.hash_hit_archives:ar['sha256']=sha_file(path)
        archive_rows.append(ar)
        for row in found:
            t=by_pair[(row['nameHash'],row['dataHash29'])];blob=idx.read_span(row)
            fn=f"{safe_name(str(t['id']))}__{row['nameHash']:08X}_{row['dataHash29']:08X}__{safe_name(path.name)}.ipakspan"
            op=slice_dir/fn;op.write_bytes(blob)
            results.append({'target':t,'archive':{'path':str(path),'basename':path.name,'precedenceRank':rank,'bytes':path.stat().st_size,'sha256':ar.get('sha256')},
                            'indexEntry':{k:row[k] for k in ('index','nameHash','dataHash29','relativeOffset','span','absoluteOffset')},
                            'slice':{'path':str(op.relative_to(a.output_dir)),'bytes':len(blob),'sha256':sha_bytes(blob)}})
    counts={str(t['id']):0 for t in targets}
    for r in results:counts[str(r['target']['id'])]+=1
    doc={'format':'t6-ipak-exact-slice-collection-v1','targets':targets,'archives':archive_rows,'matches':results,
         'summary':{'targets':len(targets),'archivesScanned':len(archives),'matchedSlices':len(results),'targetsMatched':sum(v>0 for v in counts.values()),'targetsUnmatched':sum(v==0 for v in counts.values()),'matchCountsByTarget':counts},
         'proofBoundary':'Raw IPAK spans are selected only by exact nameHash+dataHash29. No payload is claimed until later IPAK reconstruction, CRC29 and IWI dimension checks succeed.'}
    (a.output_dir/'ipak_slice_manifest.json').write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(doc['summary'],indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
