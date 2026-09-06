#!/usr/bin/env python3
"""Build exact packed-Material -> packed-GfxImage bindings for Nuketown.

Inputs:
  * the pointer-proven cross-family packed GfxImage alias bank;
  * the canonical 81/81 DLC0/shared IPAK payload closure.

Each alias-bank evidence row proves that a packed Material variant reuses the
same retail texture-table slot as its independently decoded inline Material
counterpart.  This stage does not infer from material names: it only serializes
those retained evidence joins and attaches the exact payload identity already
closed by the IPAK census.
"""
from __future__ import annotations

import argparse, base64, hashlib, json, zlib
from collections import defaultdict
from pathlib import Path


def load_zb64(path: Path):
    raw=zlib.decompress(base64.b64decode(path.read_bytes().strip()))
    return json.loads(raw),raw

def sha(b: bytes)->str:return hashlib.sha256(b).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--alias-bank',type=Path,required=True)
    ap.add_argument('--closure',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    bank,bank_raw=load_zb64(a.alias_bank); closure,closure_raw=load_zb64(a.closure)
    if bank.get('format')!='t6-nuketown-cross-material-type-packed-image-alias-bank-v1':
        raise ValueError(f"unexpected alias bank {bank.get('format')!r}")
    if int(bank.get('aliasCount',-1))!=81 or int(bank.get('conflictCount',-1))!=0:
        raise ValueError('alias bank is not the retained conflict-free 81-row proof')
    cs=closure.get('summary') or {}
    expected={'aliasCount':81,'resolved':81,'missing':0,'conflict':0,'exactPair':81,'dataHashByteIdentical':0,'uniquePayloadCount':81}
    if cs!=expected: raise ValueError(f'closure is not canonical 81/81 exact: {cs}')
    if closure.get('failures'):raise ValueError('closure contains failures')

    by_alias={int(r['aliasIndex']):r for r in closure['aliases']}
    if sorted(by_alias)!=list(range(81)):raise ValueError('closure alias indices are not dense 0..80')
    bindings=[]; pair_seen={}; alias_use=defaultdict(int)
    for ai,alias in enumerate(bank['aliases']):
        cr=by_alias[ai]
        if cr['status']!='resolved' or cr['resolution']!='exact-pair':
            raise ValueError(f'alias {ai} is not exact-pair resolved')
        exact=(int(alias['hash'])&0xffffffff,int(alias['dataHash'])&0x1fffffff)
        if (int(cr['nameHash']),int(cr['dataHash']))!=exact:
            raise ValueError(f'alias/closure hash drift at {ai}')
        if cr['name']!=alias['name']:
            raise ValueError(f'alias/closure name drift at {ai}')
        if not cr.get('payloadSha256'):
            raise ValueError(f'alias {ai} lacks exact payload SHA')
        ev=alias.get('evidence') or []
        if not ev: raise ValueError(f'alias {ai} has no retained binding evidence')
        for e in ev:
            if set(e)!={'inlineMaterial','packedMaterial'}:
                raise ValueError(f'unexpected evidence schema at alias {ai}: {sorted(e)}')
            row={
                'packedMaterial':e['packedMaterial'],
                'slot':int(alias['slot']),
                'semantic':int(alias['semantic']),
                'samplerState':int(alias['samplerState']),
                'gfxImage':alias['name'],
                'gfxImageHash':int(alias['hash'])&0xffffffff,
                'streamedDataHash':int(alias['dataHash'])&0x1fffffff,
                'block':int(alias['block']),
                'virtualOffset':int(alias['virtualOffset']),
                'width':int(alias['width']),'height':int(alias['height']),'depth':int(alias['depth']),
                'payloadSha256':cr['payloadSha256'],
                'inlineEvidenceMaterial':e['inlineMaterial'],
                'aliasIndex':ai,
            }
            key=(row['packedMaterial'],row['slot'])
            signature={k:v for k,v in row.items() if k not in ('inlineEvidenceMaterial','aliasIndex')}
            old=pair_seen.get(key)
            if old is not None and old!=signature:
                raise ValueError(f'conflicting packed Material slot binding {key}: {old} != {signature}')
            pair_seen[key]=signature; bindings.append(row); alias_use[ai]+=1

    # Multiple inline witnesses may prove one packed slot; collapse only when
    # every identity field is equal while preserving all witnesses.
    grouped={}
    for r in bindings:
        key=(r['packedMaterial'],r['slot']); g=grouped.get(key)
        witness={'inlineMaterial':r['inlineEvidenceMaterial'],'aliasIndex':r['aliasIndex']}
        core={k:v for k,v in r.items() if k not in ('inlineEvidenceMaterial','aliasIndex')}
        if g is None:
            g=dict(core);g['evidence']=[witness];grouped[key]=g
        elif witness not in g['evidence']:g['evidence'].append(witness)
    rows=[]
    for key in sorted(grouped):
        r=grouped[key];r['evidence'].sort(key=lambda x:(x['inlineMaterial'],x['aliasIndex']));rows.append(r)

    bymat=defaultdict(list)
    for r in rows:bymat[r['packedMaterial']].append(r)
    materials=[]
    for m in sorted(bymat):
        rr=sorted(bymat[m],key=lambda x:x['slot'])
        slots=[x['slot'] for x in rr]
        if len(slots)!=len(set(slots)):raise ValueError(f'duplicate slot after grouping for {m}')
        materials.append({'material':m,'bindings':rr})

    out={
      'format':'t6-nuketown-packed-material-image-binding-v1','map':'mp_nuketown_2020',
      'source':{
        'aliasBank':{'path':str(a.alias_bank),'rawBytes':len(bank_raw),'rawSha256':sha(bank_raw)},
        'ipakClosure':{'path':str(a.closure),'rawBytes':len(closure_raw),'rawSha256':sha(closure_raw)},
      },
      'summary':{
        'aliasCount':81,'aliasesWithBindingEvidence':sum(1 for x in alias_use if alias_use[x]>0),
        'evidenceJoinCount':len(bindings),'uniquePackedMaterialSlotBindings':len(rows),
        'packedMaterialCount':len(materials),'conflictCount':0,
        'uniquePayloadCount':len({r['payloadSha256'] for r in rows}),
      },
      'materials':materials,
      'proofBoundary':'Only retained alias-bank evidence joins are serialized. Each packed Material/slot is linked to the exact pointer-proven GfxImage and exact-pair IPAK payload SHA. No suffix/name/semantic/visual inference is performed by this stage; those fields are archival metadata only.',
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.write_bytes(b)
    print(json.dumps({'out':str(a.out),'bytes':len(b),'sha256':sha(b),'summary':out['summary']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
