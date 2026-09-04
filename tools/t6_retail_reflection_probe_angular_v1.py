#!/usr/bin/env python3
"""Retained T6 reflection-probe angular/material coupling proof.

This verifier builds on the retained reflection coordinate, mip, and reciprocal
RGB-decode proofs.  For each of the 5,888 t15/s15 reflectionProbeSampler cube
fetches it finds the material factor multiplied into decoded probe RGB and then
walks that factor's value ancestry.

For the angular-linked family it requires writer identity, not register-name
identity: the DP3 operands must be the exact same two normalized values used by
the already-proven cube-coordinate reflect construction.  Every linked fetch
must then contain the same retained SM4 core:

    D = dp3_sat(U, -V)
    E = EXP(D * -9.28)       # SM4 EXP is component-wise 2^x
    C = min(E, P)

where P is value-independent of D.  The later factor arithmetic is reduced to a
canonical skeleton with all D-independent material expressions represented as
P.  This intentionally does not assign physical "normal"/"view" labels to U/V
or a universal semantic name such as roughness/gloss to P.
"""
from __future__ import annotations
import argparse, bisect, collections, functools, hashlib, importlib.util, json, struct
from pathlib import Path

EXPECTED_SHADERS=5868
EXPECTED_FETCHES=5888
NEG_9_28_BITS=0xC1147AE1
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_IMM32=4; TYPE_SAMPLER=6; TYPE_RESOURCE=7; TYPE_CB=8
OP_DP2=15; OP_DP3=16; OP_DP4=17; OP_EXP=25; OP_MUL=56; OP_MIN=51
DP_WIDTH={OP_DP2:2,OP_DP3:3,OP_DP4:4}
OPS=['add','and','break','breakc','call','callc','case','continue','continuec','cut','default','deriv_rtx','deriv_rty','discard','div','dp2','dp3','dp4','else','emit','emitthencut','endif','endloop','endswitch','eq','exp','frc','ftoi','ftou','ge','iadd','if','ieq','ige','ilt','imad','imax','imin','imul','ine','ineg','ishl','ishr','itof','label','ld','ld_ms','log','loop','lt','mad','min','max','customdata','mov','movc','mul','ne','nop','not','or','resinfo','ret','retc','round_ne','round_ni','round_pi','round_z','rsq','sample','sample_c','sample_c_lz','sample_l','sample_d','sample_b','sqrt','switch','sincos','udiv','ult','uge','umul','umad','umax','umin','ushr','utof','xor','dcl_resource','dcl_constant_buffer','dcl_sampler','dcl_index_range','dcl_gs_output_primitive_topology','dcl_gs_input_primitive','dcl_max_output_vertex_count','dcl_input','dcl_input_sgv','dcl_input_siv','dcl_output','dcl_output_sgv','dcl_output_siv','dcl_temps','dcl_indexable_temp','dcl_global_flags','reserved0','lod','gather4','sample_pos','sample_info']


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def float_bits_label(bits:int):
 return format(struct.unpack('<f',struct.pack('<I',bits))[0],'.9g')

def vector_writer_id(coord,weight,inst,w,before,opnd):
 if opnd['type']!=TYPE_TEMP or len(opnd['idx'])!=1 or not isinstance(opnd['idx'][0],int):return None
 comps=opnd['comps'][:3]
 if len(comps)!=3:return None
 ws=[weight.latest_writer_any(coord,inst,w,before,opnd['idx'][0],ch) for ch in set(comps)]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:return None
 return ws[0][0]

def coordinate_pair(coord,weight,w,inst,sidx,p,op):
 O,q=coord.parse_sample(w,p,op)
 if q!=p+inst[sidx][2]:raise ValueError('reflection sample operand walk mismatch')
 dst,cube,res,sam=O[:4]
 if not(res['type']==TYPE_RESOURCE and sam['type']==TYPE_SAMPLER and res['idx']==[15] and sam['idx']==[15]):return None
 if cube['type']!=TYPE_TEMP or len(cube['idx'])!=1 or not isinstance(cube['idx'][0],int):raise ValueError('cube coordinate is not direct TEMP')
 logical=cube['comps'][:3]
 if len(logical)!=3:raise ValueError('cube coordinate does not expose three components')
 ws=[weight.latest_writer_any(coord,inst,w,sidx,cube['idx'][0],ch) for ch in set(logical)]
 if any(x is None for x in ws) or len({x[0] for x in ws})!=1:raise ValueError('cube coordinate writer identity split')
 coord_mad=ws[0]
 if coord_mad[2]!=50:raise ValueError('cube coordinate writer is not MAD')
 M=coord_mad[4];neg2dot=M[2]
 if neg2dot['type']!=TYPE_TEMP or neg2dot['modifier']!='neg' or not neg2dot['comps']:raise ValueError('coordinate double-dot operand malformed')
 add=weight.latest_writer_any(coord,inst,w,coord_mad[0],neg2dot['idx'][0],neg2dot['comps'][0])
 if add is None or add[2]!=0:raise ValueError('coordinate doubled dot is not ADD')
 s=add[4][1]
 if s['type']!=TYPE_TEMP or not s['comps']:raise ValueError('coordinate ADD source is not TEMP scalar')
 dot=weight.latest_writer_any(coord,inst,w,add[0],s['idx'][0],s['comps'][0])
 if dot is None or dot[2]!=OP_DP3:raise ValueError('coordinate scalar source is not DP3')
 d1,d2=dot[4][1],dot[4][2]
 w1=vector_writer_id(coord,weight,inst,w,dot[0],d1);w2=vector_writer_id(coord,weight,inst,w,dot[0],d2)
 if w1 is None or w2 is None or w1==w2:raise ValueError('coordinate normalized vector writers unresolved')
 return {'pair':frozenset((w1,w2)),'coordinateDotIndex':dot[0],'coordinateMadIndex':coord_mad[0]}

def first_use(weight,coord,inst,w,start,reg,comps):
 first={}
 for j in range(start+1,len(inst)):
  p,op,ln,tok=inst[j]
  if op in weight.DCL_OPS or op in (weight.OP_RET,weight.OP_ELSE,weight.OP_ENDIF):continue
  O=weight.parse_all(coord,w,p,ln)
  for ix,src in weight.source_operands(op,O):
   if src['type']!=TYPE_TEMP or src['idx']!=[reg]:continue
   used=weight.source_components_read(op,O,ix)
   for ch in comps:
    if ch not in first and ch in used:first[ch]=(j,p,op,O,ix)
  if len(first)==len(comps):break
 return first

def second_factor(weight,coord,w,inst,decode):
 decode_mul=decode['mulIndex'];md=weight.parse_all(coord,w,inst[decode_mul][0],inst[decode_mul][2])[0]
 if md['type']!=TYPE_TEMP or len(md['idx'])!=1:raise ValueError('decoded RGB destination is not direct TEMP')
 fu=first_use(weight,coord,inst,w,decode_mul,md['idx'][0],md['comps'])
 if len(fu)!=len(md['comps']) or len({x[0] for x in fu.values()})!=1:raise ValueError('decoded RGB first use is split')
 j,p,op,O,ix=next(iter(fu.values()))
 if op!=OP_MUL:raise ValueError('decoded RGB first downstream consumer is not MUL')
 d,a,b=O;cands=[]
 for decoded,other in ((a,b),(b,a)):
  if decoded['type']!=TYPE_TEMP or decoded['idx']!=[md['idx'][0]]:continue
  try:ee=weight.eff(decoded,d['comps'])
  except ValueError:continue
  if all((wr:=weight.latest_writer_any(coord,inst,w,j,decoded['idx'][0],ch)) and wr[0]==decode_mul for ch in set(ee)):
   cands.append((j,d,other))
 if len(cands)!=1:raise ValueError('decoded RGB/material factor split is not unique')
 return cands[0]

def matching_pair_dots(coord,weight,w,inst,before,factor,pair):
 todo=[];seen=set();hits=[]
 if factor['type']!=TYPE_TEMP:return hits
 for ch in set(factor['comps'] or 'x'):todo.append((before,factor['idx'][0],ch))
 while todo:
  b,reg,ch=todo.pop();key=(b,reg,ch)
  if key in seen:continue
  seen.add(key);wr=weight.latest_writer_any(coord,inst,w,b,reg,ch)
  if wr is None:continue
  wi,p,op,d,O=wr
  if op==OP_DP3:
   a,bb=O[1],O[2];wa=vector_writer_id(coord,weight,inst,w,wi,a);wb=vector_writer_id(coord,weight,inst,w,wi,bb)
   if wa is not None and wb is not None and frozenset((wa,wb))==pair:hits.append((wi,bool(inst[wi][3]&0x2000),a,bb))
  if op in weight.DCL_OPS or op in (weight.OP_RET,weight.OP_ELSE,weight.OP_ENDIF,weight.OP_IF,weight.OP_DISCARD):continue
  srcs=O[2:] if op==weight.OP_SINCOS else O[1:]
  for src in srcs:
   if src['type']!=TYPE_TEMP or len(src['idx'])!=1 or not isinstance(src['idx'][0],int):continue
   if op in DP_WIDTH:comps=src['comps'][:DP_WIDTH[op]]
   else:
    try:comps=weight.eff(src,d['comps'])
    except ValueError:comps=src['comps'] or 'x'
   for q in set(comps):todo.append((wi,src['idx'][0],q))
 by={x[0]:x for x in hits}
 return [by[k] for k in sorted(by)]

def immediate_bits(weight,w,o):
 return weight.imm32_bits(w,o) if o['type']==TYPE_IMM32 else None

def first_value_use(weight,coord,w,inst,start,reg,ch,limit):
 for j in range(start+1,limit+1):
  p,op,ln,tok=inst[j]
  if op in weight.DCL_OPS or op in (weight.OP_RET,weight.OP_ELSE,weight.OP_ENDIF):continue
  O=weight.parse_all(coord,w,p,ln)
  for ix,src in weight.source_operands(op,O):
   if src['type']==TYPE_TEMP and src['idx']==[reg] and ch in weight.source_components_read(op,O,ix):return j,op,O,ix
 return None

def prove_angular_core(coord,weight,w,inst,dot_index,factor_use_index):
 p,op,ln,tok=inst[dot_index];D=weight.parse_all(coord,w,p,ln);dst,a,b=D
 if op!=OP_DP3 or not(tok&0x2000):raise ValueError('linked angular dot is not DP3_SAT')
 if a['modifier'] is not None or b['modifier']!='neg':raise ValueError('linked angular dot is not direct U,-V form')
 if dst['type']!=TYPE_TEMP or len(dst['idx'])!=1 or not dst['comps']:raise ValueError('angular dot destination malformed')
 reg=dst['idx'][0];ch=dst['comps'][0]
 u1=first_value_use(weight,coord,w,inst,dot_index,reg,ch,factor_use_index)
 if u1 is None or u1[1]!=OP_MUL:raise ValueError('angular dot first consumer is not MUL')
 i1,_,M,ix=u1
 others=[x for k,x in enumerate(M[1:],start=1) if k!=ix]
 if len(others)!=1 or immediate_bits(weight,w,others[0])!=NEG_9_28_BITS:raise ValueError('angular MUL is not exact -9.28 scale')
 md=M[0]
 if md['type']!=TYPE_TEMP or len(md['idx'])!=1 or not md['comps']:raise ValueError('angular MUL destination malformed')
 u2=first_value_use(weight,coord,w,inst,i1,md['idx'][0],md['comps'][0],factor_use_index)
 if u2 is None or u2[1]!=OP_EXP:raise ValueError('angular scaled dot first consumer is not EXP')
 i2,_,E,_=u2;ed=E[0]
 if ed['type']!=TYPE_TEMP or len(ed['idx'])!=1 or not ed['comps']:raise ValueError('angular EXP destination malformed')
 u3=first_value_use(weight,coord,w,inst,i2,ed['idx'][0],ed['comps'][0],factor_use_index)
 if u3 is None or u3[1]!=OP_MIN:raise ValueError('angular EXP first consumer is not MIN')
 return {'dotIndex':dot_index,'mulIndex':i1,'expIndex':i2,'minIndex':u3[0]}

def angular_expr(coord,weight,w,inst,before,reg,ch,didx,cache,depth=0):
 key=(before,reg,ch,didx)
 if key in cache:return cache[key]
 if depth>96:raise ValueError('angular expression recursion depth exceeded')
 wr=weight.latest_writer_any(coord,inst,w,before,reg,ch)
 if wr is None:return ('P',)
 wi,p,op,d,O=wr
 if wi==didx:
  if op!=OP_DP3:raise ValueError('angular identity node is not DP3')
  cache[key]=('D',);return ('D',)
 def hasD(x):
  return x==('D',) or (isinstance(x,tuple) and any(hasD(q) for q in x))
 def mod(e,src):
  if not hasD(e):return ('P',)
  return (src['modifier'],e) if src['modifier'] else e
 def scalar(src,dest_ch):
  if src['type']!=TYPE_TEMP or len(src['idx'])!=1 or not isinstance(src['idx'][0],int):return ('P',)
  try:ee=weight.eff(src,d['comps']);sch=ee[d['comps'].index(dest_ch)]
  except Exception:sch=(src['comps'] or 'x')[0]
  return mod(angular_expr(coord,weight,w,inst,wi,src['idx'][0],sch,didx,cache,depth+1),src)
 if op in DP_WIDTH:
  args=[]
  for src in O[1:3]:
   vv=[]
   if src['type']==TYPE_TEMP and len(src['idx'])==1 and isinstance(src['idx'][0],int):
    for sch in src['comps'][:DP_WIDTH[op]]:vv.append(mod(angular_expr(coord,weight,w,inst,wi,src['idx'][0],sch,didx,cache,depth+1),src))
   else:vv=[('P',)]*DP_WIDTH[op]
   args.append(tuple(vv))
 elif op in coord.SAMPLE_OPS:
  deps=[]
  for src in O[1:2]+O[4:]:
   if src['type']==TYPE_TEMP and len(src['idx'])==1 and isinstance(src['idx'][0],int):
    for sch in set(src['comps'] or 'x'):deps.append(mod(angular_expr(coord,weight,w,inst,wi,src['idx'][0],sch,didx,cache,depth+1),src))
  if not any(hasD(x) for x in deps):cache[key]=('P',);return ('P',)
  args=deps
 elif op==weight.OP_SINCOS:args=[scalar(O[2],ch)]
 else:args=[scalar(src,ch) for src in O[1:]]
 if not any(hasD(x) for x in args):cache[key]=('P',);return ('P',)
 z=(OPS[op]+('_sat' if inst[wi][3]&0x2000 else ''),)+tuple(args);cache[key]=z;return z

def skeleton_string(x):
 core=('min',('exp',('mul',('D',),('P',))),('P',))
 if x==core:return 'C'
 if x==('P',):return 'P'
 if x==('D',):return 'D'
 if isinstance(x,tuple):
  if len(x)==2 and x[0] in ('neg','abs','absneg',None):return f'{x[0]}({skeleton_string(x[1])})'
  return f"{x[0]}("+','.join(skeleton_string(q) for q in x[1:])+')'
 return str(x)

def mip_class(q):
 if q['kind']=='affine_lod':return f"affine:{q['scaleBits']}:{q['offsetBits']}"
 return f"{q['kind']}:{q['bits']}"

def factor_root_class(coord,weight,w,inst,before,d,factor):
 if factor['type']==TYPE_CB:return 'direct_constant_buffer'
 if factor['type']==TYPE_INPUT:return 'direct_input'
 if factor['type']!=TYPE_TEMP:return f'direct_type_{factor["type"]}'
 try:ee=weight.eff(factor,d['comps'])
 except ValueError:ee=factor['comps'] or 'x'
 ws=[weight.latest_writer_any(coord,inst,w,before,factor['idx'][0],ch) for ch in set(ee)]
 if any(x is None for x in ws):return 'temp_unresolved'
 ops=sorted({x[2] for x in ws})
 return 'temp_'+ '+'.join(OPS[o] for o in ops)

def build(root:Path,coordinate_verifier:Path,mip_verifier:Path,weight_verifier:Path,guard_path:Path):
 coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');guard=load(guard_path,'guard')
 all_ref={};maps=[]
 for mapname,(rel,expected_sha) in guard.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=expected_sha:raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  valid,_=guard.scan_map(path);local=0
  for hh,(blob,resources) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in resources):
    local+=1;old=all_ref.setdefault(hh,(blob,resources,set()))
    if old[0]!=blob:raise ValueError('reflection shader SHA collision')
    old[2].add(mapname)
  maps.append({'map':mapname,'validDxbcCount':len(valid),'reflectionProbeShaderCount':local})
 if len(all_ref)!=EXPECTED_SHADERS:raise ValueError(f'unique reflection shader count {len(all_ref)}')
 linked=unlinked=total=0;shapes=collections.Counter();shape_mip=collections.Counter();mip_x=collections.Counter();roots=collections.Counter();rows=[];angular_chain=collections.Counter()
 base_latest=weight.latest_writer_any; base_coord_latest=coord.latest_writer
 for hh,(blob,resources,mapnames) in sorted(all_ref.items()):
  w=coord.get_program_words(blob);inst=list(coord.walk(w))
  parsed=[]
  for p,op,ln,tok in inst:
   if op in weight.DCL_OPS or op==53:parsed.append([])
   else:parsed.append(weight.parse_all(coord,w,p,ln))
  writer_lists=collections.defaultdict(list);coord_writer_lists=collections.defaultdict(list)
  for ii,((p,op,ln,tok),O) in enumerate(zip(inst,parsed)):
   for d in weight.writer_dests(op,O):
    if d['type']==TYPE_TEMP and len(d['idx'])==1 and isinstance(d['idx'][0],int):
     for ch in d['comps'] or 'x':writer_lists[(d['idx'][0],ch)].append(ii)
   if op in coord.WRITER_OPS:
    d=coord.dest(w,p,op)
    if d and d['type']==TYPE_TEMP and len(d['idx'])==1 and isinstance(d['idx'][0],int):
     for ch in d['comps'] or 'x':coord_writer_lists[(d['idx'][0],ch)].append(ii)
  @functools.lru_cache(maxsize=None)
  def cached_latest(before,reg,ch):
   arr=writer_lists.get((reg,ch),());pos=bisect.bisect_left(arr,before)-1
   if pos<0:return None
   ii=arr[pos];p,op,ln,tok=inst[ii];O=parsed[ii]
   for d in weight.writer_dests(op,O):
    if d['type']==TYPE_TEMP and d['idx']==[reg] and ch in (d['comps'] or 'x'):return ii,p,op,d,O
   raise ValueError('indexed writer lookup mismatch')
  @functools.lru_cache(maxsize=None)
  def cached_coord_latest(before,reg,ch):
   arr=coord_writer_lists.get((reg,ch),());pos=bisect.bisect_left(arr,before)-1
   if pos<0:return None
   ii=arr[pos];p,op,ln,tok=inst[ii];d=coord.dest(w,p,op)
   if not d:raise ValueError('indexed coordinate writer lookup mismatch')
   return ii,p,op,d
  weight.latest_writer_any=lambda _c,_inst,_w,before,reg,ch:cached_latest(before,reg,ch)
  coord.latest_writer=lambda _inst,_w,before,reg,ch:cached_coord_latest(before,reg,ch)
  local_link=local_unlink=0;local_shapes=collections.Counter();local_mip=collections.Counter()
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);sd,cube,res,sam=O[:4]
   if not(res['type']==TYPE_RESOURCE and sam['type']==TYPE_SAMPLER and res['idx']==[15] and sam['idx']==[15]):continue
   coord.prove_sample(w,inst,si,p,op)
   mq=mip.prove_fetch(coord,w,inst,si,p,op)
   dec=weight.first_rgb_consumer(coord,w,inst,si,sd,res)
   ci=coordinate_pair(coord,weight,w,inst,si,p,op)
   j,d,factor=second_factor(weight,coord,w,inst,dec)
   hits=matching_pair_dots(coord,weight,w,inst,j,factor,ci['pair'])
   mc=mip_class(mq);root_class=factor_root_class(coord,weight,w,inst,j,d,factor);roots[(bool(hits),root_class)]+=1
   total+=1
   if len(hits)>1:raise ValueError(f'{hh}: multiple coordinate-pair angular dots in one factor')
   if not hits:
    unlinked+=1;local_unlink+=1;mip_x[('unlinked',mc)]+=1;local_mip['unlinked:'+mc]+=1
    continue
   linked+=1;local_link+=1;dot_index,sat,a,b=hits[0]
   if not sat or a['modifier'] is not None or b['modifier']!='neg':raise ValueError(f'{hh}: linked pair dot is not dp3_sat(U,-V)')
   prove_angular_core(coord,weight,w,inst,dot_index,j);angular_chain['dp3_sat(U,-V)->mul(-9.28)->exp2->min']+=1
   if factor['type']!=TYPE_TEMP or len(factor['idx'])!=1:raise ValueError('linked material factor is not TEMP')
   eff=weight.eff(factor,d['comps']);cache={};lane_expr=[angular_expr(coord,weight,w,inst,j,factor['idx'][0],ch,dot_index,cache) for ch in eff]
   if any('D' not in skeleton_string(x) and 'C' not in skeleton_string(x) for x in lane_expr):raise ValueError('linked factor lane lost angular ancestry')
   sk=tuple(skeleton_string(x) for x in lane_expr);shape_key=jhash(sk);shapes[(shape_key,sk)]+=1;shape_mip[(shape_key,mc)]+=1;local_shapes[shape_key]+=1
   mip_x[('linked',mc)]+=1;local_mip['linked:'+mc]+=1
  rows.append({'sha256':hh,'maps':sorted(mapnames),'linkedFetchCount':local_link,'unlinkedFetchCount':local_unlink,'shapeCounts':dict(sorted(local_shapes.items())),'mipLinkCounts':dict(sorted(local_mip.items()))})
  weight.latest_writer_any=base_latest;coord.latest_writer=base_coord_latest
 if total!=EXPECTED_FETCHES:raise ValueError(f'reflection fetch count {total}')
 if (linked,unlinked)!=(5682,206):raise ValueError(f'linked split {(linked,unlinked)}')
 if angular_chain!={'dp3_sat(U,-V)->mul(-9.28)->exp2->min':5682}:raise ValueError(f'angular chain census {angular_chain}')
 expected_mip={('linked','affine:c0800000:40800000'):4236,('linked','affine:3ef33333:00000000'):1327,('linked','affine:00000000:00000000'):59,('linked','literal_lod:00000000'):60,('unlinked','literal_lod:3f4ccccd'):48,('unlinked','literal_lod:4019999a'):40,('unlinked','literal_lod:40800000'):40,('unlinked','literal_lod:00000000'):39,('unlinked','affine:3e800000:3f400000'):30,('unlinked','literal_bias:c0400000'):9}
 if dict(mip_x)!=expected_mip:raise ValueError(f'mip/link cross-tab {mip_x}')
 shape_rows=[]
 for (dig,sk),count in sorted(shapes.items(),key=lambda kv:(-kv[1],kv[0][0])):shape_rows.append({'shapeSha256':dig,'count':count,'laneSkeletons':list(sk)})
 expected_shape_counts=[4216,1386,40,20,20]
 if sorted((x['count'] for x in shape_rows),reverse=True)!=expected_shape_counts:raise ValueError(f'angular factor shape counts {[x["count"] for x in shape_rows]}')
 shape_by_count=collections.defaultdict(list)
 for x in shape_rows:shape_by_count[x['count']].append(x['shapeSha256'])
 if len(shape_by_count[4216])!=1 or len(shape_by_count[1386])!=1 or len(shape_by_count[40])!=1 or len(shape_by_count[20])!=2:raise ValueError('unexpected angular shape count multiplicity')
 shape_mip_rows=[{'shapeSha256':k[0],'mipClass':k[1],'count':v} for k,v in sorted(shape_mip.items())]
 expected_shape_mip=collections.Counter()
 expected_shape_mip[(shape_by_count[4216][0],'affine:c0800000:40800000')]=4216
 expected_shape_mip[(shape_by_count[1386][0],'affine:3ef33333:00000000')]=1327
 expected_shape_mip[(shape_by_count[1386][0],'affine:00000000:00000000')]=59
 expected_shape_mip[(shape_by_count[40][0],'literal_lod:00000000')]=40
 twenty_pairs=[(dig,mc,v) for (dig,mc),v in shape_mip.items() if dig in shape_by_count[20]]
 if sorted(v for _,_,v in twenty_pairs)!=[20,20] or {mc for _,mc,_ in twenty_pairs}!={'affine:c0800000:40800000','literal_lod:00000000'}:raise ValueError(f'20-count shape/mip relation {twenty_pairs}')
 for dig,mc,v in twenty_pairs:expected_shape_mip[(dig,mc)]=20
 if shape_mip!=expected_shape_mip:raise ValueError(f'shape/mip cross-tab {shape_mip}')
 expected_roots={(True,'temp_mad'):5642,(True,'temp_min'):40,(False,'direct_constant_buffer'):110,(False,'direct_input'):20,(False,'temp_mov'):30,(False,'temp_mad'):46}
 if dict(roots)!=expected_roots:raise ValueError(f'factor root census {roots}')
 mip_rows=[{'linkage':k[0],'mipClass':k[1],'count':v} for k,v in sorted(mip_x.items())]
 root_rows=[{'linkage':'linked' if k[0] else 'unlinked','factorRoot':k[1],'count':v} for k,v in sorted(roots.items())]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'reflectionCubeFetchCount':total,'angularLinkedFetchCount':linked,'angularUnlinkedFetchCount':unlinked,'sharedNormalizedPairCheckCount':linked,'sharedNormalizedPairFailureCount':0,'angularDp3SatCount':linked,'angularNegatedSecondOperandCount':linked,'angularMinus9Point28MulCount':linked,'angularExp2Count':linked,'angularMinCount':linked,'angularFactorShapeCount':len(shape_rows),'angularFactorShapeCounts':expected_shape_counts,'shaderRowsSha256':jhash(rows),'shapeRowsSha256':jhash(shape_rows),'shapeMipRowsSha256':jhash(shape_mip_rows),'mipLinkRowsSha256':jhash(mip_rows),'factorRootRowsSha256':jhash(root_rows)}
 return {'format':'t6-retail-reflection-probe-angular-v1','producer':'tools/t6_retail_reflection_probe_angular_v1.py','sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json','mipProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_MIP_V1.json','weightProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_WEIGHT_V1.json','expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},'angularCore':{'D':'saturate(dot(U, -V))','pairIdentity':'U and V are the same two normalized writer values used by the reflection-coordinate construction','E':'2^(-9.28 * D)','C':'min(E, P)','minus9Point28Bits':f'{NEG_9_28_BITS:08x}','P':'a value subtree independent of D'},'angularFactorShapes':shape_rows,'shapeMipCrossTab':shape_mip_rows,'mipLinkCrossTab':mip_rows,'factorRootCounts':root_rows,'mapCoverage':maps,'summary':summary,'proofBoundary':'Direct retained-SM4 value-ancestry proof over all 5,888 t15/s15 reflectionProbeSampler cube fetches. 5,682 fetches contain exactly one material-factor DP3 whose operands resolve by writer identity to the exact same two normalized values used by the proven reflection-coordinate construction; every such DP3 is saturated, negates its second vector, and feeds the exact chain MUL(-9.28) -> EXP (SM4 2^x) -> MIN before one of five D-dependent factor skeletons. The remaining 206 fetches contain no such writer-identical angular link and are kept as a separate family. U/V and P remain mathematical/dataflow labels only: this proof does not assign physical normal/view semantics to U/V, does not assert one universal gloss/roughness meaning for P, and does not reconstruct original HLSL.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'))
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
