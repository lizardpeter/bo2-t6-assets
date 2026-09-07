#!/usr/bin/env python3
"""Exact T6 PC32 top-level XModel/MaterialTechniqueSet serialized walker v1.

Retail map zones begin with the compact KeyValuePairs/SkinnedVertsDef/StringTable
prefix, followed in the early region by interleaved XMODEL (type 5) and
TECHNIQUE_SET (type 7) XAssets. This walker advances one exact source cursor
through such a range:

* XMODEL source consumption is delegated to the independently retail-validated
  ``XModelWalker`` (including its nested Materials/GfxImages/etc.);
* TECHNIQUE_SET source consumption uses the complete TechniqueSet/Technique/
  shader serializer already encoded in ``t6_material_techset_top_level_walk_v1``.

Packed/null references consume zero source bytes. Unsupported top-level asset
types fail closed. This is intended to prove exact early TechniqueSet XAsset
identity without relying on raw-name scan rank.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_material_techset_top_level_walk_v1 import Cursor, FOLLOW, INSERT, parse_front
from t6_xmodel_serialized_walker import XModelWalker

XMODEL=5
TECHSET=7


def walk(d:bytes,start_asset:int,end_asset:int,source_start:int)->dict:
    blocks,assets,_=parse_front(d);c=Cursor(d,source_start,blocks);rows=[]
    for q in range(start_asset,end_asset+1):
        a=assets[q]
        if a['headerRaw'] not in (FOLLOW,INSERT):
            raise ValueError(f'XAsset {q} top-level header is not inline: 0x{a["headerRaw"]:08X}')
        before=c.p
        try:
            if a['type']==XMODEL:
                w=XModelWalker(d,before).walk_xmodel()
                if w['blockers']:raise ValueError(f'XModel blockers: {w["blockers"]}')
                end=int(w['assetSerializedEnd'])
                if end<=before:raise ValueError('XModel did not advance')
                c.p=end
                r={'kind':'XMODEL','xmodelName':w['xmodel'].get('name'),'numBones':w['xmodel'].get('numBones'),'numSurfs':w['xmodel'].get('numSurfs')}
            elif a['type']==TECHSET:
                t=c.techset();r={'kind':'TECHNIQUE_SET','name':t['name'],'worldVertFormat':t['worldVertFormat'],'techniqueRefs':t['techniqueRefs']}
            else:
                raise ValueError(f'unsupported top-level XAsset type {a["type"]}')
        except Exception as exc:
            raise ValueError(
                f'XAsset {q} type={a["type"]} sourceStart={before}: {exc}'
            ) from exc
        r.update({'xassetIndex':q,'xassetType':a['type'],'sourceStart':before,'sourceEnd':c.p});rows.append(r)
    return {'format':'t6-xmodel-techset-top-level-walk-v1','startAssetIndex':start_asset,'endAssetIndex':end_asset,'sourceStart':source_start,'sourceEnd':c.p,'rows':rows,'directInlineShaders':[x for x in c.inlineShaders if x.get('program') and x['program'].get('direct')]}


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('expanded',type=Path);ap.add_argument('--start-asset',type=int,required=True);ap.add_argument('--end-asset',type=int,required=True);ap.add_argument('--source-start',type=lambda x:int(x,0),required=True);ap.add_argument('--expect-end',type=lambda x:int(x,0));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    d=a.expanded.read_bytes();o=walk(d,a.start_asset,a.end_asset,a.source_start);o['expandedSha256']=hashlib.sha256(d).hexdigest()
    if a.expect_end is not None:
        o['expectedEnd']=a.expect_end;o['expectedEndMatches']=o['sourceEnd']==a.expect_end
        if not o['expectedEndMatches']:raise SystemExit(f'end {o["sourceEnd"]} != expected {a.expect_end}')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n');print(json.dumps({'sourceEnd':o['sourceEnd'],'assetCount':len(o['rows']),'directInlineShaderCount':len(o['directInlineShaders'])},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
