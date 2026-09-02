#!/usr/bin/env python3
"""Walk retained special-world SM4 SHDR token streams without textual disassembly."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path
OPCODES=['add','and','break','breakc','call','callc','case','continue','continuec','cut','default','deriv_rtx','deriv_rty','discard','div','dp2','dp3','dp4','else','emit','emitthencut','endif','endloop','endswitch','eq','exp','frc','ftoi','ftou','ge','iadd','if','ieq','ige','ilt','imad','imax','imin','imul','ine','ineg','ishl','ishr','itof','label','ld','ld_ms','log','loop','lt','mad','min','max','customdata','mov','movc','mul','ne','nop','not','or','resinfo','ret','retc','round_ne','round_ni','round_pi','round_z','rsq','sample','sample_c','sample_c_lz','sample_l','sample_d','sample_b','sqrt','switch','sincos','udiv','ult','uge','umul','umad','umax','umin','ushr','utof','xor','dcl_resource','dcl_constant_buffer','dcl_sampler','dcl_index_range','dcl_gs_output_primitive_topology','dcl_gs_input_primitive','dcl_max_output_vertex_count','dcl_input','dcl_input_sgv','dcl_input_siv','dcl_input_ps','dcl_input_ps_sgv','dcl_input_ps_siv','dcl_output','dcl_output_sgv','dcl_output_siv','dcl_temps','dcl_indexable_temp','dcl_global_flags','reserved0','lod','gather4','sample_pos','sample_info']
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def sha(b):return hashlib.sha256(b).hexdigest()
def dig(x):return sha(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def shdr_payload(dx):
 if dx[:4]!=b'DXBC':raise ValueError('missing DXBC')
 total=struct.unpack_from('<I',dx,24)[0];cc=struct.unpack_from('<I',dx,28)[0]
 if total!=len(dx):raise ValueError('DXBC size mismatch')
 for o in struct.unpack_from('<'+'I'*cc,dx,32):
  if dx[o:o+4] in (b'SHDR',b'SHEX'):
   n=struct.unpack_from('<I',dx,o+4)[0];return dx[o+8:o+8+n]
 raise ValueError('no SHDR/SHEX')
def walk(payload):
 if len(payload)%4 or len(payload)<8:raise ValueError('bad program payload size')
 dw=struct.unpack('<%dI'%(len(payload)//4),payload);decl=dw[1]
 if decl!=len(dw):raise ValueError(f'program length mismatch {decl}!={len(dw)}')
 rows=[];i=2
 while i<decl:
  tok=dw[i];op=tok&0x7ff
  if op==53:
   if i+1>=decl:raise ValueError('truncated customdata')
   ln=dw[i+1]
  else:ln=(tok>>24)&0x7f
  if ln<1 or i+ln>decl:raise ValueError(f'bad instruction length at {i}: op={op} len={ln}')
  rows.append((op,ln,bool(tok&0x80000000),bool(tok&0x2000)));i+=ln
 if i!=decl:raise ValueError('instruction walk did not land at declared end')
 return rows
def collect(root,family_manifest,parser_path,helper_path):
 p=load(parser_path,'payload');h=p.load_helper(helper_path) if hasattr(p,'load_helper') else p.load_world_helper(helper_path);famdoc=json.loads(family_manifest.read_text());fam={x['techniqueSet']:x['family'] for x in famdoc['specialTechniqueSets']};uniq={}
 for mn,cfg in p.MAPS.items():
  d=(root/cfg['rel']).read_bytes();front=h.parse_front(d);blocks=front['blockSizes'];rs=h.scan_techsets(d,blocks,before=cfg['world'])[-(cfg['q1']-cfg['q0']+1):]
  for i,r in enumerate(rs):r['xassetIndex']=cfg['q0']+i
  for i,r in enumerate(rs):
   ts=p.parse_techset(d,r,rs[i+1]['fixedStart'] if i+1<len(rs) else cfg['world'],blocks,h)
   if ts['name'] not in fam:continue
   for tr in ts['techniqueRefs']:
    it=tr.get('inlineTechnique')
    if not it:continue
    for pa in it['passes']:
     sh=pa['children']['pixelShader'].get('inline')
     if not sh or not sh['program']['direct']:continue
     pr=sh['program'];b=d[pr['start']:pr['start']+pr['bytes']]
     q=uniq.setdefault(pr['sha256'],{'data':b,'families':set()});q['families'].add(fam[ts['name']])
 return uniq
def build(root,family_manifest,parser_path,helper_path):
 unique=collect(root,family_manifest,parser_path,helper_path);ops=collections.Counter();lens=collections.Counter();byfam=collections.defaultdict(collections.Counter);shader_cf=collections.Counter();extended=0;custom=0;saturated=0;instructions=0
 for hh,x in sorted(unique.items()):
  rows=walk(shdr_payload(x['data']));local=collections.Counter();has_cf=False
  for op,ln,ext,sat in rows:
   if op>=len(OPCODES):raise ValueError(f'unknown SM4 opcode id {op}')
   ops[op]+=1;lens[(op,ln)]+=1;local[op]+=1;instructions+=1;extended+=ext;saturated+=sat;custom+=op==53;has_cf|=op in (18,21,31)
  for f in x['families']:
   for op,n in local.items():byfam[f][op]+=n
   if has_cf:shader_cf[f]+=1
 summary={'shaderCount':len(unique),'instructionCount':instructions,'walkFailureCount':0,'opcodeTypeCount':len(ops),'extendedOpcodeTokenCount':extended,'customDataInstructionCount':custom,'saturateInstructionCount':saturated,'opcodeCounts':{OPCODES[k]:v for k,v in sorted(ops.items())},'familyOpcodeTypeCounts':{f:len(c) for f,c in sorted(byfam.items())},'familyInstructionCounts':{f:sum(c.values()) for f,c in sorted(byfam.items())},'familyControlFlowShaderCounts':dict(sorted(shader_cf.items()))}
 lenrows=[{'opcode':OPCODES[op],'lengthDwords':ln,'count':n} for (op,ln),n in sorted(lens.items())]
 return {'format':'t6-retail-special-shdr-opcode-census-v1','producer':'tools/t6_retail_special_shdr_opcode_census_v1.py','sourcePixelShaderSetSha256':'aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7','reference':{'format':'Microsoft D3D10/SM4 tokenized program format','opcodeMask':'0x7ff','instructionLengthBits':'30:24','source':'d3d10TokenizedProgramFormat.hpp'},'summary':summary,'instructionLengthVariantSetSha256':dig(lenrows),'instructionLengthVariantCount':len(lenrows),'proofBoundary':'Direct token-boundary census over the 176 unique retained special pixel SHDR programs. Instruction opcode IDs and encoded DWORD lengths are decoded from authoritative retail bytecode; operands and arithmetic semantics are intentionally not decoded by this stage.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.family_manifest,a.parser,a.helper);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
