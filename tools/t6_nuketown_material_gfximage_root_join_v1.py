#!/usr/bin/env python3
"""Join unresolved production Material GfxImage identities to exact OAT-emitted filenames.

Diagnostic only. No filename normalization is performed: a basename must equal the
retail identity byte-for-byte after removal of one known export extension.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
EXTENSIONS=('.iwi','.dds','.png','.tga','.json')

def stem(path:str)->str:
    name=Path(path).name
    low=name.lower()
    for ext in EXTENSIONS:
        if low.endswith(ext): return name[:-len(ext)]
    return name

def build(payload,probe):
    if payload.get('format')!='t6-nuketown-production-texture-payload-coverage-v1': raise ValueError('payload proof drift')
    if probe.get('format')!='t6-nuketown-material-gfximage-root-probe-v1': raise ValueError('root probe drift')
    unresolved=set(payload.get('unresolvedProductionImages') or [])
    if len(unresolved)!=347: raise ValueError(f'expected 347 unresolved Material images, got {len(unresolved)}')
    owners={x:[] for x in unresolved}; emitted={}
    for root,row in probe['roots'].items():
        for p in row.get('files',[]):
            s=stem(p); emitted.setdefault(s,[]).append({'root':root,'path':p})
            if s in owners: owners[s].append({'root':root,'path':p})
    exact={k:v for k,v in owners.items() if v}; absent=sorted(k for k,v in owners.items() if not v)
    multi={k:v for k,v in exact.items() if len({x['root'] for x in v})>1}
    return {'format':'t6-nuketown-material-gfximage-root-join-v1','summary':{'unresolvedMaterialImageCount':347,'exactFilenameJoinCount':len(exact),'noExactFilenameJoinCount':len(absent),'multiRootExactFilenameJoinCount':len(multi)},'exactFilenameJoins':exact,'noExactFilenameJoin':absent,'proofBoundary':'Diagnostic root visibility only. The join performs no star/underscore, case, slash, extension-family, semantic, or fuzzy normalization. Even an exact emitted filename is not payload-byte authority; packed/inline loadDef ownership and exact bytes remain separate gates.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=build(json.loads(a.payload.read_text()),json.loads(a.probe.read_text()));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
