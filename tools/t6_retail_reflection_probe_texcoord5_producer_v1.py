#!/usr/bin/env python3
"""Retained T6 TEXCOORD5 vertex-producer proof for surface-normal reflection passes.

This verifier deliberately counts only pass occurrences where both the target
pixel shader and its paired vertex shader are physically inline/direct in the
five pinned expanded retail worlds. Packed/reused vertex-shader pointers are
reported but never aliased by resemblance.

For every directly resolved paired VS it proves from SM4 operands + RDEF/ISGN/
OSGN metadata that the pixel-shader TEXCOORD5 producer is:

    TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz, 1.0)).xyz

implemented as three DP4 instructions against cb3 rows 0,1,2, whose reflected
variable name is worldMatrix, followed by a MOV to OSGN TEXCOORD5.xyz.

This proves producer arithmetic and reflected variable identity. It does not
prove CPU-side camera-relative semantics of worldMatrix and therefore does not
rename TEXCOORD5 as view direction.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

EXPECTED_TARGET_SHADERS=4086
EXPECTED_TARGET_FETCHES=4086
EXPECTED_MAPPED_SHADERS=3410
EXPECTED_UNMAPPED_SHADERS=676
EXPECTED_PASS_OCCURRENCES=5676
EXPECTED_DIRECT_VS_OCCURRENCES=64
EXPECTED_PACKED_VS_OCCURRENCES=5612
EXPECTED_UNIQUE_DIRECT_VS=16
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_OUTPUT=2; TYPE_IMM32=4; TYPE_RESOURCE=7; TYPE_CB=8
OP_DP4=17; OP_MOV=54

FOLLOW=0xffffffff; INSERT=0xfffffffe; MASK=(1<<29)-1
PASS_MAPS={
 'mp_nuketown_2020':dict(rel='mp/mp_nuketown_2020.expanded.bin',sha='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505',world=63150420,q0=565,q1=623),
 'mp_raid':dict(rel='mp/mp_raid.expanded.bin',sha='d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8',world=66275632,q0=750,q1=845),
 'mp_hijacked':dict(rel='mp/mp_hijacked.expanded.bin',sha='8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b',world=58846527,q0=751,q1=821),
 'zm_prison':dict(rel='zm_prison.expanded.bin',sha='e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487',world=82099460,q0=986,q1=1113),
 'zm_tomb':dict(rel='zm_tomb.expanded.bin',sha='4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219',world=78964845,q0=1271,q1=1327),
}
def ff_front(d):
 blocks=struct.unpack_from('<8I',d,8);p=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
 if (sc and sp!=FOLLOW) or (dc and dp!=FOLLOW) or ap!=FOLLOW:raise ValueError('bad fastfile front pointers')
 for count in (sc,dc):
  if count:
   ps=struct.unpack_from(f'<{count}I',d,p);p+=4*count
   for x in ps:
    if x==FOLLOW:p=d.index(b'\0',p)+1
 return blocks
def ff_dec(v,blocks):
 if v==0:return ('null',None,None)
 if v==FOLLOW:return ('following',None,None)
 if v==INSERT:return ('insert',None,None)
 e=(v-1)&0xffffffff;b=e>>29;o=e&MASK
 return ('packed',b,o) if b<8 and o<blocks[b] else ('bad',b,o)
def ff_cstr_short(d,p,limit=512):
 e=d.find(b'\0',p,min(len(d),p+limit))
 if e<=p:return None
 b=d[p:e]
 return b.decode('ascii') if 1<=len(b)<=limit and all(32<=x<=126 for x in b) else None
def ff_scan_tech(d,blocks,before):
 import re
 out=[];off=100000;rx=re.compile(r'[A-Za-z0-9_./$@+~:#-]+')
 while True:
  off=d.find(b'\xff\xff\xff\xff',off,before)
  if off<0:break
  if off+152<before and d[off+4]<=8 and d[off+5:off+8]==b'\0\0\0':
   ps=struct.unpack_from('<36I',d,off+8)
   if any(ps) and all(ff_dec(x,blocks)[0]!='bad' for x in ps):
    name=ff_cstr_short(d,off+152)
    if name and len(name)<=180 and rx.fullmatch(name):out.append(dict(fixedStart=off,worldVertFormat=d[off+4],name=name))
  off+=1
 return out
def ff_cstr(d,p):
 e=d.find(b'\0',p,min(len(d),p+8192))
 if e<=p or any(x<32 or x>126 for x in d[p:e]):raise ValueError(f'bad cstring at {p}')
 return d[p:e].decode('ascii'),e+1
def ff_ptr(raw,blocks):
 k,b,o=ff_dec(raw,blocks);return {'raw':f'0x{raw:08x}','kind':k,'block':b,'offset':o}
def ff_parse_shader(d,p,blocks,skind):
 s=p;namep,runtime,progp,size=struct.unpack_from('<IIII',d,p);p+=16
 if runtime:raise ValueError(f'{skind} runtime pointer nonzero at {s}')
 k=ff_dec(namep,blocks)[0];name=None
 if k in ('following','insert'):name,p=ff_cstr(d,p)
 elif k not in ('packed','null'):raise ValueError('bad shader name pointer')
 pk=ff_dec(progp,blocks)[0]
 if size:
  if pk in ('following','insert'):
   start=p;b=d[p:p+size];p+=size
   if len(b)!=size or b[:4]!=b'DXBC':raise ValueError(f'{skind} direct program not DXBC at {s}')
   program={'start':start,'bytes':size,'sha256':hashlib.sha256(b).hexdigest(),'direct':True}
  elif pk=='packed':program={'start':None,'bytes':size,'direct':False,'pointer':ff_ptr(progp,blocks)}
  else:raise ValueError('bad shader program pointer')
 else:
  if progp:raise ValueError('zero-size nonnull program')
  program={'start':None,'bytes':0,'direct':False,'pointer':None}
 return p,{'fixedStart':s,'kind':skind,'name':name,'program':program}
def ff_parse_vdecl(d,p):
 if p+116>len(d) or any(struct.unpack_from('<20I',d,p+36)):raise ValueError(f'bad vdecl at {p}')
 return p+116
def ff_parse_args(d,p,n,blocks):
 if p+12*n>len(d):raise ValueError('args eof')
 vals=[]
 for i in range(n):
  typ,loc,size,buf,u=struct.unpack_from('<HHHHI',d,p+12*i)
  if typ>=8:raise ValueError('bad arg type')
  vals.append((typ,u))
 p+=12*n
 for typ,u in vals:
  if typ in (1,7):
   k=ff_dec(u,blocks)[0]
   if k in ('following','insert'):p+=16
   elif k not in ('packed','null'):raise ValueError('bad literal pointer')
 return p
def ff_parse_technique(d,p,blocks):
 namep=struct.unpack_from('<I',d,p)[0];flags,pc=struct.unpack_from('<HH',d,p+4);p+=8;nk=ff_dec(namep,blocks)[0]
 if not 1<=pc<=16:raise ValueError(f'bad passCount {pc}')
 passes=[]
 for j in range(pc):
  o=p+24*j;vd,vs,ps=struct.unpack_from('<III',d,o);pp,po,stable,custom,pre,mt=struct.unpack_from('<6B',d,o+12);pad=struct.unpack_from('<H',d,o+18)[0];args=struct.unpack_from('<I',d,o+20)[0]
  if pad:raise ValueError('pass padding')
  passes.append({'passIndex':j,'vertexDecl':vd,'vertexShader':vs,'pixelShader':ps,'argCount':pp+po+stable,'args':args})
 p+=24*pc
 for pa in passes:
  pa['children']={}
  for fld,ck in [('vertexShader','vs'),('vertexDecl','vd'),('pixelShader','ps'),('args','args')]:
   raw=pa[fld];k=ff_dec(raw,blocks)[0];pa['children'][fld]=ff_ptr(raw,blocks)
   if k not in ('following','insert'):continue
   if ck in ('vs','ps'):
    p,sh=ff_parse_shader(d,p,blocks,ck);pa['children'][fld]['inline']=sh
   elif ck=='vd':p=ff_parse_vdecl(d,p)
   else:
    if not pa['argCount']:raise ValueError('args follow with zero count')
    p=ff_parse_args(d,p,pa['argCount'],blocks)
 name=None
 if nk in ('following','insert'):name,p=ff_cstr(d,p)
 elif nk not in ('packed','null'):raise ValueError('bad technique name pointer')
 return p,{'name':name,'passes':passes}
def ff_parse_techset(d,row,nextstart,blocks):
 s=row['fixedStart'];name,p=ff_cstr(d,s+152)
 if name!=row['name']:raise ValueError('TechniqueSet name mismatch')
 refs=[]
 for slot,raw in enumerate(struct.unpack_from('<36I',d,s+8)):
  r=ff_ptr(raw,blocks);r['slot']=slot
  if r['kind'] in ('following','insert'):
   p,t=ff_parse_technique(d,p,blocks);r['inlineTechnique']=t
  refs.append(r)
 if p!=nextstart:raise ValueError(f'{name}: end {p} != {nextstart}')
 return {'name':name,'worldVertFormat':row['worldVertFormat'],'techniqueRefs':refs}


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def signature(blob:bytes,kind:bytes):
 cc=struct.unpack_from('<I',blob,28)[0];out={};seen=0
 for off in struct.unpack_from('<'+'I'*cc,blob,32):
  if blob[off:off+4]!=kind:continue
  seen+=1;n=struct.unpack_from('<I',blob,off+4)[0];r=blob[off+8:off+8+n]
  count=struct.unpack_from('<I',r,0)[0]
  for i in range(count):
   q=8+i*24
   if q+24>len(r):raise ValueError(f'{kind.decode()}: signature entry overflow')
   no,si,sv,ct,reg,maskrw=struct.unpack_from('<6I',r,q);e=r.find(b'\0',no)
   if e<0:raise ValueError(f'{kind.decode()}: unterminated semantic')
   out[reg]=(r[no:e].decode('utf-8'),si)
 if seen!=1:raise ValueError(f'{kind.decode()}: chunk count {seen}')
 return out

def parse_all(coord,w,p,ln):
 q=coord.first_operand_pos(w,p);out=[];end=p+ln
 while q<end:
  o=coord.parse_operand(w,q);out.append(o);q=o['end']
 if q!=end:raise ValueError(f'operand walk mismatch {q}!={end}')
 return out

def writer_table(coord,w,inst):
 out=collections.defaultdict(list)
 for ii,(p,op,ln,tok) in enumerate(inst):
  if op in range(88,107) or op in (18,21,31,62):continue
  try:O=parse_all(coord,w,p,ln)
  except Exception:continue
  if not O:continue
  d=O[0]
  if d['type'] in (TYPE_TEMP,TYPE_OUTPUT) and len(d['idx'])==1 and isinstance(d['idx'][0],int):
   for ch in d['comps'] or 'x':out[(d['type'],d['idx'][0],ch)].append((ii,p,op,d,O))
 return out

def latest(tab,typ,reg,ch,before):
 a=tab.get((typ,reg,ch),())
 for q in reversed(a):
  if q[0]<before:return q
 return None

def imm_bits(coord,w,o):
 if o['type']!=TYPE_IMM32:return None
 p=o['start']+1
 if o['token']&0x80000000:
  while True:
   t=w[p];p+=1
   if not t&0x80000000:break
 return w[p]

def homogeneous_position(coord,w,inst,tab,before,opnd,isgn):
 """Return POSITION semantic if opnd is exact temp float4(POSITION.xyz,1)."""
 if opnd['type']==TYPE_INPUT and len(opnd['idx'])==1:
  # Direct POSITION.xyzw is acceptable only if source really exposes all four lanes.
  sem=isgn.get(opnd['idx'][0]);
  if sem==('POSITION',0) and opnd['comps'][:4]=='xyzw':return sem
  return None
 if opnd['type']!=TYPE_TEMP or len(opnd['idx'])!=1 or not isinstance(opnd['idx'][0],int):return None
 reg=opnd['idx'][0]
 # DP4 must read xyzw from the homogeneous temp.
 if opnd['comps'][:4]!='xyzw':return None
 wx=[latest(tab,TYPE_TEMP,reg,ch,before) for ch in 'xyz']
 ww=latest(tab,TYPE_TEMP,reg,'w',before)
 if any(x is None for x in wx) or ww is None:return None
 if len({x[0] for x in wx})!=1 or wx[0][2]!=OP_MOV:return None
 X=wx[0][4]
 if len(X)!=2:return None
 xd,xs=X
 if xd['comps']!='xyz' or xs['type']!=TYPE_INPUT or len(xs['idx'])!=1:return None
 if isgn.get(xs['idx'][0])!=('POSITION',0):return None
 try:xe=coord.effective_for_dest(xs,xd['comps'])
 except ValueError:return None
 if xe!='xyz':return None
 if ww[2]!=OP_MOV or len(ww[4])!=2:return None
 W=ww[4];wd,ws=W
 if wd['comps']!='w' or ws['type']!=TYPE_IMM32 or imm_bits(coord,w,ws)!=0x3f800000:return None
 return ('POSITION',0)

def prove_vs(coord,sem,blob:bytes):
 isgn=signature(blob,b'ISGN');osgn=signature(blob,b'OSGN')
 regs=[r for r,s in osgn.items() if s==('TEXCOORD',5)]
 if len(regs)!=1:raise ValueError(f'OSGN TEXCOORD5 register count {len(regs)}')
 oreg=regs[0];w=coord.get_program_words(blob);inst=list(coord.walk(w));tab=writer_table(coord,w,inst)
 outs=[latest(tab,TYPE_OUTPUT,oreg,ch,len(inst)) for ch in 'xyz']
 if any(x is None for x in outs) or len({x[0] for x in outs})!=1:raise ValueError('TEXCOORD5 output writer split')
 oi,opos,oop,od,O=outs[0]
 if oop!=OP_MOV or len(O)!=2 or od['comps']!='xyz':raise ValueError('TEXCOORD5 final writer is not MOV xyz')
 src=O[1]
 if src['type']!=TYPE_TEMP or len(src['idx'])!=1:return None
 try:eff=coord.effective_for_dest(src,od['comps'])
 except ValueError:return None
 if eff!='xyz':raise ValueError(f'TEXCOORD5 MOV swizzle {eff}')
 reg=src['idx'][0];dps=[latest(tab,TYPE_TEMP,reg,ch,oi) for ch in 'xyz']
 if any(x is None for x in dps) or len({x[0] for x in dps})!=3 or any(x[2]!=OP_DP4 for x in dps):raise ValueError('TEXCOORD5 source components are not three distinct DP4s')
 rows=[];vars=[];positions=[];dpindices=[]
 for ch,q in zip('xyz',dps):
  ii,p,op,d,Q=q;dpindices.append(ii)
  if len(Q)!=3 or d['comps']!=ch:raise ValueError('DP4 destination shape mismatch')
  a,b=Q[1],Q[2]
  cb=a if a['type']==TYPE_CB else b if b['type']==TYPE_CB else None
  vv=b if cb is a else a if cb is b else None
  if cb is None or vv is None or len(cb['idx'])!=2:raise ValueError('TEXCOORD5 DP4 has no direct CB row')
  if cb['comps'][:4]!='xyzw':raise ValueError('worldMatrix DP4 CB row is not xyzw')
  if homogeneous_position(coord,w,inst,tab,ii,vv,isgn)!=('POSITION',0):raise ValueError('worldMatrix DP4 vector is not homogeneous POSITION.xyz,1')
  cbname,byteoff,var=sem.cb_var_at(blob,cb['idx'][0],cb['idx'][1],cb['comps'][0])
  rows.append((cb['idx'][0],cb['idx'][1],byteoff));vars.append((cbname,var));positions.append(isgn.get(vv['idx'][0]) if vv['type']==TYPE_INPUT else ('POSITION',0))
 expected=[(3,0,0),(3,1,16),(3,2,32)]
 if rows!=expected:raise ValueError(f'worldMatrix row binding {rows}')
 if vars!=[('dlights','worldMatrix')]*3:raise ValueError(f'worldMatrix reflected variable identities {vars}')
 return {'osgnRegister':oreg,'inputSemantic':'POSITION0','constantBuffer':'dlights','constantBufferRegister':3,'variable':'worldMatrix','rowElements':[0,1,2],'rowByteOffsets':[0,16,32],'dp4InstructionIndices':dpindices,'outputMovInstructionIndex':oi,'equation':'TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz'}

def collect_target_shaders(root,coord,mip,weight,angular,sem,surf,shared,guard):
 allref={}
 for mn,(rel,sha) in guard.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=sha:raise ValueError(f'{mn}: expanded SHA mismatch {actual}')
  valid,_=guard.scan_map(path)
  for hh,(blob,res) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in res):allref.setdefault(hh,(blob,res))
 target=collections.Counter()
 for hh,(blob,res) in sorted(allref.items()):
  sg=surf.input_signature(blob);w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,_=shared.prep_shader(coord,weight,w,inst)
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);rr,ss=O[2],O[3]
   if not(rr['type']==TYPE_RESOURCE and ss['type']==6 and rr['idx']==[15] and ss['idx']==[15]):continue
   roles=surf.formula_roles(coord,w,inst,latest,si,p,op)
   if roles and surf.prove_surface_normal(coord,mip,weight,angular,sem,guard,w,inst,parsed,res,latest,sg,roles):target[hh]+=1
 if (len(target),sum(target.values()))!=(EXPECTED_TARGET_SHADERS,EXPECTED_TARGET_FETCHES):raise ValueError(f'target shader/fetch count {(len(target),sum(target.values()))}')
 return target

def collect_pass_pairs(root):
 pairs=collections.defaultdict(list);vs_blobs={};map_rows=[]
 for mn,cfg in PASS_MAPS.items():
  path=root/cfg['rel'];d=path.read_bytes();actual=hashlib.sha256(d).hexdigest()
  if actual!=cfg['sha']:raise ValueError(f'{mn}: source mismatch {actual}')
  blocks=ff_front(d);count=cfg['q1']-cfg['q0']+1;rows=ff_scan_tech(d,blocks,cfg['world'])[-count:]
  if len(rows)!=count:raise ValueError(f'{mn}: TechniqueSet count {len(rows)}')
  parsed=[]
  for i,r in enumerate(rows):
   nxt=rows[i+1]['fixedStart'] if i+1<len(rows) else cfg['world'];parsed.append(ff_parse_techset(d,r,nxt,blocks))
  for ts in parsed:
   for tr in ts['techniqueRefs']:
    it=tr.get('inlineTechnique')
    if not it:continue
    for pa in it['passes']:
     ps=pa['children']['pixelShader'];vs=pa['children']['vertexShader'];pi=ps.get('inline');vi=vs.get('inline')
     if not pi or not pi['program']['direct']:continue
     pp=pi['program'];ph=pp['sha256']
     rec={'map':mn,'techniqueSet':ts['name'],'worldVertFormat':ts['worldVertFormat'],'slot':tr['slot'],'passIndex':pa['passIndex'],'vertexShaderKind':vs['kind'],'vertexShaderBlock':vs.get('block'),'vertexShaderOffset':vs.get('offset'),'vertexShaderSha256':None}
     if vi and vi['program']['direct']:
      vp=vi['program'];vh=vp['sha256'];rec['vertexShaderSha256']=vh;blob=d[vp['start']:vp['start']+vp['bytes']]
      if hashlib.sha256(blob).hexdigest()!=vh:raise ValueError('direct VS hash mismatch')
      old=vs_blobs.setdefault(vh,blob)
      if old!=blob:raise ValueError('VS SHA collision')
     pairs[ph].append(rec)
  map_rows.append({'map':mn,'techniqueSetCount':len(parsed)})
 return pairs,vs_blobs,map_rows

def build(root:Path,coordinate_verifier:Path,mip_verifier:Path,weight_verifier:Path,angular_verifier:Path,semantic_verifier:Path,surface_verifier:Path,shared_verifier:Path,guard_path:Path):
 coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular');sem=load(semantic_verifier,'sem');surf=load(surface_verifier,'surf');shared=load(shared_verifier,'shared');guard=load(guard_path,'guard')
 target=collect_target_shaders(root,coord,mip,weight,angular,sem,surf,shared,guard);pairs,vs_blobs,map_rows=collect_pass_pairs(root)
 mapped=sorted(set(target)&set(pairs));unmapped=sorted(set(target)-set(pairs))
 occ=[];packed=direct=0;vs_counts=collections.Counter();producer_rows={};by_map=collections.Counter();by_format=collections.Counter()
 for ph in mapped:
  for r in pairs[ph]:
   occ.append((ph,r));by_map[(r['map'],'all')]+=1;by_format[(r['worldVertFormat'],'all')]+=1
   vh=r['vertexShaderSha256']
   if vh:
    direct+=1;by_map[(r['map'],'direct')]+=1;by_format[(r['worldVertFormat'],'direct')]+=1;vs_counts[vh]+=1
    if vh not in producer_rows:producer_rows[vh]=prove_vs(coord,sem,vs_blobs[vh])
   else:
    if r['vertexShaderKind']!='packed':raise ValueError(f'non-direct target VS kind {r["vertexShaderKind"]}')
    packed+=1;by_map[(r['map'],'packed')]+=1;by_format[(r['worldVertFormat'],'packed')]+=1
 if (len(mapped),len(unmapped),len(occ),direct,packed,len(vs_counts))!=(EXPECTED_MAPPED_SHADERS,EXPECTED_UNMAPPED_SHADERS,EXPECTED_PASS_OCCURRENCES,EXPECTED_DIRECT_VS_OCCURRENCES,EXPECTED_PACKED_VS_OCCURRENCES,EXPECTED_UNIQUE_DIRECT_VS):raise ValueError(f'coverage counts {(len(mapped),len(unmapped),len(occ),direct,packed,len(vs_counts))}')
 if any(q['equation']!='TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz' for q in producer_rows.values()):raise ValueError('producer equation census mismatch')
 vs_rows=[]
 for vh,n in sorted(vs_counts.items()):vs_rows.append({'sha256':vh,'directPassOccurrenceCount':n,**producer_rows[vh]})
 map_cov=[]
 for m in [x['map'] for x in map_rows]:map_cov.append({'map':m,'targetPassOccurrenceCount':by_map[(m,'all')],'directVertexShaderOccurrenceCount':by_map[(m,'direct')],'packedVertexShaderOccurrenceCount':by_map[(m,'packed')]})
 fmt_rows=[]
 for f in sorted({k[0] for k in by_format}):fmt_rows.append({'worldVertFormat':f,'targetPassOccurrenceCount':by_format[(f,'all')],'directVertexShaderOccurrenceCount':by_format[(f,'direct')],'packedVertexShaderOccurrenceCount':by_format[(f,'packed')]})
 direct_occ_rows=[]
 for ph,r in occ:
  if not r['vertexShaderSha256']:continue
  direct_occ_rows.append({'pixelShaderSha256':ph,'vertexShaderSha256':r['vertexShaderSha256'],'map':r['map'],'techniqueSet':r['techniqueSet'],'worldVertFormat':r['worldVertFormat'],'slot':r['slot'],'passIndex':r['passIndex']})
 summary={'retainedMapCount':5,'surfaceNormalTargetShaderCount':len(target),'surfaceNormalTargetFetchCount':sum(target.values()),'targetPixelShaderMappedCount':len(mapped),'targetPixelShaderUnmappedCount':len(unmapped),'targetPassOccurrenceCount':len(occ),'directVertexShaderOccurrenceCount':direct,'packedVertexShaderOccurrenceCount':packed,'uniqueDirectVertexShaderCount':len(vs_rows),'directTexcoord5ProducerProofCount':direct,'directTexcoord5ProducerFailureCount':0,'worldMatrixProducerOccurrenceCount':direct,'positionHomogeneousInputCheckCount':direct*3,'producerRowsSha256':jhash(vs_rows),'directOccurrenceRowsSha256':jhash(direct_occ_rows),'mapCoverageRowsSha256':jhash(map_cov),'formatCoverageRowsSha256':jhash(fmt_rows),'unmappedPixelShaderSetSha256':jhash(unmapped)}
 return {'format':'t6-retail-reflection-probe-texcoord5-producer-v1','producer':'tools/t6_retail_reflection_probe_texcoord5_producer_v1.py','sources':{'surfaceNormalProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_SURFACE_NORMAL_V1.json','expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},'equation':{'directProducer':'TEXCOORD5.xyz = (worldMatrix * float4(POSITION.xyz,1)).xyz','rdefVariable':'dlights.worldMatrix','constantBufferRegister':3,'matrixRows':[0,1,2]},'directVertexShaderRows':vs_rows,'mapCoverage':map_cov,'formatCoverage':fmt_rows,'summary':summary,'proofBoundary':'Direct retained-TechniqueSet/pass + VS SM4/RDEF proof for the surface-normal reflection subset. Of 4,086 target pixel shaders, 3,410 are physically mapped into retained inline TechniqueSet passes, yielding 5,676 pass occurrences. Only 64 of those occurrences contain a physically inline/direct paired vertex shader (16 unique VS payloads); all 64 prove TEXCOORD5.xyz is emitted from three DP4s over homogeneous POSITION.xyz,1 and reflected dlights.worldMatrix rows cb3[0..2], followed by MOV to OSGN TEXCOORD5.xyz. The remaining 5,612 pass occurrences use packed VS pointers and 676 target PS hashes are not present in the parsed direct-pass map; neither group is aliased or guessed. This stage proves vertex-producer arithmetic/variable identity only and does not assign camera/view semantics to worldMatrix or TEXCOORD5.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));ap.add_argument('--semantic-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_semantics_v1.py'));ap.add_argument('--surface-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_surface_normal_v1.py'));ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.surface_verifier,a.shared_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
