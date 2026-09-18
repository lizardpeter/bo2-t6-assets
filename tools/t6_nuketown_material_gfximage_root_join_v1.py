#!/usr/bin/env python3
"""Join unresolved Material GfxImage identities to exact OAT-observed names."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def build(payload,probe):
    if payload.get('format')!='t6-nuketown-production-texture-payload-coverage-v1': raise ValueError('payload proof drift')
    if probe.get('format')!='t6-nuketown-material-gfximage-root-probe-v1': raise ValueError('root probe drift')
    unresolved=set(payload.get('unresolvedProductionImages') or [])
    if len(unresolved)!=347: raise ValueError(f'expected 347 unresolved Material images, got {len(unresolved)}')
    owners={x:[] for x in unresolved}
    for root,row in probe['roots'].items():
        names=row.get('dumpedImageNames')
        if not isinstance(names,list): raise ValueError(f'{root}: complete dumpedImageNames unavailable')
        missing=set(row.get('missingPayloadImageNames') or [])
        for name in names:
            if name in owners: owners[name].append({'root':root,'oatPayloadMissingInProbe':name in missing})
    exact={k:v for k,v in owners.items() if v}; absent=sorted(k for k,v in owners.items() if not v)
    multi={k:v for k,v in exact.items() if len({x['root'] for x in v})>1}
    missing_visible={k:v for k,v in exact.items() if all(x['oatPayloadMissingInProbe'] for x in v)}
    payload_visible={k:v for k,v in exact.items() if any(not x['oatPayloadMissingInProbe'] for x in v)}
    return {'format':'t6-nuketown-material-gfximage-root-join-v1','summary':{'unresolvedMaterialImageCount':347,'exactIdentityVisibilityJoinCount':len(exact),'noExactIdentityVisibilityJoinCount':len(absent),'multiRootExactIdentityVisibilityJoinCount':len(multi),'visibleButOatPayloadMissingCount':len(missing_visible),'visibleWithNonMissingOatPathCount':len(payload_visible)},'exactIdentityVisibilityJoins':exact,'noExactIdentityVisibilityJoin':absent,'proofBoundary':'Diagnostic root visibility only. Identity matching is exact string equality against the complete OAT-observed GfxImage names; no filename normalization, fuzzy matching, ordering, or semantic substitution is allowed. OAT missing-payload status describes only this invocation search path and is not retail payload absence. Visibility does not by itself prove packed hash/loadDef ownership or payload bytes.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=build(json.loads(a.payload.read_text()),json.loads(a.probe.read_text()));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
