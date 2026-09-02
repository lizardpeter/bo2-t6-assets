#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED={
 'retainedMapCount':5,'materialCount':1802,'layeredLitUseCount':1130,'singleLitUseCount':574,'specialUseCount':98,
 'specialDistinctTechniqueSetCount':31,'classificationFailureCount':0,
 'specialFamilyUseCounts':{'default':1,'emissive_or_burning':6,'rawnormal_special':1,'shadowcaster':8,'tv_special':1,'unlit':70,'water':11},
 'specialFamilyDistinctTechniqueSetCounts':{'default':1,'emissive_or_burning':3,'rawnormal_special':1,'shadowcaster':1,'tv_special':1,'unlit':17,'water':7},
}
MAP_SPECIAL={'mp_nuketown_2020':11,'mp_raid':15,'mp_hijacked':14,'zm_prison':31,'zm_tomb':27}
def validate(d):
 assert d['format']=='t6-retail-special-material-family-census-v1'; assert d['summary']==EXPECTED
 ms={m['map']:m for m in d['maps']}; assert set(ms)==set(MAP_SPECIAL)
 assert sum(m['materialCount'] for m in ms.values())==1802
 for n,c in MAP_SPECIAL.items(): assert ms[n]['specialUseCount']==c
 ts=d['specialTechniqueSets']; assert len(ts)==31; assert sum(x['useCount'] for x in ts)==98
 assert len({x['techniqueSet'] for x in ts})==31
 assert all(x['family'] in EXPECTED['specialFamilyUseCounts'] for x in ts)
def load(p):
 s=importlib.util.spec_from_file_location('specialv1',p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_special_material_family_census_v1.py'));ap.add_argument('--mp-root',type=Path);ap.add_argument('--zm-root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);m=load(a.verifier)
 assert m.classify('*1n_2(wpc/a:wpc/b)','lit_sm_r0c0n0_b1c1')=='layered_lit'
 assert m.classify('wpc/a','wpc_cod7water_we876z2f')=='water'
 try:m.classify('wpc/a','wpc_unknown_tech')
 except ValueError:pass
 else:raise AssertionError('unknown technique family accepted')
 if a.mp_root is not None or a.zm_root is not None:
  assert a.mp_root and a.zm_root; rerun=m.build(a.mp_root,a.zm_root); validate(rerun); assert rerun==d
 print('PASS: T6 retained special material family census v1 regression');return 0
if __name__=='__main__':raise SystemExit(main())
