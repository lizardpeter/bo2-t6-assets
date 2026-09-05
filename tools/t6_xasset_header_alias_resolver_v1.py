#!/usr/bin/env python3
"""Resolve T6 PC32 packed asset pointers that target XAsset.header slots.

The T6 zone loader allocates, in XFILE_BLOCK_VIRTUAL, the ScriptString pointer
array and its FOLLOWING strings, the dependency pointer array and its FOLLOWING
strings, then the 8-byte XAsset array. On cross-word-size loads, AddPointerLookup
registers the serialized address of every XAsset.header pointer field. Therefore a
packed zone pointer that lands exactly at assetArrayVirtualBase + 8*i + 4 is a
direct reference to XAsset i's header slot.

This tool proves only that relationship. Pointers elsewhere in the VIRTUAL block
are classified as later-virtual-alias and are not guessed.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE
XASSET_SIZE=8
HEADER_OFFSET=4
TYPE_NAMES={
0:'XMODELPIECES',1:'PHYSPRESET',2:'PHYSCONSTRAINTS',3:'DESTRUCTIBLEDEF',4:'XANIMPARTS',5:'XMODEL',6:'MATERIAL',7:'TECHNIQUE_SET',8:'IMAGE',9:'SOUND',10:'SOUND_PATCH',11:'CLIPMAP',12:'CLIPMAP_PVS',13:'COMWORLD',14:'GAMEWORLD_SP',15:'GAMEWORLD_MP',16:'MAP_ENTS',17:'GFXWORLD',18:'LIGHT_DEF',19:'UI_MAP',20:'FONT',21:'FONTICON',22:'MENULIST',23:'MENU',24:'LOCALIZE_ENTRY',25:'WEAPON',26:'WEAPONDEF',27:'WEAPON_VARIANT',28:'WEAPON_FULL',29:'ATTACHMENT',30:'ATTACHMENT_UNIQUE',31:'WEAPON_CAMO',32:'SNDDRIVER_GLOBALS',33:'FX',34:'IMPACT_FX',35:'AITYPE',36:'MPTYPE',37:'MPBODY',38:'MPHEAD',39:'CHARACTER',40:'XMODELALIAS',41:'RAWFILE',42:'STRINGTABLE',43:'LEADERBOARD',44:'XGLOBALS',45:'DDL',46:'GLASSES',47:'EMBLEMSET',48:'SCRIPTPARSETREE',49:'KEYVALUEPAIRS',50:'VEHICLEDEF',51:'MEMORYBLOCK',52:'ADDON_MAP_ENTS',53:'TRACER',54:'SKINNEDVERTS',55:'QDB',56:'SLUG',57:'FOOTSTEP_TABLE',58:'FOOTSTEPFX_TABLE',59:'ZBARRIER'}

def align(x,a):return (x+a-1)&~(a-1)
def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def cstring_len(data:bytes,pos:int)->int:
 e=data.find(b'\0',pos)
 if e<0:raise ValueError(f'unterminated FOLLOWING string at raw offset {pos}')
 return e-pos+1

def decode_zone_pointer(value:int)->dict:
 value&=0xffffffff
 if value==0:return {'raw':value,'rawHex':'0x00000000','kind':'null'}
 if value==FOLLOWING:return {'raw':value,'rawHex':'0xffffffff','kind':'following'}
 if value==INSERT:return {'raw':value,'rawHex':'0xfffffffe','kind':'insert'}
 enc=(value-1)&0xffffffff
 return {'raw':value,'rawHex':f'0x{value:08x}','kind':'packed','block':enc>>29,'offset':enc&0x1fffffff}

def parse_front(data:bytes)->dict:
 if len(data)<64:raise ValueError('expanded stream too small')
 sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',data,40)
 if sc>1_000_000 or dc>1_000_000 or ac>5_000_000:raise ValueError('implausible XAssetList counts')
 src=64;virt=0
 if sc and sp!=FOLLOWING:raise ValueError(f'ScriptString pointer array not FOLLOWING: 0x{sp:08x}')
 if src+sc*4>len(data):raise ValueError('ScriptString pointer array truncated')
 ptrs=struct.unpack_from(f'<{sc}I',data,src) if sc else ()
 src+=sc*4;virt+=sc*4
 for p in ptrs:
  if p==FOLLOWING:
   n=cstring_len(data,src);src+=n;virt+=n
  elif p not in (0,):
   pass
 virt=align(virt,4)
 dep_base=virt
 if dc:
  if dp!=FOLLOWING:raise ValueError(f'dependency pointer array not FOLLOWING: 0x{dp:08x}')
  if src+dc*4>len(data):raise ValueError('dependency pointer array truncated')
  dep_ptrs=struct.unpack_from(f'<{dc}I',data,src);src+=dc*4;virt+=dc*4
  for p in dep_ptrs:
   if p==FOLLOWING:
    n=cstring_len(data,src);src+=n;virt+=n
 elif dp not in (0,FOLLOWING):raise ValueError(f'depCount=0 but dep pointer 0x{dp:08x}')
 virt=align(virt,4)
 asset_base=virt
 if ac:
  if ap!=FOLLOWING:raise ValueError(f'XAsset array not FOLLOWING: 0x{ap:08x}')
  if src+ac*XASSET_SIZE>len(data):raise ValueError('XAsset array truncated')
 assets=[]
 for i in range(ac):
  typ,h=struct.unpack_from('<iI',data,src+i*8)
  assets.append({'index':i,'typeIndex':typ,'type':TYPE_NAMES.get(typ,f'UNKNOWN_{typ}'),'headerRaw':h,'headerRawHex':f'0x{h:08x}'})
 raw_asset=src;src+=ac*8;virt+=ac*8
 return {'scriptStringCount':sc,'dependencyCount':dc,'assetCount':ac,'dependencyArrayVirtualBase':dep_base,'assetArrayVirtualBase':asset_base,'assetArrayRawOffset':raw_asset,'assetBodyRawOffset':src,'virtualOffsetAfterAssetArray':virt,'assets':assets}

def classify(ptr:int,front:dict,expected_type:int|None=None)->dict:
 dec=decode_zone_pointer(ptr)
 out={'pointer':dec,'classification':dec['kind']}
 if dec['kind']!='packed':return out
 if dec['block']!=5:
  out['classification']='packed-non-virtual-block';return out
 off=dec['offset'];base=front['assetArrayVirtualBase'];delta=off-(base+HEADER_OFFSET)
 if delta>=0 and delta%XASSET_SIZE==0:
  idx=delta//XASSET_SIZE
  if 0<=idx<front['assetCount']:
   a=front['assets'][idx]
   out.update({'classification':'xasset-header-slot','assetIndex':idx,'asset':a,'headerSlotVirtualOffset':base+idx*8+4,'exactHeaderSlotMatch':True})
   if expected_type is not None:
    out['expectedTypeIndex']=expected_type;out['expectedType']=TYPE_NAMES.get(expected_type,str(expected_type));out['expectedTypeMatches']=a['typeIndex']==expected_type
   return out
 if off<front['virtualOffsetAfterAssetArray']:
  out['classification']='virtual-front-non-header-slot'
 else:
  out['classification']='later-virtual-alias'
 return out

def iter_manifest_refs(doc):
 rows=doc.get('packedImageReferences') if isinstance(doc,dict) else None
 if not isinstance(rows,list):raise ValueError('manifest has no packedImageReferences list')
 for r in rows:
  raw=r.get('imagePointerRaw')
  if isinstance(raw,str): ptr=int(raw,0)
  elif isinstance(raw,int):ptr=raw
  else:
   p=r.get('imagePointer') or {}; b=p.get('block');o=p.get('offset')
   if not isinstance(b,int) or not isinstance(o,int):raise ValueError('packed row lacks pointer')
   ptr=((b<<29)|o)+1
  yield r,ptr

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',action='append',nargs=2,metavar=('ZONE','EXPANDED'),required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--expected-type',type=int,default=8);a=ap.parse_args()
 doc=json.loads(a.manifest.read_text(encoding='utf-8-sig'));zones={}
 for zone,path in a.source:
  p=Path(path);data=p.read_bytes();front=parse_front(data);zones[zone]={'path':str(p),'bytes':len(data),'sha256':sha256_file(p),'front':front}
 results=[]
 for row,ptr in iter_manifest_refs(doc):
  zone=row.get('sourceZone')
  if zone not in zones:results.append({**row,'resolution':{'classification':'source-zone-not-provided'}});continue
  res=classify(ptr,zones[zone]['front'],a.expected_type)
  results.append({**row,'resolution':res})
 counts={};exact_expected=0
 for r in results:
  c=r['resolution']['classification'];counts[c]=counts.get(c,0)+1
  if c=='xasset-header-slot' and r['resolution'].get('expectedTypeMatches'):exact_expected+=1
 out={'format':'t6-xasset-header-alias-resolver-v1','authority':'retail expanded T6 XAssetList layout + zone-pointer arithmetic','loaderRule':'VIRTUAL front allocations: ScriptString pointer table/strings, dependency pointer table/strings, aligned 8-byte XAsset array; XAsset.header is +4 in each row','sources':{z:{k:v for k,v in info.items() if k!='front'}|{'front':{k:v for k,v in info['front'].items() if k!='assets'}} for z,info in zones.items()},'expectedAssetType':{'index':a.expected_type,'name':TYPE_NAMES.get(a.expected_type)},'summary':{'references':len(results),'classifications':counts,'exactHeaderSlotsWithExpectedType':exact_expected},'results':results,'proofBoundary':'xasset-header-slot is proven only when the packed VIRTUAL offset lands exactly on an in-range XAsset.header field. Later VIRTUAL aliases are intentionally not resolved by this tool.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(out['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
