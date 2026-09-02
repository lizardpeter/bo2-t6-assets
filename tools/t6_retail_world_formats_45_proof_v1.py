#!/usr/bin/env python3
"""Retail-byte proof that T6 world formats 4/5 use 12/16-byte vd1 records."""
from __future__ import annotations
import argparse, collections, hashlib, json, re, struct
from pathlib import Path
FOLLOW=0xffffffff; INSERT=0xfffffffe; MASK=(1<<29)-1
EXPECTED={4:12,5:16}
MAPS={
 "mp_raid":dict(sha="d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8",world=66275632,surfs=87215751,nSurf=5281,mm=86599274,nMat=352,base=13768,q0=750,q1=845,direct={4:17,5:4}),
 "mp_hijacked":dict(sha="8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b",world=58846527,surfs=76725770,nSurf=2366,mm=76241210,nMat=236,base=14172,q0=751,q1=821,direct={4:23,5:9}),
}
def dec(v,blocks):
 if v==0:return ('null',0,0)
 if v==FOLLOW:return ('follow',0,0)
 if v==INSERT:return ('insert',0,0)
 e=(v-1)&0xffffffff;b=e>>29;o=e&MASK
 return ('packed',b,o) if b<8 and o<blocks[b] else ('bad',b,o)
def ptr_ok(v,blocks,null=True): return (v==0 and null) or v in (FOLLOW,INSERT) or dec(v,blocks)[0]=='packed'
def front(d):
 blocks=struct.unpack_from('<8I',d,8);p=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
 assert (not sc or sp==FOLLOW) and (not dc or dp==FOLLOW) and ap==FOLLOW
 for count in (sc,dc):
  if count:
   ps=struct.unpack_from(f'<{count}I',d,p);p+=4*count
   for x in ps:
    if x==FOLLOW:p=d.index(b'\0',p)+1
 return blocks,[struct.unpack_from('<II',d,p+8*i) for i in range(ac)]
def world(d,s,nSurf,nMat):
 x=dict(surfaceCount=struct.unpack_from('<I',d,s+16)[0],lightmapCount=struct.unpack_from('<i',d,s+408)[0],vertexCount=struct.unpack_from('<I',d,s+424)[0],vd0Bytes=struct.unpack_from('<I',d,s+428)[0],vd0Ptr=struct.unpack_from('<I',d,s+432)[0],vd1Bytes=struct.unpack_from('<I',d,s+440)[0],vd1Ptr=struct.unpack_from('<I',d,s+444)[0],indexCount=struct.unpack_from('<I',d,s+452)[0],indexPtr=struct.unpack_from('<I',d,s+456)[0],materialMemoryCount=struct.unpack_from('<i',d,s+572)[0],materialMemoryPtr=struct.unpack_from('<I',d,s+576)[0])
 assert x['surfaceCount']==nSurf and x['materialMemoryCount']==nMat
 assert x['vd0Ptr']==x['vd1Ptr']==x['indexPtr']==x['materialMemoryPtr']==FOLLOW
 return x
def align16(n):return (n+15)&~15
def surfaces_and_groups(d,start,count,w):
 ss=[]
 for i in range(count):
  p=start+80*i;off0=struct.unpack_from('<I',d,p+12)[0];off1=struct.unpack_from('<I',d,p+28)[0];vc,tc=struct.unpack_from('<HH',d,p+40);bi=struct.unpack_from('<I',d,p+44)[0];mat=struct.unpack_from('<I',d,p+48)[0];lm=d[p+52]
  assert off0<w['vd0Bytes'] and off1<=w['vd1Bytes'] and bi+tc*3<=w['indexCount'] and (lm==31 or lm<max(w['lightmapCount'],1)) and mat not in (0,FOLLOW,INSERT)
  ss.append((i,off0,off1,vc,mat))
 by0=collections.defaultdict(list)
 for r in ss:by0[r[1]].append(r)
 offs=sorted(by0);groups=[]
 for gi,o in enumerate(offs):
  nxt=offs[gi+1] if gi+1<len(offs) else w['vd0Bytes'];span=nxt-o
  cand=[n for n in range(max(0,span//36-2),span//36+3) if align16(36*n)==span];stored=sorted({r[3] for r in by0[o] if r[3]})
  assert len(cand)==1 and (not stored or stored==cand);o1=sorted({r[2] for r in by0[o]});assert len(o1)==1
  groups.append(dict(i=gi,off0=o,off1=o1[0],vc=cand[0],mats=sorted({r[4] for r in by0[o]})))
 by1=collections.defaultdict(list)
 for g in groups:by1[g['off1']].append(g)
 os=sorted(by1);alloc=[]
 for i,o in enumerate(os):
  nxt=os[i+1] if i+1<len(os) else w['vd1Bytes'];span=nxt-o;mem=by1[o];vcs=sorted({g['vc'] for g in mem});stride=None
  if span>0 and len(vcs)==1 and span%vcs[0]==0 and (span//vcs[0])%4==0:stride=span//vcs[0]
  alloc.append(dict(off=o,next=nxt,span=span,vcs=vcs,stride=stride,groups=[g['i'] for g in mem],mats=sorted({m for g in mem for m in g['mats']})))
 return ss,groups,alloc
def cstr(d,p):
 e=d.find(b'\0',p,min(len(d),p+512))
 if e<=p:return None
 b=d[p:e]
 return b.decode('ascii') if 3<=len(b)<=500 and all(32<=x<=126 for x in b) else None
def scan_materials(d,blocks,lo,hi):
 out=[]
 for s in range(lo,hi-104):
  if d[s+100:s+104]!=b'\0'*4:continue
  tc,cc,sc,sf,cr,pm=d[s+76:s+82]
  if not(tc<=64 and cc<=64 and 0<sc<=64 and cr<=31 and pm<=31):continue
  tech=struct.unpack_from('<I',d,s+84)[0];kids=struct.unpack_from('<III',d,s+88)
  if tech in (0,FOLLOW,INSERT) or not ptr_ok(tech,blocks,False) or not all(ptr_ok(x,blocks) for x in kids):continue
  if (tc==0)!=(kids[0]==0) or (cc==0)!=(kids[1]==0) or (sc==0)!=(kids[2]==0):continue
  name=cstr(d,s+104)
  if name:out.append(dict(start=s,tech=tech,name=name))
 return out
def scan_tech(d,blocks,before):
 out=[];off=100000;rx=re.compile(r'[A-Za-z0-9_./$@+~:#-]+')
 while True:
  off=d.find(b'\xff\xff\xff\xff',off,before)
  if off<0:break
  if off+152<before and d[off+4]<=8 and d[off+5:off+8]==b'\0\0\0':
   ps=struct.unpack_from('<36I',d,off+8)
   if any(ps) and all(ptr_ok(x,blocks) for x in ps):
    name=cstr(d,off+152)
    if name and len(name)<=180 and rx.fullmatch(name):out.append(dict(start=off,fmt=d[off+4],name=name))
  off+=1
 return out
def solve_base(ptrs,assets,blocks):
 qs={i for i,(t,_) in enumerate(assets) if t==7};sets=[]
 for raw in ptrs:
  k,b,o=dec(raw,blocks);assert k=='packed' and b==5;sets.append({o-4-8*q for q in qs})
 x=set.intersection(*sets);assert len(x)==1;return next(iter(x))
def prove(name,d,s):
 assert hashlib.sha256(d).hexdigest()==s['sha'];blocks,assets=front(d);w=world(d,s['world'],s['nSurf'],s['nMat']);ss,groups,alloc=surfaces_and_groups(d,s['surfs'],s['nSurf'],w)
 ptrs=sorted({r[4] for r in ss});assert len(ptrs)==s['nMat'] and all(b-a==8 for a,b in zip(ptrs,ptrs[1:]));pidx={p:i for i,p in enumerate(ptrs)}
 for i in range(s['nMat']):assert struct.unpack_from('<I',d,s['mm']+8*i)[0]==FOLLOW
 m0=s['mm']+8*s['nMat'];mats=scan_materials(d,blocks,m0,s['surfs']);assert len(mats)==s['nMat'] and mats[0]['start']==m0
 base=solve_base({m['tech'] for m in mats},assets,blocks);assert base==s['base']
 for m in mats:
  _,b,o=dec(m['tech'],blocks);q=(o-base-4)//8;assert b==5 and o>=base+4 and (o-base-4)%8==0 and assets[q]==(7,FOLLOW);m['q']=q
 q0,q1=s['q0'],s['q1'];assert all(assets[q]==(7,FOLLOW) for q in range(q0,q1+1)) and assets[q1+1][0]==17
 tr=scan_tech(d,blocks,s['world']);body=tr[-(q1-q0+1):];assert len(body)==q1-q0+1;byq={q0+i:r for i,r in enumerate(body)}
 for m in mats:m['fmt']=byq[m['q']]['fmt'];m['techName']=byq[m['q']]['name']
 for g in groups:
  fs=sorted({mats[pidx[p]]['fmt'] for p in g['mats']});assert len(fs)==1;g['fmt']=fs[0]
 gb={g['i']:g for g in groups};direct=collections.defaultdict(list);shared=collections.defaultdict(list)
 for a in alloc:
  fs=sorted({gb[i]['fmt'] for i in a['groups']});a['fmts']=fs;a['matIdx']=sorted({pidx[p] for p in a['mats']})
  for f in (4,5):
   if fs==[f]:direct[f].append(a)
   elif f in fs:shared[f].append(a)
 for f in (4,5):assert len(direct[f])==s['direct'][f] and all(a['stride']==EXPECTED[f] for a in direct[f])
 return dict(map=name,expandedBytes=len(d),expandedSha256=s['sha'],gfxWorld=dict(fixedStart=s['world'],**w),surfaceArray=dict(start=s['surfs'],count=s['nSurf'],end=s['surfs']+80*s['nSurf']),vertexGroupCount=len(groups),materialMemory=dict(start=s['mm'],count=s['nMat'],end=m0,firstMaterialFixedStart=mats[0]['start']),techniqueBinding=dict(assetPointerVirtualBase=base,distinctReferenced=len({m['q'] for m in mats}),block=[q0,q1]),materialFormatCounts=dict(collections.Counter(m['fmt'] for m in mats)),groupFormatCounts=dict(collections.Counter(g['fmt'] for g in groups)),formats={str(f):dict(expectedStride=EXPECTED[f],directAllocationCount=len(direct[f]),rawStrides=sorted({a['stride'] for a in direct[f]}),sharedNonseparableCount=len(shared[f]),contradictions=0,examples=[dict(vd1Offset=a['off'],next=a['next'],span=a['span'],vertexCount=a['vcs'][0],rawStride=a['stride'],materials=[mats[i]['name'] for i in a['matIdx']],techniqueSets=[mats[i]['techName'] for i in a['matIdx']]) for a in direct[f][:6]]) for f in (4,5)})
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus/mp'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();maps=[prove(n,(a.root/f'{n}.expanded.bin').read_bytes(),s) for n,s in MAPS.items()]
 summary=dict(mapCount=2,format4DirectAllocations=sum(x['formats']['4']['directAllocationCount'] for x in maps),format5DirectAllocations=sum(x['formats']['5']['directAllocationCount'] for x in maps),format4ObservedRawStrides=sorted({v for x in maps for v in x['formats']['4']['rawStrides']}),format5ObservedRawStrides=sorted({v for x in maps for v in x['formats']['5']['rawStrides']}),contradictionCount=0,formatsPromotable=[4,5])
 out=dict(format='t6-retail-world-formats-45-proof-v1',producer='tools/t6_retail_world_formats_45_proof_v1.py',maps=maps,summary=summary,proofBoundary='worldVertFormat is read from each retail MaterialTechniqueSet reached through GfxSurface -> MaterialMemory -> Material -> TechniqueSet XAsset. Raw vd1 stride is independently allocation-span / vd0-derived vertex-count. Shared format-0 vd1 offsets are retained as non-separable and never used as proof or contradiction. Shader meaning of normalTransform words is outside this proof.')
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
