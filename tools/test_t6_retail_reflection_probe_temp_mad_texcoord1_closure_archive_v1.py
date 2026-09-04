#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED='c6252644dacd6d7d4650c8b382b0b3fc9436bb7623ab7254e0d234a2dc5a2e8f'

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);a.add_argument('--archive-verifier',type=Path,required=True);a.add_argument('--base-verifier',type=Path,required=True)
 for n in ('tangent-verifier','coordinate-verifier','weight-verifier','shared-verifier','surface-verifier','guard','mip-verifier','angular-verifier','semantic-verifier'):a.add_argument('--'+n,type=Path,required=True)
 q=a.parse_args();raw=q.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED:raise SystemExit(f'manifest sha mismatch {h}')
 arc=load(q.archive_verifier,'arc');base=load(q.base_verifier,'base')
 d=base.build(q.root,q.tangent_verifier,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);o=arc.compact(d);rb=(json.dumps(o,indent=2,sort_keys=True)+'\n').encode()
 if hashlib.sha256(rb).hexdigest()!=EXPECTED:raise SystemExit('rebuilt sha mismatch')
 s=o['summary']
 exp=(995,964,20,11,0,977,7)
 got=(s['targetTempMadTexcoord1ShaderCount'],s['normalNamedTangentBasisShaderCount'],s['camoDetailTangentBasisShaderCount'],s['waterCrossBasisShaderCount'],s['unclassifiedShaderCount'],s['xyzCrossPackingShaderCount'],s['yzwCrossPackingShaderCount'])
 if got!=exp:raise SystemExit(f'summary mismatch {got}')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED,'classes':{'normalNamedTangentBasis':964,'camoDetailTangentBasis':20,'waterCrossBasis':11}},sort_keys=True))
if __name__=='__main__':main()
