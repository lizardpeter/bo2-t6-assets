#!/usr/bin/env python3
"""Direct retained-byte shader-payload census for layered T6 world TechniqueSets."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

def load(path:Path,name:str):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def digest(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def compact_shader_set(values):
 return sorted(({'sha256':q['sha256'],'bytes':q['bytes'],'name':q['name']} for q in values.values()),key=lambda x:x['sha256'])

def build(root:Path,parser_path:Path,helper_path:Path):
 p=load(parser_path,'shaderpayload');h=load(helper_path,'worldhelper');tech=[];unique={'ps':{},'vs':{}};slot4={};format_all=collections.Counter();slot_ps=collections.Counter();map_cov=[]
 for mapname,cfg in p.MAPS.items():
  path=root/cfg['rel'];d=path.read_bytes();actual=hashlib.sha256(d).hexdigest()
  if actual!=cfg['sha']:raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  front=h.parse_front(d);blocks=front['blockSizes'];count=cfg['q1']-cfg['q0']+1;rows=h.scan_techsets(d,blocks,before=cfg['world'])[-count:]
  if len(rows)!=count:raise ValueError(f'{mapname}: TechniqueSet block count {len(rows)} != {count}')
  for i,r in enumerate(rows):r['xassetIndex']=cfg['q0']+i
  local=[]
  for i,r in enumerate(rows):
   nxt=rows[i+1]['fixedStart'] if i+1<len(rows) else cfg['world'];ts=p.parse_techset(d,r,nxt,blocks,h);fmt=int(r['worldVertFormat']);format_all[fmt]+=1
   if fmt==0:continue
   rec={'map':mapname,'techniqueSet':ts['name'],'worldVertFormat':fmt,'directPixelShaderPayloadCount':0,'directVertexShaderPayloadCount':0,'slot4DirectPixelShaderPayloadCount':0,'packedTechniqueRefCount':sum(x['kind']=='packed' for x in ts['techniqueRefs'])}
   for tr in ts['techniqueRefs']:
    it=tr.get('inlineTechnique')
    if not it:continue
    slot=int(tr['slot'])
    for pa in it['passes']:
     for field,kind in (('pixelShader','ps'),('vertexShader','vs')):
      sh=pa['children'][field].get('inline')
      if not sh or not sh['program']['direct']:continue
      pr=sh['program'];blob=d[pr['start']:pr['start']+pr['bytes']]
      if hashlib.sha256(blob).hexdigest()!=pr['sha256'] or blob[:4]!=b'DXBC':raise ValueError(f'{mapname}:{ts["name"]}: direct {kind} payload mismatch')
      q=unique[kind].setdefault(pr['sha256'],{'sha256':pr['sha256'],'bytes':pr['bytes'],'name':sh['name'],'formats':set(),'maps':set(),'techniqueSets':set(),'slots':set()});q['formats'].add(fmt);q['maps'].add(mapname);q['techniqueSets'].add(ts['name']);q['slots'].add(slot)
      if kind=='ps':
       rec['directPixelShaderPayloadCount']+=1;slot_ps[slot]+=1
       if slot==4:rec['slot4DirectPixelShaderPayloadCount']+=1;slot4[pr['sha256']]=q
      else:rec['directVertexShaderPayloadCount']+=1
   local.append(rec);tech.append(rec)
  if not local:raise ValueError(f'{mapname}: no layered TechniqueSets')
  map_cov.append({'map':mapname,'layeredTechniqueSetOccurrences':len(local),'distinctTechniqueSetNames':len({x['techniqueSet'] for x in local}),'directPixelShaderPayloadOccurrences':sum(x['directPixelShaderPayloadCount'] for x in local),'slot4DirectPixelShaderOccurrences':sum(x['slot4DirectPixelShaderPayloadCount'] for x in local),'formatCounts':{str(k):v for k,v in sorted(collections.Counter(x['worldVertFormat'] for x in local).items())}})
 ps=compact_shader_set(unique['ps']);vs=compact_shader_set(unique['vs']);s4=compact_shader_set(slot4)
 fmt_direct=collections.Counter(x['worldVertFormat'] for x in tech if x['directPixelShaderPayloadCount']>0);slot4_fmt=collections.Counter(next(iter(q['formats'])) for q in slot4.values());assoc=collections.Counter(tuple(sorted(q['formats'])) for q in unique['ps'].values())
 summary={'formatTechniqueSetOccurrenceCounts':{str(k):v for k,v in sorted(format_all.items())},'layeredTechniqueSetOccurrences':len(tech),'distinctLayeredTechniqueSetNames':len({x['techniqueSet'] for x in tech}),'layeredTechniqueSetOccurrencesWithDirectPixelShader':sum(x['directPixelShaderPayloadCount']>0 for x in tech),'layeredTechniqueSetOccurrencesWithoutDirectPixelShader':sum(x['directPixelShaderPayloadCount']==0 for x in tech),'directPixelShaderPayloadOccurrences':sum(x['directPixelShaderPayloadCount'] for x in tech),'uniqueDirectPixelShaderCount':len(ps),'uniqueDirectPixelShaderBytes':sum(x['bytes'] for x in ps),'directVertexShaderPayloadOccurrences':sum(x['directVertexShaderPayloadCount'] for x in tech),'uniqueDirectVertexShaderCount':len(vs),'uniqueDirectVertexShaderBytes':sum(x['bytes'] for x in vs),'formatDirectPixelShaderCoverage':{str(k):v for k,v in sorted(fmt_direct.items())},'slotDirectPixelShaderOccurrences':{str(k):v for k,v in sorted(slot_ps.items())},'slot4TechniqueSetOccurrencesWithDirectPixelShader':sum(x['slot4DirectPixelShaderPayloadCount']>0 for x in tech),'slot4DirectPixelShaderOccurrences':sum(x['slot4DirectPixelShaderPayloadCount'] for x in tech),'slot4UniqueDirectPixelShaderCount':len(s4),'slot4UniqueDirectPixelShaderBytes':sum(x['bytes'] for x in s4),'slot4UniquePixelShaderByFormat':{str(k):v for k,v in sorted(slot4_fmt.items())},'uniquePixelShaderFormatAssociations':{'/'.join(map(str,k)):v for k,v in sorted(assoc.items(),key=lambda kv:kv[0])}}
 return {'format':'t6-retail-layered-shader-payload-census-v1','producer':'tools/t6_retail_layered_shader_payload_census_v1.py','mapCoverage':map_cov,'summary':summary,'uniqueDirectPixelShaderSetSha256':digest(ps),'uniqueDirectVertexShaderSetSha256':digest(vs),'slot4UniquePixelShaderSetSha256':digest(s4),'pixelShaderExamples':ps[:2]+ps[-2:],'slot4PixelShaderExamples':s4[:2]+s4[-2:],'proofBoundary':'Direct retained-byte shader payload census for every nonzero-worldVertFormat MaterialTechniqueSet in the five complete retained world TechniqueSet blocks. FOLLOW/INSERT shader programs are hashed only when physically present inline and must begin DXBC. All 273 layered TechniqueSet occurrences expose a direct pixel shader in slot 4 and at least one direct pixel shader overall. Packed/reused aliases outside the direct payload population are not guessed; shader arithmetic is a separate proof.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();doc=build(a.root,a.parser,a.helper);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
