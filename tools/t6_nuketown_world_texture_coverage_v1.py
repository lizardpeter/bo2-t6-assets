#!/usr/bin/env python3
from __future__ import annotations

import argparse,base64,json,zlib
from collections import Counter
from pathlib import Path

ADMISSIBLE={'exact-pair','unique-data-hash'}
IDENTITY='$identitynormalmap'


def load_canonical(path:Path)->dict:
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))


def first_semantic(material:dict,semantic:int):
    return next((t for t in material.get('textures',[]) if int(t.get('semantic',-1))==semantic),None)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--map-census',type=Path,required=True)
    ap.add_argument('--base-extraction',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()

    doc=load_canonical(a.manifest)
    mc=json.loads(a.map_census.read_text())
    be=json.loads(a.base_extraction.read_text())
    map_images={r['image'] for r in mc['rows'] if r['state'] in ADMISSIBLE}
    base_images={r['image'] for r in be['rows']}
    assert len(map_images)==171
    assert len(base_images)==185
    assert not (map_images & base_images)
    validated=set(map_images)|set(base_images)|{IDENTITY}

    rows=[]; counts=Counter(); unresolved_first=Counter()
    for m in doc['materials']:
        color=first_semantic(m,2); normal=first_semantic(m,5)
        cimg=color['image'] if color else None
        nimg=normal['image'] if normal else None
        chas=cimg is not None; nhas=nimg is not None
        cok=cimg in validated if chas else False
        nok=nimg in validated if nhas else False
        if chas: counts['materialsWithColorSlot']+=1
        if nhas: counts['materialsWithNormalSlot']+=1
        if cok: counts['materialsWithValidatedColor']+=1
        elif chas: unresolved_first[cimg]+=1
        if nok: counts['materialsWithValidatedNormal']+=1
        elif nhas: unresolved_first[nimg]+=1
        if cok and (not nhas or nok): counts['materialsVisuallyCompleteForFirstColorNormal']+=1
        if cok: counts['materialsAtLeastColorReady']+=1
        if not cok: counts['materialsMissingPrimaryColor']+=1
        if nhas and not nok: counts['materialsMissingPrimaryNormal']+=1
        rows.append({
            'material':m['name'],
            'firstColor':{'image':cimg,'validated':cok,'source':'map' if cimg in map_images else 'base' if cimg in base_images else None} if chas else None,
            'firstNormal':{'image':nimg,'validated':nok,'source':'identity' if nimg==IDENTITY else 'map' if nimg in map_images else 'base' if nimg in base_images else None} if nhas else None,
            'visuallyCompleteForFirstColorNormal':bool(cok and (not nhas or nok)),
        })

    assert len(rows)==327
    report={
        'format':'t6-nuketown-world-validated-texture-coverage-v1',
        'validatedImageInventory':{
            'mapStreamed':len(map_images),
            'baseAdditionalStreamed':len(base_images),
            'nonStreamedIdentityNormal':1,
            'totalValidatedUsableImages':len(validated),
        },
        'summary':dict(counts),
        'unresolvedPrimaryImages':[
            {'image':name,'materialReferenceCount':count}
            for name,count in sorted(unresolved_first.items(),key=lambda x:(-x[1],x[0]))
        ],
        'materials':rows,
        'proofBoundary':'Coverage is measured only against the first live semantic-2 color entry and first live semantic-5 normal entry in each canonical retail world MaterialTextureDef array. A streamed image counts as validated only if admitted by the map census or present in the fully CRC29/dimension-validated base extraction proof. The non-streamed $identitynormalmap is admitted directly from the canonical live GfxImage identity. Later layers, semantic-8/10 entries, and unresolved streamed images do not inflate these visual-completeness counts.',
    }
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'validatedImageInventory':report['validatedImageInventory'],'summary':report['summary'],'unresolvedPrimaryImageCount':len(report['unresolvedPrimaryImages'])},indent=2,sort_keys=True))

if __name__=='__main__': main()
