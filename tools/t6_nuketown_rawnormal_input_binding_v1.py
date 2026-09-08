#!/usr/bin/env python3
"""Bind every used Nuketown raw-normal PS input without semantic guessing.

For the exact 20-pixel-shader raw-normal lit population this adapter follows:
  SM4 sample register -> DXBC RDEF binding name -> exact Technique argument
  destination -> exact `material.<property>` -> compiled T6 nameHash -> native
  OAT Material texture/constant carrying the same compiled nameHash.
Sample bindings that have no material Technique argument remain explicitly
engine/code-bound and retain their exact RDEF names/registers.

T6 material argument identity is not case-sensitive string identity. Pinned OAT
proves both Technique material arguments and Material texture/constant names use
R_HashString(...,0), implemented as DJB2-XOR-no-case with seed 0. Hash joins are
therefore collision-checked and retained explicitly.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re
from pathlib import Path
from typing import Any

FORMAT='t6-nuketown-rawnormal-input-binding-v1'
RAW_FORMAT='t6-nuketown-rawnormal-full-output-v1'
SPECIAL_FORMAT='t6-nuketown-special-material-census-v1'
TARGET='wpc/glass_clear_wall_opaque_white'
EXPECTED_SHADERS=20
EXPECTED_PROGRAMS=22
EXPECTED_MATERIAL_DESTINATIONS={
 'SpecularAndGloss2','Normal_Map','ColorMap','ReflectionAmount','SpecularAmount','NormalHeightMultiplier'
}
CB_RE=re.compile(r'^cb\d+\[\d+\]\.[xyzw]$')

class BindError(RuntimeError):pass

def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def read(path:Path):
 x=json.loads(path.read_text(encoding='utf-8'))
 if not isinstance(x,dict):raise BindError(f'expected object in {path}')
 return x

def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dig(x:Any):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def r_hash(name:str)->int:
 """Exact OAT/T6 R_HashString(name,0) = djb2_xor_nocase(name,0)."""
 h=0
 for c in name.encode('utf-8'):
  h=(((h<<5)+h) ^ (c|0x20)) & 0xffffffff
 return h

def material_path(root:Path,name:str):
 p=root/'materials'/(name+'.json')
 if not p.is_file():raise BindError(f'missing Material {p}')
 return p

def one_hash(rows:list[dict],source_name:str,label:str):
 expected=r_hash(source_name)
 hits=[]
 for x in rows:
  if not isinstance(x,dict):continue
  native=str(x.get('name') or '')
  if native and r_hash(native)==expected:hits.append(x)
 if len(hits)!=1:raise BindError(f'{label}: T6 nameHash 0x{expected:08x} for {source_name!r} hits {hits}')
 return hits[0],expected

def build(special_path:Path,raw_path:Path,material_root:Path,rdef_tool:Path):
 special=read(special_path);raw=read(raw_path);rdef=load(rdef_tool,'rdef_helper')
 if special.get('format')!=SPECIAL_FORMAT:raise BindError('special format changed')
 if raw.get('format')!=RAW_FORMAT:raise BindError('raw format changed')
 if raw.get('material')!=TARGET:raise BindError('raw target changed')
 if raw['summary'].get('uniquePixelShaderCount')!=EXPECTED_SHADERS or raw['summary'].get('litProgramCount')!=EXPECTED_PROGRAMS:raise BindError('raw population drift')

 sm=[x for x in special.get('materials',[]) if x.get('material')==TARGET]
 if len(sm)!=1:raise BindError('exact target Material missing from special census')
 sm=sm[0]
 special_program={str(x.get('techniqueType')):x for x in sm.get('programs',[]) if str(x.get('techniqueType') or '').startswith('lit')}
 if len(special_program)!=EXPECTED_PROGRAMS:raise BindError('special lit program population changed')
 groups={str(g.get('groupKey')):g for g in special.get('shaderGroups',[])}

 mp=material_path(material_root,TARGET);material=read(mp)
 textures=material.get('textures',[]);constants=material.get('constants',[])
 if not isinstance(textures,list) or not isinstance(constants,list):raise BindError('malformed native Material arrays')

 shader_info={}
 for rp in raw.get('programs',[]):
  tt=str(rp.get('techniqueType'));hh=str(rp.get('pixelShaderSha256'))
  sp=special_program.get(tt);g=groups.get(str(sp.get('groupKey') if sp else '')) if sp else None
  if not g:raise BindError(f'{tt}: missing exact group')
  passes=g.get('passes',[])
  if len(passes)!=1:raise BindError(f'{tt}: pass population changed')
  stages=[s for s in passes[0].get('stages',[]) if s.get('kind')=='pixelShader' and str(s.get('sha256'))==hh]
  if len(stages)!=1:raise BindError(f'{tt}: exact PS stage mismatch')
  st=stages[0];owner=Path(str(sp.get('techniqueOwner') or ''));rel=str(st.get('relativeFile') or '');path=owner/rel
  if sha(path)!=hh:raise BindError(f'{path}: shader SHA mismatch')
  rd=rdef._parse_rdef(path.read_bytes())
  args=st.get('arguments',[])
  amap={str(a.get('destination')):a for a in args if isinstance(a,dict) and a.get('sourceClass')=='material'}
  if set(amap)!=EXPECTED_MATERIAL_DESTINATIONS:raise BindError(f'{tt}: material argument set changed {sorted(amap)}')
  old=shader_info.get(hh);cur={'rdef':rd,'arguments':amap,'shaderPath':str(path),'shaderSha256':hh}
  if old:
   if old['rdef']!=rd or old['arguments']!=amap:raise BindError(f'{hh}: RDEF/argument disagreement across techniques')
  else:shader_info[hh]=cur
 if len(shader_info)!=EXPECTED_SHADERS:raise BindError(f'shader metadata count {len(shader_info)}')

 raw_rows={str(x.get('sha256')):x for x in raw.get('shaderRows',[])}
 material_sample_bindings=0;engine_sample_bindings=0;material_constant_bindings=0;engine_constant_leaves=set();used_images=set();used_sampler_states=set();used_engine_resources=set();material_hashes=set();out=[]
 for hh in sorted(shader_info):
  info=shader_info[hh];rd=info['rdef'];amap=info['arguments'];rr=raw_rows.get(hh)
  if not rr:raise BindError(f'{hh}: missing raw DAG row')
  sample_rows=[]
  for site in rr.get('sampleSites',[]):
   reg=int(site['resourceRegister']);sreg=int(site['samplerRegister'])
   tex=rdef._one_resource(rd,rdef.INPUT_TEXTURE,reg,'t');sam=rdef._one_resource(rd,rdef.INPUT_SAMPLER,sreg,'s')
   tname=str(tex['name']);sname=str(sam['name'])
   arg=amap.get(tname)
   if arg is None and sname!=tname:arg=amap.get(sname)
   if arg is not None:
    prop=str(arg.get('materialProperty') or '')
    mt,name_hash=one_hash(textures,prop,f'{hh}/t{reg}')
    image=str(mt.get('image') or '')
    if not image:raise BindError(f'{hh}/t{reg}: material texture {prop!r} has no image')
    state=mt.get('samplerState')
    if not isinstance(state,dict):raise BindError(f'{hh}/t{reg}: material texture {prop!r} has no samplerState')
    material_sample_bindings+=1;material_hashes.add(name_hash);used_images.add(image);used_sampler_states.add(json.dumps(state,sort_keys=True,separators=(',',':')))
    binding={'ownership':'material','techniqueArgument':arg,'materialArgumentNameHash':f'0x{name_hash:08x}','materialTexture':{'name':mt.get('name'),'semantic':mt.get('semantic'),'image':image,'samplerState':state}}
   else:
    engine_sample_bindings+=1;used_engine_resources.add((reg,tname,sreg,sname));binding={'ownership':'engine_or_code','techniqueArgument':None,'materialArgumentNameHash':None,'materialTexture':None}
   sample_rows.append({'sampleSite':site,'rdefTexture':tex,'rdefSampler':sam,**binding})

  crows=[]
  symbols=sorted({str(n.get('name')) for n in rr.get('nodes',[]) if isinstance(n,dict) and n.get('kind')=='symbol' and isinstance(n.get('name'),str) and CB_RE.match(str(n.get('name')))})
  for sym in symbols:
   c=rdef._resolve_cb_symbol(rd,sym);v=str(c['variable']);arg=amap.get(v);owned=None
   if arg is not None:
    prop=str(arg.get('materialProperty') or '')
    hits=[];name_hash=r_hash(prop)
    for x in constants:
     if isinstance(x,dict) and x.get('name') and r_hash(str(x['name']))==name_hash:hits.append(x)
    if len(hits)==1:
     owned={'ownership':'material','techniqueArgument':arg,'materialArgumentNameHash':f'0x{name_hash:08x}','materialConstant':hits[0]};material_constant_bindings+=1;material_hashes.add(name_hash)
    elif len(hits)>1:raise BindError(f'{hh}/{sym}: T6 nameHash collision for Material constant {prop!r}: {hits}')
   if owned is None:
    owned={'ownership':'engine_or_code','techniqueArgument':arg,'materialArgumentNameHash':None,'materialConstant':None};engine_constant_leaves.add((c['constantBuffer'],v,sym))
   crows.append({**c,**owned})
  out.append({'pixelShaderSha256':hh,'shaderPath':info['shaderPath'],'rdefDigestSha256':dig(rd),'sampleBindings':sample_rows,'constantLeaves':crows})

 core={'material':TARGET,'materialJsonSha256':sha(mp),'shaderBindings':out}
 return {
  'format':FORMAT,'producer':'tools/t6_nuketown_rawnormal_input_binding_v1.py','map':'mp_nuketown_2020',
  'sourceSpecialCensusSha256':sha(special_path),'sourceRawnormalFullOutputSha256':sha(raw_path),
  'materialArgumentIdentity':{'algorithm':'R_HashString = djb2_xor_nocase','seed':0,'widthBits':32},
  'summary':{
   'pixelShaderCount':len(out),'sampleSiteCount':material_sample_bindings+engine_sample_bindings,
   'materialOwnedSampleSiteCount':material_sample_bindings,'engineOrCodeSampleSiteCount':engine_sample_bindings,
   'uniqueMaterialImageCount':len(used_images),'uniqueMaterialSamplerStateCount':len(used_sampler_states),'uniqueMaterialNameHashCount':len(material_hashes),
   'materialOwnedConstantLeafCount':material_constant_bindings,'engineOrCodeConstantLeafCount':len(engine_constant_leaves),
   'uniqueEngineResourceBindingCount':len(used_engine_resources),
  },**core,
  'engineResourceBindings':[{'textureRegister':a,'textureName':b,'samplerRegister':c,'samplerName':d} for a,b,c,d in sorted(used_engine_resources)],
  'engineOrCodeConstantLeaves':[{'constantBuffer':a,'variable':b,'symbol':c} for a,b,c in sorted(engine_constant_leaves)],
  'evidenceDigestSha256':dig(core),
  'proofBoundary':'Every used raw-normal sample register is reflected from exact DXBC RDEF. Material ownership requires an exact native Technique material-argument destination and a unique T6 R_HashString(name,0) identity match to a native OAT Material texture/constant. Pinned OAT proves Technique material arguments and Material names compile through that same case-insensitive DJB2-XOR hash. Hash collisions fail closed. Samples/constants without that chain remain engine/code-owned; no register semantics, family names, shader filenames or ad-hoc case normalization assign ownership.'
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--special-census',type=Path,required=True);ap.add_argument('--rawnormal',type=Path,required=True);ap.add_argument('--material-root',type=Path,required=True);ap.add_argument('--rdef-tool',type=Path,default=Path('tools/t6_nuketown_special_material_input_binding_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.special_census,a.rawnormal,a.material_root,a.rdef_tool);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(d['summary'],indent=2,sort_keys=True));print(d['evidenceDigestSha256'])
if __name__=='__main__':main()
