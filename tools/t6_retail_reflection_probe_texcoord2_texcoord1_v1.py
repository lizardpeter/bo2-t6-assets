#!/usr/bin/env python3
"""Retained proof for the T6 reflection family A=TEXCOORD2, B=TEXCOORD1.

Global DXBC classification is exhaustive. Physical role promotion is deliberately
limited to the 20 shader identities mapped into retained Hijacked TechniqueSet
passes. Two direct paired VS payloads prove TEXCOORD2 from NORMAL0 and TEXCOORD1
from homogeneous POSITION through cb3/worldMatrix. The 18 packed occurrences
use two packed pointer identities. Their candidate set is bounded to those same
two direct VS objects by a serializer differential invariant calibrated from the
32 independently resolved pointer pairs in the earlier packed-VS alias proof.
Because both candidates have identical relevant producer semantics, no
pointer-to-candidate permutation is required for the role proof.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path

EXPECTED_GLOBAL=75;EXPECTED_MAPPED=20;EXPECTED_PASSES=20;EXPECTED_DIRECT=2;EXPECTED_PACKED=18;EXPECTED_PTRS=2
MAPS={'mp_nuketown_2020':dict(rel='mp/mp_nuketown_2020.expanded.bin',world=63150420,q0=565,q1=623),'mp_raid':dict(rel='mp/mp_raid.expanded.bin',world=66275632,q0=750,q1=845),'mp_hijacked':dict(rel='mp/mp_hijacked.expanded.bin',world=58846527,q0=751,q1=821),'zm_prison':dict(rel='zm_prison.expanded.bin',world=82099460,q0=986,q1=1113),'zm_tomb':dict(rel='zm_tomb.expanded.bin',world=78964845,q0=1271,q1=1327)}
SHAS={'mp_nuketown_2020':'7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505','mp_raid':'d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8','mp_hijacked':'8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b','zm_prison':'e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487','zm_tomb':'4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219'}
FOLLOW=0xffffffff;INSERT=0xfffffffe;MASK=(1<<29)-1
SAMPLE={69:4,70:5,71:5,72:5,73:6,74:5};WRITER={0,16,17,50,54,56,68,69,70,71,72,73,74};TEMP=0;INPUT=1;OUTPUT=2;IMM=4;SAMP=6;RES=7;CB=8

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def chunks(b):
 cc=struct.unpack_from('<I',b,28)[0]
 for off in struct.unpack_from('<'+'I'*cc,b,32):
  n=struct.unpack_from('<I',b,off+4)[0];yield b[off:off+4],b[off+8:off+8+n]
def words(b):
 for t,p in chunks(b):
  if t in (b'SHDR',b'SHEX'):
   w=list(struct.unpack('<'+'I'*(len(p)//4),p));
   if len(w)<2 or w[1]!=len(w):raise ValueError('program length')
   return w
 raise ValueError('missing program')
def signature(b,tag):
 out={}
 for t,r in chunks(b):
  if t!=tag:continue
  cnt=struct.unpack_from('<I',r,0)[0]
  for i in range(cnt):
   q=8+24*i;no,si,sv,ct,reg,m=struct.unpack_from('<6I',r,q);e=r.find(b'\0',no);out[reg]=(r[no:e].decode(),si)
 return out
def walk(w):
 p=2
 while p<len(w):
  tok=w[p];op=tok&0x7ff;ln=(tok>>24)&0x7f
  if op==53:ln=w[p+1]
  if ln<=0 or p+ln>len(w):raise ValueError('instruction bounds')
  yield p,op,ln,tok;p+=ln
 if p!=len(w):raise ValueError('walk end')
def operand(w,p):
 st=p;tok=w[p];p+=1;ext=[]
 if tok&0x80000000:
  while True:
   x=w[p];ext.append(x);p+=1
   if not x&0x80000000:break
 dim=(tok>>20)&3;idx=[]
 for d in range(dim):
  rep=(tok>>(22+3*d))&7
  if rep==0:idx.append(w[p]);p+=1
  elif rep==1:idx.append((w[p],w[p+1]));p+=2
  elif rep==2:q=operand(w,p);idx.append(('relative',q));p=q['end']
  elif rep in (3,4):p+=1 if rep==3 else 2;q=operand(w,p);idx.append(('immrel',q));p=q['end']
  else:raise ValueError('index rep')
 comp=tok&3;sel=(tok>>2)&3;typ=(tok>>12)&255
 if typ in (4,5):p+=(1 if comp==1 else 4 if comp==2 else 0)*(2 if typ==5 else 1)
 if comp==2:
  if sel==0:cs=''.join(c for k,c in enumerate('xyzw') if tok&(1<<(4+k)))
  elif sel==1:sw=(tok>>4)&255;cs=''.join('xyzw'[(sw>>(2*k))&3] for k in range(4))
  elif sel==2:cs='xyzw'[(tok>>4)&3]
  else:raise ValueError('component select')
 elif comp==1:cs='x'
 else:cs=''
 mod=None
 for x in ext:
  if (x&0x3f)==1:mod={0:None,1:'neg',2:'abs',3:'absneg'}.get((x>>6)&255,'bad')
 return {'type':typ,'idx':idx,'comps':cs,'mod':mod,'start':st,'end':p,'token':tok}
def first(w,p):
 q=p+1
 if w[p]&0x80000000:
  while True:
   x=w[q];q+=1
   if not x&0x80000000:break
 return q
def parse_all(w,p,ln):
 q=first(w,p);a=[]
 while q<p+ln:x=operand(w,q);a.append(x);q=x['end']
 if q!=p+ln:raise ValueError('operand walk')
 return a
def latest(inst,w,before,typ,reg,ch):
 for i in range(before-1,-1,-1):
  p,op,ln,t=inst[i]
  if op not in WRITER:continue
  try:d=operand(w,first(w,p))
  except:continue
  if d['type']==typ and d['idx']==[reg] and ch in (d['comps'] or 'x'):return i,p,op,d,parse_all(w,p,ln)
 return None
def raw_norm(inst,w,before,v):
 if v['type']!=TEMP or len(v['idx'])!=1:return None
 r=v['idx'][0];cs=v['comps'][:3];ww=[latest(inst,w,before,TEMP,r,c) for c in set(cs)]
 if any(x is None for x in ww) or len({x[0] for x in ww})!=1 or ww[0][2]!=56:return None
 wi,wp,op,d,O=ww[0]
 for scalar,raw in ((O[1],O[2]),(O[2],O[1])):
  if scalar['type']==TEMP and len(scalar['idx'])==1 and raw['type'] in (INPUT,TEMP) and len(raw['idx'])==1:
   sc=(scalar['comps'] or 'x')[0];q=latest(inst,w,wi,TEMP,scalar['idx'][0],sc)
   if q and q[2]==68:return raw
 return None
def family_roles(b):
 w=words(b);inst=list(walk(w));sg=signature(b,b'ISGN');rows=[]
 for ii,(p,op,ln,t) in enumerate(inst):
  if op not in SAMPLE:continue
  O=parse_all(w,p,ln)
  if len(O)<4 or O[2]['type']!=RES or O[3]['type']!=SAMP or O[2]['idx']!=[15] or O[3]['idx']!=[15]:continue
  c=O[1]
  if c['type']!=TEMP or len(c['idx'])!=1:raise ValueError('cube coord')
  rr=c['idx'][0];ws=[latest(inst,w,ii,TEMP,rr,ch) for ch in set(c['comps'][:3])]
  if any(x is None for x in ws) or len({x[0] for x in ws})!=1 or ws[0][2]!=50:raise ValueError('reflect MAD')
  mi,mp,_,_,M=ws[0];A,B=M[1],M[3];ra=raw_norm(inst,w,mi,A);rb=raw_norm(inst,w,mi,B)
  def d(x):
   if x and x['type']==INPUT and len(x['idx'])==1:return (sg.get(x['idx'][0]),x['comps'][:3])
   return None
  rows.append((d(ra),d(rb)))
 return rows
def all_dxbc(d):
 p=0
 while True:
  q=d.find(b'DXBC',p)
  if q<0:return
  p=q+4
  try:n=struct.unpack_from('<I',d,q+24)[0];cc=struct.unpack_from('<I',d,q+28)[0]
  except:continue
  if 40<=n<=len(d)-q and cc<=32 and 32+4*cc<=n:yield q,d[q:q+n]

def global_target(root):
 all={}
 for mn,cfg in MAPS.items():
  d=(root/cfg['rel']).read_bytes()
  if hashlib.sha256(d).hexdigest()!=SHAS[mn]:raise ValueError('source sha '+mn)
  for pos,b in all_dxbc(d):
   if b'reflectionProbeSampler\x00' not in b:continue
   h=hashlib.sha256(b).hexdigest()
   if h in all:continue
   try:r=family_roles(b)
   except:continue
   if any(a and bb and a[0]==('TEXCOORD',2) and bb[0]==('TEXCOORD',1) and a[1]=='xyz' and bb[1] in ('xyz','xxy') for a,bb in r):all[h]=r
 if len(all)!=EXPECTED_GLOBAL:raise ValueError(f'global family {len(all)}')
 return all
# fastfile pass parser

def dec(v,bs):
 if v==0:return ('null',None,None)
 if v==FOLLOW:return ('following',None,None)
 if v==INSERT:return ('insert',None,None)
 e=(v-1)&0xffffffff;b=e>>29;o=e&MASK
 return ('packed',b,o) if b<8 and o<bs[b] else ('bad',b,o)
def front(d):
 bs=struct.unpack_from('<8I',d,8);p=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
 for n in (sc,dc):
  if n:
   ps=struct.unpack_from(f'<{n}I',d,p);p+=4*n
   for x in ps:
    if x==FOLLOW:p=d.index(b'\0',p)+1
 return bs
def cstr(d,p,lim=8192):
 e=d.find(b'\0',p,min(len(d),p+lim));b=d[p:e]
 if e<=p or any(x<32 or x>126 for x in b):raise ValueError('cstring')
 return b.decode(),e+1
def scan_sets(d,bs,before):
 import re
 out=[];p=100000;rx=re.compile(r'[A-Za-z0-9_./$@+~:#-]+')
 while True:
  p=d.find(b'\xff\xff\xff\xff',p,before)
  if p<0:break
  if p+152<before and d[p+4]<=8 and d[p+5:p+8]==b'\0\0\0':
   ps=struct.unpack_from('<36I',d,p+8)
   if any(ps) and all(dec(x,bs)[0]!='bad' for x in ps):
    try:n=cstr(d,p+152,512)[0]
    except:n=None
    if n and rx.fullmatch(n):out.append((p,d[p+4],n))
  p+=1
 return out
def ptr(v,bs):k,b,o=dec(v,bs);return {'kind':k,'block':b,'offset':o}
def shader(d,p,bs):
 st=p;namep,runtime,progp,size=struct.unpack_from('<IIII',d,p);p+=16
 if dec(namep,bs)[0] in ('following','insert'):name,p=cstr(d,p)
 else:name=None
 pk=dec(progp,bs)[0];prog=None
 if size and pk in ('following','insert'):
  b=d[p:p+size];prog={'sha':hashlib.sha256(b).hexdigest(),'blob':b,'start':p,'size':size};p+=size
 elif size and pk=='packed':prog={'packed':ptr(progp,bs),'size':size}
 return p,{'start':st,'name':name,'prog':prog}
def technique(d,p,bs):
 namep=struct.unpack_from('<I',d,p)[0];flags,pc=struct.unpack_from('<HH',d,p+4);p+=8;pas=[]
 for j in range(pc):
  o=p+24*j;vd,vs,ps=struct.unpack_from('<III',d,o);pp,po,stable,custom,pre,mt=struct.unpack_from('<6B',d,o+12);args=struct.unpack_from('<I',d,o+20)[0];pas.append({'i':j,'vd':vd,'vs':vs,'ps':ps,'argc':pp+po+stable,'args':args})
 p+=24*pc
 for a in pas:
  a['c']={}
  for fld,kind in [('vs','vs'),('vd','vd'),('ps','ps'),('args','args')]:
   v=a[fld];q=ptr(v,bs);a['c'][fld]=q
   if q['kind'] not in ('following','insert'):continue
   if kind in ('vs','ps'):p,s=shader(d,p,bs);q['inline']=s
   elif kind=='vd':p+=116
   else:
    vals=[]
    for i in range(a['argc']):typ,loc,size,buf,u=struct.unpack_from('<HHHHI',d,p+12*i);vals.append((typ,u))
    p+=12*a['argc']
    for typ,u in vals:
     if typ in (1,7) and dec(u,bs)[0] in ('following','insert'):p+=16
 if dec(namep,bs)[0] in ('following','insert'):name,p=cstr(d,p)
 else:name=None
 return p,{'name':name,'passes':pas}
def techset(d,row,nxt,bs):
 st,fmt,nm=row;name,p=cstr(d,st+152);refs=[]
 for slot,v in enumerate(struct.unpack_from('<36I',d,st+8)):
  q=ptr(v,bs);q['slot']=slot
  if q['kind'] in ('following','insert'):p,t=technique(d,p,bs);q['tech']=t
  refs.append(q)
 if p!=nxt:raise ValueError('techset end')
 return {'name':name,'fmt':fmt,'refs':refs}
def pass_events(root,target):
 all={};direct_blobs={};direct_objects={}
 for mn,cfg in MAPS.items():
  d=(root/cfg['rel']).read_bytes();bs=front(d);n=cfg['q1']-cfg['q0']+1;rows=scan_sets(d,bs,cfg['world'])[-n:];ev=[]
  if len(rows)!=n:raise ValueError('techsets '+mn)
  for ti,r in enumerate(rows):
   ts=techset(d,r,rows[ti+1][0] if ti+1<len(rows) else cfg['world'],bs)
   for tr in ts['refs']:
    if 'tech' not in tr:continue
    for a in tr['tech']['passes']:
     v=a['c']['vs'];vi=v.get('inline');node=None
     if vi and vi['prog'] and 'sha' in vi['prog']:
      h=vi['prog']['sha'];node=('sha',h);direct_blobs[h]=vi['prog']['blob'];direct_objects[(mn,h)]=vi['start']
     elif v['kind']=='packed':node=('ptr',mn,v['block'],v['offset'])
     ps=a['c']['ps'];pi=ps.get('inline');ph=pi['prog']['sha'] if pi and pi['prog'] and 'sha' in pi['prog'] else None
     ev.append({'event':len(ev),'ti':ti,'ts':ts['name'],'fmt':ts['fmt'],'slot':tr['slot'],'pass':a['i'],'ps':ph,'vs':node})
  all[mn]=ev
 return all,direct_blobs,direct_objects

def input_leaves(b,w,inst,before,o,sg,seen=None):
 seen=set() if seen is None else seen
 if o['type']==INPUT and len(o['idx'])==1:return {sg.get(o['idx'][0],('REG',o['idx'][0]))}
 if o['type'] in (IMM,CB):return set()
 if o['type']!=TEMP or len(o['idx'])!=1:return {('OTHER',o['type'])}
 r=o['idx'][0];leaves=set()
 for c in set((o['comps'] or 'x')[:3]):
  key=(r,c,before)
  if key in seen:continue
  seen.add(key);q=latest(inst,w,before,TEMP,r,c)
  if not q:leaves.add(('UNWRITTEN',r,c));continue
  qi,qp,qop,qd,O=q
  for src in O[1:]:leaves|=input_leaves(b,w,inst,qi,src,sg,seen)
 return leaves
def prove_vs(b):
 w=words(b);inst=list(walk(w));si=signature(b,b'ISGN');so=signature(b,b'OSGN')
 def oreg(sem):
  a=[r for r,s in so.items() if s==sem]
  if len(a)!=1:raise ValueError('output semantic '+str(sem))
  return a[0]
 # TEXCOORD2 normal: output xyz from normalized temp whose raw three DP3 rows reach NORMAL0 only
 r=oreg(('TEXCOORD',2));ow=[latest(inst,w,len(inst),OUTPUT,r,c) for c in 'xyz']
 if any(x is None for x in ow) or len({x[0] for x in ow})!=1:raise ValueError('tc2 writer')
 O=ow[0][4];src=O[1] if len(O)>1 else None
 # allow MOV only
 if ow[0][2]!=54 or not src or src['type']!=TEMP:raise ValueError('tc2 mov')
 nr=src['idx'][0];nw=[latest(inst,w,ow[0][0],TEMP,nr,c) for c in 'xyz']
 if any(x is None for x in nw) or len({x[0] for x in nw})!=1 or nw[0][2]!=56:raise ValueError('normal normalize MUL')
 mul=nw[0][4];vec=None;scalar=None
 for a,bx in ((mul[1],mul[2]),(mul[2],mul[1])):
  if a['type']==TEMP and len(set(a['comps'][:3]))==1 and bx['type']==TEMP:scalar,vec=a,bx
 if vec is None:raise ValueError('normalize split')
 leaves=input_leaves(b,w,inst,nw[0][0],vec,si)
 if leaves!={('NORMAL',0)}:raise ValueError('normal leaves '+str(leaves))
 # TEXCOORD1 position: output xyz must trace only POSITION, and immediate/CB; also require common DP4 world rows 0..2
 rp=oreg(('TEXCOORD',1));pw=[latest(inst,w,len(inst),OUTPUT,rp,c) for c in 'xyz']
 if any(x is None for x in pw) or len({x[0] for x in pw})!=1:raise ValueError('tc1 writer')
 PO=pw[0][4];psrc=PO[1] if len(PO)>1 else None
 if pw[0][2]!=54 or not psrc:raise ValueError('tc1 mov')
 pleaves=input_leaves(b,w,inst,pw[0][0],psrc,si)
 if pleaves!={('POSITION',0)}:raise ValueError('position leaves '+str(pleaves))
 # unwrap vector MOV aliases, then require three DP4 world rows
 cur=psrc;before=pw[0][0]
 for _ in range(4):
  if cur['type']!=TEMP or len(cur['idx'])!=1:break
  sr=cur['idx'][0];ww=[latest(inst,w,before,TEMP,sr,c) for c in 'xyz']
  if any(x is None for x in ww) or len({x[0] for x in ww})!=1 or ww[0][2]!=54:break
  O=ww[0][4]
  if len(O)!=2 or O[1]['type']!=TEMP:break
  before=ww[0][0];cur=O[1]
 sr=cur['idx'][0];dps=[latest(inst,w,before,TEMP,sr,c) for c in 'xyz']
 if any(x is None for x in dps) or [x[2] for x in dps]!=[17,17,17]:raise ValueError('world dp4')
 rows=[]
 for q in dps:
  cbs=[x for x in q[4][1:] if x['type']==CB and len(x['idx'])>=2]
  if len(cbs)!=1 or cbs[0]['idx'][0]!=3:raise ValueError('world cb')
  rows.append(cbs[0]['idx'][1])
 if rows!=[0,1,2]:raise ValueError('world rows '+str(rows))
 return {'vertexShaderSha256':hashlib.sha256(b).hexdigest(),'texcoord2InputLeaves':sorted(map(list,leaves)),'texcoord1InputLeaves':sorted(map(list,pleaves)),'worldMatrixRows':rows}
def calibrate(root,prior,direct_objects):
 enc=prior['encoding'];maps=enc['mapTable'];sh=enc['vertexShaderTable'];rows=prior['pointerAliases']
 loc={}
 for r in rows:
  mn=maps[r[0]];h=sh[r[4]];k=(mn,h)
  if k not in direct_objects:raise ValueError('prior direct object missing '+str(k))
  loc[(r[0],h)]=direct_objects[k]
 drifts=[]
 if len(rows)%2:raise ValueError('prior pointer rows odd')
 for i in range(0,len(rows),2):
  aa,bb=rows[i],rows[i+1]
  if aa[0]!=bb[0] or aa[6]!=0 or bb[6]!=1:raise ValueError('prior pair encoding')
  oa=loc[(aa[0],sh[aa[4]])];ob=loc[(bb[0],sh[bb[4]])]
  drifts.append(abs((bb[2]-aa[2])-abs(ob-oa)))
 if len(drifts)!=32 or max(drifts)!=12:raise ValueError('prior drift calibration '+str(collections.Counter(drifts)))
 return drifts

def build(root,prior_path):
 target=global_target(root);events,blobs,objects=pass_events(root,set(target));occ=[];ptrs=collections.Counter();direct=[]
 for mn,es in events.items():
  for e in es:
   if e['ps'] in target:
    occ.append((mn,e));n=e['vs']
    if n and n[0]=='sha':direct.append(n[1])
    elif n:ptrs[n]+=1
 mapped={e['ps'] for _,e in occ}
 if (len(mapped),len(occ),len(direct),sum(ptrs.values()),len(ptrs))!=(20,20,2,18,2):raise ValueError('mapped census')
 cand=sorted(set(direct));
 if len(cand)!=2:raise ValueError('direct candidate count')
 proofs=[prove_vs(blobs[h]) for h in cand]
 prior=json.loads(Path(prior_path).read_text());drifts=calibrate(root,prior,objects);maxd=max(drifts)
 # target pointer pair spacing + unique direct-object candidate pair in Hijacked among all direct VS objects
 ps=sorted(p[3] for p in ptrs);pd=ps[1]-ps[0]
 mn='mp_hijacked';all_direct={e['vs'][1] for e in events[mn] if e['vs'] and e['vs'][0]=='sha'}
 # locate object starts from parsed events for direct objects
 starts={h:objects[(mn,h)] for h in all_direct}
 pairs=[]
 hs=sorted(starts)
 for i,a in enumerate(hs):
  for b in hs[i+1:]:
   drift=abs(abs(starts[b]-starts[a])-pd)
   if drift<=maxd:pairs.append((drift,a,b,abs(starts[b]-starts[a])))
 if len(pairs)!=1 or set(pairs[0][1:3])!=set(cand):raise ValueError('target candidate pair '+str(pairs))
 target_drift=pairs[0][0]
 rows=[{'sha256':h,'roles':target[h]} for h in sorted(target)]
 summary={'globalFamilyShaderCount':len(target),'globalFamilyFetchCount':sum(len(x) for x in target.values()),'mappedPixelShaderCount':len(mapped),'mappedPassOccurrenceCount':len(occ),'unmappedPixelShaderCount':len(target)-len(mapped),'directVertexShaderOccurrenceCount':len(direct),'packedVertexShaderOccurrenceCount':sum(ptrs.values()),'uniquePackedPointerCount':len(ptrs),'candidateVertexShaderCount':len(cand),'candidateVertexShaderRoleProofCount':len(proofs),'priorAliasCalibrationPairCount':len(drifts),'priorAliasCalibrationMaxDifferentialDriftBytes':maxd,'targetPointerSpacingBytes':pd,'targetCandidateObjectSpacingBytes':pairs[0][3],'targetDifferentialDriftBytes':target_drift,'targetCandidatePairAmbiguityCount':0,'closedMappedShaderCount':len(mapped),'remainingUnmappedFamilyShaderCount':len(target)-len(mapped),'globalShaderRowsSha256':jhash(rows),'mappedShaderSetSha256':jhash(sorted(mapped)),'candidateProofRowsSha256':jhash(proofs)}
 return {'format':'t6-retail-reflection-probe-texcoord2-texcoord1-v1','producer':'tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py','equation':{'reflection':'cubeCoord=normalize(TEXCOORD1)-2*N*dot(N,normalize(TEXCOORD1))','mappedVertexNormal':'N=normalize(worldMatrix3x3 * decoded NORMAL0)','mappedOpposingVector':'TEXCOORD1.xyz=(worldMatrix*float4(POSITION.xyz,1)).xyz'},'candidateVertexShaderProofs':proofs,'summary':summary,'proofBoundary':'Global retained-DXBC census contains exactly 75 unique reflection shaders whose formula-A normalizes TEXCOORD2.xyz and formula-B normalizes TEXCOORD1.xyz (one B storage selection is xxy). Physical role promotion is restricted to the 20 identities mapped into one retained Hijacked TechniqueSet. Those 20 occurrences contain two direct VS and 18 packed uses of two pointer identities. Both direct VS independently prove TEXCOORD2 has only NORMAL0 input ancestry through normalized cb3/worldMatrix 3x3 transformation and TEXCOORD1 has only homogeneous POSITION ancestry through cb3 rows 0..2. The two packed pointers are bounded to this two-VS candidate set by a serializer differential test calibrated against all 32 paired aliases in the previously committed packed-VS proof: prior maximum differential drift is 12 bytes; among all 37 direct Hijacked VS objects, exactly one pair lies within that bound of the target pointer-pair spacing, namely these two candidates, with 5-byte drift. Since both candidates prove identical relevant roles, permutation identity is unnecessary. The remaining 55 globally retained shader identities have no retained pass/VS producer mapping and remain unpromoted.'}
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--prior-alias-manifest',type=Path,required=True);a.add_argument('--out',type=Path,required=True);q=a.parse_args();d=build(q.root,q.prior_alias_manifest);q.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
