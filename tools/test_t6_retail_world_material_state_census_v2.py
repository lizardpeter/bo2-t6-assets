#!/usr/bin/env python3
"""Regression for retained-world T6 Material state census v2."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
EXPECTED_SUMMARY={
 'retainedMapCount':5,'retainedMpMapCount':3,'retainedZombiesMapCount':2,
 'materialCount':1802,'textureCount':6854,'inlineImageCount':1140,'inlineLoadDefCount':1136,'inlineResourceBytes':0,
 'constantCount':4518,'stateCount':8751,'activeRouteSlotCount':48750,'referencedStateCount':8751,
 'runtimeD3DPointerSlotCount':26253,'runtimeD3DNonzeroPointerCount':0,'routingFailureCount':0,'enumFailureCount':0,
 'constantValidationFailureCount':0,'uniqueRawStateCount':43,'uniqueDecodedStateCount':43,'retainedCorpusExecutionClean':True,
}
EXPECTED={
 'mp_nuketown_2020':(327,84618654,'741b142f5a9e1399e1c8aa9018b8dbff3f5e35968cab5489d20252f24e653ed5'),
 'mp_raid':(352,86768156,'78a02da16a5fd8400af6563783714d3f562055f90b4525ad8dc41365e8070b70'),
 'mp_hijacked':(236,76363007,'62333ae7adb66c23cf8d02448db75e3f5d90eb5ebd1e8a1a2ecb8df14fe4a9eb'),
 'zm_prison':(607,119605168,'36a5aa076ed968bfdbe93fffb215c59bfacba91698ee9cbcd1f9b21a2f3ff243'),
 'zm_tomb':(280,108564480,'ce8319d3ca56bca4a324c2f19e31c0e8dedbd43c81598a0af31868afda2d3081'),
}
SIG='09aa0dfb2286a231d2757b87fe9f8eec72a2460da9fc002dc99e0be8ca4044cb'
def validate(d):
 assert d['format']=='t6-retail-world-material-state-census-v2'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['uniqueStateSignatureSetSha256']==SIG
 maps={m['map']:m for m in d['maps']}; assert set(maps)==set(EXPECTED)
 for n,(count,end,root) in EXPECTED.items():
  m=maps[n]; assert m['materialChain']['materialCount']==count; assert m['materialChain']['lastEnd']==end
  assert m['materialArchiveRootSha256']==root
  s=m['stats']; assert s['materialCount']==count and s['routingFailureCount']==s['enumFailureCount']==s['constantValidationFailureCount']==0
  assert s['runtimeD3DNonzeroPointerCount']==0 and s['referencedStateCount']==s['stateCount']
def load_tool(path):
 spec=importlib.util.spec_from_file_location('t6_state_v2',path); assert spec and spec.loader
 m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_WORLD_MATERIAL_STATE_CENSUS_V2.json')); ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_world_material_state_census_v2.py')); ap.add_argument('--mp-root',type=Path); ap.add_argument('--zm-root',type=Path); a=ap.parse_args()
 d=json.loads(a.manifest.read_text()); validate(d)
 m=load_tool(a.verifier)
 assert not m.valid_state(0)
 assert not m.valid_state(0x000000000000400f)
 if a.mp_root is not None or a.zm_root is not None:
  assert a.mp_root is not None and a.zm_root is not None
  rerun=m.build(a.mp_root,a.zm_root); validate(rerun); assert rerun==d
 print('PASS: T6 retained-world Material state census v2 regression')
 return 0
if __name__=='__main__': raise SystemExit(main())
