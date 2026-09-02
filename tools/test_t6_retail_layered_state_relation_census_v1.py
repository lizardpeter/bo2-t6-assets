#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXP={'retainedMapCount':5,'layeredMaterialCount':1130,'baseComponentPresentCount':1126,'baseComponentMissingCount':4,'activeGeneratedRouteCount':31514,'activeGeneratedBaseRouteMissingCount':0,'byteIdenticalToBaseRouteCount':31500,'transformedRouteCount':14,'distinctTransformationCount':2,'transformedSlots':[2,34],'onlyObservedTransformation':'srcBlendRgb SRCALPHA(5) -> ONE(2), all other 60 state bits unchanged'}
def validate(d):
 assert d['format']=='t6-retail-layered-state-relation-census-v1';assert d['summary']==EXP;assert len(d['missingFirstComponents'])==4;assert sum(t['count'] for t in d['transformations'])==14
 for t in d['transformations']:
  assert t['slot'] in (2,34) and t['baseSrcBlendRgb']==5 and t['generatedSrcBlendRgb']==2 and t['xor']=='0000000000000007' and t['semantic']=='SRCALPHA -> ONE'
def load(p):
 s=importlib.util.spec_from_file_location('r',p);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_STATE_RELATION_CENSUS_V1.json'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_state_relation_census_v1.py'));ap.add_argument('--mp-root',type=Path);ap.add_argument('--zm-root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.mp_root is not None or a.zm_root is not None:
  assert a.mp_root and a.zm_root;m=load(a.verifier);r=m.build(a.mp_root,a.zm_root);validate(r);assert r==d
 print('PASS: T6 layered state relation census v1 regression');return 0
if __name__=='__main__':raise SystemExit(main())
