#!/usr/bin/env python3
"""Build exact T6 character Material -> GfxImage -> IPAK key evidence.

Authority: expanded retail T6 PC XFile serialization. Packed asset references are
never converted into names by proximity or filename guessing.

GfxStreamedPartInfo (PC32) is decoded exactly, including the 4-bit ipakIndex.
Repository name hints are attached only for mappings already independently proven
by prior retail extraction. At present, ipakIndex 0 -> base.ipak is proven.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE
MATERIAL_FIXED=112
TEXTURE_DEF=16
GFXIMAGE_FIXED=80
SEMANTIC={0:'2D',1:'function',2:'colorMap',3:'unused1',4:'unused2',5:'normalMap',6:'unused3',7:'unused4',8:'specularMap',9:'unused5',10:'occlusionMap',11:'unused6',12:'color0Map',13:'color1Map'}
PROVEN_IPAK_REPOSITORIES={0:'base.ipak'}


def sha256_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1<<20),b''):h.update(c)
 return h.hexdigest()
def cstr(data:bytes,pos:int)->tuple[str,int]:
 e=data.find(b'\0',pos)
 if e<0:raise ValueError(f'unterminated string {pos}')
 return data[pos:e].decode('latin1'),e+1
def r_hash_string(s:str)->int:
 h=5381
 for c in s.encode('latin1'):
  h=(((h<<5)+h) ^ (c|0x20)) & 0xffffffff
 return h


def parse_streamed_part(data:bytes,start:int)->dict:
 if start < 0 or start + 24 > len(data): raise ValueError('streamed part outside stream')
 level_word, raw_hash = struct.unpack_from('<II',data,start)
 width,height=struct.unpack_from('<HH',data,start+8)
 offset=struct.unpack_from('<I',data,start+12)[0]
 size_word=struct.unpack_from('<I',data,start+16)[0]
 adjacency_word=struct.unpack_from('<I',data,start+20)[0]
 index=(size_word >> 28) & 0xF
 return {
  'rawOffset':start,'rawHex':data[start:start+24].hex(),
  'levelCount':level_word & 0xF,'levelSize':level_word >> 4,
  'rawHashU32':raw_hash,'dataHash':raw_hash & 0x1FFFFFFF,
  'dataHashHex':f'0x{raw_hash & 0x1FFFFFFF:08x}',
  'streamedWidth':width,'streamedHeight':height,'offset':offset,
  'size':size_word & 0x0FFFFFFF,'ipakIndex':index,
  'repositoryHint':PROVEN_IPAK_REPOSITORIES.get(index),
  'repositoryHintEvidence':('independently retail-proven ipakIndex mapping; exact prior nameHash+dataHash recovery' if index in PROVEN_IPAK_REPOSITORIES else None),
  'adjacentLeft':adjacency_word & 0x7FFF,
  'adjacentRight':(adjacency_word >> 15) & 0x7FFF,
  'compressed':bool((adjacency_word >> 30) & 1),
  'valid':bool((adjacency_word >> 31) & 1),
  'rawLevelWord':level_word,'rawSizeWord':size_word,'rawAdjacencyWord':adjacency_word,
 }


def parse_image(data:bytes,start:int)->dict:
 if start<0 or start+GFXIMAGE_FIXED>len(data):raise ValueError('image fixed outside stream')
 nameptr=struct.unpack_from('<I',data,start+72)[0]
 if nameptr not in (FOLLOWING,INSERT):raise ValueError(f'image at {start} has non-inline name ptr {nameptr:#x}')
 name,end=cstr(data,start+80); sp=parse_streamed_part(data,start+36); nh=r_hash_string(name)
 return {
  'structOffset':start,'fixedSha256':sha256_bytes(data[start:start+80]),'nameOffset':start+80,
  'name':name,'nameHash':nh,'nameHashHex':f'0x{nh:08x}',
  'mapType':data[start+4],'semantic':data[start+5],'category':data[start+6],'delayLoadPixels':bool(data[start+7]),
  'width':struct.unpack_from('<H',data,start+20)[0],'height':struct.unpack_from('<H',data,start+22)[0],
  'depth':struct.unpack_from('<H',data,start+24)[0],'levelCount':data[start+26],'streaming':data[start+27],
  'baseSize':struct.unpack_from('<I',data,start+28)[0],'streamedPartCount':data[start+60],
  'streamedPart0':sp,'loadedSize':struct.unpack_from('<I',data,start+64)[0],'skippedMipLevels':data[start+68],
  'runtimeHashRaw':struct.unpack_from('<I',data,start+76)[0],
  'runtimeHashRawHex':f'0x{struct.unpack_from("<I",data,start+76)[0]:08x}',
 }


def parse_material(data:bytes,start:int,expected_name:str)->dict:
 if start<0 or start+MATERIAL_FIXED>len(data):raise ValueError('material fixed outside stream')
 nameptr=struct.unpack_from('<I',data,start)[0]
 if nameptr not in (FOLLOWING,INSERT):raise ValueError(f'{expected_name}: material name not inline')
 name,q=cstr(data,start+MATERIAL_FIXED)
 if name != expected_name:raise ValueError(f'material identity mismatch {name!r} != {expected_name!r}')
 tc=data[start+84]; tp=struct.unpack_from('<I',data,start+96)[0]
 if tc and tp not in (FOLLOWING,INSERT): return {'name':name,'start':start,'textureCount':tc,'textureTableStatus':'packed','slots':[]}
 if not tc:return {'name':name,'start':start,'textureCount':0,'textureTableStatus':'empty','slots':[]}
 table=q
 if table+tc*TEXTURE_DEF>len(data):raise ValueError(f'{name}: texture table outside stream')
 slots=[]; q=table+tc*TEXTURE_DEF
 for i in range(tc):
  o=table+i*TEXTURE_DEF; namehash=struct.unpack_from('<I',data,o)[0]; ns,ne,sampler,semantic=data[o+4:o+8]; imageptr=struct.unpack_from('<I',data,o+12)[0]
  slot={'index':i,'rawOffset':o,'rawHex':data[o:o+TEXTURE_DEF].hex(),'slotNameHash':namehash,'slotNameHashHex':f'0x{namehash:08x}',
   'nameStart':chr(ns) if 32<=ns<127 else f'\\x{ns:02x}','nameEnd':chr(ne) if 32<=ne<127 else f'\\x{ne:02x}',
   'samplerStateRaw':sampler,'semanticRaw':semantic,'semanticName':SEMANTIC.get(semantic,f'unknown-{semantic}'),'imagePointerRaw':f'0x{imageptr:08x}'}
  if imageptr in (FOLLOWING,INSERT):
   im=parse_image(data,q);slot['imageStatus']='inline-definition';slot['image']=im
   q=im['nameOffset']+len(im['name'].encode('latin1'))+1; loadptr=struct.unpack_from('<I',data,im['structOffset'])[0]
   if loadptr in (FOLLOWING,INSERT):
    if q+12>len(data):raise ValueError('truncated loadDef')
    resource=struct.unpack_from('<i',data,q+8)[0]
    if resource<0 or q+12+resource>len(data):raise ValueError('bad loadDef resource')
    q += 12+resource
  elif imageptr==0: slot['imageStatus']='null'
  else:
   enc=(imageptr-1)&0xffffffff; slot['imageStatus']='packed-reference'; slot['imagePointer']={'block':enc>>29,'offset':enc&0x1fffffff}
  slots.append(slot)
 return {'name':name,'start':start,'textureCount':tc,'textureTableStatus':'inline','textureTableRawOffset':table,'slots':slots}


def load_catalog(path:Path)->list[dict]:
 x=json.loads(path.read_text(encoding='utf-8-sig'))
 if isinstance(x,list):return x
 out=[]
 if isinstance(x,dict):
  for rows in x.values():
   if isinstance(rows,list):out.extend(r for r in rows if isinstance(r,dict))
 return out


def main():
 a=argparse.ArgumentParser(); a.add_argument('--source',action='append',nargs=3,metavar=('ZONE','EXPANDED','CATALOG'),required=True); a.add_argument('--material',action='append',required=True); a.add_argument('--out',type=Path,required=True)
 q=a.parse_args(); wanted=set(q.material); materials=[]; sources=[]
 for zone,ep,cp in q.source:
  e=Path(ep);c=Path(cp);data=e.read_bytes();cat=load_catalog(c)
  sources.append({'zone':zone,'expanded':str(e),'expandedBytes':len(data),'expandedSha256':sha256_file(e),'catalog':str(c),'catalogSha256':sha256_file(c)})
  by={r.get('name'):r for r in cat if isinstance(r.get('name'),str)}
  for name in sorted(wanted & set(by)):
   row=by[name]
   if row.get('kind')=='import-stub' or row.get('status')=='not-full-material':continue
   start=row.get('start')
   if isinstance(start,int): m=parse_material(data,start,name);m['sourceZone']=zone;materials.append(m)
 found={m['name'] for m in materials}; missing=sorted(wanted-found); images={}; packed=[]
 for m in materials:
  for s in m['slots']:
   rec={'material':m['name'],'sourceZone':m['sourceZone'],'slotIndex':s['index'],'semanticRaw':s['semanticRaw'],'semanticName':s['semanticName'],'samplerStateRaw':s['samplerStateRaw']}
   if s['imageStatus']=='inline-definition':
    im=s['image'];key=(m['sourceZone'],im['name'],im['structOffset']);images.setdefault(key,{**im,'sourceZone':m['sourceZone'],'uses':[]})['uses'].append(rec)
   elif s['imageStatus']=='packed-reference': packed.append({**rec,'imagePointerRaw':s['imagePointerRaw'],'imagePointer':s['imagePointer']})
 direct=list(images.values()); exact=[im for im in direct if im['streaming'] and im['streamedPartCount']==1 and im['width'] and im['height'] and im['streamedPart0']['dataHash']]; stubs=[im for im in direct if not im['width'] and not im['height'] and not im['streaming']]
 repo_counts={}
 for im in exact:
  repo=im['streamedPart0'].get('repositoryHint') or f"unmapped-ipak-index-{im['streamedPart0']['ipakIndex']}";repo_counts[repo]=repo_counts.get(repo,0)+1
 doc={'format':'t6-character-texture-key-manifest-v2','authority':'expanded retail T6 material and GfxImage serialization; no filename substitution','sources':sources,
  'ipakRepositoryMapping':{'proven':{str(k):v for k,v in PROVEN_IPAK_REPOSITORIES.items()},'policy':'Repository names are emitted only for independently retail-proven ipakIndex mappings.'},
  'summary':{'requestedMaterials':len(wanted),'resolvedFullMaterials':len(found),'missingFullMaterials':len(missing),'textureSlots':sum(m['textureCount'] for m in materials),'directInlineImages':len(direct),'exactStreamKeys':len(exact),'inlineImageStubs':len(stubs),'packedImageReferences':len(packed),'exactStreamKeysByRepository':repo_counts},
  'missingMaterials':missing,'materials':materials,'exactStreamKeyImages':exact,'inlineImageStubs':stubs,'packedImageReferences':packed,
  'proofBoundary':'Exact stream keys require an inline retail GfxImage with streaming enabled, one streamed part, nonzero retained dimensions, and nonzero 29-bit streamed-part dataHash. Packed references and zero-metadata image imports remain unresolved.'}
 q.out.parent.mkdir(parents=True,exist_ok=True);q.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
