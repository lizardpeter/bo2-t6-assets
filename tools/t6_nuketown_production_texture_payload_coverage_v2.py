#!/usr/bin/env python3
"""Extend v1 exact production payload coverage with traced retail IPAK resolutions."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def build(base,res):
    if base.get('format')!='t6-nuketown-production-texture-payload-coverage-v1': raise ValueError('base coverage drift')
    if res.get('format')!='t6-nuketown-unresolved-material-ipak-resolution-v1': raise ValueError('resolution drift')
    unresolved=set(base['unresolvedProductionImages']); resolved={x['name']:x for x in res['rows'] if x['status']=='resolved'}
    if not set(resolved)<=unresolved: raise ValueError('resolution contains non-v1-unresolved identity')
    for name,x in resolved.items():
        if not x.get('payloadSha256') or len(x['payloadSha256'])!=64 or not x.get('matches'): raise ValueError(f'{name}: incomplete exact payload proof')
    remaining=unresolved-set(resolved); s0=base['summary']; covered=s0['exactPayloadCoveredCount']+len(resolved); total=s0['productionUniqueImageCount']
    providers=[{'image':name,'provider':'retail-ipak-traced-native-hash','payloadSha256':x['payloadSha256'],'resolution':x['resolution'],'matches':x['matches'],'proof':'T6_NUKETOWN_UNRESOLVED_MATERIAL_IPAK_RESOLUTION_V1.json'} for name,x in sorted(resolved.items())]
    return {'format':'t6-nuketown-production-texture-payload-coverage-v2','map':base.get('map'),'summary':{'productionUniqueImageCount':total,'v1ExactPayloadCoveredCount':s0['exactPayloadCoveredCount'],'newTracedIpakCoveredCount':len(resolved),'exactPayloadCoveredCount':covered,'exactPayloadMissingCount':len(remaining),'exactPayloadCoverageRatio':covered/total,'materialUniqueImageCount':s0['materialUniqueImageCount'],'materialExactPayloadCoveredCount':s0['materialExactPayloadCoveredCount']+len(resolved),'materialExactPayloadMissingCount':len(remaining)},'newExactProviders':providers,'unresolvedProductionImages':sorted(remaining),'proofBoundary':'v1 providers are retained unchanged. New providers are admitted only from the separate native GfxImage hash trace plus exact retail IPAK byte-resolution proof; no name similarity, inferred hash, visual substitution, or expected dimensions are introduced.'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--resolution',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();o=build(json.loads(a.base.read_text()),json.loads(a.resolution.read_text()));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n');print(json.dumps(o['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
