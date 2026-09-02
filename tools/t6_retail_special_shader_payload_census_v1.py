#!/usr/bin/env python3
"""Direct retained-byte census of shader payloads used by special T6 world TechniqueSets.

Proof boundary:
- Reads MaterialTechniqueSet -> inline MaterialTechnique -> MaterialPass serialization directly
  from expanded retail XFiles.
- Hashes only shader programs whose serialized program pointer is FOLLOW/INSERT and whose
  bytes are therefore present inline at the current file location.
- Packed/reused technique/shader/program pointers are recorded by raw pointer + decoded
  block/offset and remain unresolved; no guessed alias resolution is performed.
- Requires exact parser landing at every next TechniqueSet fixed record/GfxWorld boundary.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, struct
from collections import Counter, defaultdict
from pathlib import Path

FOLLOW=0xffffffff; INSERT=0xfffffffe
ROOT_DEFAULT=Path('/mnt/data/t6_xanim_corpus')
MAPS={
 'mp_nuketown_2020': dict(rel='mp/mp_nuketown_2020.expanded.bin', sha='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505', world=63150420, q0=565, q1=623),
 'mp_raid': dict(rel='mp/mp_raid.expanded.bin', sha='d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8', world=66275632, q0=750, q1=845),
 'mp_hijacked': dict(rel='mp/mp_hijacked.expanded.bin', sha='8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b', world=58846527, q0=751, q1=821),
 'zm_prison': dict(rel='zm_prison.expanded.bin', sha='e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487', world=82099460, q0=986, q1=1113),
 'zm_tomb': dict(rel='zm_tomb.expanded.bin', sha='4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219', world=78964845, q0=1271, q1=1327),
}

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def dig(x):return sha(canon(x))

def load_world_helper(path:Path):
 spec=importlib.util.spec_from_file_location('fmt45',path); m=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(m); return m

def cstr(d:bytes,p:int)->tuple[str,int]:
 e=d.find(b'\0',p,min(len(d),p+8192))
 if e<=p:raise ValueError(f'bad cstring at {p}')
 b=d[p:e]
 if any(x<32 or x>126 for x in b):raise ValueError(f'nonprintable cstring at {p}')
 return b.decode('ascii'),e+1

def decode_ptr(raw:int,blocks,helper):
 z=helper.decode_zone_pointer(raw,blocks)
 return {'raw':f'0x{raw:08x}','kind':z['kind'],'block':z.get('block'),'offset':z.get('offset')}

def pkind(raw:int,blocks,helper): return helper.decode_zone_pointer(raw,blocks)['kind']

def parse_shader(d,p,blocks,helper,kind):
 s=p; namep,runtime,progp,size=struct.unpack_from('<IIII',d,p); p+=16
 if runtime!=0:raise ValueError(f'{kind} runtime pointer nonzero at {s}')
 nk=pkind(namep,blocks,helper); name=None
 if nk in ('following','insert'):name,p=cstr(d,p)
 elif nk not in ('packed','null'):raise ValueError(f'{kind} invalid name pointer at {s}: {nk}')
 pk=pkind(progp,blocks,helper); prog=None
 if size:
  if pk in ('following','insert'):
   if p+size>len(d):raise ValueError(f'{kind} program eof at {s}')
   program_start=p; b=d[p:p+size]; p+=size
   prog={'start':program_start,'bytes':size,'sha256':sha(b),'magic':b[:4].decode('latin1'),'direct':True}
   if b[:4]!=b'DXBC':raise ValueError(f'{kind} direct program not DXBC at {s}: {b[:4]!r}')
  elif pk=='packed':
   prog={'start':None,'bytes':size,'direct':False,'pointer':decode_ptr(progp,blocks,helper)}
  else:raise ValueError(f'{kind} invalid program pointer at {s}: {pk}')
 else:
  if progp!=0:raise ValueError(f'{kind} zero-size nonnull program pointer at {s}')
  prog={'start':None,'bytes':0,'direct':False,'pointer':None}
 return p,{'fixedStart':s,'kind':kind,'name':name,'namePointer':decode_ptr(namep,blocks,helper),'program':prog}

def parse_vdecl(d,p):
 if p+116>len(d):raise ValueError('vdecl eof')
 if any(struct.unpack_from('<20I',d,p+36)):raise ValueError(f'vdecl runtime pointers nonzero at {p}')
 return p+116

def parse_args(d,p,n,blocks,helper):
 if p+12*n>len(d):raise ValueError('args eof')
 arr=[]
 for i in range(n):
  typ,loc,size,buf,u=struct.unpack_from('<HHHHI',d,p+12*i)
  if typ>=8:raise ValueError(f'arg type {typ} at {p+12*i}')
  arr.append((typ,u))
 p+=12*n
 for typ,u in arr:
  if typ in (1,7):
   k=pkind(u,blocks,helper)
   if k in ('following','insert'):
    if p+16>len(d):raise ValueError('literal eof')
    p+=16
   elif k not in ('packed','null'):raise ValueError(f'literal ptr {k}')
 return p

def parse_technique(d,p,blocks,helper):
 s=p; namep=struct.unpack_from('<I',d,p)[0]; flags,pc=struct.unpack_from('<HH',d,p+4); p+=8
 nk=pkind(namep,blocks,helper)
 if not 1<=pc<=16:raise ValueError(f'passCount={pc} at {s}')
 passes=[]
 for j in range(pc):
  o=p+24*j; vd,vs,ps=struct.unpack_from('<III',d,o)
  pp,po,stable,custom,pre,mt=struct.unpack_from('<6B',d,o+12); pad=struct.unpack_from('<H',d,o+18)[0]; args=struct.unpack_from('<I',d,o+20)[0]
  if pad:raise ValueError(f'pass padding nonzero at {o}')
  passes.append({'passIndex':j,'vertexDecl':vd,'vertexShader':vs,'pixelShader':ps,'argCount':pp+po+stable,'args':args,'counts':{'perPrim':pp,'perObj':po,'stable':stable,'customSamplerFlags':custom,'precompiledIndex':pre,'materialType':mt}})
 p+=24*pc; shaders=[]
 for pa in passes:
  pa['children']={}
  for fld,kind in [('vertexShader','vs'),('vertexDecl','vd'),('pixelShader','ps'),('args','args')]:
   raw=pa[fld]; k=pkind(raw,blocks,helper); pa['children'][fld]=decode_ptr(raw,blocks,helper)
   if k not in ('following','insert'):continue
   if kind in ('vs','ps'):
    p,sh=parse_shader(d,p,blocks,helper,kind); pa['children'][fld]['inline']=sh; shaders.append(sh)
   elif kind=='vd':p=parse_vdecl(d,p)
   else:
    if pa['argCount']==0:raise ValueError(f'args FOLLOW with zero count at {s}')
    p=parse_args(d,p,pa['argCount'],blocks,helper)
 name=None
 if nk in ('following','insert'):name,p=cstr(d,p)
 elif nk not in ('packed','null'):raise ValueError(f'technique name ptr {nk} at {s}')
 return p,{'fixedStart':s,'end':p,'name':name,'namePointer':decode_ptr(namep,blocks,helper),'flags':flags,'passCount':pc,'passes':passes,'shaders':shaders}

def parse_techset(d,row,nextstart,blocks,helper):
 s=row['fixedStart']; name,p=cstr(d,s+152); assert name==row['name']
 ptrs=struct.unpack_from('<36I',d,s+8); techs=[]; refs=[]
 for slot,raw in enumerate(ptrs):
  pr=decode_ptr(raw,blocks,helper); pr['slot']=slot; refs.append(pr)
  if pr['kind'] in ('following','insert'):
   p,t=parse_technique(d,p,blocks,helper); t['slot']=slot; techs.append(t); pr['inlineTechnique']=t
 if p!=nextstart:raise ValueError(f"{row['name']}: serialized end {p} != next {nextstart} ({nextstart-p:+d})")
 return {'xassetIndex':row.get('xassetIndex'),'fixedStart':s,'end':p,'name':name,'worldVertFormat':row['worldVertFormat'],'techniqueRefs':refs,'inlineTechniqueCount':len(techs)}

def build(root:Path,special_manifest:Path,helper_path:Path):
 helper=load_world_helper(helper_path)
 spec=json.loads(special_manifest.read_text())
 special={x['techniqueSet']:x['family'] for x in spec['specialTechniqueSets']}
 maps=[]; selected=[]; all_direct={'ps':{},'vs':{}}; structural=[]
 for mapname,cfg in MAPS.items():
  path=root/cfg['rel']; d=path.read_bytes(); h=sha(d)
  if h!=cfg['sha']:raise ValueError(f'{mapname}: SHA mismatch {h}')
  front=helper.parse_front(d); blocks=front['blockSizes']
  rows=helper.scan_techsets(d,blocks,before=cfg['world'])[-(cfg['q1']-cfg['q0']+1):]
  if len(rows)!=(cfg['q1']-cfg['q0']+1):raise ValueError(f'{mapname}: techset block count')
  for i,r in enumerate(rows):r['xassetIndex']=cfg['q0']+i
  parsed=[]; inline_tech=inline_sh=0
  for i,r in enumerate(rows):
   nxt=rows[i+1]['fixedStart'] if i+1<len(rows) else cfg['world']
   t=parse_techset(d,r,nxt,blocks,helper); parsed.append(t); inline_tech+=t['inlineTechniqueCount']
   for tr in t['techniqueRefs']:
    if 'inlineTechnique' in tr:inline_sh+=len(tr['inlineTechnique']['shaders'])
  structural.append({'map':mapname,'techniqueSetCount':len(rows),'inlineTechniqueCount':inline_tech,'inlineShaderObjectCount':inline_sh,'end':parsed[-1]['end'],'gfxWorldStart':cfg['world']})
  picked=[]
  for t in parsed:
   if t['name'] not in special:continue
   rec={'map':mapname,'family':special[t['name']],'techniqueSet':t['name'],'xassetIndex':t['xassetIndex'],'fixedStart':t['fixedStart'],'worldVertFormat':t['worldVertFormat'],'techniques':[]}
   for tr in t['techniqueRefs']:
    if tr['kind']=='null':continue
    rr={k:tr.get(k) for k in ('slot','raw','kind','block','offset')}
    it=tr.get('inlineTechnique')
    if it:
     rr.update({'name':it['name'],'flags':it['flags'],'passCount':it['passCount'],'passes':[]})
     for pa in it['passes']:
      pr={'passIndex':pa['passIndex'],'counts':pa['counts'],'children':{}}
      for fld in ('vertexDecl','vertexShader','pixelShader','args'):
       ch=pa['children'][fld]; q={k:ch.get(k) for k in ('raw','kind','block','offset')}
       sh=ch.get('inline')
       if sh:
        q['inline']={'fixedStart':sh['fixedStart'],'name':sh['name'],'namePointer':sh['namePointer'],'program':sh['program']}
        if sh['program']['direct']:
         typ=sh['kind']; key=sh['program']['sha256']; all_direct[typ].setdefault(key,{'sha256':key,'bytes':sh['program']['bytes'],'name':sh['name'],'maps':set(),'techniqueSets':set(),'slots':set()})
         a=all_direct[typ][key];a['maps'].add(mapname);a['techniqueSets'].add(t['name']);a['slots'].add(tr['slot'])
       pr['children'][fld]=q
      rr['passes'].append(pr)
    rec['techniques'].append(rr)
   picked.append(rec);selected.append(rec)
  maps.append({'map':mapname,'source':{'file':cfg['rel'],'bytes':len(d),'sha256':h},'techniqueSetBlock':{'xassetRange':[cfg['q0'],cfg['q1']],'count':len(rows),'firstFixedStart':rows[0]['fixedStart'],'end':cfg['world']},'structural':structural[-1],'specialTechniqueSetOccurrenceCount':len(picked),'specialTechniqueSets':[x['techniqueSet'] for x in picked]})
 coverage=[]
 for ts,fam in sorted(special.items()):
  occ=[r for r in selected if r['techniqueSet']==ts]
  direct_ps=[]; direct_vs=[]; packed_ps=packed_vs=packed_tech=0; nonnull_tech=0
  for r in occ:
   for t in r['techniques']:
    nonnull_tech+=1
    if t['kind']=='packed':packed_tech+=1;continue
    for p in t.get('passes',[]):
     for fld,typ,lst in [('pixelShader','ps',direct_ps),('vertexShader','vs',direct_vs)]:
      ch=p['children'][fld]
      if ch['kind']=='packed':
       if typ=='ps':packed_ps+=1
       else:packed_vs+=1
      sh=ch.get('inline')
      if sh and sh['program']['direct']:lst.append({'map':r['map'],'slot':t['slot'],'passIndex':p['passIndex'],'name':sh['name'],'bytes':sh['program']['bytes'],'sha256':sh['program']['sha256']})
  coverage.append({'techniqueSet':ts,'family':fam,'occurrenceCount':len(occ),'nonnullTechniqueRefCount':nonnull_tech,'packedTechniqueRefCount':packed_tech,'directPixelShaderPayloadCount':len(direct_ps),'directPixelShaderUniqueCount':len({x['sha256'] for x in direct_ps}),'packedPixelShaderRefCountWithinInlineTechniques':packed_ps,'directVertexShaderPayloadCount':len(direct_vs),'directVertexShaderUniqueCount':len({x['sha256'] for x in direct_vs}),'packedVertexShaderRefCountWithinInlineTechniques':packed_vs,'hasDirectPixelShaderPayload':bool(direct_ps),'pixelShaders':direct_ps,'vertexShaders':direct_vs})
 def finish(vals):
  out=[]
  for v in vals.values():
   q={'sha256':v['sha256'],'bytes':v['bytes'],'name':v['name']};out.append(q)
  return sorted(out,key=lambda x:x['sha256'])
 full_coverage=coverage
 forensic_digest=dig(full_coverage)
 coverage=[{k:v for k,v in x.items() if k not in ('pixelShaders','vertexShaders')} for x in full_coverage]
 ps=finish(all_direct['ps']);vs=finish(all_direct['vs'])
 summary={'retainedMapCount':5,'specialDistinctTechniqueSetCount':31,'specialTechniqueSetOccurrenceCount':len(selected),'techniqueSetBlocksStructurallyExact':all(x['end']==x['gfxWorldStart'] for x in structural),'totalTechniqueSetCount':sum(x['techniqueSetCount'] for x in structural),'totalInlineTechniqueCount':sum(x['inlineTechniqueCount'] for x in structural),'totalInlineShaderObjectCount':sum(x['inlineShaderObjectCount'] for x in structural),'specialTechniqueSetsWithDirectPixelShaderPayload':sum(x['hasDirectPixelShaderPayload'] for x in coverage),'specialTechniqueSetsWithoutDirectPixelShaderPayload':sum(not x['hasDirectPixelShaderPayload'] for x in coverage),'directPixelShaderPayloadCount':sum(x['directPixelShaderPayloadCount'] for x in coverage),'uniqueDirectPixelShaderCount':len(ps),'directPixelShaderBytes':sum(x['bytes'] for x in ps),'directVertexShaderPayloadCount':sum(x['directVertexShaderPayloadCount'] for x in coverage),'uniqueDirectVertexShaderCount':len(vs),'directVertexShaderBytes':sum(x['bytes'] for x in vs),'directDxbcValidationFailureCount':0}
 return {'format':'t6-retail-special-shader-payload-census-v1','producer':'tools/t6_retail_special_shader_payload_census_v1.py','sources':{'specialFamilyManifest':special_manifest.name,'serializationContract':'OpenAssetTools T6 MaterialTechniqueSet.txt @ 7d027e8f89118196713e955b0e11f8404149c54d'},'maps':maps,'structuralValidation':structural,'specialTechniqueSetCoverage':coverage,'uniqueDirectPixelShaders':ps,'uniqueDirectVertexShaders':vs,'uniqueDirectPixelShaderSetSha256':dig(ps),'uniqueDirectVertexShaderSetSha256':dig(vs),'summary':summary,'forensicCoverageDigestSha256':forensic_digest,'proofBoundary':'Direct retail-byte shader payload census over the 31 special world TechniqueSets identified by the retained special-material family census. Only MaterialTechnique/MaterialPass/shader objects/programs serialized inline via FOLLOW/INSERT are decoded and hashed. Packed/reused technique, shader, and program pointers are recorded but intentionally not alias-resolved here. Every direct non-empty program must begin with DXBC, and every complete retained TechniqueSet block must parse to the exact next TechniqueSet/GfxWorld boundary. Shader arithmetic/visual semantics are outside this manifest.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT_DEFAULT);ap.add_argument('--special-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();doc=build(a.root,a.special_manifest,a.helper);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
