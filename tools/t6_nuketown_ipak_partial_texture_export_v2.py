#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, ctypes, ctypes.util, hashlib, io, json, struct, zlib
from pathlib import Path
from PIL import Image

IPAK_CHUNK=0x8000
IPAK_BLOCK=0x80
IPAK_DATA=2
IPAK_INDEX=1
IWI27=27
IWI_DXT1=0x0B
IWI_DXT5=0x0D
IWI_DXN=0x0E
SEMANTIC_COLOR=2
SEMANTIC_NORMAL=5

def sha256(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def align(n,a): return (n+a-1)//a*a

def r_hash_string(s:str,h:int=0)->int:
    for c in s.encode('latin1'):
        h=((33*h) ^ (c|0x20)) & 0xffffffff
    return h

class IPak:
    def __init__(self,path:Path):
        self.path=path; self.data=path.read_bytes()
        magic,ver,size,sc=struct.unpack_from('<4sIII',self.data,0)
        if magic!=b'KAPI' or ver!=0x50000 or size!=len(self.data):
            raise ValueError('invalid T6 IPAK header')
        self.sections=[]
        for i in range(sc):
            self.sections.append(struct.unpack_from('<IIII',self.data,16+16*i))
        d=[s for s in self.sections if s[0]==IPAK_DATA]
        ix=[s for s in self.sections if s[0]==IPAK_INDEX]
        if len(d)!=1 or len(ix)!=1: raise ValueError('missing data/index section')
        self.data_sec=d[0]; self.index_sec=ix[0]
        self.by_name={}
        _,ioff,isz,icount=self.index_sec
        if icount*16>isz: raise ValueError('index size')
        for i in range(icount):
            e=struct.unpack_from('<IIII',self.data,ioff+16*i)
            if e[1] in self.by_name: raise ValueError('duplicate nameHash in IPAK')
            self.by_name[e[1]]=e
        libname=ctypes.util.find_library('lzo2')
        if not libname: raise RuntimeError('liblzo2 not found')
        self.lzo=ctypes.CDLL(libname).lzo1x_decompress_safe
        self.lzo.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p]
        self.lzo.restype=ctypes.c_int
    def entry_for_name(self,name:str): return self.by_name.get(r_hash_string(name))
    def extract(self,name:str)->tuple[bytes,tuple[int,int,int,int]]:
        e=self.entry_for_name(name)
        if not e: raise KeyError(name)
        data_hash,name_hash,rel_off,raw_size=e
        pos=self.data_sec[1]+rel_off; end=pos+raw_size; out=bytearray(); blocks=0
        while pos<end:
            pos=align(pos,IPAK_BLOCK)
            if pos>=end: break
            hdr=self.data[pos:pos+128]
            if len(hdr)!=128: raise ValueError('truncated block header')
            co=struct.unpack_from('<I',hdr,0)[0]; file_off=co&0xffffff; cnt=(co>>24)&0xff
            if cnt>31: raise ValueError('block command count')
            cmds=[]
            for i in range(cnt):
                w=struct.unpack_from('<I',hdr,4+4*i)[0]
                cmds.append((w&0xffffff,(w>>24)&0xff))
            if any(c in (0,1) for _,c in cmds) and file_off!=len(out):
                raise ValueError(f'block offset mismatch {file_off} != {len(out)}')
            p=pos+128
            for sz,comp in cmds:
                blob=self.data[p:p+sz]
                if len(blob)!=sz: raise ValueError('truncated command')
                if comp==0:
                    out.extend(blob)
                elif comp==1:
                    dst=ctypes.create_string_buffer(0x8000); n=ctypes.c_size_t(0x8000)
                    src=ctypes.create_string_buffer(blob)
                    rc=self.lzo(src,len(blob),dst,ctypes.byref(n),None)
                    if rc!=0: raise ValueError(f'lzo error {rc}')
                    out.extend(dst.raw[:n.value])
                elif comp==0xCF:
                    # Retail T6 padding/skip command: consume stored bytes but emit no output.
                    pass
                else:
                    raise ValueError(f'unsupported IPAK compression command {comp:#x}')
                p+=sz
            pos=p; blocks+=1
            if blocks>10000: raise ValueError('block runaway')
        result=bytes(out)
        crc=zlib.crc32(result)&0xffffffff
        if (crc&0x1fffffff)!=data_hash:
            raise ValueError(f'CRC mismatch {name}: {(crc&0x1fffffff):08x}!={data_hash:08x}')
        return result,e

def parse_iwi27(b:bytes):
    if len(b)<64 or b[:3]!=b'IWi' or b[3]!=IWI27: raise ValueError('not IWI27')
    fmt=b[4]; flags=b[5]; w,h,d=struct.unpack_from('<3H',b,6); gamma=struct.unpack_from('<f',b,12)[0]
    sizes=struct.unpack_from('<8I',b,32)
    if sizes[0]!=len(b): raise ValueError(f'IWI size mismatch {sizes[0]} != {len(b)}')
    return fmt,flags,w,h,d,gamma,sizes

def rgb565(c):
    r=(c>>11)&31; g=(c>>5)&63; b=c&31
    return (r*255//31,g*255//63,b*255//31)

def decode_bc1(src,w,h):
    out=bytearray(w*h*4); p=0
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            c0,c1,bits=struct.unpack_from('<HHI',src,p); p+=8
            r0,g0,b0=rgb565(c0); r1,g1,b1=rgb565(c1)
            if c0>c1:
                cols=[(r0,g0,b0,255),(r1,g1,b1,255),((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3,255),((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3,255)]
            else:
                cols=[(r0,g0,b0,255),(r1,g1,b1,255),((r0+r1)//2,(g0+g1)//2,(b0+b1)//2,255),(0,0,0,0)]
            for py in range(4):
                y=by*4+py
                if y>=h: continue
                for px in range(4):
                    x=bx*4+px
                    if x>=w: continue
                    q=(bits>>(2*(py*4+px)))&3; o=(y*w+x)*4; out[o:o+4]=bytes(cols[q])
    return bytes(out)

def decode_bc3(src,w,h):
    out=bytearray(w*h*4); p=0
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            a0,a1=src[p],src[p+1]; abits=int.from_bytes(src[p+2:p+8],'little')
            if a0>a1: al=[a0,a1]+[((6-i)*a0+(i+1)*a1)//7 for i in range(6)]
            else: al=[a0,a1]+[((4-i)*a0+(i+1)*a1)//5 for i in range(4)]+[0,255]
            c0,c1,cbits=struct.unpack_from('<HHI',src,p+8); p+=16
            r0,g0,b0=rgb565(c0); r1,g1,b1=rgb565(c1)
            cols=[(r0,g0,b0),(r1,g1,b1),((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3),((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3)]
            for py in range(4):
                y=by*4+py
                if y>=h: continue
                for px in range(4):
                    x=bx*4+px
                    if x>=w: continue
                    i=py*4+px; ci=(cbits>>(2*i))&3; ai=(abits>>(3*i))&7; o=(y*w+x)*4
                    out[o:o+4]=bytes((*cols[ci],al[ai]))
    return bytes(out)

def decode_bc4_block(block:bytes):
    a0,a1=block[0],block[1]; bits=int.from_bytes(block[2:8], 'little')
    if a0>a1:
        vals=[a0,a1]+[((6-i)*a0+(i+1)*a1)//7 for i in range(6)]
    else:
        vals=[a0,a1]+[((4-i)*a0+(i+1)*a1)//5 for i in range(4)]+[0,255]
    return [vals[(bits>>(3*i))&7] for i in range(16)]

def decode_bc5_normal(src,w,h):
    import math
    out=bytearray(w*h*4); p=0
    for by in range((h+3)//4):
        for bx in range((w+3)//4):
            xs=decode_bc4_block(src[p:p+8]); ys=decode_bc4_block(src[p+8:p+16]); p+=16
            for py in range(4):
                y=by*4+py
                if y>=h: continue
                for px in range(4):
                    x=bx*4+px
                    if x>=w: continue
                    i=py*4+px; xn=xs[i]/127.5-1.0; yn=ys[i]/127.5-1.0
                    zn=math.sqrt(max(0.0,1.0-xn*xn-yn*yn)); z=int(round((zn*0.5+0.5)*255.0))
                    o=(y*w+x)*4; out[o:o+4]=bytes((xs[i],ys[i],max(0,min(255,z)),255))
    return bytes(out)

def iwi_top_png(b:bytes, normal_semantic:bool=False)->tuple[bytes,dict]:
    fmt,flags,w,h,d,gamma,sizes=parse_iwi27(b)
    block_bytes=8 if fmt==IWI_DXT1 else 16 if fmt in (IWI_DXT5,IWI_DXN) else None
    if block_bytes is None: raise NotImplementedError(f'IWI format {fmt}')
    top_bytes=((w+3)//4)*((h+3)//4)*block_bytes
    end=sizes[0]; start=end-top_bytes
    if start < 64: raise ValueError(f'IWI top mip bounds {start} < 64')
    src=b[start:end]
    if fmt==IWI_DXT1: rgba=decode_bc1(src,w,h)
    elif fmt==IWI_DXT5: rgba=decode_bc3(src,w,h)
    elif fmt==IWI_DXN and normal_semantic: rgba=decode_bc5_normal(src,w,h)
    else: raise NotImplementedError(f'IWI format {fmt} for semantic')
    im=Image.frombytes('RGBA',(w,h),rgba)
    buf=io.BytesIO(); im.save(buf,format='PNG',optimize=False)
    return buf.getvalue(),{'format':fmt,'flags':flags,'width':w,'height':h,'depth':d,'gamma':gamma,'iwiBytes':len(b),'topMipOffset':start,'topMipBytes':len(src)}

def read_glb(path:Path):
    b=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b): raise ValueError('invalid GLB')
    o=12; js=None; bins=[]
    while o<total:
        n,t=struct.unpack_from('<I4s',b,o); o+=8; c=b[o:o+n]; o+=n
        if t==b'JSON': js=json.loads(c)
        elif t==b'BIN\0': bins.append(c)
    if js is None or len(bins)!=1: raise ValueError('expected one BIN chunk')
    return js,bytearray(bins[0])

def write_glb(path:Path,js:dict,binbuf:bytearray):
    while len(binbuf)%4: binbuf.append(0)
    js['buffers'][0]['byteLength']=len(binbuf)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    while len(jb)%4: jb+=b' '
    total=12+8+len(jb)+8+len(binbuf)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total)); out+=struct.pack('<I4s',len(jb),b'JSON')+jb; out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
    path.write_bytes(out)

def first_semantic_image(mat, semantic):
    # Fail closed: only the first texture-table entry for a semantic may be promoted.
    # If that first entry is packed/unresolved, a later layer/decal with the same semantic
    # must not be mistaken for the base layer.
    for t in mat.get('textures',[]):
        if t.get('semantic')!=semantic: continue
        im=t.get('image') or {}
        if im.get('inline') and im.get('name'): return t,im
        return t,None
    return None,None

def build(glb:Path,materials_json:Path,ipak_path:Path,out:Path,manifest_path:Path):
    js,binbuf=read_glb(glb); mats=json.loads(materials_json.read_text())['materials']; by_name={m['name']:m for m in mats}; ipak=IPak(ipak_path)
    images=js.setdefault('images',[]); textures=js.setdefault('textures',[]); samplers=js.setdefault('samplers',[]); bufferViews=js.setdefault('bufferViews',[])
    sampler_cache={}
    def sampler_for(flags):
        key=(bool(flags&0x40),bool(flags&0x80))
        if key in sampler_cache:return sampler_cache[key]
        wrapS=33071 if key[0] else 10497; wrapT=33071 if key[1] else 10497
        samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':wrapS,'wrapT':wrapT})
        sampler_cache[key]=len(samplers)-1; return sampler_cache[key]
    rows=[]; failures=[]; png_cache={}; color_bound=0; normal_bound=0
    def embed_image(iname, semantic, sampler_state):
        cache_key=(iname,semantic)
        if cache_key in png_cache:return png_cache[cache_key]
        iwi,e=ipak.extract(iname); png,meta=iwi_top_png(iwi, normal_semantic=(semantic==SEMANTIC_NORMAL)); key=sha256(png)
        while len(binbuf)%4: binbuf.append(0)
        off=len(binbuf); binbuf.extend(png); bufferViews.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{iname}_PNG'}); bvi=len(bufferViews)-1
        images.append({'name':iname,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':'mp_nuketown_2020.ipak','nameHash':r_hash_string(iname),'dataHash':e[0],'iwiSha256':sha256(iwi),'pngSha256':key,'semantic':semantic,'samplerState':sampler_state,**meta}}})
        ii=len(images)-1; si=sampler_for(meta['flags']); textures.append({'name':iname,'sampler':si,'source':ii}); ti=len(textures)-1; png_cache[cache_key]=(ti,key,meta,e)
        return png_cache[cache_key]
    for mi,gmat in enumerate(js.get('materials',[])):
        name=gmat.get('name'); src=by_name.get(name)
        if not src: continue
        matrow={'materialIndex':mi,'material':name}
        for semantic,kind in ((SEMANTIC_COLOR,'color'),(SEMANTIC_NORMAL,'normal')):
            t,im=first_semantic_image(src,semantic)
            if not im: continue
            iname=im['name']; ent=ipak.entry_for_name(iname)
            if not ent: continue
            try:
                tex_idx,key,meta,e=embed_image(iname,semantic,t.get('samplerState'))
            except Exception as ex:
                failures.append({'material':name,'kind':kind,'image':iname,'error':type(ex).__name__+': '+str(ex)}); continue
            if kind=='color':
                gmat.setdefault('pbrMetallicRoughness',{})['baseColorTexture']={'index':tex_idx,'texCoord':0}; color_bound+=1
            else:
                gmat['normalTexture']={'index':tex_idx,'texCoord':0,'scale':1.0}; normal_bound+=1
            gmat.setdefault('extras',{}).setdefault('T6',{}).setdefault('realTextureBindings',[]).append({'kind':kind,'image':iname,'semantic':semantic,'samplerState':t.get('samplerState'),'sourceContainer':'mp_nuketown_2020.ipak'})
            matrow[kind]={'image':iname,'textureIndex':tex_idx,'pngSha256':key,'iwiSha256':sha256(ipak.extract(iname)[0]),'format':meta['format'],'width':meta['width'],'height':meta['height'],'dataHash':e[0],'nameHash':e[1]}
        if len(matrow)>2 or 'color' in matrow or 'normal' in matrow: rows.append(matrow)
    js.setdefault('extras',{}).setdefault('T6',{})['realTextureExport']={'source':'mp_nuketown_2020.ipak','materialCatalog':materials_json.name,'boundColorMaterials':color_bound,'boundNormalMaterials':normal_bound,'uniqueEmbeddedTextures':len(png_cache),'proofBoundary':'First semantic-2/5 texture entry only. Exact inline GfxImage name must hash to an IPAK index entry; extracted IWI is CRC29 validated against that entry and decoded only for measured IWI27 BC formats.'}
    write_glb(out,js,binbuf)
    manifest={'format':'t6-nuketown-real-texture-export-v2','input':{'glb':glb.name,'glbSha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'materials':materials_json.name,'materialsSha256':hashlib.sha256(materials_json.read_bytes()).hexdigest(),'ipak':ipak_path.name,'ipakSha256':hashlib.sha256(ipak_path.read_bytes()).hexdigest()},'output':{'glb':out.name,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},'summary':{'boundColorMaterials':color_bound,'boundNormalMaterials':normal_bound,'uniqueEmbeddedTextures':len(png_cache),'failedExtractions':len(failures)},'materials':rows,'failures':failures,'proofBoundary':'Image bindings come only from exact retail Material first-semantic entries, exact GfxImage names, exact T6 name hashes, IPAK decompression with CRC29 validation, IWI27 parsing and BC1/BC3/BC5 decode. No filename-nearest matching, generated color guessing or placeholder textures are introduced.'}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('--glb',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--ipak',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();m=build(a.glb,a.materials,a.ipak,a.out,a.manifest);print(json.dumps(m['summary'],indent=2));print(json.dumps(m['output'],indent=2))
if __name__=='__main__':main()
