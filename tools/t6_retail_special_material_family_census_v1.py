#!/usr/bin/env python3
"""Retail census of non-layered/special T6 world TechniqueSet families.

Every world material in the five retained decoded worlds is rebound from its
serialized Material::techniqueSet pointer to the retail TechniqueSet XAsset.
Generated/layered identities and ordinary lit families are separated from the
small special tail. Classification is based on exact TechniqueSet name
families and never on rendered appearance.

The helper API bridge accepts both the current world-format proof names
(front/scan_tech/dec) and the older parse_front/scan_techsets/
technique_asset_index names. The arithmetic is identical and remains fail-closed
on packed block, alignment, and XAsset type.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path); assert s and s.loader
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
state=load('statev2',HERE/'t6_retail_world_material_state_census_v2.py')
world=load('world45',HERE/'t6_retail_world_formats_45_proof_v1.py')
BIND={
 'mp_nuketown_2020':dict(world=63150420,base=13472,q0=565,q1=623),
 'mp_raid':dict(world=66275632,base=13768,q0=750,q1=845),
 'mp_hijacked':dict(world=58846527,base=14172,q0=751,q1=821),
 'zm_prison':dict(world=82099460,base=34760,q0=986,q1=1113),
 'zm_tomb':dict(world=78964845,base=46940,q0=1271,q1=1327),
}
def front(d):
 f=getattr(world,'front',None)
 if f:return f(d)
 x=world.parse_front(d); return x['blockSizes'],x['assets']
def techs(d,blocks,before):
 f=getattr(world,'scan_tech',None)
 rows=f(d,blocks,before) if f else world.scan_techsets(d,blocks,before=before)
 return [{'name':r['name'],'fmt':r.get('fmt',r.get('worldVertFormat'))} for r in rows]
def tech_q(raw,base,blocks,assets):
 f=getattr(world,'technique_asset_index',None)
 if f:return f(raw,base,blocks,assets)
 k,b,o=world.dec(raw,blocks)
 if k!='packed' or b!=5:raise ValueError(f'TechniqueSet pointer 0x{raw:08x} is not packed block 5')
 delta=o-base-4
 if delta<0 or delta%8:raise ValueError(f'TechniqueSet pointer 0x{raw:08x} is not aligned to asset-pointer base {base}')
 q=delta//8
 if q<0 or q>=len(assets) or assets[q][0]!=7:raise ValueError(f'TechniqueSet pointer 0x{raw:08x} resolves to invalid XAsset {q}')
 return q
def classify(material,tech):
 if material.startswith('*'):
  if not tech.startswith('lit_'): raise ValueError(f'layered material uses unexpected techset {tech!r}')
  return 'layered_lit'
 if tech.startswith('wpc_lit_'): return 'single_lit'
 if tech.startswith('wpc_unlit') or tech.startswith('wpc_sw4_3d_unlit_'): return 'unlit'
 if tech.startswith('wpc_cod7water') or tech.startswith('wpc_sw4_3d_water_'): return 'water'
 if tech=='wpc_shadowcaster_wj6w5j60': return 'shadowcaster'
 if tech.startswith('wpc_sw4_3d_phong_emissive_') or tech.startswith('wpc_sw4_3d_burning_'): return 'emissive_or_burning'
 if tech.startswith('wpc_sw4_3d_tv_'): return 'tv_special'
 if tech.startswith('wpc_sw4_3d_phong_rawnormal_'): return 'rawnormal_special'
 if tech=='wpc_default': return 'default'
 raise ValueError(f'unclassified TechniqueSet {tech!r} for {material!r}')
def bind_map(name,path):
 cfg=state.MAPS[name]; d=path.read_bytes()
 assert len(d)==cfg[2] and hashlib.sha256(d).hexdigest()==cfg[1]
 blocks,assets=front(d); b=BIND[name]; body=techs(d,blocks,b['world'])[-(b['q1']-b['q0']+1):]
 assert len(body)==b['q1']-b['q0']+1
 byq={b['q0']+i:r for i,r in enumerate(body)}
 p=cfg[3]; rows=[]; last_end=None
 for _ in range(cfg[4]):
  r=state.material(d,p,blocks); raw=struct.unpack_from('<I',d,p+84)[0]; q=tech_q(raw,b['base'],blocks,assets)
  assert b['q0']<=q<=b['q1']; t=byq[q]; tech=t['name']; fmt=int(t['fmt']); family=classify(r['name'],tech)
  rows.append({'material':r['name'],'techniqueSet':tech,'worldVertFormat':fmt,'family':family})
  last_end=r['end']; p=r['end']+8
 assert last_end==cfg[5]
 return rows
def build(mp_root,zm_root):
 allrows=[]; maps=[]; special_by_tech=collections.defaultdict(lambda:{'useCount':0,'maps':collections.Counter(),'families':set(),'formats':set(),'examples':[]})
 for name in state.MAPS:
  root=mp_root if state.MAPS[name][0]=='mp' else zm_root; rows=bind_map(name,root/f'{name}.expanded.bin'); allrows.extend((name,r) for r in rows); fc=collections.Counter(r['family'] for r in rows)
  maps.append({'map':name,'materialCount':len(rows),'familyUseCounts':dict(sorted(fc.items())),'specialUseCount':sum(v for k,v in fc.items() if k not in ('layered_lit','single_lit'))})
  for r in rows:
   if r['family'] in ('layered_lit','single_lit'): continue
   x=special_by_tech[r['techniqueSet']];x['useCount']+=1;x['maps'][name]+=1;x['families'].add(r['family']);x['formats'].add(r['worldVertFormat'])
   if len(x['examples'])<4:x['examples'].append({'map':name,'material':r['material']})
 fc=collections.Counter(r['family'] for _,r in allrows); special=sum(v for k,v in fc.items() if k not in ('layered_lit','single_lit'))
 techrows=[]
 for tech,x in sorted(special_by_tech.items()):
  assert len(x['families'])==1
  techrows.append({'techniqueSet':tech,'family':next(iter(x['families'])),'useCount':x['useCount'],'maps':dict(sorted(x['maps'].items())),'worldVertFormats':sorted(x['formats']),'examples':x['examples']})
 famtech=collections.Counter(r['family'] for r in techrows)
 return {'format':'t6-retail-special-material-family-census-v1','producer':'tools/t6_retail_special_material_family_census_v1.py','maps':maps,'specialTechniqueSets':techrows,'summary':{'retainedMapCount':5,'materialCount':len(allrows),'layeredLitUseCount':fc['layered_lit'],'singleLitUseCount':fc['single_lit'],'specialUseCount':special,'specialDistinctTechniqueSetCount':len(techrows),'specialFamilyUseCounts':{k:fc[k] for k in sorted(fc) if k not in ('layered_lit','single_lit')},'specialFamilyDistinctTechniqueSetCounts':dict(sorted(famtech.items())),'classificationFailureCount':0},'proofBoundary':'This census proves the exact retained-world material population and TechniqueSet identities for the non-layered special tail. Family labels are deterministic name-family routing, not claims about pixel-shader arithmetic. Helper compatibility preserves the same packed-pointer proof. Water/emissive/unlit/TV/raw-normal behavior still requires shader/pass semantic proof before exact visual playback is certified.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mp-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus/mp'));ap.add_argument('--zm-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.mp_root,a.zm_root);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
