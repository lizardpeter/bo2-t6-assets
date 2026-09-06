#!/usr/bin/env python3
"""Prove XAsset IMAGE index -> serialized GfxImage name by exact contiguous runs.

A run is accepted only when:
- every declared XAsset index is consecutive and ASSET_TYPE_IMAGE;
- every supplied raw GfxImage record walks exactly to the next record;
- the last GfxImage walks exactly to the next declared top-level asset start;
- that anchor asset index/type/name validates at its fixed-record start.
This turns XAsset.header alias indices into exact retail GfxImage identities without
name proximity or semantic guessing.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from t6_xasset_header_alias_resolver_v1 import parse_front,TYPE_NAMES,FOLLOWING,INSERT

IMAGE_FIXED=80;TECHSET_FIXED=152;MATERIAL_FIXED=112

def rhash(s:str)->int:
 h=5381
 for c in s.encode('latin1'):h=(((h<<5)+h)^(c|0x20))&0xffffffff
 return h
def cstr(data:bytes,pos:int):
 e=data.find(b'\0',pos)
 if e<0:raise ValueError(f'unterminated string at {pos}')
 return data[pos:e].decode('latin1'),e+1
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def walk_image(data:bytes,start:int)->dict:
 if start+IMAGE_FIXED>len(data):raise ValueError('image fixed outside stream')
 load=struct.unpack_from('<I',data,start)[0];nameptr=struct.unpack_from('<I',data,start+72)[0]
 if nameptr not in (FOLLOWING,INSERT):raise ValueError(f'image name not inline at {start}')
 name,q=cstr(data,start+80)
 if load in (FOLLOWING,INSERT):
  if q+12>len(data):raise ValueError('truncated GfxImageLoadDef')
  resource=struct.unpack_from('<i',data,q+8)[0]
  if resource<0 or q+12+resource>len(data):raise ValueError('bad GfxImageLoadDef resourceSize')
  q+=12+resource
 level_word,raw_hash=struct.unpack_from('<II',data,start+36);size_word=struct.unpack_from('<I',data,start+52)[0]
 return {'rawStart':start,'rawEnd':q,'serializedBytes':q-start,'serializedSha256':sha(data[start:q]),'name':name,'nameHash':rhash(name),'nameHashHex':f'0x{rhash(name):08x}','width':struct.unpack_from('<H',data,start+20)[0],'height':struct.unpack_from('<H',data,start+22)[0],'streaming':data[start+27],'streamedPartCount':data[start+60],'dataHash':raw_hash&0x1fffffff,'dataHashHex':f'0x{raw_hash&0x1fffffff:08x}','ipakIndex':(size_word>>28)&0xf,'loadDefPointerRaw':f'0x{load:08x}','fixedSha256':sha(data[start:start+80])}
def validate_anchor(data:bytes,start:int,kind:str,expected_name:str|None):
 if kind=='TECHNIQUE_SET':fixed=TECHSET_FIXED
 elif kind=='MATERIAL':fixed=MATERIAL_FIXED
 else:raise ValueError(f'unsupported anchor kind {kind}')
 if start+fixed>len(data):raise ValueError('anchor outside stream')
 np=struct.unpack_from('<I',data,start)[0]
 if np not in (FOLLOWING,INSERT):raise ValueError('anchor name not inline')
 name,_=cstr(data,start+fixed)
 if expected_name is not None and name!=expected_name:raise ValueError(f'anchor name {name!r} != {expected_name!r}')
 return {'kind':kind,'rawStart':start,'fixedBytes':fixed,'fixedSha256':sha(data[start:start+fixed]),'name':name}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--expanded',type=Path,required=True);ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 data=a.expanded.read_bytes();front=parse_front(data);spec=json.loads(a.spec.read_text(encoding='utf-8-sig'));groups=[];promoted=[]
 for g in spec['groups']:
  inds=[int(x) for x in g['assetIndices']];starts=[int(x) for x in g['rawImageStarts']]
  if len(inds)!=len(starts) or not inds:raise ValueError('group index/start length mismatch')
  if inds!=list(range(inds[0],inds[0]+len(inds))):raise ValueError('image indices not consecutive')
  assets=[front['assets'][i] for i in inds]
  if any(x['typeIndex']!=8 for x in assets):raise ValueError('group contains non-IMAGE XAsset')
  images=[walk_image(data,s) for s in starts]
  for x,y in zip(images,images[1:]):
   if x['rawEnd']!=y['rawStart']:raise ValueError(f"image gap {x['name']} end {x['rawEnd']} != {y['rawStart']}")
  anchor=g['anchor'];ai=int(anchor['assetIndex']);astart=int(anchor['rawStart']);ak=anchor['type'];expected_type={'TECHNIQUE_SET':7,'MATERIAL':6}[ak]
  if ai!=inds[-1]+1:raise ValueError('anchor is not immediately after image run in XAsset list')
  if front['assets'][ai]['typeIndex']!=expected_type:raise ValueError('anchor XAsset type mismatch')
  if images[-1]['rawEnd']!=astart:raise ValueError(f"image run end {images[-1]['rawEnd']} != anchor start {astart}")
  av=validate_anchor(data,astart,ak,anchor.get('name'))
  rows=[]
  for idx,im in zip(inds,images):
   row={'assetIndex':idx,'xassetHeaderRaw':front['assets'][idx]['headerRawHex'],**im};rows.append(row)
   if idx in set(g.get('promoteAssetIndices',inds)):
    if not im['streaming'] or im['streamedPartCount']!=1 or not im['width'] or not im['height'] or not im['dataHash']:raise ValueError(f"promoted image {im['name']} lacks exact stream key")
    promoted.append(row)
  groups.append({'name':g.get('name'),'assetIndices':inds,'images':rows,'anchor':{'assetIndex':ai,'xassetTypeIndex':expected_type,'xassetType':TYPE_NAMES[expected_type],**av},'exactContiguousSourceRun':True})
 out={'format':'t6-xasset-image-run-proof-v1','authority':'expanded retail T6 source order + exact XAsset type/order + exact serialized GfxImage boundaries','source':{'path':str(a.expanded),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()},'summary':{'groups':len(groups),'imageAssetsProven':sum(len(g['images']) for g in groups),'promotedExactStreamKeys':len(promoted)},'groups':groups,'promotedExactStreamKeys':promoted,'proofBoundary':'Only declared contiguous IMAGE runs whose final byte equals the immediately following validated top-level asset start are promoted.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(out['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
