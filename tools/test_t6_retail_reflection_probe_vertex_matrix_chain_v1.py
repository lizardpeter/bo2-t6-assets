#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED_SHA='2b9b22cc2dbb6508add1a6aed9a472b2b44218d367f57437650de9c65710dbf6'
EXPECTED_SUMMARY={
 'resolvedPassOccurrenceCount':5676,'resolvedVertexShaderCount':16,
 'texcoord5ExactWorldValueReuseCheckCount':48,'texcoord5ExactWorldValueReuseFailureCount':0,
 'vertexShaderRowsSha256':'73d7da5c1dab1de6b9dc553d3db64b920af633f4bcfa4946168e308546914f67',
 'viewProjectionDp4CheckCount':64,'viewProjectionDp4FailureCount':0,'viewProjectionRdefRowCheckCount':64,
 'worldMatrixRdefRowCheckCount':64,'worldPositionDp4CheckCount':64,'worldPositionDp4FailureCount':0}
def load(p):
 s=importlib.util.spec_from_file_location('proof',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True)
 a.add_argument('--verifier',type=Path,required=True);a.add_argument('--producer-verifier',type=Path,required=True)
 a.add_argument('--alias-verifier',type=Path,required=True);a.add_argument('--coordinate-verifier',type=Path,required=True)
 a.add_argument('--semantic-verifier',type=Path,required=True);a.add_argument('--alias-manifest',type=Path,required=True)
 a.add_argument('--matrix-manifest',type=Path,required=True);q=a.parse_args()
 raw=q.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED_SHA:raise SystemExit(f'manifest sha mismatch {h}')
 doc=json.loads(raw)
 if doc.get('summary')!=EXPECTED_SUMMARY:raise SystemExit('summary mismatch')
 m=load(q.verifier);rebuilt=m.build(q.root,q.producer_verifier,q.alias_verifier,q.coordinate_verifier,q.semantic_verifier,q.alias_manifest,q.matrix_manifest)
 b=(json.dumps(rebuilt,indent=2,sort_keys=True)+'\n').encode()
 if hashlib.sha256(b).hexdigest()!=EXPECTED_SHA:raise SystemExit('rebuilt sha mismatch')
 if rebuilt!=doc:raise SystemExit('rebuilt manifest differs')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED_SHA,'resolvedPassOccurrenceCount':5676,'resolvedVertexShaderCount':16},sort_keys=True))
if __name__=='__main__':main()
