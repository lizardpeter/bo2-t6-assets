#!/usr/bin/env python3
"""Inspect all directly retained special-world T6 pixel DXBC programs."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def dig(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def build(root:Path,family_manifest:Path,payload_manifest:Path,parser_path:Path,helper_path:Path,inspector_path:Path):
 parser=load(parser_path,'shaderpayload');helper=parser.load_helper(helper_path) if hasattr(parser,'load_helper') else parser.load_world_helper(helper_path);inspector=load(inspector_path,'dxbc')
 famdoc=json.loads(family_manifest.read_text());family={x['techniqueSet']:x['family'] for x in famdoc['specialTechniqueSets']};want=set(family)
 source=json.loads(payload_manifest.read_text());unique={}
 for mapname,cfg in parser.MAPS.items():
  d=(root/cfg['rel']).read_bytes(); front=helper.parse_front(d);blocks=front['blockSizes']; rows=helper.scan_techsets(d,blocks,before=cfg['world'])[-(cfg['q1']-cfg['q0']+1):]
  for i,r in enumerate(rows):r['xassetIndex']=cfg['q0']+i
  for i,r in enumerate(rows):
   nxt=rows[i+1]['fixedStart'] if i+1<len(rows) else cfg['world'];ts=parser.parse_techset(d,r,nxt,blocks,helper)
   if ts['name'] not in want:continue
   for tr in ts['techniqueRefs']:
    it=tr.get('inlineTechnique')
    if not it:continue
    for pa in it['passes']:
     ch=pa['children']['pixelShader'];sh=ch.get('inline')
     if not sh or not sh['program']['direct']:continue
     p=sh['program'];b=d[p['start']:p['start']+p['bytes']]
     if hashlib.sha256(b).hexdigest()!=p['sha256']:raise ValueError('direct shader hash mismatch')
     q=unique.setdefault(p['sha256'],{'sha256':p['sha256'],'bytes':p['bytes'],'name':sh['name'],'data':b,'techniqueSets':set(),'maps':set()})
     if q['data']!=b:raise ValueError('same shader hash differs')
     q['techniqueSets'].add(ts['name']);q['maps'].add(mapname)
 base=sorted(({'sha256':x['sha256'],'bytes':x['bytes'],'name':x['name']} for x in unique.values()),key=lambda x:x['sha256'])
 if len(base)!=source['summary']['uniqueDirectPixelShaderCount'] or parser.dig(base)!=source['uniqueDirectPixelShaderSetSha256']:raise ValueError('payload-census shader set mismatch')
 rows=[]
 for h in sorted(unique):
  x=unique[h];q=inspector.inspect_dxbc(x['data'],name=x['name']);fs=sorted({family[t] for t in x['techniqueSets']})
  if len(fs)!=1:raise ValueError('shader crosses special families')
  resources=q['reflection']['boundResources'];lights=[r for r in resources if r['name'] in ('lightmapSamplerPrimary','lightmapSamplerSecondary')]
  rows.append({'sha256':h,'bytes':x['bytes'],'name':x['name'],'family':fs[0],'techniqueSets':sorted(x['techniqueSets']),'maps':sorted(x['maps']),'program':q['program'],'chunks':[{'tag':c['tag'],'payloadBytes':c['payloadBytes'],'payloadSha256':c['payloadSha256']} for c in q['chunks']],'creator':q['reflection']['creator'],'constantBufferCount':q['reflection']['constantBufferCount'],'resources':resources,'lightmapResources':lights})
 model=collections.Counter(x['program']['shaderModel'] for x in rows);ptype=collections.Counter(x['program']['programType'] for x in rows);chunk=collections.Counter('|'.join(c['tag'] for c in x['chunks']) for x in rows);creator=collections.Counter(x['creator'] for x in rows);inputs=collections.Counter(r['inputType'] for x in rows for r in x['resources']);dims=collections.Counter(r['dimension'] for x in rows for r in x['resources']);names=collections.Counter(r['name'] for x in rows for r in x['resources']);bind=collections.Counter((r['name'],r['inputType'],r['dimension'],r['bindPoint'],r['bindCount']) for x in rows for r in x['lightmapResources']);byfam={}
 for f in sorted(set(family.values())):
  rr=[x for x in rows if x['family']==f];byfam[f]={'uniqueShaderCount':len(rr),'lightmapShaderCount':sum(bool(x['lightmapResources']) for x in rr),'nonLightmapShaderCount':sum(not x['lightmapResources'] for x in rr)}
 compact=[{'sha256':x['sha256'],'family':x['family'],'program':x['program'],'chunks':x['chunks'],'creator':x['creator'],'resources':x['resources']} for x in rows]
 summary={'shaderCount':len(rows),'inspectionFailureCount':0,'shaderModelCounts':dict(sorted(model.items())),'programTypeCounts':dict(sorted(ptype.items())),'chunkSequenceCounts':dict(sorted(chunk.items())),'creatorCounts':dict(sorted(creator.items())),'resourceInputTypeCounts':dict(sorted(inputs.items())),'resourceDimensionCounts':dict(sorted(dims.items())),'distinctResourceNameCount':len(names),'lightmapShaderCount':sum(bool(x['lightmapResources']) for x in rows),'lightmapPrimaryShaderCount':sum(any(r['name']=='lightmapSamplerPrimary' for r in x['lightmapResources']) for x in rows),'lightmapSecondaryShaderCount':sum(any(r['name']=='lightmapSamplerSecondary' for r in x['lightmapResources']) for x in rows)}
 return {'format':'t6-retail-special-dxbc-inspection-v1','producer':'tools/t6_retail_special_dxbc_inspection_v1.py','sourcePixelShaderSetSha256':source['uniqueDirectPixelShaderSetSha256'],'summary':summary,'familyCoverage':byfam,'lightmapBindingSignatures':[{'name':k[0],'inputType':k[1],'dimension':k[2],'bindPoint':k[3],'bindCount':k[4],'shaderCount':v} for k,v in sorted(bind.items())],'resourceNameCounts':dict(sorted(names.items())),'inspectionSetSha256':dig(compact),'examples':[{'sha256':x['sha256'],'name':x['name'],'family':x['family'],'program':x['program'],'chunkTags':[c['tag'] for c in x['chunks']],'resourceNames':sorted({r['name'] for r in x['resources']})} for x in (rows[:2]+rows[-2:])],'proofBoundary':'Strict container/program/RDEF reflection inspection of the 176 unique direct pixel DXBC programs established by T6_RETAIL_SPECIAL_SHADER_PAYLOAD_CENSUS_V1. This proves bytecode container structure and reflected resource bindings only; shader instruction arithmetic and visual semantics remain separate.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--payload-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_SHADER_PAYLOAD_CENSUS_V1.json'));ap.add_argument('--parser',type=Path,default=Path('tools/t6_retail_special_shader_payload_census_v1.py'));ap.add_argument('--helper',type=Path,default=Path('tools/t6_retail_world_formats_45_proof_v1.py'));ap.add_argument('--inspector',type=Path,default=Path('tools/t6_dxbc_inspect_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.family_manifest,a.payload_manifest,a.parser,a.helper,a.inspector);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
