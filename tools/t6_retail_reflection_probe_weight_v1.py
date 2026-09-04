#!/usr/bin/env python3
"""Retained T6 reflection-probe RGB decode and final-output ancestry proof.

For every t15/s15 reflectionProbeSampler cube fetch in the five pinned retail
worlds this verifier proves, directly from SM4 operands, that:

    decodedProbe.rgb = probe.rgb * (probe.a + 1e-6)

is the first consumer of the sampled RGB values. It then executes a branch-aware
value-dependency taint over the supported retained SM4 instruction population
and requires each semantic probe RGB channel to remain an ancestor of the
matching final o0.rgb channel. Branch conditions are not treated as value
operands; IF/ELSE states are executed independently and union-merged at ENDIF.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

OP_ADD=0; OP_DISCARD=13; OP_DP2=15; OP_DP3=16; OP_DP4=17; OP_ELSE=18; OP_ENDIF=21
OP_IF=31; OP_MAD=50; OP_MOV=54; OP_MOVC=55; OP_MUL=56; OP_RET=62; OP_SINCOS=77
TYPE_TEMP=0; TYPE_OUTPUT=2; TYPE_IMM32=4; TYPE_SAMPLER=6; TYPE_RESOURCE=7
BIAS_BITS=0x358637bd
EXPECTED_REFLECTION_SHADERS=5868; EXPECTED_FETCHES=5888
DCL_OPS=set(range(88,107))
DP_WIDTH={OP_DP2:2,OP_DP3:3,OP_DP4:4}


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def parse_all(c,w,p,ln):
 q=c.first_operand_pos(w,p);end=p+ln;out=[]
 while q<end:
  o=c.parse_operand(w,q);out.append(o);q=o['end']
 if q!=end:raise ValueError(f'operand walk mismatch at {p}: {q}!={end}')
 return out

def imm32_bits(w,o):
 if o['type']!=TYPE_IMM32:raise ValueError('operand is not immediate32')
 p=o['start']+1
 if o['token']&0x80000000:
  while True:
   if p>=len(w):raise ValueError('truncated extended immediate operand')
   t=w[p];p+=1
   if not t&0x80000000:break
 if p>=len(w):raise ValueError('missing immediate32 payload')
 return w[p]

def eff(src,dst_components):
 s=src['comps']
 if len(s)==1:return s*len(dst_components)
 if len(s)>=4:return ''.join(s['xyzw'.index(ch)] for ch in dst_components)
 if len(s)==len(dst_components):return s
 raise ValueError(f'cannot map source components {s!r} to destination {dst_components!r}')

def sample_semantic_channels(res,dst_components):
 return eff(res,dst_components)

def storage_for_semantic(dst,res,semantic):
 chans=sample_semantic_channels(res,dst['comps']);hits=[d for d,ch in zip(dst['comps'],chans) if ch==semantic]
 if len(hits)!=1:raise ValueError(f'sample semantic channel {semantic} maps to {hits}')
 return hits[0]

def writer_same_sample(c,inst,w,before_idx,operand,component,sample_idx):
 if operand['type']!=TYPE_TEMP or len(operand['idx'])!=1 or not isinstance(operand['idx'][0],int):return False
 wr=c.latest_writer(inst,w,before_idx,operand['idx'][0],component)
 return wr is not None and wr[0]==sample_idx

def source_components_read(op,O,src_index):
 src=O[src_index]
 if src['type']!=TYPE_TEMP:return set()
 if op in DP_WIDTH:return set(src['comps'][:DP_WIDTH[op]])
 if op in (OP_IF,OP_DISCARD):return set(src['comps'] or 'x')
 if op==OP_SINCOS:
  z=set()
  for d in O[:2]:
   try:z.update(eff(src,d['comps']))
   except ValueError:z.update(src['comps'])
  return z
 if op in (69,70,71,72,73,74):return set(src['comps'])
 if O and O[0]['type'] in (TYPE_TEMP,TYPE_OUTPUT):
  try:return set(eff(src,O[0]['comps']))
  except ValueError:return set(src['comps'])
 return set(src['comps'])

def source_operands(op,O):
 if op in DCL_OPS or op in (OP_RET,OP_ELSE,OP_ENDIF):return []
 if op in (OP_IF,OP_DISCARD):return list(enumerate(O))
 if op==OP_SINCOS:return list(enumerate(O[2:],start=2))
 if not O:return []
 return list(enumerate(O[1:],start=1))

def first_rgb_consumer(c,w,inst,sidx,sd,res):
 reg=sd['idx'][0];storage={ch:storage_for_semantic(sd,res,ch) for ch in 'xyz'};first={}
 for j in range(sidx+1,len(inst)):
  p,op,ln,tok=inst[j]
  if op in DCL_OPS or op in (OP_RET,OP_ELSE,OP_ENDIF):continue
  O=parse_all(c,w,p,ln)
  for src_index,src in source_operands(op,O):
   if src['type']!=TYPE_TEMP or src['idx']!=[reg]:continue
   read=source_components_read(op,O,src_index)
   for semantic,component in storage.items():
    if semantic not in first and component in read:first[semantic]=(j,p,op,O,src_index)
  if len(first)==3:break
  if O and op not in (OP_IF,OP_DISCARD) and op!=OP_SINCOS:
   d=O[0]
   if d['type']==TYPE_TEMP and d['idx']==[reg]:
    for semantic,component in storage.items():
     if semantic not in first and component in d['comps']:
      raise ValueError(f'sample RGB {semantic} overwritten before first use')
  elif op==OP_SINCOS:
   for d in O[:2]:
    if d['type']==TYPE_TEMP and d['idx']==[reg]:
     for semantic,component in storage.items():
      if semantic not in first and component in d['comps']:
       raise ValueError(f'sample RGB {semantic} overwritten by SINCOS before first use')
 if len(first)!=3:raise ValueError(f'not all sample RGB components have a first consumer: {first.keys()}')
 if len({v[0] for v in first.values()})!=1:raise ValueError('sample RGB components do not share the same first consumer')
 j,p,op,O,_=next(iter(first.values()))
 if op!=OP_MUL:raise ValueError(f'first RGB consumer opcode is {op}, not MUL')
 if len(O)!=3:raise ValueError('first RGB MUL does not have three operands')
 md,a,b=O;candidates=[]
 for sm,other in ((a,b),(b,a)):
  if sm['type']!=TYPE_TEMP or sm['idx']!=[reg]:continue
  if eff(sm,md['comps'])!='xyz':continue
  ok=True
  for semantic,component in storage.items():
   if not writer_same_sample(c,inst,w,j,sm,storage[semantic],sidx):ok=False;break
  if not ok:continue
  oe=eff(other,md['comps'])
  if len(set(oe))!=1:continue
  candidates.append((sm,other,oe[0]))
 if len(candidates)!=1:raise ValueError('first RGB MUL sample/scalar split is not unique')
 sm,other,other_comp=candidates[0]
 if other['type']!=TYPE_TEMP or len(other['idx'])!=1 or not isinstance(other['idx'][0],int):raise ValueError('RGB decode multiplier is not TEMP scalar')
 aw=c.latest_writer(inst,w,j,other['idx'][0],other_comp)
 if aw is None or aw[2]!=OP_ADD:raise ValueError('RGB decode multiplier is not produced by ADD')
 ai,ap,aop,ad=aw;add,aq=c.parse_n(w,ap,3)
 if aq!=ap+inst[ai][2]:raise ValueError('RGB decode ADD operand length mismatch')
 adst,s1,s2=add
 if other_comp not in adst['comps']:raise ValueError('RGB multiplier component absent from ADD destination')
 pos=adst['comps'].index(other_comp);resolved=[]
 for alpha,imm in ((s1,s2),(s2,s1)):
  if imm['type']!=TYPE_IMM32 or imm['modifier'] is not None:continue
  if imm32_bits(w,imm)!=BIAS_BITS:continue
  ae=eff(alpha,adst['comps'])[pos]
  if alpha['type']!=TYPE_TEMP or alpha['idx']!=[reg] or alpha['modifier'] is not None:continue
  if not writer_same_sample(c,inst,w,ai,alpha,ae,sidx):continue
  if ae!=storage_for_semantic(sd,res,'w'):continue
  resolved.append((alpha,imm))
 if len(resolved)!=1:raise ValueError('RGB decode ADD is not same-sample alpha + 1e-6')
 return {'sampleIndex':sidx,'mulIndex':j,'mulDistance':j-sidx,'mulDest':md['comps'],'sampleMulSwizzle':sm['comps'],
         'scalarMulSwizzle':other['comps'],'addIndex':ai,'formula':'probe.rgb * (probe.a + 1e-6)'}

def dest_lanes(o):return list(o['comps']) if o['comps'] else ['x']
def src_lane_tags(o,dlanes,state):
 if o['type'] not in (TYPE_TEMP,TYPE_OUTPUT):return [set() for _ in dlanes]
 reg=o['idx'][0] if len(o['idx'])==1 and isinstance(o['idx'][0],int) else None
 if reg is None:return [set() for _ in dlanes]
 try:comps=eff(o,''.join(dlanes))
 except ValueError:comps=(o['comps'] or 'x')[:1]*len(dlanes)
 return [set(state.get((o['type'],reg,ch),set())) for ch in comps]
def all_src_tags(o,state):
 if o['type'] not in (TYPE_TEMP,TYPE_OUTPUT):return set()
 reg=o['idx'][0] if len(o['idx'])==1 and isinstance(o['idx'][0],int) else None
 if reg is None:return set()
 z=set()
 for ch in set(o['comps'] or 'x'):z|=state.get((o['type'],reg,ch),set())
 return z
def write_state(state,dest,vals):
 if dest['type'] not in (TYPE_TEMP,TYPE_OUTPUT):return
 reg=dest['idx'][0] if len(dest['idx'])==1 and isinstance(dest['idx'][0],int) else None
 if reg is None:return
 dl=dest_lanes(dest)
 if len(vals)!=len(dl):raise ValueError('taint write width mismatch')
 for ch,v in zip(dl,vals):state[(dest['type'],reg,ch)]=set(v)
def copy_state(s):return {k:set(v) for k,v in s.items()}
def merge_state(a,b):return {k:set(a.get(k,set()))|set(b.get(k,set())) for k in set(a)|set(b)}

def output_ancestry(c,w,inst):
 state={};stack=[];fetchno=0;tags=[]
 for ii,(p,op,ln,tok) in enumerate(inst):
  if op in DCL_OPS or op==OP_RET:continue
  if op==OP_IF:
   stack.append({'entry':copy_state(state),'then':None,'inThen':True});continue
  if op==OP_ELSE:
   if not stack or not stack[-1]['inThen']:raise ValueError('unmatched ELSE')
   fr=stack[-1];fr['then']=copy_state(state);fr['inThen']=False;state=copy_state(fr['entry']);continue
  if op==OP_ENDIF:
   if not stack:raise ValueError('unmatched ENDIF')
   fr=stack.pop()
   if fr['inThen']:then=copy_state(state);els=fr['entry']
   else:then=fr['then'];els=copy_state(state)
   state=merge_state(then,els);continue
  if op==OP_DISCARD:continue
  O=parse_all(c,w,p,ln)
  if not O:continue
  if op==OP_SINCOS:
   if len(O)!=3:raise ValueError('SINCOS arity')
   for d in O[:2]:write_state(state,d,src_lane_tags(O[2],dest_lanes(d),state))
   continue
  d=O[0];dl=dest_lanes(d)
  if op in c.SAMPLE_OPS:
   if len(O)<4:raise ValueError('sample arity')
   coorddeps=set()
   for src in O[1:2]+O[4:]:coorddeps|=all_src_tags(src,state)
   vals=[set(coorddeps) for _ in dl];res,sam=O[2],O[3]
   if res['type']==TYPE_RESOURCE and sam['type']==TYPE_SAMPLER and res['idx']==[15] and sam['idx']==[15]:
    chans=sample_semantic_channels(res,d['comps'])
    for k,ch in enumerate(chans):
     if ch in 'xyz':
      tag=(fetchno,ch);vals[k].add(tag);tags.append(tag)
    fetchno+=1
   write_state(state,d,vals);continue
  if op in DP_WIDTH:
   width=DP_WIDTH[op];z=set()
   for src in O[1:]:
    if src['type'] not in (TYPE_TEMP,TYPE_OUTPUT):continue
    reg=src['idx'][0] if len(src['idx'])==1 and isinstance(src['idx'][0],int) else None
    if reg is None:continue
    comps=src['comps'][:width] if len(src['comps'])>=width else src['comps'] or 'x'
    for ch in comps:z|=state.get((src['type'],reg,ch),set())
   write_state(state,d,[z for _ in dl]);continue
  vals=[set() for _ in dl]
  for src in O[1:]:
   q=src_lane_tags(src,dl,state)
   for k,z in enumerate(q):vals[k]|=z
  write_state(state,d,vals)
 if stack:raise ValueError('unterminated IF stack')
 outs=[state.get((TYPE_OUTPUT,0,ch),set()) for ch in 'xyz']
 if len(tags)!=fetchno*3:raise ValueError(f'reflection RGB tag count {len(tags)} != {fetchno*3}')
 checks=0;fails=0
 for f in range(fetchno):
  for ci,ch in enumerate('xyz'):
   checks+=1
   if (f,ch) not in outs[ci]:fails+=1
 return {'fetchCount':fetchno,'checkCount':checks,'failureCount':fails,'outputTagCardinality':tuple(len(x) for x in outs)}

def build(root:Path,coordinate_verifier:Path=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'),guard_path:Path=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py')):
 c=load(coordinate_verifier,'coord');g=load(guard_path,'guard');all_ref={};map_rows=[]
 for mapname,(rel,expected_sha) in g.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=expected_sha:raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  valid,_=g.scan_map(path);n=0
  for hh,(blob,resources) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in resources):
    n+=1;old=all_ref.setdefault(hh,(blob,resources,set()))
    if old[0]!=blob:raise ValueError('reflection shader SHA collision')
    old[2].add(mapname)
  map_rows.append({'map':mapname,'validDxbcCount':len(valid),'reflectionProbeShaderCount':n})
 if len(all_ref)!=EXPECTED_REFLECTION_SHADERS:raise ValueError(f'reflection shader count {len(all_ref)}')
 rows=[];fetch_total=0;distance=collections.Counter();pack=collections.Counter();outcards=collections.Counter();ancestry=failures=0;sampleops=collections.Counter()
 for hh,(blob,resmeta,maps) in sorted(all_ref.items()):
  w=c.get_program_words(blob);inst=list(c.walk(w));local=[]
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in c.SAMPLE_OPS:continue
   O,q=c.parse_sample(w,p,op)
   if q!=p+ln:raise ValueError('sample operand length mismatch')
   sd,co,res,sam=O[:4]
   if res['type']!=TYPE_RESOURCE or sam['type']!=TYPE_SAMPLER or res['idx']!=[15] or sam['idx']!=[15]:continue
   z=first_rgb_consumer(c,w,inst,si,sd,res);local.append(z);fetch_total+=1;distance[z['mulDistance']]+=1
   pack[(z['mulDest'],z['sampleMulSwizzle'],z['scalarMulSwizzle'])]+=1;sampleops[c.SAMPLE_OPS[op]]+=1
  if not local:raise ValueError(f'{hh}: reflected shader has no t15/s15 sample')
  a=output_ancestry(c,w,inst)
  if a['fetchCount']!=len(local):raise ValueError(f'{hh}: taint fetch count mismatch')
  ancestry+=a['checkCount'];failures+=a['failureCount'];outcards[a['outputTagCardinality']]+=1
  rows.append({'sha256':hh,'maps':sorted(maps),'fetchCount':len(local),'firstMulDistanceCounts':dict(sorted(collections.Counter(x['mulDistance'] for x in local).items())),
               'alignedFinalRgbAncestryCheckCount':a['checkCount'],'outputTagCardinality':list(a['outputTagCardinality'])})
 if fetch_total!=EXPECTED_FETCHES:raise ValueError(f'reflection fetch count {fetch_total}')
 if failures:raise ValueError(f'final aligned RGB ancestry failures {failures}')
 if distance!={3:5858,4:30}:raise ValueError(f'first MUL distance census {distance}')
 if sampleops!={'SAMPLE_L':5879,'SAMPLE_B':9}:raise ValueError(f'sample opcode census {sampleops}')
 expected_cards={(1,1,1):5234,(3,3,3):470,(1,1,2):128,(2,2,2):20,(1,2,2):16}
 if dict(outcards)!=expected_cards:raise ValueError(f'output tag cardinality census {outcards}')
 pack_rows=[{'mulDest':k[0],'sampleMulSwizzle':k[1],'scalarMulSwizzle':k[2],'count':v} for k,v in sorted(pack.items())]
 card_rows=[{'o0RgbTagCardinality':list(k),'shaderCount':v} for k,v in sorted(outcards.items())]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'reflectionCubeFetchCount':fetch_total,
          'sampleLOpcodeCount':sampleops['SAMPLE_L'],'sampleBOpcodeCount':sampleops['SAMPLE_B'],
          'firstRgbConsumerMulCount':fetch_total,'firstRgbConsumerFailureCount':0,'alphaBiasBits':f'{BIAS_BITS:08x}',
          'firstMulDistance3Count':distance[3],'firstMulDistance4Count':distance[4],
          'finalAlignedRgbAncestryCheckCount':ancestry,'finalAlignedRgbAncestryFailureCount':failures,
          'shaderRowsSha256':jhash(rows),'firstMulPackingRowsSha256':jhash(pack_rows),'outputTagCardinalityRowsSha256':jhash(card_rows)}
 return {'format':'t6-retail-reflection-probe-weight-v1','producer':'tools/t6_retail_reflection_probe_weight_v1.py',
         'equation':{'decodedProbeRgb':'probe.rgb * (probe.a + 1e-6)','alphaBiasBits':f'{BIAS_BITS:08x}'},
         'sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json','mipProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_MIP_V1.json',
                    'rdefGuard':'manifests/render/T6_RETAIL_REFLECTION_PROBE_RDEF_GUARD_V1.json',
                    'expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in g.SOURCES.items()}},
         'mapCoverage':map_rows,'firstMulPackingPatterns':pack_rows,'outputTagCardinalityPatterns':card_rows,'summary':summary,
         'proofBoundary':'Direct retained-SM4 proof over all 5,888 t15/s15 reflectionProbeSampler cube fetches in 5,868 unique reflected shaders. For each fetch, all semantic RGB sample components share the same first consumer MUL; its replicated scalar multiplier is produced by ADD of that exact same sample alpha and immediate 0x358637bd (~1e-6), proving decodedProbe.rgb = probe.rgb * (probe.a + 1e-6). A branch-aware lane-level value-taint then requires each probe x/y/z tag to be an ancestor of matching final o0.x/y/z, yielding 17,664 aligned RGB ancestry checks with zero failures. IF/ELSE states are union-merged as potential value dataflow; control dependence is not promoted to value ancestry. This does not yet simplify the later Fresnel/specular/material weighting between decoded probe RGB and final output, nor assign a physical meaning to every mip-control source.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
