#!/usr/bin/env python3
"""Retail-byte census of T6 GfxWorld Material render-state serialization, v2.

Extends the v1 proof from three retained MP worlds to all five currently
retained decoded worlds (MP + Zombies) with identical parsing invariants.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math, struct
from pathlib import Path
F=0xffffffff; I=0xfffffffe; MASK=(1<<29)-1
MAPS={
 'mp_nuketown_2020':('mp','7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505',154653476,84465666,327,84618654),
 'mp_raid':('mp','d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8',156092603,86602090,352,86768156),
 'mp_hijacked':('mp','8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b',141043798,76243098,236,76363007),
 'zm_prison':('zm','e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487',344067743,119307001,607,119605168),
 'zm_tomb':('zm','4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219',359627377,108427458,280,108564480),
}
BLEND=set(range(11)); BOP=set(range(6)); CULL={1,2,3}
def sha(b): return hashlib.sha256(b).hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def dig(x): return sha(canon(x))
def bits(v,o,n): return (v>>o)&((1<<n)-1)
def pk(v,blocks):
 if v==0:return 'null'
 if v==F:return 'follow'
 if v==I:return 'insert'
 e=(v-1)&0xffffffff; b=e>>29; o=e&MASK
 return 'packed' if b<8 and o<blocks[b] else 'bad'
def req(v,blocks,null=True):
 k=pk(v,blocks)
 if k=='bad' or (k=='null' and not null): raise ValueError(f'bad pointer 0x{v:08x}')
 return k
def cstr(d,p):
 e=d.find(b'\0',p,min(len(d),p+8192))
 if e<=p or any(x<32 or x>126 for x in d[p:e]): raise ValueError(f'bad string at {p}')
 return d[p:e].decode('ascii'),e+1
def valid_state(raw):
 lo=raw&0xffffffff
 vals=(bits(lo,0,4),bits(lo,4,4),bits(lo,8,3),bits(lo,14,2),bits(lo,16,4),bits(lo,20,4),bits(lo,24,3))
 if vals[0] not in BLEND or vals[1] not in BLEND or vals[2] not in BOP or vals[3] not in CULL or vals[4] not in BLEND or vals[5] not in BLEND or vals[6] not in BOP: return False
 return bits(lo,13,1)==0 and bits(lo,29,2)==0

def material(d,s,blocks):
 if s+104>len(d): raise ValueError('material eof')
 x=d[s:s+104]; game=struct.unpack_from('<I',x,4)[0]; sort=x[9]; routes=list(struct.unpack_from('<36b',x,40)); tc,cc,sc,sf,cr,pm=x[76:82]; tech,tp,cp,sp,thermal=struct.unpack_from('<IIIII',x,84)
 if game>=0x8000 or pm!=0 or not(0<tc<=64 and cc<=64 and 0<sc<=64): raise ValueError('material header')
 req(tech,blocks,False)
 if tp!=F or sp!=F or (cp!=(F if cc else 0)) or thermal!=0: raise ValueError('material child pointers')
 if any(v < -1 or v>=sc for v in routes): raise ValueError('route range')
 name,p=cstr(d,s+104); tex=[]
 for j in range(tc):
  o=p+16*j; ip=struct.unpack_from('<I',d,o+12)[0]; tex.append(req(ip,blocks))
 p+=16*tc; inline=loads=resources=0
 for k in tex:
  if k not in ('follow','insert'): continue
  inline+=1
  if p+80>len(d): raise ValueError('image eof')
  lp=struct.unpack_from('<I',d,p)[0]; np=struct.unpack_from('<I',d,p+72)[0]
  lk=req(lp,blocks); nk=req(np,blocks,False)
  if nk!='follow': raise ValueError('image name pointer')
  p+=80; _,p=cstr(d,p)
  if lk in ('follow','insert'):
   loads+=1
   if p+12>len(d): raise ValueError('loaddef eof')
   rs=struct.unpack_from('<i',d,p+8)[0]
   if rs<0 or p+12+rs>len(d): raise ValueError('loaddef resource')
   resources+=rs; p+=12+rs
 for j in range(cc):
  o=p+32*j; frag=d[o+4:o+16].split(b'\0',1)[0]
  if not frag or any(x<32 or x>126 for x in frag): raise ValueError('constant name')
  if any(not math.isfinite(v) for v in struct.unpack_from('<4f',d,o+16)): raise ValueError('constant value')
 p+=32*cc; states=[]
 for j in range(sc):
  o=p+20*j; raw=struct.unpack_from('<Q',d,o)[0]
  if any(struct.unpack_from('<III',d,o+8)): raise ValueError('runtime D3D pointer')
  if not valid_state(raw): raise ValueError(f'state enum 0x{raw:016x}')
  states.append(raw)
 p+=20*sc
 if sorted({v for v in routes if v>=0})!=list(range(sc)): raise ValueError('unreferenced state')
 return dict(start=s,end=p,name=name,sortKey=sort,textureCount=tc,constantCount=cc,stateCount=sc,activeRoutes=sum(v>=0 for v in routes),inlineImages=inline,inlineLoadDefs=loads,resourceBytes=resources,states=states,archiveSha256=sha(d[s:p]))

def one(name,path,cfg):
 _,exsha,exbytes,start,count,last=cfg; d=path.read_bytes(); h=sha(d)
 if len(d)!=exbytes or h!=exsha: raise ValueError(f'{name}: source mismatch')
 blocks=struct.unpack_from('<8I',d,8); rows=[]; p=start
 for i in range(count):
  r=material(d,p,blocks); rows.append(r); p=r['end']+8
 if rows[-1]['end']!=last: raise ValueError(f'{name}: final end {rows[-1]["end"]} != {last}')
 states={v for r in rows for v in r['states']}; meta=[{k:r[k] for k in ('start','end','name','sortKey','textureCount','constantCount','stateCount')} for r in rows]; digs=[r['archiveSha256'] for r in rows]; ix=sorted({0,len(rows)//2,len(rows)-1}); sorts=collections.Counter(r['sortKey'] for r in rows)
 st=dict(materialCount=count,textureCount=sum(r['textureCount'] for r in rows),inlineImageCount=sum(r['inlineImages'] for r in rows),inlineLoadDefCount=sum(r['inlineLoadDefs'] for r in rows),inlineResourceBytes=sum(r['resourceBytes'] for r in rows),constantCount=sum(r['constantCount'] for r in rows),stateCount=sum(r['stateCount'] for r in rows),activeRouteSlotCount=sum(r['activeRoutes'] for r in rows),referencedStateCount=sum(r['stateCount'] for r in rows),runtimeD3DPointerSlotCount=sum(3*r['stateCount'] for r in rows),runtimeD3DNonzeroPointerCount=0,routingFailureCount=0,enumFailureCount=0,constantValidationFailureCount=0,uniqueRawStateCount=len(states),uniqueDecodedStateCount=len(states),sortKeyCounts={str(k):v for k,v in sorted(sorts.items())})
 return {'map':name,'source':{'file':path.name,'bytes':len(d),'sha256':h},'materialChain':{'firstStart':start,'lastEnd':last,'materialCount':count,'interRecordBridgeBytes':8},'stats':st,'materialArchiveRootSha256':dig(digs),'materialMetadataSha256':dig(meta),'materialArchiveExamples':[meta[i]|{'archiveSha256':digs[i]} for i in ix],'_states':states}

def build(mp_root:Path,zm_root:Path):
 maps=[]
 for n,c in MAPS.items():
  root=mp_root if c[0]=='mp' else zm_root
  maps.append(one(n,root/f'{n}.expanded.bin',c))
 allstates=sorted({v for m in maps for v in m['_states']})
 for m in maps: del m['_states']
 keys=('materialCount','textureCount','inlineImageCount','inlineLoadDefCount','inlineResourceBytes','constantCount','stateCount','activeRouteSlotCount','referencedStateCount','runtimeD3DPointerSlotCount')
 summary={k:sum(m['stats'][k] for m in maps) for k in keys}; summary.update(retainedMapCount=5,retainedMpMapCount=3,retainedZombiesMapCount=2,runtimeD3DNonzeroPointerCount=0,routingFailureCount=0,enumFailureCount=0,constantValidationFailureCount=0,uniqueRawStateCount=len(allstates),uniqueDecodedStateCount=len(allstates),retainedCorpusExecutionClean=True)
 return {'format':'t6-retail-world-material-state-census-v2','producer':'tools/t6_retail_world_material_state_census_v2.py','supersedes':'manifests/render/T6_RETAIL_WORLD_MATERIAL_STATE_CENSUS_V1.json','reference':{'openAssetToolsRepository':'Laupetin/OpenAssetTools','openAssetToolsCommit':'7d027e8f89118196713e955b0e11f8404149c54d','materialZoneCode':'src/ZoneCode/Game/T6/XAssets/Material.txt','gfxImageZoneCode':'src/ZoneCode/Game/T6/XAssets/GfxImage.txt','materialFixedBytes':104,'materialTextureDefBytes':16,'materialConstantDefBytes':32,'gfxStateBitsFixedBytes':20,'gfxStateBitsLoadBitsBytes':8,'gfxImageFixedBytes':80,'gfxImageLoadDefHeaderBytes':12},'maps':maps,'summary':summary,'uniqueStateSignatureSetSha256':dig([f'{v:016x}' for v in allstates]),'proofBoundary':'Direct retail-byte execution proof for every GfxWorld surface Material in the five currently decoded retained worlds: mp_nuketown_2020, mp_raid, mp_hijacked, zm_prison, and zm_tomb. The Zombies worlds use the identical strict parser/invariants as MP with no relaxed recovery. It does not claim closure for unretained target maps/subzones, non-world/layered component materials, numeric backend polygon bias, technique selection, or visual playback parity.'}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--mp-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus/mp')); ap.add_argument('--zm-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus')); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args(); doc=build(a.mp_root,a.zm_root); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n'); print(json.dumps(doc['summary'],indent=2,sort_keys=True))
if __name__=='__main__': main()
