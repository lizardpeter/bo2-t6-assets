#!/usr/bin/env python3
"""Fail-closed compact projection of the exact current-client sink field-flow proof."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
FORMAT='t6-current-client-zone-sink-fieldflow-probe-v1'; CLIENT='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf'; SINK='0x004174b0'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();raw=a.source.read_bytes();d=json.loads(raw)
 if d.get('format')!=FORMAT or d.get('client',{}).get('sha256')!=CLIENT or d.get('sink')!=SINK: raise SystemExit('unexpected source identity')
 groups=[g for g in d.get('baseRegisterGroups',[]) if set(g.get('offsetCounts',{}))=={'0','4','8'}]
 regs={g['baseRegister'] for g in groups}; hits=[]
 for h in d.get('fieldOffsetHits',[]):
  if any(m.get('base') in regs for m in h.get('matchedMemoryOperands',[])): hits.append(h)
 out={'format':'t6-current-client-zone-sink-fieldflow-compact-v1','source':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'client':d['client'],'sink':SINK,'groupsTouchingAllThreeOffsets':groups,'selectedHitContexts':hits,'summary':{'groupCount':len(groups),'selectedHitCount':len(hits)},'proofBoundary':'This is a lossless selection from the SHA-classified current-client field-flow proof. A register touching displacements 0/4/8 is not thereby proven to be the input row pointer and no source-level field name, priority rule, historical-retail behavior, or Technique winner is inferred.'}
 payload=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({'groups':groups,'selectedHitCount':len(hits),'outBytes':len(payload),'outSha256':hashlib.sha256(payload).hexdigest()},indent=2,sort_keys=True))
if __name__=='__main__':main()
