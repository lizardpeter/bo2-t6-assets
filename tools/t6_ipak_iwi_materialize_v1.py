#!/usr/bin/env python3
"""Materialize exact T6 IPAK stream keys as verified IWI + PNG texture files.

A texture is promoted only when all identity and payload checks agree:
- exact retail (nameHash, dataHash) selects exactly one IPAK index row;
- the indexed span reconstructs using only known T6 raw/LZO IPAK commands;
- CRC32(payload) & 0x1fffffff equals retained GfxImage dataHash;
- the payload is IWI version 27;
- retained width/height/depth, when available, exactly match IWI metadata;
- PNG export supports the exact IWI format/semantic (BC1, BC3, or BC5 normal).

The reconstructed IWI remains the authoritative pixel payload. PNG is a usable
lossless top-mip derivative and is never used as identity evidence.
"""
from __future__ import annotations
import argparse, ctypes, ctypes.util, hashlib, json, struct, zlib
from pathlib import Path

IPAK_MAGIC=b'KAPI'; IPAK_VERSION=0x50000; IPAK_BLOCK=0x80
IWI27=27; IWI_DXT1=0x0B; IWI_DXT5=0x0D; IWI_DXN=0x0E
ENTRY=struct.Struct('<IIII')
class TextureError(RuntimeError): pass

def align(n:int,a:int)->int:return (n+a-1)//a*a
def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def sha256_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def parse_u32(v)->int:
 if isinstance(v,bool):raise TextureError('boolean is not a u32')
 if isinstance(v,int):return v&0xffffffff
 if isinstance(v,str):return int(v,0)&0xffffffff
 raise TextureError(f'not a u32: {v!r}')
def safe_name(s:str)->str:
 out=''.join(c if (c.isalnum() or c in '._-~+') else '_' for c in s);return out[:180] or 'unnamed'

def load_targets(path:Path)->list[dict]:
 doc=json.loads(path.read_text(encoding='utf-8-sig'));rows=doc if isinstance(doc,list) else doc.get('exactBaseIpakKeys') or doc.get('exactStreamKeyImages')
 if not isinstance(rows,list):raise TextureError('target manifest has no exactBaseIpakKeys/exactStreamKeyImages/list')
 out=[];seen=set()
 for r in rows:
  if not isinstance(r,dict):continue
  name=r.get('image') or r.get('name')
  if not isinstance(name,str) or not name:raise TextureError('target missing image/name')
  sp=r.get('streamedPart0') or {};nh=parse_u32(r.get('nameHash',r.get('nameHashHex')));dh=parse_u32(sp.get('dataHash',sp.get('dataHashHex',r.get('dataHash',r.get('dataHashHex')))))&0x1fffffff;key=(nh,dh)
  if key in seen:continue
  seen.add(key);out.append({'image':name,'nameHash':nh,'dataHash':dh,'target':r})
 if not out:raise TextureError('no exact texture targets')
 return out

def add_meta(index,name,meta):index.setdefault(name,[]).append(meta)
def load_metadata(paths:list[Path])->dict[str,dict]:
 candidates={}
 for path in paths:
  doc=json.loads(path.read_text(encoding='utf-8-sig'))
  for key in ('exactBaseIpakKeys','exactStreamKeyImages'):
   rows=doc.get(key) if isinstance(doc,dict) else None
   if isinstance(rows,list):
    for r in rows:
     if not isinstance(r,dict):continue
     name=r.get('image') or r.get('name')
     if isinstance(name,str):
      sp=r.get('streamedPart0') or {};add_meta(candidates,name,{'sourceManifest':str(path),'nameHash':r.get('nameHash',r.get('nameHashHex')),'dataHash':sp.get('dataHash',sp.get('dataHashHex',r.get('dataHash',r.get('dataHashHex')))),'width':r.get('width'),'height':r.get('height'),'depth':r.get('depth'),'uses':r.get('uses') or []})
  rows=doc.get('promotions') if isinstance(doc,dict) else None
  if isinstance(rows,list):
   for r in rows:
    im=r.get('image') or {};name=im.get('name')
    if isinstance(name,str):
     sp=im.get('streamedPart0') or {};add_meta(candidates,name,{'sourceManifest':str(path),'nameHash':im.get('nameHash',im.get('nameHashHex')),'dataHash':sp.get('dataHash',sp.get('dataHashHex')),'width':im.get('width'),'height':im.get('height'),'depth':im.get('depth'),'uses':r.get('uses') or []})
 out={}
 for name,rows in candidates.items():
  merged={'sourceManifests':sorted({r['sourceManifest'] for r in rows}),'uses':[]}
  for field in ('nameHash','dataHash','width','height','depth'):
   vals=[]
   for r in rows:
    v=r.get(field)
    if v is None:continue
    if field in ('nameHash','dataHash'):v=parse_u32(v)&(0x1fffffff if field=='dataHash' else 0xffffffff)
    else:v=int(v)
    vals.append(v)
   if vals and len(set(vals))!=1:raise TextureError(f'{name}: conflicting metadata {field}: {sorted(set(vals))}')
   if vals:merged[field]=vals[0]
  for r in rows:merged['uses'].extend(x for x in r.get('uses',[]) if x not in merged['uses'])
  out[name]=merged
 return out

def parse_ipak(path:Path)->dict:
 size=path.stat().st_size
 with path.open('rb') as f:
  head=f.read(16)
  if len(head)!=16:raise TextureError('IPAK header truncated')
  magic,ver,declared,nsec=struct.unpack('<4sIII',head)
  if magic!=IPAK_MAGIC or ver!=IPAK_VERSION:raise TextureError(f'invalid T6 IPAK header {magic!r} v=0x{ver:x}')
  if declared!=size:raise TextureError(f'IPAK declared size {declared} != actual {size}')
  sections=[]
  for i in range(nsec):
   raw=f.read(16)
   if len(raw)!=16:raise TextureError('IPAK section table truncated')
   typ,off,span,count=struct.unpack('<IIII',raw)
   if off+span>size:raise TextureError(f'IPAK section {i} outside file')
   sections.append({'type':typ,'offset':off,'size':span,'itemCount':count})
  data=next((s for s in sections if s['type']==2),None);idx=next((s for s in sections if s['type']==1),None)
  if data is None or idx is None:raise TextureError('IPAK missing data/index section')
  need=idx['itemCount']*ENTRY.size
  if need>idx['size']:raise TextureError('IPAK index itemCount exceeds index bytes')
  f.seek(idx['offset']);raw=f.read(need)
  if len(raw)!=need:raise TextureError('IPAK index truncated')
 rows=[];by={}
 for i in range(idx['itemCount']):
  dhraw,nh,rel,span=ENTRY.unpack_from(raw,i*ENTRY.size);dh=dhraw&0x1fffffff
  if rel+span>data['size']:raise TextureError(f'IPAK index row {i} outside data section')
  row={'index':i,'dataHashRaw':dhraw,'dataHash':dh,'nameHash':nh,'relativeOffset':rel,'entrySpan':span,'absoluteOffset':data['offset']+rel};rows.append(row);by.setdefault((nh,dh),[]).append(row)
 return {'version':ver,'declaredSize':declared,'sections':sections,'dataSection':data,'indexSection':idx,'rows':rows,'byExact':by}

def load_lzo():
 libname=ctypes.util.find_library('lzo2')
 if not libname:raise TextureError('liblzo2 not found')
 fn=ctypes.CDLL(libname).lzo1x_decompress_safe;fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p];fn.restype=ctypes.c_int;return fn

def extract_entry(path:Path,data_sec:dict,row:dict,lzo)->bytes:
 pos=row['absoluteOffset'];end=pos+row['entrySpan'];out=bytearray();blocks=0
 with path.open('rb') as f:
  while pos<end:
   pos=align(pos,IPAK_BLOCK)
   if pos>=end:break
   if pos+128>end:raise TextureError('IPAK entry has truncated block header')
   f.seek(pos);hdr=f.read(128)
   if len(hdr)!=128:raise TextureError('IPAK block header short read')
   co=struct.unpack_from('<I',hdr,0)[0];file_off=co&0xffffff;cnt=(co>>24)&0xff
   if cnt>31:raise TextureError(f'IPAK block command count {cnt} > 31')
   cmds=[]
   for i in range(cnt):
    w=struct.unpack_from('<I',hdr,4+4*i)[0];cmds.append((w&0xffffff,(w>>24)&0xff))
   if any(comp in (0,1) for _,comp in cmds) and file_off!=len(out):raise TextureError(f'IPAK block output offset {file_off} != {len(out)}')
   p=pos+128
   for span,comp in cmds:
    if p+span>end:raise TextureError('IPAK command crosses indexed entry span')
    f.seek(p);blob=f.read(span)
    if len(blob)!=span:raise TextureError('IPAK command short read')
    if comp==0:out.extend(blob)
    elif comp==1:
     dst=ctypes.create_string_buffer(0x8000);n=ctypes.c_size_t(0x8000);src=ctypes.create_string_buffer(blob);rc=lzo(src,len(blob),dst,ctypes.byref(n),None)
     if rc!=0:raise TextureError(f'LZO decompression error {rc}')
     out.extend(dst.raw[:n.value])
    else:raise TextureError(f'unsupported IPAK compression command {comp}')
    p+=span
   pos=p;blocks+=1
   if blocks>10000:raise TextureError('IPAK block runaway')
 payload=bytes(out);crc=zlib.crc32(payload)&0x1fffffff
 if crc!=row['dataHash']:raise TextureError(f"IPAK CRC29 {crc:08x} != index dataHash {row['dataHash']:08x}")
 return payload

def parse_iwi27(b:bytes)->dict:
 if len(b)<64 or b[:3]!=b'IWi' or b[3]!=IWI27:raise TextureError('payload is not IWI v27')
 fmt=b[4];flags=b[5];w,h,d=struct.unpack_from('<3H',b,6);gamma=struct.unpack_from('<f',b,12)[0];sizes=struct.unpack_from('<8I',b,32)
 if sizes[0]!=len(b):raise TextureError(f'IWI size table {sizes[0]} != payload bytes {len(b)}')
 if not w or not h or not d:raise TextureError(f'IWI invalid dimensions {w}x{h}x{d}')
 return {'format':fmt,'flags':flags,'width':w,'height':h,'depth':d,'gamma':gamma,'sizes':list(sizes)}
def rgb565(c:int):return (((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31)
def decode_bc1(src,w,h):
 out=bytearray(w*h*4);p=0
 for by in range((h+3)//4):
  for bx in range((w+3)//4):
   if p+8>len(src):raise TextureError('BC1 top mip truncated')
   c0,c1,bits=struct.unpack_from('<HHI',src,p);p+=8;r0,g0,b0=rgb565(c0);r1,g1,b1=rgb565(c1);cols=[(r0,g0,b0,255),(r1,g1,b1,255)]
   cols += [((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3,255),((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3,255)] if c0>c1 else [((r0+r1)//2,(g0+g1)//2,(b0+b1)//2,255),(0,0,0,0)]
   for py in range(4):
    for px in range(4):
     x=bx*4+px;y=by*4+py
     if x<w and y<h:q=(bits>>(2*(py*4+px)))&3;o=(y*w+x)*4;out[o:o+4]=bytes(cols[q])
 return bytes(out)
def decode_bc3(src,w,h):
 out=bytearray(w*h*4);p=0
 for by in range((h+3)//4):
  for bx in range((w+3)//4):
   if p+16>len(src):raise TextureError('BC3 top mip truncated')
   a0,a1=src[p],src[p+1];abits=int.from_bytes(src[p+2:p+8],'little');al=[a0,a1]+([((6-i)*a0+(i+1)*a1)//7 for i in range(6)] if a0>a1 else [((4-i)*a0+(i+1)*a1)//5 for i in range(4)]+[0,255]);c0,c1,cbits=struct.unpack_from('<HHI',src,p+8);p+=16;r0,g0,b0=rgb565(c0);r1,g1,b1=rgb565(c1);cols=[(r0,g0,b0),(r1,g1,b1),((2*r0+r1)//3,(2*g0+g1)//3,(2*b0+b1)//3),((r0+2*r1)//3,(g0+2*g1)//3,(b0+2*b1)//3)]
   for py in range(4):
    for px in range(4):
     x=bx*4+px;y=by*4+py
     if x<w and y<h:i=py*4+px;ci=(cbits>>(2*i))&3;ai=(abits>>(3*i))&7;o=(y*w+x)*4;out[o:o+4]=bytes((*cols[ci],al[ai]))
 return bytes(out)
def decode_bc4_block(block):
 if len(block)!=8:raise TextureError('BC4 block truncated')
 a0,a1=block[0],block[1];bits=int.from_bytes(block[2:8],'little');vals=[a0,a1]+([((6-i)*a0+(i+1)*a1)//7 for i in range(6)] if a0>a1 else [((4-i)*a0+(i+1)*a1)//5 for i in range(4)]+[0,255]);return [vals[(bits>>(3*i))&7] for i in range(16)]
def decode_bc5_normal(src,w,h):
 import math
 out=bytearray(w*h*4);p=0
 for by in range((h+3)//4):
  for bx in range((w+3)//4):
   if p+16>len(src):raise TextureError('BC5 top mip truncated')
   xs=decode_bc4_block(src[p:p+8]);ys=decode_bc4_block(src[p+8:p+16]);p+=16
   for py in range(4):
    for px in range(4):
     x=bx*4+px;y=by*4+py
     if x<w and y<h:i=py*4+px;xn=xs[i]/127.5-1.0;yn=ys[i]/127.5-1.0;zn=math.sqrt(max(0.0,1.0-xn*xn-yn*yn));z=int(round((zn*0.5+0.5)*255));o=(y*w+x)*4;out[o:o+4]=bytes((xs[i],ys[i],max(0,min(255,z)),255))
 return bytes(out)
def top_png(iwi,is_normal):
 m=parse_iwi27(iwi);fmt=m['format'];w=m['width'];h=m['height'];block=8 if fmt==IWI_DXT1 else 16 if fmt in (IWI_DXT5,IWI_DXN) else None
 if block is None:raise TextureError(f'unsupported IWI format 0x{fmt:02x}')
 top=((w+3)//4)*((h+3)//4)*block;start=len(iwi)-top
 if start<64:raise TextureError(f'IWI top mip starts before header: {start}')
 src=iwi[start:]
 if fmt==IWI_DXT1:rgba=decode_bc1(src,w,h)
 elif fmt==IWI_DXT5:rgba=decode_bc3(src,w,h)
 elif fmt==IWI_DXN and is_normal:rgba=decode_bc5_normal(src,w,h)
 else:raise TextureError('DXN/BC5 image is not proven normal semantic')
 def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
 scan=bytearray();stride=w*4
 for y in range(h):scan.append(0);scan.extend(rgba[y*stride:(y+1)*stride])
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(scan),9))+chunk(b'IEND',b'')
 return png,{**m,'topMipOffset':start,'topMipBytes':top,'normalSemantic':bool(is_normal)}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--ipak',type=Path,required=True);ap.add_argument('--targets',type=Path,required=True);ap.add_argument('--metadata',type=Path,action='append',default=[]);ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--expect-ipak-sha256');a=ap.parse_args()
 if not a.ipak.is_file():raise SystemExit(f'IPAK not found: {a.ipak}')
 actual_sha=sha256_file(a.ipak) if a.expect_ipak_sha256 else None
 if a.expect_ipak_sha256 and actual_sha.lower()!=a.expect_ipak_sha256.lower():raise SystemExit(f'IPAK SHA-256 mismatch: {actual_sha}')
 targets=load_targets(a.targets);metadata=load_metadata(a.metadata);ipak=parse_ipak(a.ipak);lzo=load_lzo();a.outdir.mkdir(parents=True,exist_ok=True);rows=[];unresolved=[]
 for t in targets:
  key=(t['nameHash'],t['dataHash']);matches=ipak['byExact'].get(key,[])
  if len(matches)!=1:unresolved.append({**t,'reason':'exact-key-not-found' if not matches else 'ambiguous-exact-key','matchCount':len(matches)});continue
  meta=metadata.get(t['image'],{})
  if 'nameHash' in meta and meta['nameHash']!=t['nameHash']:raise TextureError(f"{t['image']}: metadata nameHash mismatch")
  if 'dataHash' in meta and meta['dataHash']!=t['dataHash']:raise TextureError(f"{t['image']}: metadata dataHash mismatch")
  try:
   payload=extract_entry(a.ipak,ipak['dataSection'],matches[0],lzo);iwi_meta=parse_iwi27(payload)
   for field in ('width','height','depth'):
    if field in meta and meta[field] not in (None,0) and int(meta[field])!=int(iwi_meta[field]):raise TextureError(f"{t['image']}: retained {field} {meta[field]} != IWI {iwi_meta[field]}")
   uses=meta.get('uses') or t['target'].get('uses') or [];normal=any((isinstance(x,str) and ('normalMap' in x or x.endswith(':normal'))) or (isinstance(x,dict) and (x.get('semanticName')=='normalMap' or x.get('semanticRaw')==5)) for x in uses);png,png_meta=top_png(payload,normal)
  except Exception as exc:unresolved.append({**t,'reason':'payload-validation-failed','error':str(exc)});continue
  stem=f"{safe_name(t['image'])}__nh_{t['nameHash']:08x}__dh_{t['dataHash']:08x}";iwi_name=stem+'.iwi';png_name=stem+'.png';(a.outdir/iwi_name).write_bytes(payload);(a.outdir/png_name).write_bytes(png);rows.append({**t,'index':matches[0]['index'],'entrySpan':matches[0]['entrySpan'],'iwiFile':iwi_name,'pngFile':png_name,'iwiSha256':sha256_bytes(payload),'pngSha256':sha256_bytes(png),'retainedMetadata':meta,'iwi':png_meta,'crc29Validated':True,'exactKeyValidated':True})
 doc={'format':'t6-ipak-iwi-materialization-v1','authority':'exact retail stream keys + T6 IPAK raw/LZO reconstruction + CRC29 + IWI27 + retained dimension validation','sourceIpak':{'path':str(a.ipak),'bytes':a.ipak.stat().st_size,'sha256':actual_sha,'versionHex':f"0x{ipak['version']:x}"},'targetManifest':{'path':str(a.targets),'sha256':sha256_file(a.targets)},'metadataManifests':[{'path':str(p),'sha256':sha256_file(p)} for p in a.metadata],'summary':{'requested':len(targets),'materialized':len(rows),'unresolved':len(unresolved),'iwiFiles':len(rows),'pngFiles':len(rows)},'textures':rows,'unresolved':unresolved,'proofBoundary':'IWI is the authoritative reconstructed retail payload. PNG is a top-mip derivative. No filename fallback, dataHash-only fallback, or unsupported-format substitution is permitted.'};(a.outdir/'manifest.json').write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(doc['summary'],indent=2,sort_keys=True));return 2 if unresolved else 0
if __name__=='__main__':raise SystemExit(main())
