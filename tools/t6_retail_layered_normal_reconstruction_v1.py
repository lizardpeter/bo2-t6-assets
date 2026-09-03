#!/usr/bin/env python3
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def literal(d,i):
 n=d.n[i]
 if n['kind']!='lit':return None
 try:return float(n['value'])
 except:return None
def chmaker(comp,d):
 H={}
 def ch(i):
  if i not in H:H[i]=comp.canon_hash(d,i)
  return H[i]
 return ch
def sample_channels(comp,d,i,res):
 out=set();seen=set()
 def f(j):
  if j in seen:return
  seen.add(j);n=d.n[j]
  if n['kind']=='sample' and n['resource']==res:out.add(n['channel'])
  for a in n.get('args',[]):f(a)
 f(i);return out

def current_pair(comp,d,L,w):
 nr=f'normalMapSampler{L}';rm={};dep={}
 def rs(i):
  if i not in rm:rm[i]=comp.value_resources(d,i)
  return rm[i]
 def has(i,t):
  k=(i,t)
  if k not in dep:dep[k]=(i==t or any(has(a,t) for a in d.n[i].get('args',[])))
  return dep[k]
 def maximal(i):
  if rs(i)=={nr}:return [i]
  out=[]
  for a in d.n[i].get('args',[]):
   if nr in rs(a):out+=maximal(a)
  return out
 js=[i for i in range(len(d.n)) if nr in rs(i) and has(i,w)];mins=[i for i in js if not any((nr in rs(a) and has(a,w)) for a in d.n[i].get('args',[]))];cur=[]
 for j in mins:
  n=d.n[j]
  if n['kind']=='select':cur+=maximal(n['args'][1])
  else:
   for a in n.get('args',[]):
    if nr in rs(a):cur+=maximal(a)
 cur=sorted(set(cur))
 if len(cur)!=2:raise ValueError(f'layer {L}: current normal pair count {len(cur)}')
 if all(d.n[i]['kind']=='dot' for i in cur):
  def half(i):
   ds=comp.input_deps(d,i);lo=sum(x.endswith('.x') or x.endswith('.y') for x in ds);hi=sum(x.endswith('.z') or x.endswith('.w') for x in ds);return 0 if lo>hi else 1
  mp={half(i):i for i in cur}
  if set(mp)!={0,1}:raise ValueError('normal 2x2 transform halves unresolved')
  return [mp[0],mp[1]]
 if all(d.n[i]['kind']=='add' for i in cur):
  out={}
  for i in cur:
   cs=sample_channels(comp,d,i,nr)
   if cs=={'x'}:out[0]=i
   elif cs=={'y'}:out[1]=i
  if set(out)!={0,1}:raise ValueError('direct normal xy unresolved')
  return [out[0],out[1]]
 raise ValueError('mixed normal transform kinds')
def base_pair(comp,d):
 res='normalMapSampler';out={}
 for i,n in enumerate(d.n):
  if n['kind']!='add' or comp.value_resources(d,i)!={res}:continue
  cs=sample_channels(comp,d,i,res)
  if cs=={'x'}:out[0]=i
  elif cs=={'y'}:out[1]=i
 return [out[0],out[1]] if set(out)=={0,1} else None

def signed_factors(comp,d,i,ch):
 sign=1;out=[]
 def f(j):
  nonlocal sign
  n=d.n[j]
  if n['kind']=='neg':sign*=-1;f(n['args'][0])
  elif n['kind']=='mul':f(n['args'][0]);f(n['args'][1])
  else:out.append(ch(j))
 f(i);return sign,sorted(out)
def neg_equiv(comp,d,a,b,ch):
 if comp.negof(d,a,b):return True
 va=literal(d,a);vb=literal(d,b)
 if va is not None and vb is not None and abs(va+vb)<1e-6:return True
 sa,fa=signed_factors(comp,d,a,ch);sb,fb=signed_factors(comp,d,b,ch);return fa==fb and sa==-sb
def rem_factors(comp,d,term,w,ch):
 rem=list(comp.factors(d,term))
 for z in comp.factors(d,w):
  hz=ch(z);pos=next((j for j,v in enumerate(rem) if ch(v)==hz),None)
  if pos is None:return None
  rem.pop(pos)
 return rem
def match_b(comp,d,prev,cur,w,ch):
 out=[]
 if prev is None:
  for i,n in enumerate(d.n):
   if n['kind']!='mul':continue
   rem=rem_factors(comp,d,i,w,ch)
   if rem is not None and len(rem)==1 and ch(rem[0])==ch(cur):out.append(i)
  return sorted(set(out))
 for i,n in enumerate(d.n):
  if n['kind']!='add':continue
  for base,term in (n['args'],n['args'][::-1]):
   if ch(base)!=ch(prev):continue
   rem=rem_factors(comp,d,term,w,ch)
   if rem is None:continue
   diff=comp.product(d,rem);aa=comp.addp(d,diff)
   if not aa:continue
   for lay,negb in (aa,aa[::-1]):
    if ch(lay)==ch(cur) and neg_equiv(comp,d,negb,prev,ch):out.append(i)
 return sorted(set(out))
def match_t(comp,d,prev,cur,w,ch):
 if prev is None:return []
 return [i for i,n in enumerate(d.n) if n['kind']=='select' and ch(n['args'][0])==ch(w) and ch(n['args'][1])==ch(cur) and ch(n['args'][2])==ch(prev)]

def final_xy(comp,d,ts):
 sp=comp.specs(ts);rgb=comp.sequence(d,comp.mode_sig(ts),'x')
 if not rgb:raise ValueError(f'{ts}: no RGB compositor sequence')
 weights=rgb[0][1];ch=chmaker(comp,d);prev=base_pair(comp,d)
 for L,md,F in sp:
  if 'n' not in F:continue
  cur=current_pair(comp,d,L,weights[L-1]);new=[]
  for c in (0,1):
   pp=None if prev is None else prev[c]
   z=match_b(comp,d,pp,cur[c],weights[L-1],ch) if md=='b' else match_t(comp,d,pp,cur[c],weights[L-1],ch) if md=='t' else []
   if not z:raise ValueError(f'{ts}: normal recurrence layer {L}/{c} failed')
   new.append(z[0])
  prev=new
 if prev is None:raise ValueError(f'{ts}: no layered normal state')
 return prev,ch

def flatten_add(d,i,sign=1,out=None):
 if out is None:out=[]
 z=d.n[i]
 if z['kind']=='add':flatten_add(d,z['args'][0],sign,out);flatten_add(d,z['args'][1],sign,out)
 elif z['kind']=='neg':flatten_add(d,z['args'][0],-sign,out)
 else:out.append((sign,i))
 return out
def mul_factors(d,i,atomic,ch,sign=1):
 if ch(i) in atomic:return sign,[i]
 z=d.n[i]
 if z['kind']=='neg':return mul_factors(d,z['args'][0],atomic,ch,-sign)
 if z['kind']=='mul':
  s1,a=mul_factors(d,z['args'][0],atomic,ch,sign);s2,b=mul_factors(d,z['args'][1],atomic,ch,1);return s1*s2,a+b
 return sign,[i]
def linear_component(comp,d,i,X,Y,ch):
 hx,hy=ch(X),ch(Y);base=[];bx=[];by=[]
 for s,t in flatten_add(d,i):
  sg,ff=mul_factors(d,t,{hx,hy},ch,s);hs=[ch(x) for x in ff];cx=hs.count(hx);cy=hs.count(hy)
  if cx and cy:return None
  if cx:
   rem=[ff[j] for j,x in enumerate(hs) if x!=hx]
   if cx!=1 or len(rem)!=1:return None
   bx.append((sg,rem[0]))
  elif cy:
   rem=[ff[j] for j,x in enumerate(hs) if x!=hy]
   if cy!=1 or len(rem)!=1:return None
   by.append((sg,rem[0]))
  else:base.append((sg,t))
 if len(base)==len(bx)==len(by)==1 and base[0][0]==bx[0][0]==by[0][0]==1:return base[0][1],bx[0][1],by[0][1]
 return None
def one_input(comp,d,i):
 z=sorted(comp.input_deps(d,i));return z[0] if len(z)==1 else None
def signed_secondary_channel(d,i):
 n=d.n[i]
 if n['kind']!='add':return None
 for a,b in (n['args'],n['args'][::-1]):
  va=literal(d,a)
  if va is None or abs(va+1)>1e-6:continue
  z=d.n[b]
  if z['kind']!='mul':continue
  for s,c in (z['args'],z['args'][::-1]):
   sn=d.n[s];vc=literal(d,c)
   if sn['kind']=='sample' and sn['resource']=='lightmapSamplerSecondary' and vc is not None and abs(vc-2)<1e-6:return sn['channel']
 return None

def prove_shader(comp,opcode,operand,inspect,hh,q):
 d=comp.symbolic(q['blob'],opcode,operand,inspect);(X,Y),ch=final_xy(comp,d,q['techniqueSet']);parents=collections.defaultdict(list)
 for j,z in enumerate(d.n):
  for a in z.get('args',[]):parents[a].append(j)
 candidates=[]
 for di,z in enumerate(d.n):
  if z['kind']!='dot' or len(z['args'])!=6:continue
  aa=z['args'];trip=[];ok=True
  for k in range(0,6,2):
   if ch(aa[k])!=ch(aa[k+1]):ok=False;break
   meta=linear_component(comp,d,aa[k],X,Y,ch)
   if meta is None:ok=False;break
   trip.append((aa[k],meta))
  if ok:candidates.append((di,trip))
 if len(candidates)!=1:raise ValueError(f'{q["techniqueSet"]}: raw normal vector candidate count {len(candidates)}')
 di,trip=candidates[0];rs=[j for j in parents[di] if d.n[j]['kind']=='rsq' and d.n[j]['args']==[di]]
 if len(rs)!=1:raise ValueError(f'{q["techniqueSet"]}: normalization rsq count {len(rs)}')
 r=rs[0];norm=[]
 for vi,meta in trip:
  cand=[j for j in set(parents[vi])&set(parents[r]) if d.n[j]['kind']=='mul' and set(d.n[j]['args'])==set((vi,r))]
  if len(cand)!=1:raise ValueError(f'{q["techniqueSet"]}: normalized component count {len(cand)}')
  norm.append(cand[0])
 bases=tuple(one_input(comp,d,x[1][0]) for x in trip);xb=tuple(one_input(comp,d,x[1][1]) for x in trip);yb=tuple(one_input(comp,d,x[1][2]) for x in trip)
 expected=(('TEXCOORD1.x','TEXCOORD1.y','TEXCOORD1.z'),('TEXCOORD3.x','TEXCOORD3.y','TEXCOORD3.z'),('TEXCOORD2.x','TEXCOORD2.y','TEXCOORD2.z'))
 if (bases,xb,yb)!=expected:raise ValueError(f'{q["techniqueSet"]}: basis mismatch {(bases,xb,yb)}')
 hn=[ch(x) for x in norm];light=[];view=0
 for j,z in enumerate(d.n):
  if z['kind']!='dot' or len(z['args'])!=6:continue
  pairs=[z['args'][k:k+2] for k in range(0,6,2)];decoded=[];ok=True
  for h in hn:
   other=None
   for a,b in pairs:
    if ch(a)==h:other=b;break
    if ch(b)==h:other=a;break
   if other is None:ok=False;break
   sc=signed_secondary_channel(d,other)
   if sc is None:ok=False;break
   decoded.append(sc)
  if ok and decoded==['x','y','z']:light.append(j)
  hs=[ch(a) for a in z['args']]
  if all(h in hs for h in hn) and any(x.startswith('TEXCOORD5.') for x in comp.input_deps(d,j)):view+=1
 if len(light)!=1:raise ValueError(f'{q["techniqueSet"]}: signed secondary lightmap dot count {len(light)}')
 return {'sha256':hh,'techniqueSet':q['techniqueSet'],'worldVertFormat':q['format'],'rawVectorSha256':jhash([ch(x[0]) for x in trip]),'normalizedVectorSha256':jhash(hn),'signedSecondaryDotSha256':ch(light[0]),'texcoord5NormalizedDotCount':view}

def build(root:Path,parser_path:Path,helper_path:Path,compositor_path:Path,opcode_path:Path,operand_path:Path,inspect_path:Path):
 parser=load(parser_path,'parser');helper=load(helper_path,'helper');comp=load(compositor_path,'comp');opcode=load(opcode_path,'opcode');operand=load(operand_path,'operand');inspect=load(inspect_path,'inspect');_,U=comp.collect(root,parser,helper);rows=[]
 for hh,q in sorted(U.items()):
  if any('n' in F for L,md,F in comp.specs(q['techniqueSet'])):rows.append(prove_shader(comp,opcode,operand,inspect,hh,q))
 if len(rows)!=107:raise ValueError(f'normal shader count {len(rows)} != 107')
 view=collections.Counter(r['texcoord5NormalizedDotCount'] for r in rows)
 if view!={2:101,0:6}:raise ValueError(f'TEXCOORD5 consumer distribution {view}')
 summary={'shaderCount':107,'rawVectorConstructionCheckCount':107,'rawVectorConstructionFailureCount':0,'basisPatternCount':1,'normalizationVectorCheckCount':107,'normalizationComponentCheckCount':321,'normalizationFailureCount':0,'signedSecondaryLightmapDotShaderCount':107,'signedSecondaryChannelDecodeCheckCount':321,'signedSecondaryChannelDecodeFailureCount':0,'texcoord5NormalizedDotShaderCount':101,'texcoord5NormalizedDotCount':202,'texcoord5NoDotShaderCount':6,'rowsSha256':jhash(rows)}
 return {'format':'t6-retail-layered-normal-reconstruction-v1','producer':'tools/t6_retail_layered_normal_reconstruction_v1.py','sourceSlot4ShaderSetSha256':'f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799','equations':{'rawNormal':'TEXCOORD1.xyz + layeredNormalX * TEXCOORD3.xyz + layeredNormalY * TEXCOORD2.xyz','normalize':'rawNormal * rsq(dot(rawNormal, rawNormal))','secondaryDirection':'2 * lightmapSamplerSecondary.rgb - 1','secondaryDirectionalDot':'dot(secondaryDirection, normalizedNormal)'},'basis':{'baseNormal':['TEXCOORD1.x','TEXCOORD1.y','TEXCOORD1.z'],'layeredXBasis':['TEXCOORD3.x','TEXCOORD3.y','TEXCOORD3.z'],'layeredYBasis':['TEXCOORD2.x','TEXCOORD2.y','TEXCOORD2.z']},'summary':summary,'examples':rows[:5],'proofBoundary':'Direct retained-DXBC proof over all 107 unique slot-4 layered shaders that contain layered normals. The already-proven layered XY state is converted to a three-component vector by one universal input-basis equation, normalized with rsq(dot(v,v)), and consumed by exactly one dot against lightmapSamplerSecondary.rgb decoded channelwise as 2*x-1. This proves retained normal reconstruction and the signed secondary-RGB directional relation; downstream interpretation of that dot, other lightmap channels, non-slot4 normal paths, renderer playback, and unretained maps remain separate.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--compositor',type=Path,default=Path('tools/t6_retail_layered_lmap_compositor_v1.py'));ap.add_argument('--opcode',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));ap.add_argument('--operand',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));ap.add_argument('--inspect',type=Path,default=Path('tools/t6_dxbc_inspect_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.parser,a.helper,a.compositor,a.opcode,a.operand,a.inspect);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
