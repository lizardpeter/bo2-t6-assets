#!/usr/bin/env python3
"""Retained T6 instruction-level reflection-probe cube-coordinate proof.

For every strictly valid embedded DXBC program in the five pinned retail worlds
that reflects `reflectionProbeSampler`, this verifier:
- parses the SHDR/SHEX SM4 token stream fail-closed;
- finds every SAMPLE* instruction using resource t15 and sampler s15;
- proves the cube-coordinate temp's three consumed components are last written
  together by MAD;
- proves that MAD is B + A * (-(2 * dot(A,B)));
- proves both A and B are normalized immediately beforehand by
  raw * rsq(dot(raw,raw)).

Names A/B are deliberately mathematical only. Physical interpretation of which
raw vector is the surface normal/view/incident vector is a separate connection.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

SAMPLE_OPS={69:'SAMPLE',70:'SAMPLE_C',71:'SAMPLE_C_LZ',72:'SAMPLE_L',73:'SAMPLE_D',74:'SAMPLE_B'}
SAMPLE_ARITY={69:4,70:5,71:5,72:5,73:6,74:5}
WRITER_OPS={0,16,50,56,68,69,70,71,72,73,74}
OP_ADD=0; OP_DP3=16; OP_MAD=50; OP_MUL=56; OP_RSQ=68
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_SAMPLER=6; TYPE_RESOURCE=7
RESOURCE_BIND=15
EXPECTED_MAPS={
 'mp_nuketown_2020':(1972,1285),'mp_raid':(3064,2063),'mp_hijacked':(2299,1722),
 'zm_prison':(3920,3158),'zm_tomb':(2839,1979)}

def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def get_program_words(blob:bytes):
 count=struct.unpack_from('<I',blob,28)[0]
 for i in range(count):
  off=struct.unpack_from('<I',blob,32+4*i)[0]
  tag=blob[off:off+4];size=struct.unpack_from('<I',blob,off+4)[0]
  if tag in (b'SHDR',b'SHEX'):
   p=blob[off+8:off+8+size]
   if len(p)%4:raise ValueError('program payload not DWORD aligned')
   w=list(struct.unpack('<'+'I'*(len(p)//4),p))
   if len(w)<2 or w[1]!=len(w):raise ValueError('declared program DWORD length mismatch')
   return w
 raise ValueError('missing SHDR/SHEX')

def walk(w):
 p=2
 while p<len(w):
  tok=w[p];op=tok&0x7ff;ln=(tok>>24)&0x7f
  if op==53:
   if p+1>=len(w):raise ValueError('truncated customdata')
   ln=w[p+1]
  if ln<=0 or p+ln>len(w):raise ValueError(f'instruction bounds at {p} op={op} len={ln}')
  yield p,op,ln,tok
  p+=ln
 if p!=len(w):raise ValueError('instruction walk did not end at declared program length')

def parse_operand(w,p):
 start=p;tok=w[p];p+=1;exts=[]
 if tok&0x80000000:
  while True:
   if p>=len(w):raise ValueError('truncated extended operand')
   et=w[p];exts.append(et);p+=1
   if not et&0x80000000:break
 dim=(tok>>20)&3;idx=[]
 for d in range(dim):
  rep=(tok>>(22+3*d))&7
  if rep==0:
   idx.append(w[p]);p+=1
  elif rep==1:
   idx.append((w[p],w[p+1]));p+=2
  elif rep==2:
   sub=parse_operand(w,p);idx.append(('relative',sub));p=sub['end']
  elif rep==3:
   imm=w[p];p+=1;sub=parse_operand(w,p);p=sub['end'];idx.append((imm,'relative',sub))
  elif rep==4:
   imm=(w[p],w[p+1]);p+=2;sub=parse_operand(w,p);p=sub['end'];idx.append((imm,'relative',sub))
  else:raise ValueError(f'unsupported operand index representation {rep}')
 comp=tok&3;sel=(tok>>2)&3;typ=(tok>>12)&0xff
 if typ in (4,5):
  value_count=1 if comp==1 else 4 if comp==2 else 0
  p+=value_count*(2 if typ==5 else 1)
  if p>len(w):raise ValueError('truncated immediate operand')
 if comp==2:
  if sel==0:comps=''.join(c for k,c in enumerate('xyzw') if tok&(1<<(4+k)))
  elif sel==1:
   sw=(tok>>4)&0xff;comps=''.join('xyzw'[(sw>>(2*k))&3] for k in range(4))
  elif sel==2:comps='xyzw'[(tok>>4)&3]
  else:raise ValueError('reserved 4-component selection mode')
 elif comp==1:comps='x'
 elif comp in (0,3):comps=''
 else:raise ValueError('invalid component mode')
 modifier=None
 for et in exts:
  etype=et&0x3f
  if etype==1:
   mod=(et>>6)&0xff
   if mod not in (0,1,2,3):raise ValueError(f'unknown source modifier {mod}')
   modifier={0:None,1:'neg',2:'abs',3:'absneg'}[mod]
 return {'type':typ,'idx':idx,'comps':comps,'modifier':modifier,'end':p,'token':tok,'start':start}

def first_operand_pos(w,p):
 q=p+1
 if w[p]&0x80000000:
  while True:
   if q>=len(w):raise ValueError('truncated extended opcode')
   t=w[q];q+=1
   if not t&0x80000000:break
 return q

def parse_n(w,p,n):
 q=first_operand_pos(w,p);out=[]
 for _ in range(n):
  x=parse_operand(w,q);out.append(x);q=x['end']
 return out,q

def parse_sample(w,p,op):
 return parse_n(w,p,SAMPLE_ARITY[op])

def dest(w,p,op):
 if op not in WRITER_OPS:return None
 try:return parse_operand(w,first_operand_pos(w,p))
 except (ValueError,IndexError,struct.error):return None

def latest_writer(inst,w,before_idx,reg,component):
 for i in range(before_idx-1,-1,-1):
  p,op,ln,tok=inst[i];d=dest(w,p,op)
  if d and d['type']==TYPE_TEMP and d['idx']==[reg] and component in d['comps']:
   return i,p,op,d
 return None

def effective_for_dest(src,dst_components):
 s=src['comps']
 if len(s)<4:raise ValueError('vector source lacks 4-lane selection')
 return ''.join(s['xyzw'.index(ch)] for ch in dst_components)

def base_sig(x):
 return (x['type'],tuple(x['idx']),x['modifier'])

def prove_normalized_vector(inst,w,before_idx,v):
 if v['type']!=TYPE_TEMP or len(v['idx'])!=1 or not isinstance(v['idx'][0],int):raise ValueError('dot vector is not direct TEMP')
 logical=v['comps'][:3]
 if len(logical)!=3:raise ValueError('dot vector does not expose three components')
 reg=v['idx'][0]
 ws=[latest_writer(inst,w,before_idx,reg,ch) for ch in set(logical)]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:raise ValueError('normalized vector components do not share one writer')
 wi,wp,wop,wd=ws[0]
 if wop!=OP_MUL:raise ValueError('normalized vector writer is not MUL')
 mul,q=parse_n(w,wp,3)
 if q!=wp+next(x[2] for x in inst if x[0]==wp):raise ValueError('MUL operand length mismatch')
 mdst,s1,s2=mul;candidates=[]
 for scalar,raw in ((s1,s2),(s2,s1)):
  try:
   seff=effective_for_dest(scalar,mdst['comps']);reff=effective_for_dest(raw,mdst['comps'])
  except ValueError:continue
  if len(seff)==3 and len(set(seff))==1 and len(reff)==3 and len(set(reff))>=2:candidates.append((scalar,raw,seff,reff))
 if len(candidates)!=1:raise ValueError('normalized MUL scalar/vector split unresolved')
 scalar,raw,seff,reff=candidates[0]
 if scalar['type']!=TYPE_TEMP or len(scalar['idx'])!=1 or not isinstance(scalar['idx'][0],int):raise ValueError('normalization scale is not TEMP')
 rw=latest_writer(inst,w,wi,scalar['idx'][0],seff[0])
 if rw is None or rw[2]!=OP_RSQ:raise ValueError('normalization scale is not produced by RSQ')
 ri,rp,rop,rd=rw;rsq,_=parse_n(w,rp,2);rinput=rsq[1]
 if rinput['type']!=TYPE_TEMP or len(rinput['idx'])!=1 or not isinstance(rinput['idx'][0],int):raise ValueError('RSQ input is not TEMP scalar')
 qw=latest_writer(inst,w,ri,rinput['idx'][0],rinput['comps'][0])
 if qw is None or qw[2]!=OP_DP3:raise ValueError('RSQ input is not self-DP3')
 qi,qp,qop,qd=qw;dp,_=parse_n(w,qp,3);a,b=dp[1],dp[2]
 if base_sig(a)!=base_sig(b) or a['comps'][:3]!=b['comps'][:3]:raise ValueError('normalization DP3 is not self-dot')
 if base_sig(raw)!=base_sig(a) or reff!=a['comps'][:3]:raise ValueError('normalization MUL raw vector differs from self-dot vector')
 return {'rawType':'INPUT' if raw['type']==TYPE_INPUT else 'TEMP' if raw['type']==TYPE_TEMP else f'TYPE{raw["type"]}',
         'rawRegister':raw['idx'][0] if len(raw['idx'])==1 and isinstance(raw['idx'][0],int) else None,
         'rawComponents':reff,'storageComponents':mdst['comps']}

def prove_sample(w,inst,sidx,p,op):
 sample,q=parse_sample(w,p,op)
 if q!=p+inst[sidx][2]:raise ValueError(f'sample operand length mismatch op={op} at {p}: parsed={q-p} declared={inst[sidx][2]}')
 dst,coord,res,sam=sample[:4]
 if res['type']!=TYPE_RESOURCE or sam['type']!=TYPE_SAMPLER or res['idx']!=[RESOURCE_BIND] or sam['idx']!=[RESOURCE_BIND]:
  return None
 logical=coord['comps'][:3]
 if coord['type']!=TYPE_TEMP or len(coord['idx'])!=1 or not isinstance(coord['idx'][0],int) or len(logical)!=3:
  raise ValueError('cube coordinate is not three-component TEMP selection')
 reg=coord['idx'][0]
 ws=[latest_writer(inst,w,sidx,reg,ch) for ch in set(logical)]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:raise ValueError('cube-coordinate components do not share one writer')
 mi,mp,mop,md=ws[0]
 if mop!=OP_MAD:raise ValueError('cube-coordinate writer is not MAD')
 mad,mq=parse_n(w,mp,4)
 if mq!=mp+inst[mi][2]:raise ValueError('MAD operand length mismatch')
 mdst,A,neg2dot,B=mad
 if neg2dot['modifier']!='neg' or len(neg2dot['comps'])<3 or len(set(neg2dot['comps'][:3]))!=1:
  raise ValueError('MAD multiplier is not a negated replicated scalar')
 scalar_comp=neg2dot['comps'][0]
 if neg2dot['type']!=TYPE_TEMP or len(neg2dot['idx'])!=1 or not isinstance(neg2dot['idx'][0],int):
  raise ValueError('MAD double-dot scalar is not TEMP')
 aw=latest_writer(inst,w,mi,neg2dot['idx'][0],scalar_comp)
 if aw is None or aw[2]!=OP_ADD:raise ValueError('MAD scalar is not produced by ADD')
 ai,ap,aop,ad=aw;add,_=parse_n(w,ap,3);s1,s2=add[1],add[2]
 sig=lambda x:(x['type'],tuple(x['idx']),x['comps'],x['modifier'])
 if sig(s1)!=sig(s2):raise ValueError('ADD does not exactly double one scalar')
 if s1['type']!=TYPE_TEMP or len(s1['idx'])!=1 or not isinstance(s1['idx'][0],int):raise ValueError('doubled scalar is not TEMP')
 dw=latest_writer(inst,w,ai,s1['idx'][0],s1['comps'][0])
 if dw is None or dw[2]!=OP_DP3:raise ValueError('doubled scalar is not produced by DP3')
 di,dp,dop,dd=dw;dot,_=parse_n(w,dp,3);d1,d2=dot[1],dot[2]
 if {base_sig(A),base_sig(B)}!={base_sig(d1),base_sig(d2)}:
  raise ValueError('MAD vectors differ from DP3 vector pair')
 na=prove_normalized_vector(inst,w,di,d1)
 nb=prove_normalized_vector(inst,w,di,d2)
 return {'opcode':SAMPLE_OPS[op],'coordStorage':logical,
         'rawVectorKinds':sorted((na['rawType'],nb['rawType'])),
         'rawVectorA':na,'rawVectorB':nb,
         'formula':'B - 2 * A * dot(A, B)'}

def prove_shader(blob:bytes):
 w=get_program_words(blob);inst=list(walk(w));samples=[]
 for i,(p,op,ln,tok) in enumerate(inst):
  if op in SAMPLE_OPS:
   z=prove_sample(w,inst,i,p,op)
   if z is not None:samples.append(z)
 if not samples:raise ValueError('reflection RDEF shader has no t15/s15 sample')
 return samples

def build(root:Path,guard_path:Path=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py')):
 g=load(guard_path,'rdef_guard');all_ref={};maps=[]
 for mapname,(rel,expected_sha) in g.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=expected_sha:raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  valid,_=g.scan_map(path);ref={}
  for hh,(blob,resources) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in resources):ref[hh]=blob
  exp=EXPECTED_MAPS[mapname]
  if (len(valid),len(ref))!=exp:raise ValueError(f'{mapname}: reflection census mismatch')
  for hh,blob in ref.items():
   old=all_ref.setdefault(hh,(blob,set()))
   if old[0]!=blob:raise ValueError('SHA collision with differing reflection bytes')
   old[1].add(mapname)
  maps.append({'map':mapname,'validDxbcCount':len(valid),'reflectionProbeShaderCount':len(ref)})
 rows=[];opcodes=collections.Counter();samples_per=collections.Counter();coord=collections.Counter();pairs=collections.Counter();total=0
 for hh,(blob,names) in sorted(all_ref.items()):
  ss=prove_shader(blob);samples_per[len(ss)]+=1;total+=len(ss)
  for x in ss:
   opcodes[x['opcode']]+=1;coord[x['coordStorage']]+=1;pairs['+'.join(x['rawVectorKinds'])]+=1
  rows.append({'sha256':hh,'maps':sorted(names),'sampleCount':len(ss),
               'sampleOpcodes':dict(sorted(collections.Counter(x['opcode'] for x in ss).items())),
               'coordStorageCounts':dict(sorted(collections.Counter(x['coordStorage'] for x in ss).items())),
               'rawVectorKindPairs':dict(sorted(collections.Counter('+'.join(x['rawVectorKinds']) for x in ss).items()))})
 if len(rows)!=5868:raise ValueError(f'unique reflection shader count {len(rows)} != 5868')
 expected_ops={'SAMPLE_B':9,'SAMPLE_L':5879}; expected_per={1:5848,2:20}; expected_coord={'xzw':8,'xyw':725,'xyz':4896,'yzw':259}; expected_pairs={'INPUT+INPUT':768,'INPUT+TEMP':5120}
 if dict(sorted(opcodes.items()))!=expected_ops:raise ValueError(f'opcode census {opcodes}')
 if dict(samples_per)!=expected_per:raise ValueError(f'samples/shader {samples_per}')
 if dict(sorted(coord.items()))!=expected_coord:raise ValueError(f'coordinate storage {coord}')
 if dict(sorted(pairs.items()))!=expected_pairs:raise ValueError(f'raw vector kinds {pairs}')
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'reflectionCubeSampleCount':5888,
          'oneSampleShaderCount':5848,'twoSampleShaderCount':20,'sampleOpcodeCounts':expected_ops,
          'resourceSamplerPairFailureCount':0,'coordinateMadCheckCount':5888,'doubleDotCheckCount':5888,
          'normalizedVectorCheckCount':11776,'reflectFormulaFailureCount':0,'coordinateStorageCounts':expected_coord,
          'rawVectorKindPairCounts':expected_pairs,'shaderRowsSha256':jhash(rows)}
 return {'format':'t6-retail-reflection-probe-coordinate-v1','producer':'tools/t6_retail_reflection_probe_coordinate_v1.py',
         'sources':{'rdefGuard':'manifests/render/T6_RETAIL_REFLECTION_PROBE_RDEF_GUARD_V1.json',
                    'expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in g.SOURCES.items()}},
         'equation':{'normalizedA':'rawA * rsq(dot(rawA,rawA))','normalizedB':'rawB * rsq(dot(rawB,rawB))',
                     'cubeCoordinate':'normalizedB - 2 * normalizedA * dot(normalizedA, normalizedB)'},
         'mapCoverage':maps,'summary':summary,
         'proofBoundary':'Direct retained-SM4 operand/dataflow proof over all 5,868 unique shaders reflecting reflectionProbeSampler in the five pinned retail worlds. All 5,888 t15/s15 cube fetches are identified from decoded SAMPLE* operands. Their three consumed coordinate components are universally produced by the exact reflect-form equation B - 2*A*dot(A,B), and both A and B are immediately normalized by raw*rsq(dot(raw,raw)). A/B are intentionally mathematical labels only: this proof does not yet assign physical normal/view semantics to either raw vector. SAMPLE_L versus SAMPLE_B opcode identity is counted exactly, but LOD/bias value semantics, Fresnel/specular weighting, final RGB ancestry, and renderer playback remain separate.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
