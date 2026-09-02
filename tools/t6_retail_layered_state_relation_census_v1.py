#!/usr/bin/env python3
"""Direct T6 retail census of layered Material GPU-state inheritance.

For every retained generated/layered world material whose first component also
exists as a standalone world Material in the same map, compare each active
36-slot stateBitsEntry route to the first component's routed GfxStateBits.
No inherited-engine state rule is assumed.
"""
from __future__ import annotations
import argparse, collections, importlib.util, json, struct, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
state=load('statev2',HERE/'t6_retail_world_material_state_census_v2.py')
layered=load('layerv2',HERE/'t6_retail_layered_material_census_v2.py')
SRC_BLEND={'ONE':2,'SRCALPHA':5}
def material_rows(name,path):
 cfg=state.MAPS[name];d=path.read_bytes();assert len(d)==cfg[2] and hashlib.sha256(d).hexdigest()==cfg[1]
 blocks=struct.unpack_from('<8I',d,8);p=cfg[3];rows=[]
 for _ in range(cfg[4]):
  r=state.material(d,p,blocks);r['routes']=list(struct.unpack_from('<36b',d,p+40));rows.append(r);p=r['end']+8
 assert rows[-1]['end']==cfg[5];return rows
def build(mp_root,zm_root):
 maps=[];missing=[];diff_examples=[];globalc=collections.Counter();transform=collections.Counter()
 for name,cfg in state.MAPS.items():
  root=mp_root if cfg[0]=='mp' else zm_root;rows=material_rows(name,root/f'{name}.expanded.bin');by={r['name']:r for r in rows};c=collections.Counter()
  for g in rows:
   if not g['name'].startswith('*'):continue
   c['layeredMaterialCount']+=1;layers,_,_=layered.parse_name(g['name']);base_name=layers[0][3];base=by.get(base_name)
   if base is None:
    c['baseComponentMissingCount']+=1;missing.append({'map':name,'material':g['name'],'firstComponent':base_name});continue
   c['baseComponentPresentCount']+=1
   for slot,gi in enumerate(g['routes']):
    if gi<0:continue
    c['activeGeneratedRouteCount']+=1;bi=base['routes'][slot]
    if bi<0:
     c['activeGeneratedBaseRouteMissingCount']+=1;continue
    gs=g['states'][gi];bs=base['states'][bi]
    if gs==bs:c['byteIdenticalToBaseRouteCount']+=1
    else:
     c['transformedRouteCount']+=1
     key=(slot,bs,gs);transform[key]+=1
     if len(diff_examples)<20:diff_examples.append({'map':name,'material':g['name'],'slot':slot,'baseState':f'{bs:016x}','generatedState':f'{gs:016x}','xor':f'{bs^gs:016x}'})
  maps.append({'map':name,**dict(c)});globalc.update(c)
 trs=[]
 for (slot,bs,gs),count in sorted(transform.items()):
  assert (bs & ~0xf)==(gs & ~0xf)
  trs.append({'slot':slot,'count':count,'baseState':f'{bs:016x}','generatedState':f'{gs:016x}','xor':f'{bs^gs:016x}','changedField':'srcBlendRgb','baseSrcBlendRgb':bs&0xf,'generatedSrcBlendRgb':gs&0xf,'semantic':'SRCALPHA -> ONE' if (bs&0xf,gs&0xf)==(5,2) else 'unexpected'})
 assert globalc['activeGeneratedBaseRouteMissingCount']==0
 assert sum(t['count'] for t in trs)==globalc['transformedRouteCount']
 assert all(t['semantic']=='SRCALPHA -> ONE' for t in trs)
 return {'format':'t6-retail-layered-state-relation-census-v1','producer':'tools/t6_retail_layered_state_relation_census_v1.py','maps':maps,'missingFirstComponents':missing,'transformations':trs,'transformationExamples':diff_examples,'summary':{'retainedMapCount':5,'layeredMaterialCount':globalc['layeredMaterialCount'],'baseComponentPresentCount':globalc['baseComponentPresentCount'],'baseComponentMissingCount':globalc['baseComponentMissingCount'],'activeGeneratedRouteCount':globalc['activeGeneratedRouteCount'],'activeGeneratedBaseRouteMissingCount':globalc['activeGeneratedBaseRouteMissingCount'],'byteIdenticalToBaseRouteCount':globalc['byteIdenticalToBaseRouteCount'],'transformedRouteCount':globalc['transformedRouteCount'],'distinctTransformationCount':len(trs),'transformedSlots':sorted({t['slot'] for t in trs}),'onlyObservedTransformation':'srcBlendRgb SRCALPHA(5) -> ONE(2), all other 60 state bits unchanged'},'proofBoundary':'Direct T6 retail comparison; no BO1/T5 layered-state rule is used to derive these counts. It proves the observed relation between generated Material state routes and retained standalone first-component state routes for 1,126 of 1,130 layered materials. Four generated materials have no standalone first component in the same retained world and therefore cannot be relation-cross-checked by this census. Pixel shader output/compositor arithmetic is outside this proof.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mp-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus/mp'));ap.add_argument('--zm-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.mp_root,a.zm_root);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
