#!/usr/bin/env python3
"""Retained T6 reflection-probe mip/bias proof.

For every t15/s15 cube fetch established by the reflection-coordinate proof,
this verifier decodes the SAMPLE_L LOD or SAMPLE_B bias operand and proves the
small retained family of exact literal/affine forms. The scalar x in an affine
LOD is intentionally left as a bytecode source value; direct first-writer
provenance is counted but no universal physical roughness/gloss interpretation
is asserted here.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

OP_ADD=0; OP_MAD=50; OP_MUL=56
TYPE_TEMP=0; TYPE_IMM32=4; TYPE_CB=8
EXPECTED_REFLECTION_SHADERS=5868
EXPECTED_FETCHES=5888


def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def jhash(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

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

def f32(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]

def bits_label(bits):
 v=f32(bits)
 if v==0.0:return '0'
 return format(v,'.9g')

def effective_scalar(src,dst_components,dst_component):
 s=src['comps']
 if len(s)==1:return s[0]
 if len(s)>=4:
  try:return s[dst_components.index(dst_component)]
  except ValueError as e:raise ValueError('destination lane absent from affine MAD mask') from e
 raise ValueError('cannot resolve scalar source component')

def source_origin(coord,inst,w,before_idx,x,dst_components,lod_component):
 xc=effective_scalar(x,dst_components,lod_component)
 if x['type']==TYPE_CB:
  if len(x['idx'])!=2 or not all(isinstance(z,int) for z in x['idx']):raise ValueError('affine x has non-direct constant-buffer indices')
  return {'kind':'constant_buffer','register':x['idx'][0],'element':x['idx'][1],'component':xc}
 if x['type']!=TYPE_TEMP or len(x['idx'])!=1 or not isinstance(x['idx'][0],int):
  raise ValueError(f'affine x unsupported operand type {x["type"]}')
 wr=coord.latest_writer(inst,w,before_idx,x['idx'][0],xc)
 if wr is None:raise ValueError('affine x TEMP has no supported latest writer')
 wi,wp,wop,wd=wr
 names={OP_ADD:'ADD',OP_MAD:'MAD',OP_MUL:'MUL',**coord.SAMPLE_OPS}
 if wop not in names:raise ValueError(f'affine x first writer opcode {wop} outside retained census')
 out={'kind':'temp','firstWriter':names[wop]}
 if wop in coord.SAMPLE_OPS:
  ops,q=coord.parse_sample(w,wp,wop)
  if q!=wp+inst[wi][2]:raise ValueError('affine x source sample operand length mismatch')
  sd,sc,sr,ss=ops[:4]
  if sr['type']!=coord.TYPE_RESOURCE or len(sr['idx'])!=1 or not isinstance(sr['idx'][0],int):raise ValueError('affine x source sample resource unresolved')
  channel=effective_scalar(sr,sd['comps'],xc)
  out.update({'sampleResourceRegister':sr['idx'][0],'sampleChannel':channel,'sampleOpcode':coord.SAMPLE_OPS[wop]})
 return out

def prove_fetch(coord,w,inst,i,p,op):
 ops,q=coord.parse_sample(w,p,op)
 if q!=p+inst[i][2]:raise ValueError('reflection sample operand length mismatch')
 dst,co,res,sam=ops[:4]
 if res['type']!=coord.TYPE_RESOURCE or sam['type']!=coord.TYPE_SAMPLER or res['idx']!=[15] or sam['idx']!=[15]:return None
 if op not in (72,74):raise ValueError(f'reflection cube fetch opcode {op} is neither SAMPLE_L nor SAMPLE_B')
 if len(ops)!=5:raise ValueError('reflection mip/bias sample does not have exactly five operands')
 extra=ops[4]
 if op==74:
  if extra['type']!=TYPE_IMM32:raise ValueError('SAMPLE_B bias is not immediate32')
  bits=imm32_bits(w,extra)
  if bits!=0xc0400000:raise ValueError(f'unexpected SAMPLE_B bias bits 0x{bits:08x}')
  return {'opcode':'SAMPLE_B','kind':'literal_bias','bits':f'{bits:08x}','value':bits_label(bits)}
 if extra['type']==TYPE_IMM32:
  bits=imm32_bits(w,extra)
  allowed={0x00000000,0x3f4ccccd,0x4019999a,0x40800000}
  if bits not in allowed:raise ValueError(f'unexpected literal SAMPLE_L LOD bits 0x{bits:08x}')
  return {'opcode':'SAMPLE_L','kind':'literal_lod','bits':f'{bits:08x}','value':bits_label(bits)}
 if extra['type']!=TYPE_TEMP or len(extra['idx'])!=1 or not isinstance(extra['idx'][0],int) or len(extra['comps'])!=1:
  raise ValueError('computed SAMPLE_L LOD is not a direct TEMP scalar')
 wr=coord.latest_writer(inst,w,i,extra['idx'][0],extra['comps'][0])
 if wr is None or wr[2]!=OP_MAD:raise ValueError('computed SAMPLE_L LOD is not produced by MAD')
 wi,wp,wop,wd=wr; mad,mq=coord.parse_n(w,wp,4)
 if mq!=wp+inst[wi][2]:raise ValueError('LOD MAD operand length mismatch')
 md,x,scale,offset=mad
 if scale['type']!=TYPE_IMM32 or offset['type']!=TYPE_IMM32:raise ValueError('LOD affine scale/offset are not immediate32')
 sb=imm32_bits(w,scale);ob=imm32_bits(w,offset)
 allowed={(0xc0800000,0x40800000),(0x3ef33333,0x00000000),(0x3e800000,0x3f400000),(0x00000000,0x00000000)}
 if (sb,ob) not in allowed:raise ValueError(f'unexpected computed LOD affine pair 0x{sb:08x},0x{ob:08x}')
 origin=source_origin(coord,inst,w,wi,x,md['comps'],extra['comps'][0])
 return {'opcode':'SAMPLE_L','kind':'affine_lod','scaleBits':f'{sb:08x}','offsetBits':f'{ob:08x}',
         'scale':bits_label(sb),'offset':bits_label(ob),'sourceOrigin':origin}

def build(root:Path,coordinate_verifier:Path=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'),guard_path:Path=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py')):
 coord=load(coordinate_verifier,'coord');g=load(guard_path,'guard');all_ref={}
 for mapname,(rel,expected_sha) in g.SOURCES.items():
  path=root/rel;actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=expected_sha:raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  valid,_=g.scan_map(path)
  for hh,(blob,resources) in valid.items():
   if any(x['name']=='reflectionProbeSampler' for x in resources):
    old=all_ref.setdefault(hh,(blob,resources,set()))
    if old[0]!=blob:raise ValueError('reflection SHA collision')
    old[2].add(mapname)
 if len(all_ref)!=EXPECTED_REFLECTION_SHADERS:raise ValueError(f'reflection shader count {len(all_ref)}')
 kinds=collections.Counter(); literals=collections.Counter(); affine=collections.Counter(); origins=collections.Counter(); direct_samples=collections.Counter(); rows=[];total=0
 for hh,(blob,resources,maps) in sorted(all_ref.items()):
  w=coord.get_program_words(blob);inst=list(coord.walk(w));found=[]
  for i,(p,op,ln,tok) in enumerate(inst):
   if op not in coord.SAMPLE_OPS:continue
   q=prove_fetch(coord,w,inst,i,p,op)
   if q is None:continue
   found.append(q);total+=1;kinds[(q['opcode'],q['kind'])]+=1
   if q['kind'].startswith('literal'):
    literals[(q['opcode'],q['bits'],q['value'])]+=1
   elif q['kind']=='affine_lod':
    affine[(q['scaleBits'],q['offsetBits'],q['scale'],q['offset'])]+=1
    o=q['sourceOrigin'];origins[(q['scaleBits'],q['offsetBits'],o['kind'],o.get('firstWriter','CB'))]+=1
    if 'sampleResourceRegister' in o:
     rr=o['sampleResourceRegister'];names=sorted({r['name'] for r in resources if r['inputType']==g.INPUT_TEXTURE and r['bindPoint']==rr})
     if len(names)!=1:raise ValueError(f'{hh}: direct LOD source texture t{rr} has names {names}')
     direct_samples[(q['scaleBits'],q['offsetBits'],names[0],rr,o['sampleChannel'],o['sampleOpcode'])]+=1
  if not found:raise ValueError(f'{hh}: reflection shader has no t15/s15 mip fetch')
  local_forms=collections.Counter(f"{x['opcode']}:{x['kind']}" for x in found)
  rows.append({'sha256':hh,'maps':sorted(maps),'fetchCount':len(found),'mipForms':dict(sorted(local_forms.items()))})
 if total!=EXPECTED_FETCHES:raise ValueError(f'reflection fetch count {total}')
 expected_kinds={('SAMPLE_B','literal_bias'):9,('SAMPLE_L','affine_lod'):5652,('SAMPLE_L','literal_lod'):227}
 if dict(kinds)!=expected_kinds:raise ValueError(f'mip kind census {kinds}')
 expected_literals={
  ('SAMPLE_B','c0400000','-3'):9,('SAMPLE_L','00000000','0'):99,('SAMPLE_L','3f4ccccd','0.800000012'):48,
  ('SAMPLE_L','4019999a','2.4000001'):40,('SAMPLE_L','40800000','4'):40}
 if dict(literals)!=expected_literals:raise ValueError(f'literal mip census {literals}')
 expected_affine={
  ('c0800000','40800000','-4','4'):4236,('3ef33333','00000000','0.474999994','0'):1327,
  ('3e800000','3f400000','0.25','0.75'):30,('00000000','00000000','0','0'):59}
 if dict(affine)!=expected_affine:raise ValueError(f'affine mip census {affine}')
 expected_origins={
  ('c0800000','40800000','constant_buffer','CB'):40,
  ('c0800000','40800000','temp','MAD'):1350,('c0800000','40800000','temp','MUL'):822,('c0800000','40800000','temp','SAMPLE'):2024,
  ('3ef33333','00000000','temp','MAD'):85,('3ef33333','00000000','temp','MUL'):425,('3ef33333','00000000','temp','SAMPLE'):817,
  ('3e800000','3f400000','constant_buffer','CB'):25,('3e800000','3f400000','temp','ADD'):2,('3e800000','3f400000','temp','MUL'):3,
  ('00000000','00000000','temp','MAD'):3,('00000000','00000000','temp','MUL'):15,('00000000','00000000','temp','SAMPLE'):41}
 if dict(origins)!=expected_origins:raise ValueError(f'affine source origin census {origins}')
 direct_rows=[{'scaleBits':k[0],'offsetBits':k[1],'resourceName':k[2],'resourceRegister':k[3],'channel':k[4],'opcode':k[5],'count':v}
              for k,v in sorted(direct_samples.items(),key=lambda kv:(kv[0],kv[1]))]
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':len(all_ref),'reflectionCubeFetchCount':total,
          'sampleLOpcodeCount':5879,'sampleBOpcodeCount':9,'literalLodCount':227,'affineLodCount':5652,'literalBiasCount':9,
          'affine4Minus4xCount':4236,'affine0475xCount':1327,'affine025xPlus075Count':30,'compiledZeroAffineCount':59,
          'literalLod0Count':99,'literalLod08Count':48,'literalLod24Count':40,'literalLod4Count':40,'literalBiasMinus3Count':9,
          'mipFormFailureCount':0,'shaderRowsSha256':jhash(rows),'directSourceSampleRowsSha256':jhash(direct_rows)}
 return {'format':'t6-retail-reflection-probe-mip-v1','producer':'tools/t6_retail_reflection_probe_mip_v1.py',
         'sources':{'coordinateProof':'manifests/render/T6_RETAIL_REFLECTION_PROBE_COORDINATE_V1.json',
                    'rdefGuard':'manifests/render/T6_RETAIL_REFLECTION_PROBE_RDEF_GUARD_V1.json',
                    'expandedRetailMaps':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in g.SOURCES.items()}},
         'forms':{'sampleL':{'literalLodBits':['00000000','3f4ccccd','4019999a','40800000'],
                             'affineLod':'scale*x + offset','affinePairsBits':[['c0800000','40800000'],['3ef33333','00000000'],['3e800000','3f400000'],['00000000','00000000']]},
                  'sampleB':{'literalBiasBits':'c0400000'}},
         'affineSourceOriginCounts':[{'scaleBits':k[0],'offsetBits':k[1],'sourceKind':k[2],'firstWriter':k[3],'count':v} for k,v in sorted(origins.items())],
         'directAffineSourceSamples':direct_rows,'summary':summary,
         'proofBoundary':'Direct retained-SM4 proof of the mip-selection operand for all 5,888 t15/s15 reflectionProbeSampler cube fetches. SAMPLE_L uses either one of four exact immediate LOD values or a MAD implementing one of four exact affine scalar forms; SAMPLE_B uses the exact immediate bias -3. First-writer provenance for the affine source x is counted and direct texture-sample sources are tied to reflected resource names/channels. This does not yet claim that x has one universal physical meaning, nor prove downstream Fresnel/specular weighting or final RGB contribution.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.coordinate_verifier,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
