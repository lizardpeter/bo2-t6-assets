#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
EXPECTED_SHA='0b44b3e1fdabf7a5b468ea004b0ef91dd41810a37725a7d3036a6e9f5bcafc06'
EXPECTED={'globalFamilyShaderCount':11,'globalFamilyFetchCount':11,'mappedPixelShaderCount':11,'mappedPassOccurrenceCount':11,'directVertexShaderRoleProofCount':5,'introductionCalibrationCount':5,'introductionCalibrationFailureCount':0,'resolvedPackedPointerCount':2,'closedShaderCount':11,'closedFetchCount':11}
def run(root,a):
 with tempfile.TemporaryDirectory() as td:
  out=Path(td)/'m.json'
  subprocess.run(['python',str(a.verifier),'--root',str(root),'--base-verifier',str(a.base_verifier),'--broad-verifier',str(a.broad_verifier),'--target-set',str(a.target_set),'--out',str(out)],check=True,stdout=subprocess.DEVNULL)
  raw=out.read_bytes();h=hashlib.sha256(raw).hexdigest();d=json.loads(raw)
  if h!=EXPECTED_SHA:raise SystemExit(f'manifest SHA mismatch {h}')
  for k,v in EXPECTED.items():
   if d['summary'].get(k)!=v:raise SystemExit(f'{k}: {d["summary"].get(k)} != {v}')
  return h
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root-a',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--root-b',type=Path,default=Path('/mnt/data/t6_rebuild2'));ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord1_texcoord0_v1.py'));ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'));ap.add_argument('--broad-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'));ap.add_argument('--target-set',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_TEXCOORD1_TEXCOORD0_TARGET_V1.json'));a=ap.parse_args();h1=run(a.root_a,a);h2=run(a.root_b,a)
 if h1!=h2:raise SystemExit('independent manifests differ')
 print('PASS',h1)
