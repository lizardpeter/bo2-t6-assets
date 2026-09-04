#!/usr/bin/env python3
"""Fail-closed retained-retail RDEF guard for T6 reflectionProbeSampler."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

def load_guard(path:Path):
 s=importlib.util.spec_from_file_location('secondary_guard',path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def build(root:Path, guard_path:Path=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py')):
 g=load_guard(guard_path); name='reflectionProbeSampler'; all_ref={}; maps=[]
 expected_maps={'mp_nuketown_2020':(1972,1285),'mp_raid':(3064,2063),'mp_hijacked':(2299,1722),'zm_prison':(3920,3158),'zm_tomb':(2839,1979)}
 for mapname,(rel,expected_sha) in g.SOURCES.items():
  path=root/rel; actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if actual!=expected_sha: raise ValueError(f'{mapname}: expanded SHA mismatch {actual}')
  valid,_=g.scan_map(path); ref={}
  for hh,(blob,resources) in valid.items():
   rr=[x for x in resources if x['name']==name]
   if rr: ref[hh]=(len(blob),rr)
  for hh,(size,rr) in ref.items():
   if hh not in all_ref: all_ref[hh]=(size,rr,set())
   elif all_ref[hh][:2]!=(size,rr): raise ValueError('reflection shader collision')
   all_ref[hh][2].add(mapname)
  row={'map':mapname,'validDxbcCount':len(valid),'reflectionProbeShaderCount':len(ref)}
  if (row['validDxbcCount'],row['reflectionProbeShaderCount'])!=expected_maps[mapname]: raise ValueError(f'{mapname}: census mismatch')
  maps.append(row)
 rows=[]
 for hh,(size,rr,names) in sorted(all_ref.items()):
  tex=[x for x in rr if x['inputType']==2]; sam=[x for x in rr if x['inputType']==3]
  if len(rr)!=2 or len(tex)!=1 or len(sam)!=1: raise ValueError(f'{hh}: reflection entry multiplicity')
  if tex[0]['dimension']!=9 or sam[0]['dimension']!=0: raise ValueError(f'{hh}: reflection dimensions')
  if tex[0]['bindPoint']!=15 or tex[0]['bindCount']!=1: raise ValueError(f'{hh}: reflection texture binding')
  if sam[0]['bindPoint']!=15 or sam[0]['bindCount']!=1: raise ValueError(f'{hh}: reflection sampler binding')
  rows.append({'sha256':hh,'bytes':size,'maps':sorted(names)})
 if len(rows)!=5868: raise ValueError(f'unique reflection shader count {len(rows)} != 5868')
 summary={'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'bindingFailureCount':0,
          'textureBindPoint':15,'textureBindCount':1,'textureDimension':'TEXTURECUBE',
          'samplerBindPoint':15,'samplerBindCount':1,'samplerDimension':'UNKNOWN','shaderRowsSha256':g.jhash(rows)}
 return {'format':'t6-retail-reflection-probe-rdef-guard-v1','producer':'tools/t6_retail_reflection_probe_rdef_guard_v1.py',
         'sources':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in g.SOURCES.items()},'mapCoverage':maps,
         'binding':{'name':name,'texture':{'inputType':'TEXTURE','dimension':'TEXTURECUBE','bindPoint':15,'bindCount':1},
                    'sampler':{'inputType':'SAMPLER','dimension':'UNKNOWN','bindPoint':15,'bindCount':1}},
         'summary':summary,
         'proofBoundary':'Strict retained-byte DXBC/RDEF guard over every valid embedded shader discovered in the five pinned expanded retail worlds. Every unique shader reflecting reflectionProbeSampler must expose exactly one TEXTURECUBE and one SAMPLER entry at bind point 15 with bind count 1. This proves reflected resource identity/binding only; reflection-vector construction, cube lookup coordinates, mip/LOD behavior, Fresnel/specular weighting, and final RGB contribution remain separate instruction-level proofs.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.root,a.guard);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
