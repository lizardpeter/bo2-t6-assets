#!/usr/bin/env python3
from __future__ import annotations

import argparse,base64,ctypes,ctypes.util,hashlib,importlib.util,json,re,struct,urllib.request,zlib
from collections import defaultdict
from pathlib import Path

URL='https://r2.houseofkublai.com/bo2/zone/all/base.ipak'
IPAK_BLOCK=0x80
ADMISSIBLE={'exact-pair','unique-data-hash'}
HERE=Path(__file__).resolve().parent
BASE_PATH=HERE/'t6_nuketown_ipak_partial_texture_export_v2.py'
DEC_PATH=HERE/'t6_iwi27_png_v1.py'
spec=importlib.util.spec_from_file_location('t6_texture_base',BASE_PATH)
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
dspec=importlib.util.spec_from_file_location('t6_iwi27_png',DEC_PATH)
dec=importlib.util.module_from_spec(dspec); dspec.loader.exec_module(dec)


def sha256(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def align(n:int,a:int)->int: return (n+a-1)//a*a

def rg(start:int,end:int)->tuple[bytes,str]:
    q=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}','User-Agent':'bo2-t6-assets-world-base-extract/1'})
    with urllib.request.urlopen(q,timeout=120) as r:
        if r.status!=206: raise RuntimeError(f'range not honored: HTTP {r.status}')
        b=r.read(); cr=r.headers.get('Content-Range','')
    if len(b)!=end-start+1: raise RuntimeError(f'range length mismatch: {cr}')
    return b,cr


def load_canonical(path:Path)->dict:
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))
def safe_name(name:str)->str:
    s=re.sub(r'[^A-Za-z0-9_.-]+','_',name).strip('._'); return s or 'image'
def image_semantics(doc:dict)->dict[str,list[int]]:
    out=defaultdict(set)
    for m in doc['materials']:
        for t in m.get('textures',[]): out[t['image']].add(int(t['semantic']))
    return {k:sorted(v) for k,v in out.items()}


def open_base_index():
    head,hcr=rg(0,65535)
    magic,ver,total,sc=struct.unpack_from('<4sIII',head,0)
    if magic!=b'KAPI' or ver!=0x50000: raise ValueError('invalid T6 base IPAK')
    secs=[struct.unpack_from('<IIII',head,16+16*i) for i in range(sc)]
    ix=[s for s in secs if s[0]==1]; ds=[s for s in secs if s[0]==2]
    if len(ix)!=1 or len(ds)!=1: raise ValueError('expected one index and data section')
    _,ioff,isz,n=ix[0]
    if n*16>isz: raise ValueError('invalid base index size')
    raw,icr=rg(ioff,ioff+n*16-1)
    entries=[struct.unpack_from('<IIII',raw,16*i) for i in range(n)]
    return {'head':head,'headRange':hcr,'indexRaw':raw,'indexRange':icr,'total':total,'entries':entries,'dataSection':ds[0]}


def make_lzo():
    lib=ctypes.util.find_library('lzo2')
    if not lib: raise RuntimeError('liblzo2 not found')
    fn=ctypes.CDLL(lib).lzo1x_decompress_safe
    fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p]; fn.restype=ctypes.c_int
    return fn


def extract_segment(seg:bytes,start:int,e:tuple[int,int,int,int],lzo)->bytes:
    dh,nh,rel,raw=e; ap=start; ae=start+raw; out=bytearray(); blocks=0
    while ap<ae:
        ap=align(ap,IPAK_BLOCK)
        if ap>=ae: break
        p0=ap-start
        hdr=seg[p0:p0+128]
        if len(hdr)!=128: raise ValueError('truncated block header')
        co=struct.unpack_from('<I',hdr,0)[0]; file_off=co&0xffffff; cnt=(co>>24)&0xff
        if cnt>31: raise ValueError(f'block command count {cnt}')
        cmds=[]
        for i in range(cnt):
            w=struct.unpack_from('<I',hdr,4+4*i)[0]; cmds.append((w&0xffffff,(w>>24)&0xff))
        if any(c in (0,1) for _,c in cmds) and file_off!=len(out): raise ValueError(f'block offset mismatch {file_off}!={len(out)}')
        p=p0+128
        for sz,c in cmds:
            blob=seg[p:p+sz]
            if len(blob)!=sz: raise ValueError('truncated IPAK command')
            if c==0: out.extend(blob)
            elif c==1:
                dst=ctypes.create_string_buffer(0x8000); ln=ctypes.c_size_t(0x8000); src=ctypes.create_string_buffer(blob)
                rc=lzo(src,len(blob),dst,ctypes.byref(ln),None)
                if rc: raise ValueError(f'lzo error {rc}')
                out.extend(dst.raw[:ln.value])
            elif c==0xCF: pass
            else: raise ValueError(f'unsupported compression command {c:#x}')
            p+=sz
        ap=start+p; blocks+=1
        if blocks>10000: raise ValueError('IPAK block runaway')
    result=bytes(out)
    crc=zlib.crc32(result)&0x1fffffff
    if crc!=dh: raise ValueError(f'CRC29 {crc:08x}!={dh:08x}')
    return result


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',type=Path,required=True); ap.add_argument('--base-census',type=Path,required=True); ap.add_argument('--map-census',type=Path,required=True); ap.add_argument('--out-dir',type=Path,required=True); ap.add_argument('--expected',type=int,default=185); a=ap.parse_args()
    doc=load_canonical(a.manifest); sems=image_semantics(doc); meta={x['image']:x for x in doc['images']}
    bc=json.loads(a.base_census.read_text()); mc=json.loads(a.map_census.read_text()); maprows={r['image']:r for r in mc['rows']}
    candidates=[r for r in bc['rows'] if r['state'] in ADMISSIBLE and maprows[r['image']]['state'] not in ADMISSIBLE]
    if len(candidates)!=a.expected: raise ValueError(f'base-additional candidates {len(candidates)} != {a.expected}')

    ix=open_base_index(); entries=ix['entries']; entryset=set(entries); by_data=defaultdict(list)
    for e in entries: by_data[e[0]].append(e)
    if ix['total']!=2614362112: raise ValueError(f'unexpected base.ipak bytes {ix["total"]}')
    lzo=make_lzo(); data_off=ix['dataSection'][1]; a.out_dir.mkdir(parents=True,exist_ok=True)
    network=len(ix['head'])+len(ix['indexRaw']); rows=[]
    for i,r in enumerate(candidates):
        name=r['image']; e=tuple(int(x) for x in r['chosenEntry'])
        if e not in entryset: raise ValueError(f'{name}: census entry absent from live base index')
        if e[0]!=int(r['dataHash29']): raise ValueError(f'{name}: retained dataHash mismatch')
        if r['state']=='exact-pair' and e[1]!=int(r['nameHash']): raise ValueError(f'{name}: exact pair nameHash mismatch')
        if r['state']=='unique-data-hash' and len(by_data[e[0]])!=1: raise ValueError(f'{name}: dataHash no longer unique')
        start=data_off+e[2]; end=start+e[3]-1; seg,cr=rg(start,end); network+=len(seg)
        iwi=extract_segment(seg,start,e,lzo)
        fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
        dims=(int(r['width']),int(r['height']),int(r['depth']))
        if (w,h,d)!=dims: raise ValueError(f'{name}: IWI dimensions {(w,h,d)} != retained {dims}')
        im=meta[name]
        if (w,h,d)!=(int(im['width']),int(im['height']),int(im['depth'])): raise ValueError(f'{name}: canonical dimension mismatch')
        stem=f'{i:03d}_{safe_name(name)}'; iwif=stem+'.iwi'; (a.out_dir/iwif).write_bytes(iwi)
        ss=sems.get(name,[]); roles=[]
        if 5 in ss: roles.append(('normal',True))
        if any(s!=5 for s in ss) or not roles: roles.append(('colorlike',False))
        variants=[]
        for role,is_normal in roles:
            png,pmeta=dec.iwi_top_png(iwi,normal_semantic=is_normal); fn=f'{stem}.{role}.png'; (a.out_dir/fn).write_bytes(png)
            variants.append({'role':role,'normalSemanticDecode':is_normal,'file':fn,'bytes':len(png),'sha256':sha256(png),'decodeMeta':pmeta})
        rows.append({'image':name,'state':r['state'],'retainedNameHash':int(r['nameHash']),'retainedDataHash29':int(r['dataHash29']),'ipakEntry':list(e),'contentRange':cr,'semanticSet':ss,'dimensions':[w,h,d],'format':fmt,'flags':flags,'gamma':gamma,'iwiFile':iwif,'iwiBytes':len(iwi),'iwiSha256':sha256(iwi),'crc29Validated':True,'dimensionsValidated':True,'pngVariants':variants})

    report={'format':'t6-nuketown-live-world-base-ipak-texture-extraction-v1','source':{'url':URL,'bytes':ix['total'],'indexEntryCount':len(entries),'headContentRange':ix['headRange'],'indexContentRange':ix['indexRange'],'headSha256':sha256(ix['head']),'indexSha256':sha256(ix['indexRaw']),'networkBytes':network},'summary':{'baseAdditionalCandidates':len(candidates),'validatedPayloads':len(rows),'exactPairPayloads':sum(r['state']=='exact-pair' for r in rows),'uniqueDataHashPayloads':sum(r['state']=='unique-data-hash' for r in rows),'normalSemanticImages':sum(5 in r['semanticSet'] for r in rows),'colorlikeSemanticImages':sum(any(s!=5 for s in r['semanticSet']) for r in rows),'pngVariantCount':sum(len(r['pngVariants']) for r in rows)},'rows':rows,'proofBoundary':'Only live images not already covered by the pinned map IPAK are extracted. Each base.ipak row must remain census-admissible against a freshly range-read retail base index. Its streamed dataHash must equal the canonical retained CRC29; decompressed bytes must recompute that CRC29; IWI27 must parse; retained dimensions must match exactly; BC1, BC2/DXT3, BC3 and BC5/DXN top mips are decoded only then.'}
    (a.out_dir/'TEXTURE_EXTRACTION_V1.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps(report['summary'],indent=2,sort_keys=True)); print('networkBytes',network)

if __name__=='__main__': main()
