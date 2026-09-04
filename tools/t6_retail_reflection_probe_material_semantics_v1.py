#!/usr/bin/env python3
"""Retained T6 reflection-probe material semantic provenance proof.

This stage does not infer semantics from arithmetic shape. It promotes the prior
mathematical labels x and S only where retained DXBC RDEF metadata proves a
consistent material provenance:

  * x follows a gloss-named resource/variable path in every member of the
    LOD=4-4*x family;
  * S.rgb follows a specular-named resource/variable path in every member of
    the 4,216-case squared-material-color family.

Derived layered variants are checked by recursive value ancestry. 4,116 cases
share at least one exact texture-sample instruction between S and x whose RDEF
name contains specular/gloss; 60 use separate explicitly named specular and
 gloss textures; 40 use reflected $Globals variables SpecularColor and
GlossAmount. The 20 P=0.04 cases source x from DiffuseAndGloss.w.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

EXPECTED_REFLECTION_SHADERS=5868
EXPECTED_TARGET=4236
TYPE_TEMP=0; TYPE_INPUT=1; TYPE_IMM32=4; TYPE_CB=8


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def resource_name(guard,resources,rr):
 names=sorted({r['name'] for r in resources if r['inputType']==guard.INPUT_TEXTURE and r['bindPoint']==rr})
 if len(names)!=1:raise ValueError(f't{rr}: reflected texture names {names}')
 return names[0]

def used_component(weight,src,dest,dch):
 try:return weight.eff(src,dest['comps'])[dest['comps'].index(dch)]
 except (ValueError,IndexError):return (src['comps'] or 'x')[0]

def sample_leaves(coord,mip,weight,angular,guard,w,inst,parsed,resources,latest,reg,ch,before,cache,depth=0):
 key=(before,reg,ch)
 if key in cache:return cache[key]
 if depth>100:raise ValueError('sample ancestry recursion depth exceeded')
 wr=latest(before,reg,ch)
 if wr is None:return set()
 wi,p,op,d,O=wr
 if op in coord.SAMPLE_OPS:
  SO,_=coord.parse_sample(w,p,op);sd,c,res,sam=SO[:4];sem=mip.effective_scalar(res,sd['comps'],ch)
  z={(wi,resource_name(guard,resources,res['idx'][0]),res['idx'][0],sem,coord.SAMPLE_OPS[op])};cache[key]=z;return z
 if op in weight.DCL_OPS or op in (weight.OP_RET,weight.OP_ELSE,weight.OP_ENDIF,weight.OP_IF,weight.OP_DISCARD):return set()
 srcs=O[2:4] if op==55 else O[2:3] if op==weight.OP_SINCOS else O[1:]
 z=set()
 if op in angular.DP_WIDTH:
  for src in srcs[:2]:
   if src['type']==TYPE_TEMP and len(src['idx'])==1:
    for sc in src['comps'][:angular.DP_WIDTH[op]]:z|=sample_leaves(coord,mip,weight,angular,guard,w,inst,parsed,resources,latest,src['idx'][0],sc,wi,cache,depth+1)
 else:
  for src in srcs:
   if src['type']==TYPE_TEMP and len(src['idx'])==1:
    sc=used_component(weight,src,d,ch);z|=sample_leaves(coord,mip,weight,angular,guard,w,inst,parsed,resources,latest,src['idx'][0],sc,wi,cache,depth+1)
 cache[key]=z;return z

def rdef_bytes(blob):
 if len(blob)<32 or blob[:4]!=b'DXBC':raise ValueError('missing DXBC')
 cc=struct.unpack_from('<I',blob,28)[0]
 for off in struct.unpack_from('<'+'I'*cc,blob,32):
  if blob[off:off+4]==b'RDEF':
   n=struct.unpack_from('<I',blob,off+4)[0];return blob[off+8:off+8+n]
 raise ValueError('RDEF missing')

def cstr(r,o):
 if o<0 or o>=len(r):raise ValueError('RDEF string offset outside chunk')
 e=r.find(b'\0',o)
 if e<0:raise ValueError('unterminated RDEF string')
 return r[o:e].decode('utf-8')

def cb_reflection(blob):
 r=rdef_bytes(blob);cbc,cbo,rbc,rbo=struct.unpack_from('<4I',r,0);minor=r[16];major=r[17];es=40 if (major,minor)>=(5,1) else 32
 bindings={}
 for i in range(rbc):
  o=rbo+i*es
  if o+32>len(r):raise ValueError('RDEF resource table overflow')
  no,it,rt,dim,ns,bp,bc,flags=struct.unpack_from('<8I',r,o)
  if it==0:bindings[bp]=cstr(r,no)
 cbs={}
 for i in range(cbc):
  o=cbo+i*24
  if o+24>len(r):raise ValueError('RDEF cbuffer table overflow')
  no,vc,vo,size,flags,typ=struct.unpack_from('<6I',r,o);name=cstr(r,no);rows=[]
  for j in range(vc):
   q=vo+j*24
   if q+24>len(r):raise ValueError('RDEF variable table overflow')
   vno,start,vsize,vflags,to,do=struct.unpack_from('<6I',r,q);rows.append((start,vsize,cstr(r,vno)))
  cbs[name]=rows
 return bindings,cbs

def cb_var_at(blob,cbreg,element,component):
 bindings,cbs=cb_reflection(blob)
 if cbreg not in bindings:raise ValueError(f'cb{cbreg} has no RDEF binding')
 cbname=bindings[cbreg];off=element*16+'xyzw'.index(component)*4
 hits=[x for x in cbs[cbname] if x[0]<=off<x[0]+x[1]]
 if len(hits)!=1:raise ValueError(f'{cbname} byte {off}: variable hits {hits}')
 return cbname,off,hits[0][2]

def direct_x_source(coord,mip,weight,guard,w,inst,resources,latest,si,sampleO,blob):
 extra=sampleO[4];lod=latest(si,extra['idx'][0],extra['comps'][0])
 if lod is None or lod[2]!=50:raise ValueError('target LOD writer missing')
 L=lod[4];xsrc=L[1];xc=mip.effective_scalar(xsrc,L[0]['comps'],extra['comps'][0])
 if xsrc['type']==TYPE_CB:return ('CB',cb_var_at(blob,xsrc['idx'][0],xsrc['idx'][1],xc))
 if xsrc['type']!=TYPE_TEMP:return ('OTHER',xsrc['type'])
 wr=latest(lod[0],xsrc['idx'][0],xc)
 if wr and wr[2] in coord.SAMPLE_OPS:
  SO,_=coord.parse_sample(w,wr[1],wr[2]);sd,c,res,sam=SO[:4];sem=mip.effective_scalar(res,sd['comps'],xc)
  return ('SAMPLE',resource_name(guard,resources,res['idx'][0]),res['idx'][0],sem,coord.SAMPLE_OPS[wr[2]])
 return ('DERIVED',)

def build(root:Path,coordinate_verifier:Path,mip_verifier:Path,weight_verifier:Path,angular_verifier:Path,shared_verifier:Path,material_verifier:Path,guard_path:Path):
 coord=load(coordinate_verifier,'coord');mip=load(mip_verifier,'mip');weight=load(weight_verifier,'weight');angular=load(angular_verifier,'angular');shared=load(shared_verifier,'shared');material=load(material_verifier,'material');guard=load(guard_path,'guard')
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
 if len(all_ref)!=EXPECTED_REFLECTION_SHADERS:raise ValueError(f'reflection shader count {len(all_ref)}')
 shared_named=split_named=cb_named=imm_default=total=squared=0
 shared_patterns=collections.Counter();split_patterns=collections.Counter();cb_patterns=collections.Counter();imm_x=collections.Counter();rows=[]
 bw=weight.latest_writer_any;bc=coord.latest_writer
 for hh,(blob,resources,mapnames) in sorted(all_ref.items()):
  w=coord.get_program_words(blob);inst=list(coord.walk(w));parsed,latest,coord_latest=shared.prep_shader(coord,weight,w,inst)
  weight.latest_writer_any=lambda _c,_i,_w,b,r,ch:latest(b,r,ch);coord.latest_writer=lambda _i,_w,b,r,ch:coord_latest(b,r,ch)
  local=collections.Counter()
  for si,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   O,_=coord.parse_sample(w,p,op);sd,cube,res,sam=O[:4]
   if not(res['type']==7 and sam['type']==6 and res['idx']==[15] and sam['idx']==[15]):continue
   mq=mip.prove_fetch(coord,w,inst,si,p,op)
   if not(mq and mq['kind']=='affine_lod' and mq['scaleBits']=='c0800000' and mq['offsetBits']=='40800000'):continue
   dec=weight.first_rgb_consumer(coord,w,inst,si,sd,res);factor_use,dest,factor=angular.second_factor(weight,coord,w,inst,dec)
   xid=shared.x_identity(coord,mip,w,inst,latest,si,p,op);packs=[ii for ii in range(factor_use) if parsed[ii] and shared.is_pack(w,parsed[ii],xid,latest,ii,inst[ii][1],weight,angular)]
   if len(packs)!=1:raise ValueError(f'{hh}:{si}: Q pack count {len(packs)}')
   pi,pdest,P=material.p_operand(coord,weight,angular,shared,factor,dest,factor_use,packs[0],latest,inst)
   total+=1
   if P['type']==TYPE_IMM32:
    bits=tuple(shared.raw_imms(w,P))
    if bits!=(0x3d23d70a,):raise ValueError('unexpected immediate P in semantics proof')
    xd=direct_x_source(coord,mip,weight,guard,w,inst,resources,latest,si,O,blob)
    if xd!=('SAMPLE','DiffuseAndGloss',2,'w','SAMPLE'):raise ValueError(f'immediate-P gloss provenance {xd}')
    imm_x[xd]+=1;imm_default+=1;local['immediateDefault']+=1;continue
   squared+=1
   try:pcs=weight.eff(P,pdest['comps'])
   except ValueError:pcs=P['comps'] or 'x'
   pw=[latest(pi,P['idx'][0],ch) for ch in pcs]
   if any(x is None for x in pw) or len({x[0] for x in pw})!=1 or pw[0][2]!=56:raise ValueError('squared P writer mismatch')
   mi=pw[0][0];M=parsed[mi];md,S,_=M
   # direct CB semantic pair
   if S['type']==TYPE_CB and xid[0]=='cb':
    scs=weight.eff(S,md['comps']);snames=tuple(cb_var_at(blob,S['idx'][0],S['idx'][1],sc) for sc in scs)
    xname=cb_var_at(blob,xid[1][0],xid[1][1],xid[2])
    if {x[2] for x in snames}!={'SpecularColor'} or xname[2]!='GlossAmount':raise ValueError(f'CB material semantic pair {(snames,xname)}')
    cb_patterns[(snames,xname)]+=1;cb_named+=1;local['constantVariables']+=1;continue
   # recursive exact sample ancestry for S and x
   Sleaves=set()
   if S['type']==TYPE_TEMP:
    for sc in weight.eff(S,md['comps']):Sleaves|=sample_leaves(coord,mip,weight,angular,guard,w,inst,parsed,resources,latest,S['idx'][0],sc,mi,{})
   extra=O[4];lod=latest(si,extra['idx'][0],extra['comps'][0]);L=lod[4];xsrc=L[1];xc=mip.effective_scalar(xsrc,L[0]['comps'],extra['comps'][0]);Xleaves=set()
   if xsrc['type']==TYPE_TEMP:Xleaves|=sample_leaves(coord,mip,weight,angular,guard,w,inst,parsed,resources,latest,xsrc['idx'][0],xc,lod[0],{})
   sby=collections.defaultdict(set);xby=collections.defaultdict(set);meta={}
   for ii,name,rr,ch,sop in Sleaves:sby[ii].add(ch);meta[ii]=(name,rr,sop)
   for ii,name,rr,ch,sop in Xleaves:xby[ii].add(ch);meta[ii]=(name,rr,sop)
   qualifying=[]
   for ii in sorted(set(sby)&set(xby)):
    name,rr,sop=meta[ii];low=name.lower()
    if ('specular' in low or 'gloss' in low) and len(sby[ii])>=3 and len(xby[ii])>=1:
     qualifying.append((ii,name,rr,''.join(sorted(sby[ii])),''.join(sorted(xby[ii])),sop))
   if qualifying:
    q=qualifying[0];shared_patterns[q[1:]]+=1;shared_named+=1;local['sharedNamedSample']+=1;continue
   # exactly the retained split-map families
   s_names=tuple(sorted({x[1] for x in Sleaves}));x_names=tuple(sorted({x[1] for x in Xleaves}))
   pair=(s_names,x_names)
   if pair not in {(("specular_map",),("gloss_map",)),(("Specular_Color_Map",),("Specular_Gloss_Map",))}:raise ValueError(f'unresolved material semantic provenance {pair}')
   split_patterns[pair]+=1;split_named+=1;local['splitNamedSamples']+=1
  if sum(local.values()):rows.append({'sha256':hh,'maps':sorted(mapnames),'provenanceCounts':dict(sorted(local.items()))})
  weight.latest_writer_any=bw;coord.latest_writer=bc
 if (total,squared,shared_named,split_named,cb_named,imm_default)!=(4236,4216,4116,60,40,20):raise ValueError(f'material semantics split {(total,squared,shared_named,split_named,cb_named,imm_default)}')
 expected_split={(('specular_map',),('gloss_map',)):40,(('Specular_Color_Map',),('Specular_Gloss_Map',)):20}
 if dict(split_patterns)!=expected_split:raise ValueError(f'split named pair census {split_patterns}')
 if sum(cb_patterns.values())!=40 or len(cb_patterns)!=1:raise ValueError(f'CB semantic pair census {cb_patterns}')
 shared_rows=[{'resourceName':k[0],'resourceRegister':k[1],'sChannels':k[2],'xChannels':k[3],'opcode':k[4],'count':v} for k,v in sorted(shared_patterns.items())]
 split_rows=[{'sResources':list(k[0]),'xResources':list(k[1]),'count':v} for k,v in sorted(split_patterns.items())]
 cb_rows=[]
 for (sn,xn),v in cb_patterns.items():cb_rows.append({'sVariables':[{'constantBuffer':a,'byteOffset':b,'variable':c} for a,b,c in sn],'xVariable':{'constantBuffer':xn[0],'byteOffset':xn[1],'variable':xn[2]},'count':v})
 imm_rows=[{'sourceKind':k[0],'resourceName':k[1],'resourceRegister':k[2],'channel':k[3],'opcode':k[4],'count':v} for k,v in sorted(imm_x.items())]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'targetFetchCount':total,'squaredSpecularPathCount':squared,'sharedSpecGlossSampleCount':shared_named,'splitSpecGlossSampleCount':split_named,'constantSpecGlossVariableCount':cb_named,'immediatePoint04GlossSampleCount':imm_default,'semanticProvenanceFailureCount':0,'sharedPatternRowsSha256':jhash(shared_rows),'splitPatternRowsSha256':jhash(split_rows),'constantPatternRowsSha256':jhash(cb_rows),'immediateGlossRowsSha256':jhash(imm_rows),'shaderRowsSha256':jhash(rows)}
 return {'format':'t6-retail-reflection-probe-material-semantics-v1','producer':'tools/t6_retail_reflection_probe_material_semantics_v1.py','sources':{'materialColorProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_MATERIAL_COLOR_V1.json','sharedParameterProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_SHARED_PARAMETER_V1.json','expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in guard.SOURCES.items()}},'semanticPromotion':{'x':'gloss-path scalar (retail RDEF provenance)','S.rgb':'specular-color path (retail RDEF provenance)','scope':'the 4,236-member LOD=4-4*x reflection family'},'sharedNamedSamplePatterns':shared_rows,'splitNamedSamplePatterns':split_rows,'constantVariablePatterns':cb_rows,'immediatePoint04GlossSources':imm_rows,'mapCoverage':maps,'summary':summary,'proofBoundary':'Retained-DXBC provenance proof layered on the already-proven reflection arithmetic. For all 4,236 LOD=4-4*x fetches, x is tied to gloss-named RDEF material inputs: 4,116 squared-color cases share an exact sample instruction with S through a specular/gloss-named texture, 60 squared-color cases use separate explicitly named specular/gloss textures, 40 squared-color cases resolve through RDEF $Globals variables SpecularColor and GlossAmount, and the 20 P=0.04 cases source x from DiffuseAndGloss.w. This promotes x to a gloss-path scalar and S.rgb to a specular-color path within this proven family. It does not assert a universal engine-wide channel convention outside this family, nor claim the S squaring operation is sRGB/gamma decoding.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'));ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'));ap.add_argument('--angular-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'));ap.add_argument('--shared-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_shared_parameter_v1.py'));ap.add_argument('--material-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_material_color_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.shared_verifier,a.material_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
