#!/usr/bin/env python3
"""Recover exact Nuketown streamed GfxImage payloads from an IPAK by data hash.

This is a fail-closed fallback for the case where a retained Material names an
inline streaming GfxImage, but the map-specific IPAK does not index that payload
under R_HashString(imageName). The retained GfxImageStreamedPartInfo.hash is a
29-bit CRC identity for the streamed payload and the IPAK index's dataHash uses
the same identity. Promotion requires a unique broad-scan image row, a unique
IPAK dataHash entry, CRC equality after raw/LZO extraction, IWI27 parse success,
and exact retained width/height/depth agreement.
"""
from __future__ import annotations
import argparse, ctypes, ctypes.util, hashlib, importlib.util, json, struct, zlib
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE/'t6_nuketown_ipak_partial_texture_export_v2.py'
spec=importlib.util.spec_from_file_location('t6_tex_v2',BASE)
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

SEMANTICS=((2,'color'),(5,'normal'))
IPAK_BLOCK=0x80

def sha_file(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def align(n,a): return (n+a-1)//a*a

def first_semantic(material,semantic):
    for t in material.get('textures',[]):
        if t.get('semantic')==semantic:
            return t
    return None

def exact_inline_name(t):
    im=(t or {}).get('image') or {}
    return im.get('name') if im.get('inline') and im.get('name') else None

def read_ipak(path:Path):
    data=path.read_bytes(); magic,ver,size,sc=struct.unpack_from('<4sIII',data,0)
    if magic!=b'KAPI' or ver!=0x50000 or size!=len(data): raise ValueError('invalid T6 IPAK')
    sections=[struct.unpack_from('<IIII',data,16+16*i) for i in range(sc)]
    d=[s for s in sections if s[0]==2]; ix=[s for s in sections if s[0]==1]
    if len(d)!=1 or len(ix)!=1: raise ValueError('missing IPAK data/index section')
    _,ioff,isz,icount=ix[0]
    if icount*16>isz: raise ValueError('invalid IPAK index size')
    entries=[]; by_data=defaultdict(list); by_name={}
    for i in range(icount):
        e=struct.unpack_from('<IIII',data,ioff+16*i)
        entries.append(e); by_data[e[0]].append(e)
        if e[1] in by_name: raise ValueError('duplicate IPAK nameHash')
        by_name[e[1]]=e
    libname=ctypes.util.find_library('lzo2')
    if not libname: raise RuntimeError('liblzo2 not found')
    lzo=ctypes.CDLL(libname).lzo1x_decompress_safe
    lzo.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p]
    lzo.restype=ctypes.c_int
    return data,d[0],entries,by_data,by_name,lzo

def extract_entry(data,data_sec,e,lzo):
    data_hash,name_hash,rel_off,raw_size=e
    pos=data_sec[1]+rel_off; end=pos+raw_size; out=bytearray(); blocks=0
    while pos<end:
        pos=align(pos,IPAK_BLOCK)
        if pos>=end: break
        hdr=data[pos:pos+128]
        if len(hdr)!=128: raise ValueError('truncated IPAK block header')
        co=struct.unpack_from('<I',hdr,0)[0]; file_off=co&0xffffff; cnt=(co>>24)&0xff
        if cnt>31: raise ValueError('IPAK block command count')
        cmds=[]
        for i in range(cnt):
            w=struct.unpack_from('<I',hdr,4+4*i)[0]; cmds.append((w&0xffffff,(w>>24)&0xff))
        if any(c in (0,1) for _,c in cmds) and file_off!=len(out):
            raise ValueError(f'IPAK block offset mismatch {file_off} != {len(out)}')
        p=pos+128
        for sz,comp in cmds:
            blob=data[p:p+sz]
            if len(blob)!=sz: raise ValueError('truncated IPAK command')
            if comp==0: out.extend(blob)
            elif comp==1:
                dst=ctypes.create_string_buffer(0x8000); n=ctypes.c_size_t(0x8000); src=ctypes.create_string_buffer(blob)
                rc=lzo(src,len(blob),dst,ctypes.byref(n),None)
                if rc!=0: raise ValueError(f'lzo error {rc}')
                out.extend(dst.raw[:n.value])
            elif comp==0xCF:
                # Retail T6 padding/skip command: consume stored bytes but emit no output.
                pass
            else: raise ValueError(f'unsupported IPAK compression command {comp:#x}')
            p+=sz
        pos=p; blocks+=1
        if blocks>10000: raise ValueError('IPAK block runaway')
    result=bytes(out)
    crc29=zlib.crc32(result)&0x1fffffff
    if crc29!=data_hash: raise ValueError(f'IPAK CRC29 mismatch {crc29:08x}!={data_hash:08x}')
    return result

def broad_rows(scan_doc):
    rows=scan_doc.get('records') or []
    by_name=defaultdict(list)
    for r in rows:
        name=r.get('image') or r.get('name')
        if name: by_name[name].append(r)
    return by_name

def build(in_glb,materials_path,scan_path,ipak_path,out_glb,manifest_path):
    js,binbuf=base.read_glb(in_glb)
    mats=json.loads(materials_path.read_text())['materials']; bymat={m['name']:m for m in mats}
    scans=broad_rows(json.loads(scan_path.read_text()))
    data,data_sec,entries,by_data,by_name_hash,lzo=read_ipak(ipak_path)

    images=js.setdefault('images',[]); textures=js.setdefault('textures',[]); samplers=js.setdefault('samplers',[]); bvs=js.setdefault('bufferViews',[])
    sampler_cache={}
    def sampler_for(flags):
        key=(bool(flags&0x40),bool(flags&0x80))
        if key in sampler_cache:return sampler_cache[key]
        samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':33071 if key[0] else 10497,'wrapT':33071 if key[1] else 10497})
        sampler_cache[key]=len(samplers)-1;return sampler_cache[key]

    cache={}; promotions=[]; considered=[]
    for mi,gmat in enumerate(js.get('materials',[])):
        src=bymat.get(gmat.get('name'))
        if not src: continue
        for semantic,kind in SEMANTICS:
            if kind=='color' and (gmat.get('pbrMetallicRoughness') or {}).get('baseColorTexture') is not None: continue
            if kind=='normal' and gmat.get('normalTexture') is not None: continue
            t=first_semantic(src,semantic); iname=exact_inline_name(t)
            if not iname: continue
            if base.r_hash_string(iname) in by_name_hash: continue
            rr=scans.get(iname,[])
            if len(rr)!=1: continue
            r=rr[0]
            if int(r.get('streaming',0))==0 or int(r.get('streamedPartCountRaw',0))!=1: continue
            h=r.get('streamedPart0Hash29')
            if not isinstance(h,int): continue
            es=by_data.get(h,[])
            considered.append({'material':gmat.get('name'),'materialIndex':mi,'kind':kind,'image':iname,'streamHash29':h,'ipakCandidateCount':len(es)})
            if len(es)!=1: continue
            e=es[0]
            key=(iname,semantic,h)
            if key not in cache:
                iwi=extract_entry(data,data_sec,e,lzo)
                fmt,flags,w,hh,d,gamma,sizes=base.parse_iwi27(iwi)
                if (w,hh,d)!=(int(r['width']),int(r['height']),int(r['depth'])):
                    raise ValueError(f'{iname}: retained/IWI dimensions mismatch {(r["width"],r["height"],r["depth"])} != {(w,hh,d)}')
                png,meta=base.iwi_top_png(iwi,normal_semantic=(semantic==5))
                while len(binbuf)%4:binbuf.append(0)
                off=len(binbuf);binbuf.extend(png)
                bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{iname}_streamhash_PNG'}); bvi=len(bvs)-1
                images.append({'name':iname,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':ipak_path.name,'identityResolution':'streamed-part-data-hash','streamedPartHash29':h,'ipakDataHash':e[0],'ipakNameHash':e[1],'expectedNameHash':base.r_hash_string(iname),'iwiSha256':base.sha256(iwi),'pngSha256':base.sha256(png),**meta}}})
                ii=len(images)-1; si=sampler_for(flags); textures.append({'name':iname,'sampler':si,'source':ii}); ti=len(textures)-1
                cache[key]=(ti,meta,e,base.sha256(iwi),base.sha256(png))
            ti,meta,e,iwi_sha,png_sha=cache[key]
            if kind=='color': gmat.setdefault('pbrMetallicRoughness',{})['baseColorTexture']={'index':ti,'texCoord':0}
            else: gmat['normalTexture']={'index':ti,'texCoord':0,'scale':1.0}
            gmat.setdefault('extras',{}).setdefault('T6',{}).setdefault('realTextureBindings',[]).append({'kind':kind,'image':iname,'semantic':semantic,'samplerState':t.get('samplerState'),'sourceContainer':ipak_path.name,'identityResolution':'streamed-part-data-hash','streamedPartHash29':h})
            promotions.append({'material':gmat.get('name'),'materialIndex':mi,'kind':kind,'image':iname,'semantic':semantic,'streamedPartHash29':h,'ipakDataHash':e[0],'ipakNameHash':e[1],'expectedNameHash':base.r_hash_string(iname),'iwiSha256':iwi_sha,'pngSha256':png_sha,**meta})

    if not promotions: raise ValueError('no exact streamed-part data-hash texture promotions')
    js.setdefault('extras',{}).setdefault('T6',{})['streamHashTextureRecoveryV1']={'promotionCount':len(promotions),'uniqueImages':len(cache),'proofBoundary':'Fallback only when exact retained inline streaming GfxImage name is known but IPAK name-hash lookup is absent. Requires one broad-scan streamedPart hash, one IPAK dataHash match, decompressed CRC29 equality, IWI27 parse, and exact retained dimensions.'}
    base.write_glb(out_glb,js,binbuf)
    js2,bin2=base.read_glb(out_glb)
    if js2['buffers'][0]['byteLength']!=len(bin2):raise ValueError('output GLB buffer length mismatch')
    manifest={'format':'t6-nuketown-ipak-streamhash-texture-recovery-v1','inputGlb':{'file':in_glb.name,'bytes':in_glb.stat().st_size,'sha256':sha_file(in_glb)},'materials':{'file':materials_path.name,'sha256':sha_file(materials_path)},'imageScan':{'file':scan_path.name,'sha256':sha_file(scan_path)},'ipak':{'file':ipak_path.name,'bytes':ipak_path.stat().st_size,'sha256':sha_file(ipak_path)},'outputGlb':{'file':out_glb.name,'bytes':out_glb.stat().st_size,'sha256':sha_file(out_glb)},'summary':{'promotionCount':len(promotions),'uniqueImageCount':len(cache),'colorPromotions':sum(p['kind']=='color' for p in promotions),'normalPromotions':sum(p['kind']=='normal' for p in promotions)},'promotions':promotions,'consideredExactNameButMissingNameHash':considered,'validation':{'glbReparse':'pass','bufferByteLengthMatches':'pass'},'proofBoundary':'No image is admitted by proximity or filename similarity. The exact retained GfxImage name and streamedPart hash must identify a unique map-IPAK dataHash entry; its decompressed CRC29 and IWI dimensions must independently agree.'}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return manifest

def main():
    a=argparse.ArgumentParser();a.add_argument('--glb',type=Path,required=True);a.add_argument('--materials',type=Path,required=True);a.add_argument('--image-scan',type=Path,required=True);a.add_argument('--ipak',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);q=a.parse_args()
    m=build(q.glb,q.materials,q.image_scan,q.ipak,q.out,q.manifest);print(json.dumps(m['summary'],indent=2));print(json.dumps(m['outputGlb'],indent=2))
if __name__=='__main__':main()
