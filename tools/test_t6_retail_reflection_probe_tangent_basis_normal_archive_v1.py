#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED='4fdd74db0c782398e92a83b284577e0a2a108a1abc9ae10139781c2c9fbee7d7'
def load(p):
 s=importlib.util.spec_from_file_location('a',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);a.add_argument('--archive-verifier',type=Path,required=True);a.add_argument('--base-verifier',type=Path,required=True)
 for n in ('coordinate-verifier','weight-verifier','shared-verifier','surface-verifier','guard','mip-verifier','angular-verifier','semantic-verifier'):a.add_argument('--'+n,type=Path,required=True)
 q=a.parse_args();raw=q.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED:raise SystemExit(f'manifest sha mismatch {h}')
 m=load(q.archive_verifier);b=load(q.base_verifier);d=b.build(q.root,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);o=m.compact(d);rb=(json.dumps(o,indent=2,sort_keys=True)+'\n').encode()
 if hashlib.sha256(rb).hexdigest()!=EXPECTED:raise SystemExit('rebuilt sha mismatch')
 if json.loads(raw)['summary']!=o['summary']:raise SystemExit('summary mismatch')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED,'standardTangentBasisShaderCount':958,'alternateTargetShaderCount':37},sort_keys=True))
if __name__=='__main__':main()
