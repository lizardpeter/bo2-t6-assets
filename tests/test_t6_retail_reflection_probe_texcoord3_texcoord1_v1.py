#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
EXPECTED_SHA='7fbb15c7e8c4eba05aafd22587ed4cc4ab58265e51fe75ed0ad7dba82a18d2c2'
EXPECTED={'globalFamilyShaderCount':42,'globalFamilyFetchCount':42,'mappedPixelShaderCount':22,'mappedPassOccurrenceCount':24,'closedMappedShaderCount':22,'remainingUnmappedFamilyShaderCount':20,'directVertexShaderRoleProofCount':4,'crossMapAnchorConflictCount':0,'nuketownCandidatePairAmbiguityCount':0}
def run(root,verifier,base,prior):
 with tempfile.TemporaryDirectory() as td:
  out=Path(td)/'m.json'
  subprocess.run(['python',str(verifier),'--root',str(root),'--base-verifier',str(base),'--prior-alias',str(prior),'--out',str(out)],check=True,stdout=subprocess.DEVNULL)
  b=out.read_bytes();h=hashlib.sha256(b).hexdigest();d=json.loads(b)
  if h!=EXPECTED_SHA:raise SystemExit(f'manifest SHA mismatch {h}')
  for k,v in EXPECTED.items():
   if d['summary'].get(k)!=v:raise SystemExit(f'{k}: {d["summary"].get(k)} != {v}')
 return h
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root-a',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--root-b',type=Path,default=Path('/mnt/data/t6_rebuild2'))
 ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py'));ap.add_argument('--base-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py'));ap.add_argument('--prior-alias',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_PACKED_VS_ALIAS_V1.json'));a=ap.parse_args()
 h1=run(a.root_a,a.verifier,a.base_verifier,a.prior_alias);h2=run(a.root_b,a.verifier,a.base_verifier,a.prior_alias)
 if h1!=h2:raise SystemExit('independent manifests differ')
 print('PASS',h1)
