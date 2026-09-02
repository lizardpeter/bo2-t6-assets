#!/usr/bin/env python3
"""Regression for retained T6 GfxWorld Material render-state retail proof."""
from __future__ import annotations
import argparse, importlib.util, json, re
from pathlib import Path

HEX64=re.compile(r'^[0-9a-f]{64}$')
EXPECTED_SUMMARY={
 'activeRouteSlotCount':24851,'constantCount':2030,'constantValidationFailureCount':0,
 'enumFailureCount':0,'inlineImageCount':667,'inlineLoadDefCount':665,
 'inlineResourceBytes':0,'materialCount':915,'referencedStateCount':4463,
 'retainedCorpusExecutionClean':True,'retainedMapCount':3,'routingFailureCount':0,
 'runtimeD3DNonzeroPointerCount':0,'runtimeD3DPointerSlotCount':13389,
 'stateCount':4463,'textureCount':3287,'uniqueDecodedStateCount':36,'uniqueRawStateCount':36,
}
EXPECTED_STATE_SET='8a2ab7669ec0f3d84bd14daf6ba76feaa2303f8995372b174008c94432c49e26'
EXPECTED_MAPS={
 'mp_nuketown_2020':dict(source='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505',first=84465666,last=84618654,count=327,root='741b142f5a9e1399e1c8aa9018b8dbff3f5e35968cab5489d20252f24e653ed5',meta='8f4619f35f9e2663def2dee7cd7ebfdb3693278d5d0f064c58124dfd8eb1de9d'),
 'mp_raid':dict(source='d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8',first=86602090,last=86768156,count=352,root='78a02da16a5fd8400af6563783714d3f562055f90b4525ad8dc41365e8070b70',meta='99d15d44174048ecdbed65aa5c9686db461650d36d08b878bfaa1106ae293701'),
 'mp_hijacked':dict(source='8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b',first=76243098,last=76363007,count=236,root='62333ae7adb66c23cf8d02448db75e3f5d90eb5ebd1e8a1a2ecb8df14fe4a9eb',meta='19e91ca5efe0fe6b97b524355825839aaaaf5aad6fc2756bcc367255ba2dd9c8'),
}

def load_module(path:Path):
 spec=importlib.util.spec_from_file_location('t6_state_census',path)
 if spec is None or spec.loader is None: raise RuntimeError(f'cannot import {path}')
 mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def validate(doc:dict)->None:
 assert doc['format']=='t6-retail-world-material-state-census-v1'
 assert doc['producer']=='tools/t6_retail_world_material_state_census_v1.py'
 assert doc['summary']==EXPECTED_SUMMARY
 assert doc['uniqueStateSignatureSetSha256']==EXPECTED_STATE_SET
 r=doc['reference']
 assert (r['materialFixedBytes'],r['materialTextureDefBytes'],r['materialConstantDefBytes'])==(104,16,32)
 assert (r['gfxStateBitsFixedBytes'],r['gfxStateBitsLoadBitsBytes'])==(20,8)
 assert (r['gfxImageFixedBytes'],r['gfxImageLoadDefHeaderBytes'])==(80,12)
 maps={m['map']:m for m in doc['maps']}; assert set(maps)==set(EXPECTED_MAPS)
 for name,exp in EXPECTED_MAPS.items():
  m=maps[name]; c=m['materialChain']; s=m['stats']
  assert m['source']['sha256']==exp['source']
  assert c['firstStart']==exp['first'] and c['lastEnd']==exp['last'] and c['materialCount']==exp['count'] and c['interRecordBridgeBytes']==8
  assert m['materialArchiveRootSha256']==exp['root'] and m['materialMetadataSha256']==exp['meta']
  assert HEX64.fullmatch(m['materialArchiveRootSha256']) and HEX64.fullmatch(m['materialMetadataSha256'])
  assert s['routingFailureCount']==s['enumFailureCount']==s['constantValidationFailureCount']==s['runtimeD3DNonzeroPointerCount']==0
  assert s['referencedStateCount']==s['stateCount']
  ex=m['materialArchiveExamples']; assert len(ex)==3
  assert ex[0]['start']==exp['first'] and ex[-1]['end']==exp['last']
  assert all(HEX64.fullmatch(x['archiveSha256']) for x in ex)

def main()->int:
 ap=argparse.ArgumentParser(); ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_WORLD_MATERIAL_STATE_CENSUS_V1.json')); ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_world_material_state_census_v1.py')); ap.add_argument('--root',type=Path); a=ap.parse_args()
 doc=json.loads(a.manifest.read_text()); validate(doc)
 mod=load_module(a.verifier)
 assert mod.valid_state(0) is False, 'all-zero state must fail cull validation'
 assert mod.valid_state(0xB) is False, 'blend factor 11 must be rejected'
 if a.root is not None:
  rerun=mod.build(a.root); validate(rerun); assert rerun==doc, 'retail rerun differs from committed proof'
 print('PASS: T6 retained world material render-state census regression')
 return 0
if __name__=='__main__': raise SystemExit(main())
