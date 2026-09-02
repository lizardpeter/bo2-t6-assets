#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED={'retainedMapCount':5,'materialCount':1802,'layeredMaterialCount':1130,'exactSameMapGeneratedTextureSumProofCount':781,'pendingSameMapGeneratedTextureSumCount':349,'generatedTextureSumFailureCount':0,'mapLocalAmbiguousTokenCount':0,'formatPredictionMismatchCount':0,'actualWorldVertFormatHistogram':{'1':491,'2':297,'3':138,'4':123,'5':58,'6':12,'7':11}}
MAPS={'mp_nuketown_2020':120,'mp_raid':255,'mp_hijacked':151,'zm_prison':440,'zm_tomb':164}
def validate(d):
 assert d['format']=='t6-retail-layered-material-census-v2'; assert d['summary']==EXPECTED
 ms={m['map']:m for m in d['maps']}; assert set(ms)==set(MAPS)
 for n,count in MAPS.items():
  m=ms[n]; assert m['layeredMaterialCount']==count; assert m['formatPredictionMismatchCount']==0; assert m['mapLocalAmbiguousTokenCount']==0
 assert sum(m['exactSameMapGeneratedTextureSumProofCount'] for m in ms.values())==781
 assert sum(m['pendingSameMapGeneratedTextureSumCount'] for m in ms.values())==349
def load(path):
 s=importlib.util.spec_from_file_location('layeredv2',path); assert s and s.loader
 m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_MATERIAL_CENSUS_V2.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_material_census_v2.py'));ap.add_argument('--mp-root',type=Path);ap.add_argument('--zm-root',type=Path);ap.add_argument('--nuketown-fixture',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d);m=load(a.verifier)
 assert m.parse_name('*22n_14(wpc/a:wpc/b)')[1]==1
 assert m.parse_name('*65n_82n(wpc/a:wpc/b)')[1]==2
 assert m.parse_name('*22n_14_127(wpc/a:wpc/b:wpc/c)')[1]==3
 try:m.parse_name('*1n(wpc/a)')
 except ValueError:pass
 else:raise AssertionError('single-layer compound accepted')
 if a.mp_root is not None or a.zm_root is not None or a.nuketown_fixture is not None:
  assert a.mp_root and a.zm_root and a.nuketown_fixture
  rerun=m.build(a.mp_root,a.zm_root,a.nuketown_fixture);validate(rerun);assert rerun==d
 print('PASS: T6 retained layered material census v2 regression');return 0
if __name__=='__main__':raise SystemExit(main())
