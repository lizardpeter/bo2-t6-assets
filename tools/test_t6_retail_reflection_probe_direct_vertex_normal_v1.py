#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from pathlib import Path
EXPECTED_SHA='0fbe6a12648e177e117ae8f4841ab1223f5babbf9c7057247f04dc3584f59469'
EXPECTED_SUMMARY={'crossMapAnchoredPointerCount':18,'directVertexShaderOccurrenceCount':24,'globalOperandFamilyShaderCount':616,
'introductionOnlyPointerCount':6,'introductionPatternCountsSha256':'ae17ae2ec340aec3fef7f4b24e4429febc169d6e3f43076ae745f1b01910e612',
'introductionRuleValidationCount':18,'introductionRuleValidationFailureCount':0,'mappedPassOccurrenceCount':902,'mappedPixelShaderCount':374,
'normalInputAncestryCheckCount':24,'normalInputAncestryFailureCount':0,'packedVertexShaderOccurrenceCount':878,'resolvedVertexShaderCount':8,
'resolvedVsCountsSha256':'e7b6016ac6b48c6478176057becba9d37cb2685e3076baa5a27ad9a8cb36da25','shadowLookupBindingCount':410,
'texcoord5WorldPositionProducerProofCount':8,'uniquePackedPointerCount':24,'vertexNormalProducerFailureCount':0,'vertexNormalProducerProofCount':8,
'vertexShaderRowsSha256':'9b1e5b65cd559cfbd09e243cc5c9e6c17321114088c025bb01b480603676c793',
'viewProjectionBindingCheckCount':902,'worldMatrixBindingCheckCount':902}
def load(p):
 s=importlib.util.spec_from_file_location('proof',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);a.add_argument('--verifier',type=Path,required=True)
 for n in ('producer-verifier','alias-verifier','coordinate-verifier','weight-verifier','surface-verifier','shared-verifier','semantic-verifier','guard','matrix-verifier'):
  a.add_argument('--'+n,type=Path,required=True)
 q=a.parse_args();raw=q.manifest.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if h!=EXPECTED_SHA:raise SystemExit(f'manifest sha mismatch {h}')
 doc=json.loads(raw)
 if doc.get('summary')!=EXPECTED_SUMMARY:raise SystemExit('summary mismatch')
 m=load(q.verifier);d=m.build(q.root,q.producer_verifier,q.alias_verifier,q.coordinate_verifier,q.weight_verifier,q.surface_verifier,q.shared_verifier,q.semantic_verifier,q.guard,q.matrix_verifier)
 b=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
 if hashlib.sha256(b).hexdigest()!=EXPECTED_SHA:raise SystemExit('rebuilt sha mismatch')
 if d!=doc:raise SystemExit('rebuilt manifest differs')
 print(json.dumps({'status':'pass','manifestSha256':EXPECTED_SHA,'mappedPassOccurrenceCount':902,'resolvedVertexShaderCount':8},sort_keys=True))
if __name__=='__main__':main()
