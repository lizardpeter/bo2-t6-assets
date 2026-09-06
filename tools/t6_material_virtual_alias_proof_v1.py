#!/usr/bin/env python3
"""Prove T6 packed GfxImage aliases by exact VIRTUAL MaterialTextureDef layout.

T6 Material assets live in TEMP, but their asset-member traversal runs in the
default normal VIRTUAL block. A FOLLOWING textureTable allocates 16-byte
MaterialTextureDef rows there; each row's GfxImage* is at +12. GfxImage itself
is an asset in TEMP, while its FOLLOWING name string consumes VIRTUAL bytes and
an INSERT reusable loadDef consumes a 4-byte alias entry in the insert/VIRTUAL
block. Material constants and state bits then consume their aligned VIRTUAL
arrays. This tool walks those allocations and requires target packed pointers to
land exactly on the source MaterialTextureDef.image field that introduced the
retail image identity.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

TEXTURE_DEF=16
IMAGE_FIELD=12
CONSTANT_BYTES=32
STATEBITS_BYTES=20

def align(x:int,a:int)->int:return (x+a-1)&~(a-1)
def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def load_catalog(p:Path)->list[dict]:
 x=json.loads(p.read_text(encoding='utf-8-sig'))
 if isinstance(x,list):return x
 out=[]
 if isinstance(x,dict):
  for v in x.values():
   if isinstance(v,list):out.extend(r for r in v if isinstance(r,dict))
 return out
def packed_offset(ptr:dict)->int|None:
 if ptr.get('kind')!='packed':return None
 v=ptr.get('offset')
 return int(v) if isinstance(v,int) else None

def simulate_material(row:dict, table_base:int)->dict:
 p=table_base
 n=int(row['textureCount'])
 table={'start':p,'bytes':n*TEXTURE_DEF,'end':p+n*TEXTURE_DEF}
 p=table['end'];slots=[];alloc=[]
 for t in row.get('textures',[]):
  i=int(t['index']); field=table_base+i*TEXTURE_DEF+IMAGE_FIELD
  s={'slotIndex':i,'imageFieldVirtualOffset':field,'nameHash':t.get('nameHash'),'imagePointer':t.get('imagePointer')}
  im=t.get('inlineImage')
  if im:
   name=im['name'];nb=len(name.encode('latin1'))+1
   s['inlineImageName']=name;s['inlineImageRawStart']=im.get('start')
   alloc.append({'kind':'GfxImage.name','slotIndex':i,'start':p,'bytes':nb,'end':p+nb,'name':name});p+=nb
   if (im.get('loadDefPointer') or {}).get('kind')=='insert':
    q=align(p,4)
    if q!=p:alloc.append({'kind':'alignment','alignment':4,'start':p,'bytes':q-p,'end':q})
    p=q;alloc.append({'kind':'GfxImage.loadDef INSERT alias','slotIndex':i,'start':p,'bytes':4,'end':p+4});p+=4
  slots.append(s)
 if int(row.get('constantCount',0)):
  q=align(p,16)
  if q!=p:alloc.append({'kind':'alignment','alignment':16,'start':p,'bytes':q-p,'end':q})
  p=q;b=int(row['constantCount'])*CONSTANT_BYTES;alloc.append({'kind':'Material.constantTable','start':p,'bytes':b,'end':p+b,'count':int(row['constantCount'])});p+=b
 if int(row.get('stateBitsCount',0)):
  q=align(p,8)
  if q!=p:alloc.append({'kind':'alignment','alignment':8,'start':p,'bytes':q-p,'end':q})
  p=q;b=int(row['stateBitsCount'])*STATEBITS_BYTES;alloc.append({'kind':'Material.stateBitsTable','start':p,'bytes':b,'end':p+b,'count':int(row['stateBitsCount'])});p+=b
 thermal=(row.get('thermalPointer') or {}).get('kind')
 if thermal=='insert':
  q=align(p,4)
  if q!=p:alloc.append({'kind':'alignment','alignment':4,'start':p,'bytes':q-p,'end':q})
  p=q;alloc.append({'kind':'Material.thermalMaterial INSERT alias','start':p,'bytes':4,'end':p+4});p+=4
 return {'material':row['name'],'rawStart':row.get('start'),'rawEnd':row.get('end'),'textureTable':table,'slots':slots,'virtualAllocationsAfterTextureTable':alloc,'virtualEnd':p}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--source-expanded',type=Path,required=True);ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 rows=load_catalog(a.catalog);by={r.get('name'):r for r in rows if isinstance(r.get('name'),str)};spec=json.loads(a.spec.read_text(encoding='utf-8-sig'));chains=[];field_owners={}
 for ch in spec['chains']:
  names=ch['materials'];base=int(ch['firstTextureTableVirtualBase']);walk=[];p=None
  for j,name in enumerate(names):
   if name not in by:raise SystemExit(f'material not in catalog: {name}')
   row=by[name]
   if j==0: table_base=base
   else:
    prev=by[names[j-1]]
    if prev.get('end')!=row.get('start'):raise SystemExit(f'raw materials not contiguous: {prev["name"]} end {prev.get("end")} != {name} start {row.get("start")}')
    name_start=p; name_bytes=len(name.encode('latin1'))+1; name_end=name_start+name_bytes; table_base=align(name_end,4)
    walk[-1]['transitionToNextMaterial']={'nextMaterial':name,'nameVirtualStart':name_start,'nameBytes':name_bytes,'nameVirtualEnd':name_end,'nextTextureTableVirtualBase':table_base}
   sim=simulate_material(row,table_base);walk.append(sim);p=sim['virtualEnd']
   for s in sim['slots']:
    if s.get('inlineImageName'):field_owners[s['imageFieldVirtualOffset']]={'material':name,'slotIndex':s['slotIndex'],'image':s['inlineImageName'],'inlineImageRawStart':s.get('inlineImageRawStart')}
  chains.append({'name':ch.get('name'),'firstTextureTableVirtualBase':base,'materials':walk,'virtualEnd':p})
 proofs=[]
 for t in spec['targets']:
  src_off=int(t['sourceImageFieldVirtualOffset']); owner=field_owners.get(src_off)
  if owner is None:raise SystemExit(f'no inline image owner at VIRTUAL {src_off}')
  later=by.get(t['laterMaterial'])
  if later is None:raise SystemExit(f'later material absent: {t["laterMaterial"]}')
  slot=next((x for x in later.get('textures',[]) if int(x['index'])==int(t['laterSlotIndex'])),None)
  if slot is None:raise SystemExit('later slot absent')
  po=packed_offset(slot.get('imagePointer') or {})
  if po!=src_off:raise SystemExit(f'packed alias mismatch {t["laterMaterial"]}:{t["laterSlotIndex"]}: {po} != {src_off}')
  exp=t.get('expectedImage')
  if exp is not None and owner['image']!=exp:raise SystemExit(f'identity mismatch {owner["image"]!r} != {exp!r}')
  proofs.append({'sourceImageFieldVirtualOffset':src_off,'sourceOwner':owner,'laterUse':{'material':t['laterMaterial'],'slotIndex':int(t['laterSlotIndex']),'packedPointerRaw':slot['imagePointer'].get('raw'),'packedPointerOffset':po},'exactIdentity':owner['image'],'exactAliasProven':True})
 out={'format':'t6-material-virtual-image-alias-proof-v1','authority':'retail expanded T6 material serialization + pinned T6 loader VIRTUAL allocation rules','source':{'expandedPath':str(a.source_expanded),'expandedBytes':a.source_expanded.stat().st_size,'expandedSha256':sha256_file(a.source_expanded),'catalogPath':str(a.catalog),'catalogSha256':sha256_file(a.catalog)},'rules':{'MaterialTextureDefBytes':TEXTURE_DEF,'MaterialTextureDefImageFieldOffset':IMAGE_FIELD,'MaterialConstantDefBytes':CONSTANT_BYTES,'GfxStateBitsBytes':STATEBITS_BYTES,'GfxImageName':'FOLLOWING string in default VIRTUAL block','GfxImageLoadDefInsertAlias':'4-byte aligned INSERT alias in VIRTUAL insert block','MaterialConstantTableAlignment':16,'MaterialStateBitsTableAlignment':8},'summary':{'chains':len(chains),'targets':len(proofs),'exactAliasesProven':sum(1 for x in proofs if x['exactAliasProven'])},'chains':chains,'proofs':proofs,'proofBoundary':'A packed image identity is promoted only when its decoded VIRTUAL offset equals exactly the +12 GfxImage* field of a source MaterialTextureDef row whose inline retail GfxImage name is directly serialized. Chain transitions additionally require raw source adjacency and exact VIRTUAL allocation accounting.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(out['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
