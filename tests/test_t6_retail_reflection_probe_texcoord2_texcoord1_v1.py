#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED='7396c3ee4e75570ed31eac402c547cb7fe956bf49d7e32098987156c393f3293'
def load(p):
 s=importlib.util.spec_from_file_location('v',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def main():
 a=argparse.ArgumentParser();a.add_argument('--manifest',type=Path,required=True);a.add_argument('--verifier',type=Path,required=True);a.add_argument('--root',type=Path);a.add_argument('--prior-alias-manifest',type=Path,required=True);q=a.parse_args()
 raw=q.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED:raise SystemExit(f'manifest sha mismatch {h}')
 d=json.loads(raw);s=d['summary']
 exp={'globalFamilyShaderCount':75,'globalFamilyFetchCount':75,'mappedPixelShaderCount':20,'mappedPassOccurrenceCount':20,'unmappedPixelShaderCount':55,'candidateVertexShaderRoleProofCount':2,'targetCandidatePairAmbiguityCount':0,'closedMappedShaderCount':20,'remainingUnmappedFamilyShaderCount':55}
 for k,v in exp.items():
  if s.get(k)!=v:raise SystemExit(f'{k}: {s.get(k)} != {v}')
 if q.root:
  m=load(q.verifier);o=m.build(q.root,q.prior_alias_manifest);rb=(json.dumps(o,indent=2,sort_keys=True)+'\n').encode();rh=hashlib.sha256(rb).hexdigest()
  if rh!=EXPECTED:raise SystemExit(f'rebuilt sha mismatch {rh}')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED,'closedMappedShaderCount':20,'remainingUnmappedFamilyShaderCount':55},sort_keys=True))
if __name__=='__main__':main()
