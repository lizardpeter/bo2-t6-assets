#!/usr/bin/env python3
"""Direct retained-byte census of shader payloads used by special T6 world TechniqueSets."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, struct
from pathlib import Path
ROOT_DEFAULT=Path('/mnt/data/t6_xanim_corpus')
MAPS={
 'mp_nuketown_2020':dict(rel='mp/mp_nuketown_2020.expanded.bin',sha='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505',world=63150420,q0=565,q1=623),
 'mp_raid':dict(rel='mp/mp_raid.expanded.bin',sha='d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8',world=66275632,q0=750,q1=845),
 'mp_hijacked':dict(rel='mp/mp_hijacked.expanded.bin',sha='8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b',world=58846527,q0=751,q1=821),
 'zm_prison':dict(rel='zm_prison.expanded.bin',sha='e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487',world=82099460,q0=986,q1=1113),
 'zm_tomb':dict(rel='zm_tomb.expanded.bin',sha='4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219',world=78964845,q0=1271,q1=1327),
}
def sha(b):return hashlib.sha256(b).hexdigest()
def dig(x):return sha(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def load_helper(path):
 s=importlib.util.spec_from_file_location('fmt45',path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def cstr(d,p):
 e=d.find(b'\0',p,min(len(d),p+8192))
 if e<=p or any(x<32 or x>126 for x in d[p:e]):raise ValueError(f'bad cstring at {p}')
 return d[p:e].decode('ascii'),e+1
def kind(raw,blocks,h):return h.decode_zone_pointer(raw,blocks)['kind']
def ptr(raw,blocks,h):
 z=h.decode_zone_pointer(raw,blocks);return {'raw':f'0x{raw:08x}','kind':z['kind'],'block':z.get('block'),'offset':z.get('offset')}
def parse_shader(d,p,blocks,h,skind):
 s=p;namep,runtime,progp,size=struct.unpack_from('<IIII',d,p);p+=16
 if runtime:raise ValueError(f'{skind} runtime pointer nonzero at {s}')
 k=kind(namep,blocks,h);name=None
 if k in ('following','insert'):name,p=cstr(d,p)
 elif k not in ('packed','null'):raise ValueError('bad shader name pointer')
 pk=kind(progp,blocks,h)
 if size:
  if pk in ('following','insert'):
   start=p;b=d[p:p+size];p+=size
   if len(b)!=size or b[:4]!=b'DXBC':raise ValueError(f'{skind} direct program not DXBC at {s}')
   program={'start':start,'bytes':size,'sha256':sha(b),'magic':'DXBC','direct':True}
  elif pk=='packed':program={'start':None,'bytes':size,'direct':False,'pointer':ptr(progp,blocks,h)}
  else:raise ValueError('bad shader program pointer')
 else:
  if progp:raise ValueError('zero-size nonnull program')
  program={'start':None,'bytes':0,'direct':False,'pointer':None}
 return p,{'fixedStart':s,'kind':skind,'name':name,'namePointer':ptr(namep,blocks,h),'program':program}
def parse_vdecl(d,p):
 if p+116>len(d) or any(struct.unpack_from('<20I',d,p+36)):raise ValueError(f'bad vdecl at {p}')
 return p+116
def parse_args(d,p,n,blocks,h):
 if p+12*n>len(d):raise ValueError('args eof')
 vals=[]
 for i in range(n):
  typ,loc,size,buf,u=struct.unpack_from('<HHHHI',d,p+12*i)
  if typ>=8:raise ValueError('bad arg type')
  vals.append((typ,u))
 p+=12*n
 for typ,u in vals:
  if typ in (1,7):
   k=kind(u,blocks,h)
   if k in ('following','insert'):p+=16
   elif k not in ('packed','null'):raise ValueError('bad literal pointer')
 return p
def parse_technique(d,p,blocks,h):
 s=p;namep=struct.unpack_from('<I',d,p)[0];flags,pc=struct.unpack_from('<HH',d,p+4);p+=8
 nk=kind(namep,blocks,h)
 if not 1<=pc<=16:raise ValueError(f'bad passCount {pc}')
 passes=[]
 for j in range(pc):
  o=p+24*j;vd,vs,ps=struct.unpack_from('<III',d,o);pp,po,stable,custom,pre,mt=struct.unpack_from('<6B',d,o+12);pad=struct.unpack_from('<H',d,o+18)[0];args=struct.unpack_from('<I',d,o+20)[0]
  if pad:raise ValueError('pass padding')
  passes.append({'passIndex':j,'vertexDecl':vd,'vertexShader':vs,'pixelShader':ps,'argCount':pp+po+stable,'args':args,'counts':{'perPrim':pp,'perObj':po,'stable':stable,'customSamplerFlags':custom,'precompiledIndex':pre,'materialType':mt}})
 p+=24*pc;shaders=[]
 for pa in passes:
  pa['children']={}
  for fld,ck in [('vertexShader','vs'),('vertexDecl','vd'),('pixelShader','ps'),('args','args')]:
   raw=pa[fld];k=kind(raw,blocks,h);pa['children'][fld]=ptr(raw,blocks,h)
   if k not in ('following','insert'):continue
   if ck in ('vs','ps'):
    p,sh=parse_shader(d,p,blocks,h,ck);pa['children'][fld]['inline']=sh;shaders.append(sh)
   elif ck=='vd':p=parse_vdecl(d,p)
   else:
    if not pa['argCount']:raise ValueError('args follow with zero count')
    p=parse_args(d,p,pa['argCount'],blocks,h)
 name=None
 if nk in ('following','insert'):name,p=cstr(d,p)
 elif nk not in ('packed','null'):raise ValueError('bad technique name pointer')
 return p,{'fixedStart':s,'name':name,'flags':flags,'passCount':pc,'passes':passes,'shaders':shaders}
def parse_techset(d,row,nextstart,blocks,h):
 s=row['fixedStart'];name,p=cstr(d,s+152);assert name==row['name'];refs=[]
 for slot,raw in enumerate(struct.unpack_from('<36I',d,s+8)):
  r=ptr(raw,blocks,h);r['slot']=slot
  if r['kind'] in ('following','insert'):
   p,t=parse_technique(d,p,blocks,h);t['slot']=slot;r['inlineTechnique']=t
  refs.append(r)
 if p!=nextstart:raise ValueError(f'{name}: end {p} != {nextstart}')
 return {'xassetIndex':row['xassetIndex'],'fixedStart':s,'end':p,'name':name,'worldVertFormat':row['worldVertFormat'],'techniqueRefs':refs,'inlineTechniqueCount':sum('inlineTechnique' in r for r in refs)}
def build(root,special_manifest,helper_path):
 h=load_helper(helper_path);sp=json.loads(special_manifest.read_text());special={x['techniqueSet']:x['family'] for x in sp['specialTechniqueSets']};maps=[];selected=[];all_direct={'ps':{},'vs':{}};structural=[]
 for mapname,cfg in MAPS.items():
  d=(root/cfg['rel']).read_bytes();hh=sha(d)
  if hh!=cfg['sha']:raise ValueError(f'{mapname}: source mismatch')
  front=h.parse_front(d);blocks=front['blockSizes'];rows=h.scan_techsets(d,blocks,before=cfg['world'])[-(cfg['q1']-cfg['q0']+1):]
  if len(rows)!=cfg['q1']-cfg['q0']+1:raise ValueError('techset count')
  for i,r in enumerate(rows):r['xassetIndex']=cfg['q0']+i
  parsed=[];itc=isc=0
  for i,r in enumerate(rows):
   nxt=rows[i+1]['fixedStart'] if i+1<len(rows) else cfg['world'];t=parse_techset(d,r,nxt,blocks,h);parsed.append(t);itc+=t['inlineTechniqueCount'];isc+=sum(len(x['inlineTechnique']['shaders']) for x in t['techniqueRefs'] if 'inlineTechnique' in x)
  structural.append({'map':mapname,'techniqueSetCount':len(rows),'inlineTechniqueCount':itc,'inlineShaderObjectCount':isc,'end':parsed[-1]['end'],'gfxWorldStart':cfg['world']})
  picked=[]
  for t in parsed:
   if t['name'] not in special:continue
   rec={'map':mapname,'family':special[t['name']],'techniqueSet':t['name'],'techniques':[]}
   for tr in t['techniqueRefs']:
    if tr['kind']=='null':continue
    rr={k:tr.get(k) for k in ('slot','raw','kind','block','offset')};it=tr.get('inlineTechnique')
    if it:
     rr.update({'name':it['name'],'passes':[]})
     for pa in it['passes']:
      pr={'passIndex':pa['passIndex'],'children':{}}
      for fld in ('vertexDecl','vertexShader','pixelShader','args'):
       ch=pa['children'][fld];q={k:ch.get(k) for k in ('raw','kind','block','offset')};sh=ch.get('inline')
       if sh:
        q['inline']=sh
        if sh['program']['direct']:
         typ=sh['kind'];key=sh['program']['sha256'];all_direct[typ].setdefault(key,{'sha256':key,'bytes':sh['program']['bytes'],'name':sh['name']})
       pr['children'][fld]=q
      rr['passes'].append(pr)
    rec['techniques'].append(rr)
   picked.append(rec);selected.append(rec)
  maps.append({'map':mapname,'source':{'file':cfg['rel'],'bytes':len(d),'sha256':hh},'techniqueSetBlock':{'xassetRange':[cfg['q0'],cfg['q1']],'count':len(rows),'firstFixedStart':rows[0]['fixedStart'],'end':cfg['world']},'specialTechniqueSetOccurrenceCount':len(picked)})
 coverage=[]
 for ts,fam in sorted(special.items()):
  occ=[r for r in selected if r['techniqueSet']==ts];dps=[];dvs=[];pps=pvs=pt=non=0
  for r in occ:
   for t in r['techniques']:
    non+=1
    if t['kind']=='packed':pt+=1;continue
    for p in t.get('passes',[]):
     for fld,lst,isps in [('pixelShader',dps,True),('vertexShader',dvs,False)]:
      ch=p['children'][fld]
      if ch['kind']=='packed':
       if isps:pps+=1
       else:pvs+=1
      sh=ch.get('inline')
      if sh and sh['program']['direct']:lst.append(sh['program']['sha256'])
  coverage.append({'techniqueSet':ts,'family':fam,'occurrenceCount':len(occ),'nonnullTechniqueRefCount':non,'packedTechniqueRefCount':pt,'directPixelShaderPayloadCount':len(dps),'directPixelShaderUniqueCount':len(set(dps)),'packedPixelShaderRefCountWithinInlineTechniques':pps,'directVertexShaderPayloadCount':len(dvs),'directVertexShaderUniqueCount':len(set(dvs)),'packedVertexShaderRefCountWithinInlineTechniques':pvs,'hasDirectPixelShaderPayload':bool(dps)})
 ps=sorted(all_direct['ps'].values(),key=lambda x:x['sha256']);vs=sorted(all_direct['vs'].values(),key=lambda x:x['sha256']);summary={'retainedMapCount':5,'specialDistinctTechniqueSetCount':31,'specialTechniqueSetOccurrenceCount':len(selected),'techniqueSetBlocksStructurallyExact':all(x['end']==x['gfxWorldStart'] for x in structural),'totalTechniqueSetCount':sum(x['techniqueSetCount'] for x in structural),'totalInlineTechniqueCount':sum(x['inlineTechniqueCount'] for x in structural),'totalInlineShaderObjectCount':sum(x['inlineShaderObjectCount'] for x in structural),'specialTechniqueSetsWithDirectPixelShaderPayload':sum(x['hasDirectPixelShaderPayload'] for x in coverage),'specialTechniqueSetsWithoutDirectPixelShaderPayload':sum(not x['hasDirectPixelShaderPayload'] for x in coverage),'directPixelShaderPayloadCount':sum(x['directPixelShaderPayloadCount'] for x in coverage),'uniqueDirectPixelShaderCount':len(ps),'directPixelShaderBytes':sum(x['bytes'] for x in ps),'directVertexShaderPayloadCount':sum(x['directVertexShaderPayloadCount'] for x in coverage),'uniqueDirectVertexShaderCount':len(vs),'directVertexShaderBytes':sum(x['bytes'] for x in vs),'directDxbcValidationFailureCount':0}
 return {'format':'t6-retail-special-shader-payload-census-v1','producer':'tools/t6_retail_special_shader_payload_census_v1.py','sources':{'specialFamilyManifest':special_manifest.name,'serializationContract':'OpenAssetTools T6 MaterialTechniqueSet.txt @ 7d027e8f89118196713e955b0e11f8404149c54d'},'maps':maps,'structuralValidation':structural,'specialTechniqueSetCoverage':coverage,'directPixelShaderExamples':[ps[0],ps[5],ps[-6],ps[-1]],'directVertexShaderExamples':[vs[0],vs[-1]],'uniqueDirectPixelShaderSetSha256':dig(ps),'uniqueDirectVertexShaderSetSha256':dig(vs),'summary':summary,'forensicCoverageDigestSha256':dig(coverage),'proofBoundary':'Direct retained-byte census. FOLLOW/INSERT shader programs are hashed only when physically inline and must begin DXBC. Packed/reused pointers remain unresolved; no alias is guessed. All five complete TechniqueSet blocks must land exactly at the next TechniqueSet/GfxWorld boundary. Shader arithmetic/visual semantics remain outside this proof.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT_DEFAULT);ap.add_argument('--special-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.special_manifest,a.helper);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
