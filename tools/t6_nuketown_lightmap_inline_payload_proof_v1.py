#!/usr/bin/env python3
"""Hash the two exact inline Nuketown secondary-lightmap payloads from retail bytes."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
SOURCE_SHA='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'
def h(b): return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--expanded',type=Path,required=True);ap.add_argument('--role-proof',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();raw=a.expanded.read_bytes()
 if h(raw)!=SOURCE_SHA or len(raw)!=154653476: raise ValueError('expanded retail source drift')
 p=json.loads(a.role_proof.read_text());
 if p.get('format')!='t6-nuketown-lightmap-role-presence-proof-v1' or not p.get('validation',{}).get('lightmapImagesEndExactlyAtVd0'): raise ValueError('role proof drift')
 rows=[]
 for e in p['lightmapArray']['entries']:
  if e['primary']['present'] or not e['secondary']['present']: raise ValueError('nullable lightmap role drift')
  g=e['secondary']['gfxImage']; start=g['dataStart']; size=g['resourceSize']; end=start+size
  if end!=g['objectEnd']: raise ValueError(f"{g['name']}: payload/object boundary drift")
  payload=raw[start:end]
  if len(payload)!=size: raise ValueError(f"{g['name']}: truncated payload")
  rows.append({'lightmapIndex':e['index'],'image':g['name'],'dataStart':start,'resourceSize':size,'width':g['width'],'height':g['height'],'depth':g['depth'],'loadDefFormat':g['loadDefFormat'],'payloadSha256':h(payload)})
 if [x['image'] for x in rows]!=['*lightmap0_secondary','*lightmap1_secondary']: raise ValueError('lightmap identity drift')
 out={'format':'t6-nuketown-lightmap-inline-payload-proof-v1','map':'mp_nuketown_2020','source':{'expandedBytes':len(raw),'expandedSha256':h(raw)},'payloads':rows,'summary':{'exactInlinePayloadCount':2,'exactInlinePayloadBytes':sum(x['resourceSize'] for x in rows)},'proofBoundary':'Payload hashes are over the exact serialized inline byte ranges selected by the independently recovered nullable GfxLightmap role proof. This proves byte ownership and exact recoverability, not pixel-channel meaning or the final shader equation.'}
 b=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(b);print(json.dumps({'sha256':h(b),**out['summary'],'payloads':[(x['image'],x['payloadSha256']) for x in rows]},indent=2))
if __name__=='__main__': main()
