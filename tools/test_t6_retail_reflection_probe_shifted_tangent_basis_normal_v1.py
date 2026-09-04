#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED='8c61b6b282c21d066985df0ea7d9381cbc9c55667ef6fd94979b1ac67a127909'
def load(p):
 s=importlib.util.spec_from_file_location('m',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);a.add_argument('--verifier',type=Path,required=True)
 for n in ('closure-verifier','tangent-verifier','coordinate-verifier','weight-verifier','shared-verifier','surface-verifier','guard','mip-verifier','angular-verifier','semantic-verifier'):a.add_argument('--'+n,type=Path,required=True)
 q=a.parse_args();raw=q.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED:raise SystemExit(f'manifest sha mismatch {h}')
 m=load(q.verifier);d=m.build(q.root,q.closure_verifier,q.tangent_verifier,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);rb=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
 if hashlib.sha256(rb).hexdigest()!=EXPECTED:raise SystemExit('rebuilt sha mismatch')
 s=d['summary']
 if (s['targetFetchCount'],s['targetShaderCount'],s['unclassifiedCount'],s['baseTangentPatternCounts'])!=(24,24,0,{'TEXCOORD1/TEXCOORD2':12,'TEXCOORD2/TEXCOORD3':12}):raise SystemExit('summary mismatch')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED,'targetFetchCount':24},sort_keys=True))
if __name__=='__main__':main()
