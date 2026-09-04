#!/usr/bin/env python3
"""Bind exact-pair T6 textures to recovered Nuketown static-XModel materials.

Unlike v1, streamed IPAK images are admitted only when the full retail key
(GfxImage.hash, GfxImage.streamedParts[0].hash) matches one IPAK index entry.
This mirrors T6/OAT GetEntryStream(nameHash, dataHash).  It also reuses the
retail-proven block5/514620 $identitynormalmap for static materials whose first
semantic-5 pointer targets that exact virtual address.
"""
from __future__ import annotations
import argparse, collections, ctypes, ctypes.util, hashlib, importlib.util, io, json, struct, zlib
from pathlib import Path
from PIL import Image

HERE=Path(__file__).resolve().parent
BASE=HERE/'t6_nuketown_ipak_partial_texture_export_v2.py'
spec=importlib.util.spec_from_file_location('t6_tex_v2',BASE)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
IWI_DXT3=0x0C
SEMANTICS=((2,'color'),(5,'normal'))
IPAK_BLOCK=0x80
IDENTITY_BLOCK=5
IDENTITY_OFFSET=514620
IDENTITY_NAME='$identitynormalmap'
IDENTITY_SOURCE_SHA='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'

def sha_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def align(n,a):return (n+a-1)//a*a

def decode_bc2(src,w,h):
    out=bytearray(w*h*4);p=0
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            abits=int.from_bytes(src[p:p+8],'little');c0,c1,cbits=struct.unpack_from('<HHI',src,p+8);p+=16
            r0,g0,b0=base.rgb565(c0);r1,g1,b1=base.rgb565(c1)
            cols=[(r0,g0,b0),(r1,g1,b1),((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3),((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3)]
            for py in range(4):
                y=by*4+py
                if y>=h:continue
                for px in range(4):
                    x=bx*4+px
                    if x>=w:continue
                    i=py*4+px;ci=(cbits>>(2*i))&3;a4=(abits>>(4*i))&15;o=(y*w+x)*4
                    out[o:o+4]=bytes((*cols[ci],a4*17))
    return bytes(out)

def iwi_top_png(b,normal_semantic=False):
    """Fast native BCn decode through Pillow's DDS decoder; reconstruct BC5 normal Z."""
    import numpy as np
    fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(b)
    dxgi={11:71,12:74,13:77,14:83}.get(fmt)
    if dxgi is None: raise NotImplementedError(f'IWI format {fmt}')
    block_bytes=8 if fmt==11 else 16
    top_bytes=((w+3)//4)*((h+3)//4)*block_bytes
    end=sizes[0];start=end-top_bytes
    if start<64:raise ValueError('BCn top mip bounds')
    comp=b[start:end]
    hdr=bytearray(b'DDS ')
    hdr+=struct.pack('<I',124)
    hdr+=struct.pack('<I',0x00081007)
    hdr+=struct.pack('<IIIII',h,w,top_bytes,0,1)
    hdr+=b'\0'*(11*4)
    hdr+=struct.pack('<II4sIIIII',32,4,b'DX10',0,0,0,0,0)
    hdr+=struct.pack('<IIIII',0x1000,0,0,0,0)
    hdr+=struct.pack('<IIIII',dxgi,3,0,1,0)
    im=Image.open(io.BytesIO(bytes(hdr)+comp));im.load()
    if fmt==14 and normal_semantic:
        arr=np.asarray(im.convert('RGB'),dtype=np.uint8)
        x=arr[...,0].astype(np.float32)/127.5-1.0
        y=arr[...,1].astype(np.float32)/127.5-1.0
        z=np.sqrt(np.maximum(0.0,1.0-x*x-y*y))
        zz=np.clip(np.rint((z*0.5+0.5)*255.0),0,255).astype(np.uint8)
        a=np.full_like(zz,255,dtype=np.uint8)
        rgba=np.dstack((arr[...,0],arr[...,1],zz,a))
        im=Image.fromarray(rgba,'RGBA')
    else:
        im=im.convert('RGBA')
    buf=io.BytesIO();im.save(buf,format='PNG',compress_level=1,optimize=False)
    return buf.getvalue(),{'format':fmt,'flags':flags,'width':w,'height':h,'depth':d,'gamma':gamma,'iwiBytes':len(b),'topMipOffset':start,'topMipBytes':top_bytes,'decoder':'Pillow-DDS-native'}

def read_ipak(path):
    data=path.read_bytes();magic,ver,size,sc=struct.unpack_from('<4sIII',data,0)
    if magic!=b'KAPI' or ver!=0x50000 or size!=len(data):raise ValueError('invalid T6 IPAK')
    secs=[struct.unpack_from('<IIII',data,16+16*i) for i in range(sc)];ds=[s for s in secs if s[0]==2];ix=[s for s in secs if s[0]==1]
    if len(ds)!=1 or len(ix)!=1:raise ValueError('IPAK sections')
    _,ioff,isz,icount=ix[0];by_pair={};by_name=collections.defaultdict(list);by_data=collections.defaultdict(list)
    for i in range(icount):
        e=struct.unpack_from('<IIII',data,ioff+16*i)
        key=(e[1],e[0])
        if key in by_pair: raise ValueError(f'duplicate IPAK exact key {key!r}')
        by_pair[key]=e;by_name[e[1]].append(e);by_data[e[0]].append(e)
    libname=ctypes.util.find_library('lzo2')
    if not libname:raise RuntimeError('liblzo2 missing')
    lzo=ctypes.CDLL(libname).lzo1x_decompress_safe;lzo.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p];lzo.restype=ctypes.c_int
    return data,ds[0],by_pair,by_name,by_data,lzo

def extract_entry(data,data_sec,e,lzo):
    data_hash,name_hash,rel_off,raw_size=e;pos=data_sec[1]+rel_off;end=pos+raw_size;out=bytearray();blocks=0
    while pos<end:
        pos=align(pos,IPAK_BLOCK)
        if pos>=end:break
        hdr=data[pos:pos+128];co=struct.unpack_from('<I',hdr,0)[0];file_off=co&0xffffff;cnt=(co>>24)&255
        if cnt>31:raise ValueError('IPAK command count')
        cmds=[]
        for i in range(cnt):w=struct.unpack_from('<I',hdr,4+4*i)[0];cmds.append((w&0xffffff,(w>>24)&255))
        if any(c in (0,1) for _,c in cmds) and file_off!=len(out):raise ValueError('IPAK output offset mismatch')
        p=pos+128
        for sz,comp in cmds:
            blob=data[p:p+sz]
            if comp==0:out.extend(blob)
            elif comp==1:
                dst=ctypes.create_string_buffer(0x8000);n=ctypes.c_size_t(0x8000);src=ctypes.create_string_buffer(blob);rc=lzo(src,len(blob),dst,ctypes.byref(n),None)
                if rc!=0:raise ValueError(f'lzo {rc}')
                out.extend(dst.raw[:n.value])
            elif comp==0xCF:
                # Retail T6 padding/skip command: consume stored bytes but emit no output.
                pass
            else:raise ValueError(f'compression {comp:#x}')
            p+=sz
        pos=p;blocks+=1
        if blocks>10000:raise ValueError('IPAK runaway')
    result=bytes(out);crc=zlib.crc32(result)&0x1fffffff
    if crc!=data_hash:raise ValueError(f'CRC29 {crc:08x}!={data_hash:08x}')
    return result

def first_sem(m,sem):return next((t for t in m.get('textures',[]) if t.get('semantic')==sem),None)

def packed_key(t):
    if not t:return None
    im=t.get('image') or {};p=im.get('pointer') or t.get('imagePointer') or {}
    if not im.get('inline') and p.get('kind')=='offset':return (p.get('block'),p.get('offset'))
    return None

def existing_exact_texture(js,name,expected_data_hash):
    candidates=[]
    for ti,t in enumerate(js.get('textures',[])):
        if t.get('name')!=name:continue
        source=t.get('source')
        if not isinstance(source,int) or source>=len(js.get('images',[])):continue
        ex=((js['images'][source].get('extras') or {}).get('T6') or {})
        dh=ex.get('ipakDataHash')
        if dh==expected_data_hash:candidates.append(ti)
    if len(candidates)>1: raise ValueError(f'{name}: multiple exact embedded payloads for data hash {expected_data_hash:#x}')
    return candidates[0] if candidates else None

def find_identity_texture(js):
    found=[]
    for ti,t in enumerate(js.get('textures',[])):
        if t.get('name')!=IDENTITY_NAME:continue
        si=t.get('source')
        if not isinstance(si,int) or si>=len(js.get('images',[])):continue
        ex=((js['images'][si].get('extras') or {}).get('T6') or {})
        if (ex.get('sourceSha256')==IDENTITY_SOURCE_SHA and ex.get('identityResolution')=='loader-address-proof' and ex.get('block')==IDENTITY_BLOCK and ex.get('virtualOffset')==IDENTITY_OFFSET):found.append(ti)
    if len(found)!=1:raise ValueError(f'expected one proven {IDENTITY_NAME}, got {found}')
    return found[0]

def build(in_glb,catalog_path,ipak_path,out_glb,manifest_path):
    cat=json.loads(catalog_path.read_text());by_mat={m['name']:m for m in cat['materials'] if m.get('status')=='located'}
    js,binbuf=base.read_glb(in_glb);data,data_sec,by_pair,by_name,by_data,lzo=read_ipak(ipak_path)
    identity_ti=find_identity_texture(js)
    images=js.setdefault('images',[]);textures=js.setdefault('textures',[]);samplers=js.setdefault('samplers',[]);bvs=js.setdefault('bufferViews',[])
    cache={};sampler_cache={};prom=[];miss=collections.Counter();wrong_name_variant=[]
    def sampler_for(flags):
        key=(bool(flags&0x40),bool(flags&0x80))
        if key in sampler_cache:return sampler_cache[key]
        samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':33071 if key[0] else 10497,'wrapT':33071 if key[1] else 10497});sampler_cache[key]=len(samplers)-1;return sampler_cache[key]
    def get_payload(im):
        name=im['name'];nh=base.r_hash_string(name);dh=im.get('streamedPart0Hash29')
        if dh is None:return None,'missing-stream-hash'
        e=by_pair.get((nh,dh))
        if e is None:
            if by_name.get(nh):wrong_name_variant.append({'image':name,'nameHash':nh,'expectedDataHash':dh,'availableDataHashes':sorted({x[0] for x in by_name[nh]})})
            return None,'exact-pair-missing'
        iwi=extract_entry(data,data_sec,e,lzo);fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
        if (w,h,d)!=(im['width'],im['height'],im['depth']):raise ValueError(f'{name}: exact-pair dimensions mismatch {(w,h,d)} != {(im["width"],im["height"],im["depth"])}')
        return (iwi,e,flags,'ipak-exact-name+data-hash'),'ok'
    for mi,g in enumerate(js.get('materials',[])):
        src=by_mat.get(g.get('name'))
        if not src:continue
        for sem,kind in SEMANTICS:
            if kind=='color' and (g.get('pbrMetallicRoughness') or {}).get('baseColorTexture') is not None:continue
            if kind=='normal' and g.get('normalTexture') is not None:continue
            t=first_sem(src,sem)
            if not t:miss[(kind,'semantic-absent')]+=1;continue
            if kind=='normal' and packed_key(t)==(IDENTITY_BLOCK,IDENTITY_OFFSET):
                ti=identity_ti;resolution='reuse-proven-fastfile-identitynormal';e=None;iwi_sha=None;png_sha=None;meta={}
            else:
                im=(t or {}).get('image') or {}
                if not (im.get('inline') and im.get('name')):miss[(kind,'not-inline')]+=1;continue
                name=im['name'];got,state=get_payload(im)
                if got is None:miss[(kind,state)]+=1;continue
                iwi,e,flags,resolution=got
                ti=existing_exact_texture(js,name,e[0])
                if ti is not None:
                    resolution='reuse-existing-exact-payload';meta={};iwi_sha=None;png_sha=None
                else:
                    key=(name,sem,e[0])
                    if key in cache:ti,meta,iwi_sha,png_sha=cache[key]
                    else:
                        png,meta=iwi_top_png(iwi,normal_semantic=(sem==5));iwi_sha=hashlib.sha256(iwi).hexdigest();png_sha=hashlib.sha256(png).hexdigest()
                        while len(binbuf)%4:binbuf.append(0)
                        off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_static_exact_PNG'});bvi=len(bvs)-1
                        images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':ipak_path.name,'identityResolution':'ipak-exact-name+data-hash','ipakDataHash':e[0],'ipakNameHash':e[1],'expectedNameHash':base.r_hash_string(name),'expectedStreamedDataHash':im.get('streamedPart0Hash29'),'iwiSha256':iwi_sha,'pngSha256':png_sha,**meta}}});ii=len(images)-1;si=sampler_for(meta['flags']);textures.append({'name':name,'sampler':si,'source':ii});ti=len(textures)-1;cache[key]=(ti,meta,iwi_sha,png_sha)
            if kind=='color':
                pbr=g.setdefault('pbrMetallicRoughness',{});pbr['baseColorTexture']={'index':ti,'texCoord':0};pbr['baseColorFactor']=[1.0,1.0,1.0,1.0]
            else:g['normalTexture']={'index':ti,'texCoord':0,'scale':1.0}
            image_name=IDENTITY_NAME if resolution=='reuse-proven-fastfile-identitynormal' else t['image']['name']
            source_container='mp_nuketown_2020.expanded.bin' if resolution=='reuse-proven-fastfile-identitynormal' else (ipak_path.name if resolution!='reuse-existing-exact-payload' else 'already-embedded-exact-payload')
            g.setdefault('extras',{}).setdefault('T6',{}).setdefault('realTextureBindings',[]).append({'kind':kind,'image':image_name,'semantic':sem,'samplerState':t.get('samplerState'),'sourceContainer':source_container,'identityResolution':resolution})
            prom.append({'materialIndex':mi,'material':g.get('name'),'kind':kind,'semantic':sem,'image':image_name,'textureIndex':ti,'identityResolution':resolution,'ipakDataHash':e[0] if e else None,'ipakNameHash':e[1] if e else None,'iwiSha256':iwi_sha,'pngSha256':png_sha,**meta})
    if not prom:raise ValueError('no static material promotions')
    color_count=sum(p['kind']=='color' for p in prom);normal_count=sum(p['kind']=='normal' for p in prom);identity_count=sum(p['identityResolution']=='reuse-proven-fastfile-identitynormal' for p in prom)
    js.setdefault('extras',{}).setdefault('T6',{})['staticXModelTextureApplyV2']={'promotionCount':len(prom),'colorPromotions':color_count,'normalPromotions':normal_count,'identityNormalPromotions':identity_count,'materialCatalog':catalog_path.name,'proofBoundary':'Exact recovered retail static-XModel Material name. Streamed IPAK images require the exact retail key pair (GfxImage.hash, streamedParts[0].hash), CRC29, and exact dimensions. block5/514620 normals reuse only the already embedded loader-address-proven $identitynormalmap.'}
    base.write_glb(out_glb,js,binbuf);js2,bin2=base.read_glb(out_glb)
    if js2['buffers'][0]['byteLength']!=len(bin2):raise ValueError('GLB buffer mismatch')
    manifest={'format':'t6-nuketown-static-xmodel-real-texture-apply-v2-exact-pair','inputGlb':{'file':in_glb.name,'bytes':in_glb.stat().st_size,'sha256':sha_file(in_glb)},'catalog':{'file':catalog_path.name,'sha256':sha_file(catalog_path),'fullyLocatedCount':cat['fullyLocatedCount'],'worldCatalogCrossValidation':cat['worldCatalogCrossValidation']},'ipak':{'file':ipak_path.name,'bytes':ipak_path.stat().st_size,'sha256':sha_file(ipak_path)},'outputGlb':{'file':out_glb.name,'bytes':out_glb.stat().st_size,'sha256':sha_file(out_glb)},'summary':{'promotionCount':len(prom),'colorPromotions':color_count,'normalPromotions':normal_count,'identityNormalPromotions':identity_count,'uniqueNewPayloads':len(cache),'reusedExistingExactPayloads':sum(p['identityResolution']=='reuse-existing-exact-payload' for p in prom),'sameNameWrongDataVariantRejected':len(wrong_name_variant),'misses':{f'{k[0]}:{k[1]}':v for k,v in miss.items()}},'rejectedSameNameWrongDataVariants':wrong_name_variant,'promotions':prom,'validation':{'glbReparse':'pass','bufferByteLengthMatches':'pass'},'proofBoundary':'No material or image name inference. Static material records are exact-name located in the pinned FastFile. Streamed images are bound only on exact two-hash IPAK key equality plus CRC29 and dimension validation; same-name wrong-data variants are explicitly rejected.'}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');return manifest

def main():
    a=argparse.ArgumentParser();a.add_argument('--glb',type=Path,required=True);a.add_argument('--catalog',type=Path,required=True);a.add_argument('--ipak',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);q=a.parse_args();m=build(q.glb,q.catalog,q.ipak,q.out,q.manifest);print(json.dumps(m['summary'],indent=2));print(json.dumps(m['outputGlb'],indent=2))
if __name__=='__main__':main()
