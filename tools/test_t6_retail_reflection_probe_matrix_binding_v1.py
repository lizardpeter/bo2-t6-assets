#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, tempfile
from pathlib import Path
EXPECTED_MANIFEST_SHA256='95352fe874098ef2ebf70dc6d775dcff201897ae88f5486997777985e2378e17'
EXPECTED_SUMMARY={
 'retainedMapCount':5,'surfaceNormalTargetShaderCount':4086,'targetPassOccurrenceCount':5676,
 'targetPassArgumentPointerKinds':{'following':5676},'worldMatrixBindingCheckCount':5676,
 'worldMatrixBindingFailureCount':0,'worldMatrixSourceIndex':213,'worldMatrixDestinationBuffer':3,
 'worldMatrixDestinationOffset':0,'worldMatrixSizeBytes':64,'worldMatrixFirstRow':0,'worldMatrixRowCount':4,
 'transposeViewProjectionBindingCount':5676,'transposeShadowLookupBindingCount':2580,
 'occurrenceRowsSha256':'4454cb8cb2cf84e885192eecb823aef936f7f4dab2fa6bd899754ee7eb681768',
 'matrixBindingRowsSha256':'aca8513acaba834ae626bb79aeafaf9b313bdb1d160d8b617bc87c3e89f04d59',
 'mapCountsSha256':'7019b85253c025f3df56128bfbbaed5ae3db662dca34c0749847e4a6a2808a5d',
 'slotCountsSha256':'3e122f64523a1ae895fdd1035cba32db6734baf6a7fe5e6e9ce4c98099dc784a'}

def load(path:Path):
 s=importlib.util.spec_from_file_location('proof',path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--verifier',type=Path,required=True)
 ap.add_argument('--producer-verifier',type=Path,required=True);ap.add_argument('--coordinate-verifier',type=Path,required=True);ap.add_argument('--mip-verifier',type=Path,required=True);ap.add_argument('--weight-verifier',type=Path,required=True);ap.add_argument('--angular-verifier',type=Path,required=True);ap.add_argument('--semantic-verifier',type=Path,required=True);ap.add_argument('--surface-verifier',type=Path,required=True);ap.add_argument('--shared-verifier',type=Path,required=True);ap.add_argument('--guard',type=Path,required=True);a=ap.parse_args()
 raw=a.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED_MANIFEST_SHA256:raise SystemExit(f'manifest sha mismatch {h}')
 doc=json.loads(raw)
 if doc.get('summary')!=EXPECTED_SUMMARY:raise SystemExit('manifest summary mismatch')
 m=load(a.verifier);rebuilt=m.build(a.root,a.producer_verifier,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.angular_verifier,a.semantic_verifier,a.surface_verifier,a.shared_verifier,a.guard)
 b=(json.dumps(rebuilt,indent=2,sort_keys=True)+'\n').encode()
 if hashlib.sha256(b).hexdigest()!=EXPECTED_MANIFEST_SHA256:raise SystemExit('rebuilt manifest sha mismatch')
 if rebuilt!=doc:raise SystemExit('rebuilt manifest differs')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED_MANIFEST_SHA256,'targetPassOccurrenceCount':5676,'worldMatrixBindingCheckCount':5676},sort_keys=True))
if __name__=='__main__':main()
