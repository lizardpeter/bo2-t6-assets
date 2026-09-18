#!/usr/bin/env python3
"""Project exact Nuketown production GfxImage payload coverage beyond the IPAK bridge."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
CENSUS_FORMAT='t6-nuketown-production-texture-dependency-census-v2'; IDENTITY_FORMAT='t6-nuketown-identitynormalmap-block5-proof-v1'; LIGHTMAP_FORMAT='t6-nuketown-lightmap-inline-payload-proof-v1'; REFLECTION_FORMAT='t6-nuketown-reflection-inline-payload-probe-v1'; IDENTITY='$identitynormalmap'; SOURCE_SHA='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'
def raw(p): b=p.read_bytes(); return json.loads(b),b
def sha(b): return hashlib.sha256(b).hexdigest()
def build(census,identity,lightmaps,reflections):
 if census.get('format')!=CENSUS_FORMAT: raise ValueError('unexpected production census format')
 if identity.get('format')!=IDENTITY_FORMAT or identity.get('status')!='closed': raise ValueError('identity proof drift')
 im=identity.get('identityImage') or {}; promo=identity.get('promotion') or {}; src=identity.get('source') or {}; reg=identity.get('regression') or {}
 if im.get('name')!=IDENTITY or im.get('resourceSize')!=4 or promo.get('virtualOffset')!=514620 or promo.get('xassetIndex')!=836 or src.get('sha256')!=SOURCE_SHA or reg.get('path')!='tools/test_t6_nuketown_identitynormalmap_block5_proof_v1.py': raise ValueError('identity authority drift')
 if lightmaps.get('format')!=LIGHTMAP_FORMAT or lightmaps.get('source',{}).get('expandedSha256')!=SOURCE_SHA: raise ValueError('lightmap payload proof drift')
 lm=lightmaps.get('payloads') or []; lmnames={x['image'] for x in lm}
 if len(lm)!=2 or lmnames!={'*lightmap0_secondary','*lightmap1_secondary'} or sum(x['resourceSize'] for x in lm)!=9437184 or any(len(x.get('payloadSha256',''))!=64 for x in lm): raise ValueError('lightmap payload set drift')
 if reflections.get('format')!=REFLECTION_FORMAT or reflections.get('source',{}).get('expandedSha256')!=SOURCE_SHA: raise ValueError('reflection payload proof drift')
 rs=reflections.get('summary') or {}; rr=reflections.get('rows') or []
 if (rs.get('identityCount'),rs.get('uniqueSerializedGfxImageCount'),rs.get('uniqueInlinePayloadCount'),rs.get('ambiguousOrAbsentCount'))!=(25,25,25,0) or len(rr)!=25: raise ValueError('reflection closure is not exact 25/25')
 rp=[]
 for x in rr:
  if x.get('serializedGfxImageCandidateCount')!=1: raise ValueError('reflection candidate ambiguity')
  c=x['candidates'][0]
  if not c.get('inline') or len(c.get('payloadSha256',''))!=64: raise ValueError('reflection payload not inline/exact')
  if x['image']!=f"*reflection_probe{x['index']}": raise ValueError('reflection identity/index drift')
  rp.append({'image':x['image'],'resourceSize':c['resourceSize'],'payloadSha256':c['payloadSha256']})
 rpnames={x['image'] for x in rp}
 s=census.get('summary') or {}
 if (s.get('productionUniqueImageCount'),s.get('productionCoveredByExact81Count'),s.get('productionMissingFromExact81Count'))!=(450,75,375): raise ValueError('production denominator drift')
 missing={x['image']:x for x in census.get('missingProductionImages',[])}
 if len(missing)!=375 or not ({IDENTITY}|lmnames|rpnames)<=set(missing): raise ValueError('missing identity set drift')
 allrows=census.get('material',[])+census.get('lightmaps',[])+census.get('reflectionProbes',[]); exact81={x['image'] for x in allrows if x.get('coveredByExact81DdsBridge')}
 inline={IDENTITY}|lmnames|rpnames
 if len(exact81)!=75 or inline&exact81: raise ValueError('exact81 coverage overlap/drift')
 providers=set(exact81)|inline; required=set(exact81)|set(missing); covered=required&providers; unresolved=required-providers; material={x['image'] for x in census['material']}
 additional=[{'image':IDENTITY,'provider':'retail-inline-gfximage','resourceBytes':4,'pixelBytesHex':'8080ff80','proof':'T6_NUKETOWN_IDENTITYNORMALMAP_BLOCK5_PROOF_V1.json','sourceExpandedSha256':SOURCE_SHA}]+[{'image':x['image'],'provider':'retail-inline-gfxworld-lightmap','resourceBytes':x['resourceSize'],'payloadSha256':x['payloadSha256'],'proof':'T6_NUKETOWN_LIGHTMAP_INLINE_PAYLOAD_PROOF_V1.json','sourceExpandedSha256':SOURCE_SHA} for x in lm]+[{'image':x['image'],'provider':'retail-inline-gfxworld-reflection','resourceBytes':x['resourceSize'],'payloadSha256':x['payloadSha256'],'proof':'T6_NUKETOWN_REFLECTION_INLINE_PAYLOAD_PROBE_V1.json','sourceExpandedSha256':SOURCE_SHA} for x in rp]
 return {'format':'t6-nuketown-production-texture-payload-coverage-v1','map':census.get('map'),'summary':{'productionUniqueImageCount':len(required),'exact81IpakDdsCoveredCount':len(exact81),'retailInlineCoveredCount':len(additional),'exactPayloadCoveredCount':len(covered),'exactPayloadMissingCount':len(unresolved),'exactPayloadCoverageRatio':len(covered)/len(required),'materialUniqueImageCount':len(material),'materialExactPayloadCoveredCount':len(material&covered),'materialExactPayloadMissingCount':len(material-covered),'materialExactPayloadCoverageRatio':len(material&covered)/len(material),'lightmapExactPayloadCoveredCount':len(lmnames),'reflectionExactPayloadCoveredCount':len(rpnames)},'additionalExactProviders':additional,'unresolvedProductionImages':sorted(unresolved),'proofBoundary':'The 450-identity production denominator is unchanged. Coverage means exact retail payload authority, not visual substitution. The 75 IPAK/IWI27 DDS identities remain separately attributed; $identitynormalmap, both secondary lightmaps, and all 25 GfxWorld reflection images are added only from independent SHA-pinned inline retail byte proofs. No missing identity is inferred from names, dimensions, semantics, adjacency, or expected defaults.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--census',type=Path,required=True);ap.add_argument('--identity-proof',type=Path,required=True);ap.add_argument('--lightmap-proof',type=Path,required=True);ap.add_argument('--reflection-proof',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();c,cb=raw(a.census);i,ib=raw(a.identity_proof);l,lb=raw(a.lightmap_proof);r,rb=raw(a.reflection_proof);o=build(c,i,l,r);o['inputs']={'census':{'sha256':sha(cb)},'identityProof':{'sha256':sha(ib)},'lightmapProof':{'sha256':sha(lb)},'reflectionProof':{'sha256':sha(rb)}};payload=(json.dumps(o,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({**o['summary'],'sha256':sha(payload)},indent=2,sort_keys=True))
if __name__=='__main__': main()
