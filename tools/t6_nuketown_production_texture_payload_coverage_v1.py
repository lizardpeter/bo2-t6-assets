#!/usr/bin/env python3
"""Project exact Nuketown production GfxImage payload coverage.

The production dependency denominator is already authoritative.  This projector
adds independently retail-proven payload providers without pretending they came
from the 81-image IPAK/DDS bridge.  v1 admits exactly one such provider:
$identitynormalmap, whose inline 4-byte retail payload is independently proven by
the block-5 loader replay.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

CENSUS_FORMAT='t6-nuketown-production-texture-dependency-census-v2'
PROOF_FORMAT='t6-nuketown-identitynormalmap-block5-proof-v1'
IDENTITY='$identitynormalmap'
PIXEL='8080ff80'

def raw(p):
 b=p.read_bytes(); return json.loads(b),b

def sha(b): return hashlib.sha256(b).hexdigest()

def build(census, proof):
 if census.get('format') != CENSUS_FORMAT: raise ValueError('unexpected production census format')
 if proof.get('format') != PROOF_FORMAT or proof.get('status') != 'closed': raise ValueError('identity proof is not closed')
 image=proof.get('identityImage') or {}; promotion=proof.get('promotion') or {}
 if image.get('name') != IDENTITY or image.get('resourceSize') != 4: raise ValueError('identity image proof drift')
 if promotion.get('image') != IDENTITY or promotion.get('proof') != 'direct T6 PC32 loader destination-cursor replay plus inline GfxImage name/pixel validation': raise ValueError('identity promotion drift')
 summary=census.get('summary') or {}
 if summary.get('productionUniqueImageCount') != 450 or summary.get('productionCoveredByExact81Count') != 75 or summary.get('productionMissingFromExact81Count') != 375: raise ValueError('production denominator drift')
 missing={x['image']:x for x in census.get('missingProductionImages',[])}
 if set(missing) and len(missing)!=375: raise ValueError('missing identity list drift')
 if IDENTITY not in missing or not missing[IDENTITY].get('materialUses'): raise ValueError('identitynormalmap is not an unresolved material dependency')
 exact81={x['image'] for x in census.get('material',[])+census.get('lightmaps',[])+census.get('reflectionProbes',[]) if x.get('coveredByExact81DdsBridge')}
 if len(exact81)!=75 or IDENTITY in exact81: raise ValueError('exact81 coverage drift')
 providers={x:{'provider':'exact81-iwi27-dds-bridge'} for x in exact81}
 providers[IDENTITY]={'provider':'retail-inline-gfximage','resourceBytes':4,'pixelBytesHex':PIXEL,'proof':'T6_NUKETOWN_IDENTITYNORMALMAP_BLOCK5_PROOF_V1.json'}
 required=set(exact81)|set(missing)
 covered=required & set(providers); unresolved=required-set(providers)
 material={x['image'] for x in census['material']}
 return {
  'format':'t6-nuketown-production-texture-payload-coverage-v1','map':census.get('map'),
  'summary':{
   'productionUniqueImageCount':len(required),'exact81IpakDdsCoveredCount':len(exact81),
   'retailInlineCoveredCount':1,'exactPayloadCoveredCount':len(covered),'exactPayloadMissingCount':len(unresolved),
   'exactPayloadCoverageRatio':len(covered)/len(required),
   'materialUniqueImageCount':len(material),'materialExactPayloadCoveredCount':len(material & covered),
   'materialExactPayloadMissingCount':len(material-unresolved if False else material-covered),
   'materialExactPayloadCoverageRatio':len(material & covered)/len(material),
  },
  'additionalExactProviders':[{'image':IDENTITY,**providers[IDENTITY]}],
  'unresolvedProductionImages':sorted(unresolved),
  'proofBoundary':'The 450-identity production denominator is unchanged. Coverage means exact retail payload authority, not visual substitution. The 75 IPAK/IWI27 DDS identities remain separately attributed; $identitynormalmap is added only from its independent inline retail loader/pixel proof. No other missing identity is inferred from names, dimensions, semantics, adjacency, or expected defaults.'
 }

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--census',type=Path,required=True);ap.add_argument('--identity-proof',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 c,cb=raw(a.census);p,pb=raw(a.identity_proof);o=build(c,p);o['inputs']={'census':{'sha256':sha(cb)},'identityProof':{'sha256':sha(pb)}}
 payload=(json.dumps(o,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({**o['summary'],'sha256':sha(payload)},indent=2,sort_keys=True))
if __name__=='__main__': main()
