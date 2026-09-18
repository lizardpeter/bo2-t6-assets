#!/usr/bin/env python3
"""Join exact five-root conflicts to exact current-client classifier scalars.

This deliberately emits scalar relations only. It does not select a retail or
current-client duplicate winner until the linked-list lookup/mutation direction
is independently closed.
"""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter
from pathlib import Path

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
OWNER_CLASSIFIER={"/tmp/map_out":0x8000,"/tmp/common_out":0x80,"/tmp/patch_out":0x02,"/tmp/code_post_gfx_out":0x08}

def load(p):
 raw=p.read_bytes();return json.loads(raw),{"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--conflicts',type=Path,required=True);ap.add_argument('--ordinals',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 c,cs=load(a.conflicts);o,os=load(a.ordinals)
 if c.get('format')!='t6-oat-parent-dependency-conflict-census-v1' or c.get('authoritativeWinnerSelection') is not False:raise SystemExit('unexpected conflict authority')
 if o.get('client',{}).get('sha256')!=CLIENT_SHA:raise SystemExit('unexpected current-client identity')
 scalar={}
 # Complete exact single-bit map includes 0x8000; constructedRowMap supplies named rows.
 for key in ('singleBitAndZeroMap','constructedRowMap'):
  for x in o.get(key,[]):
   if 'classifier' in x and 'ordinal' in x:scalar[int(x['classifier'])]=int(x['ordinal'])
 required={0x02:65,0x80:54,0x8000:57}
 for k,v in required.items():
  if scalar.get(k)!=v:raise SystemExit(f'missing/drifted exact scalar 0x{k:x}: {scalar.get(k)!r} != {v}')
 rows=[];relations=Counter()
 for x in c['conflicts']:
  owners=x['parentOwners']
  if len(owners)!=2:raise SystemExit(f'unexpected owner arity {owners!r}')
  vals=[]
  for owner in owners:
   if owner not in OWNER_CLASSIFIER:raise SystemExit(f'unmapped owner {owner}')
   cl=OWNER_CLASSIFIER[owner]
   if cl not in scalar:raise SystemExit(f'no scalar for {owner} 0x{cl:x}')
   vals.append({'owner':owner,'classifier':cl,'classifierHex':f'0x{cl:08x}','scalar':scalar[cl]})
  rel='owner0_lt_owner1' if vals[0]['scalar']<vals[1]['scalar'] else ('owner0_gt_owner1' if vals[0]['scalar']>vals[1]['scalar'] else 'equal');relations[rel]+=1
  rows.append({'techniqueSet':x.get('techniqueSet'),'technique':x.get('technique'),'parentOwners':owners,'ownerScalars':vals,'scalarRelation':rel,'winner':None,'winnerAuthority':False})
 out={'format':'t6-current-client-five-root-scalar-relation-v1','authority':'exact five-root retail FastFile ownership + SHA-classified current Plutonium client scalar mapping; no historical-retail winner authority','clientSha256':CLIENT_SHA,'sources':{'conflicts':cs,'ordinals':os},'summary':{'conflictCount':len(rows),'relations':dict(relations),'winnerCount':0},'conflicts':rows,'proofBoundary':'The scalar values are byte-proven in the classified current client and owner identities are exact in the five-root retail FastFile census. This join proves only pairwise scalar ordering. It intentionally does not infer which linked record is lookup-visible or survives duplicate insertion, and therefore selects no current-client or historical-retail Technique winner.'}
 if len(rows)!=58 or relations!=Counter({'owner0_lt_owner1':58}):raise SystemExit(f'unexpected relation census {len(rows)} {relations}')
 payload=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),**out['summary']},indent=2,sort_keys=True))
if __name__=='__main__':main()
