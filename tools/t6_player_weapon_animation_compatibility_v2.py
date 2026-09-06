#!/usr/bin/env python3
"""Join a retail T6 playeranim selection matrix to one character skeleton.

v2 accepts both playeranim retail-resolution v1 and the casefold-safe v2. The
selector profile remains weapon-metadata shaped rather than weapon-name shaped,
so the same character compatibility evidence is reusable across every weapon
whose final retail WeaponDef resolves to the same selector tuple.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT='t6-third-person-animation-compatibility-v2'
DEFAULT_REQUIRED=['idle/stance','walk/run/sprint','crouch/prone','jump/fall/land','weapon-ready/fire/reload','melee','turn/aim','death/reaction']

def load(p:Path):
 d=json.loads(p.read_text(encoding='utf-8-sig'))
 if not isinstance(d,dict):raise ValueError(f'{p}: expected object')
 return d
def sha(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def clause_possible(c,selectors,forbid):
 key=c.get('key')
 if key in forbid:return False
 if key not in selectors:return True
 v=selectors[key]
 vals=c.get('expandedAcceptedValues') or c.get('acceptedValues') or []
 exc=c.get('excludedValues') or []
 return (not vals or v in vals) and v not in exc
def rule_possible(row,selectors,forbid):
 for block in row.get('conditionBlocks',[]):
  if block.get('default'):continue
  if not all(clause_possible(c,selectors,forbid) for c in block.get('clauses',[])):return False
 return True

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--matrix',type=Path,required=True);ap.add_argument('--resolution',type=Path,required=True);ap.add_argument('--profile',type=Path,required=True);ap.add_argument('--body-model',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 matrix=load(a.matrix);resolution=load(a.resolution);profile=load(a.profile)
 if matrix.get('format')!='t6-playeranim-selection-matrix-v1':raise ValueError('unsupported selection matrix')
 if resolution.get('format') not in ('t6-playeranim-retail-resolution-v1','t6-playeranim-retail-resolution-v2'):raise ValueError('unsupported compatibility resolution')
 selectors=profile.get('selectors',{});forbid=set(profile.get('forbiddenConditionKeys',[]));required=profile.get('requiredBehaviorFamilies',DEFAULT_REQUIRED)
 if not isinstance(selectors,dict) or not selectors:raise ValueError('profile selectors missing')
 resolved={x['name']:x for x in resolution.get('resolved',[]) if isinstance(x,dict) and isinstance(x.get('name'),str)}
 applicable=[x for x in matrix.get('rules',[]) if rule_possible(x,selectors,forbid)]
 names=sorted({x['animation'] for x in applicable})
 family={}
 for fam in required:
  rows=[x for x in applicable if fam in x.get('behaviorFamilies',[])];ns=sorted({x['animation'] for x in rows});un=[n for n in ns if n not in resolved];bad=[n for n in ns if n in resolved and int(resolved[n].get('matchedTrackCount',0))<=0]
  family[fam]={'ruleCount':len(rows),'uniqueAnimationCount':len(ns),'resolvedAnimationCount':len(ns)-len(un),'unresolvedAnimationNames':un,'incompatibleAnimationNames':bad,'allCompatible':bool(rows) and not un and not bad}
 unresolved=[n for n in names if n not in resolved];bad=[n for n in names if n in resolved and int(resolved[n].get('matchedTrackCount',0))<=0]
 bindings=[]
 for n in names:
  if n not in resolved:continue
  r=resolved[n];bindings.append({'name':n,'referenceName':r.get('referenceName',n),'resolvedAssetName':r.get('resolvedAssetName',n),'caseNormalizedMatch':bool(r.get('caseNormalizedMatch',False)),'bindingClass':r.get('bindingClass'),'trackCount':r.get('trackCount'),'matchedTrackCount':r.get('matchedTrackCount'),'extraAnimationTrackCount':r.get('extraAnimationTrackCount'),'rawStructOffset':r.get('rawStructOffset'),'numFrames':r.get('numFrames'),'frameRate':r.get('frameRate')})
 source_hashes=[]
 for src in [matrix.get('sources',{}).get('playeranim',{}),matrix.get('sources',{}).get('playeranimtypes',{}),*resolution.get('sources',{}).values()]:
  h=src.get('sha256') if isinstance(src,dict) else None
  if isinstance(h,str) and len(h)==64 and h not in source_hashes:source_hashes.append(h)
 all_families=all(family[f]['allCompatible'] for f in required)
 concrete=profile.get('concreteWeapon')
 weapon_meta_retail=bool(isinstance(concrete,dict) and concrete.get('authority')=='retail' and isinstance(concrete.get('sourceSha256'),str) and len(concrete['sourceSha256'])==64)
 out={'format':FORMAT,'bodyModel':a.body_model,'authority':'retail playeranim selection rules + retail XAnim track names + retail character skeleton','retailSourceSha256':source_hashes,'ownershipResolvedFromRetail':True,'allRequiredTracksCompatible':all_families and not unresolved and not bad,'animationCount':len(names),'selectionRuleCount':len(applicable),'selectorProfile':profile,'weaponSelectionMetadataResolvedFromRetail':weapon_meta_retail,'summary':{'applicableRules':len(applicable),'uniqueApplicableAnimations':len(names),'resolvedApplicableAnimations':len(names)-len(unresolved),'unresolvedApplicableAnimations':len(unresolved),'incompatibleApplicableAnimations':len(bad),'exactTrackSubsets':sum(b['bindingClass']=='exact-track-subset' for b in bindings),'animationSupersetIntersections':sum(b['bindingClass']=='animation-superset-intersection' for b in bindings),'caseNormalizedAnimationMatches':sum(b['caseNormalizedMatch'] for b in bindings),'requiredBehaviorFamilies':len(required),'requiredBehaviorFamiliesClosed':sum(family[f]['allCompatible'] for f in required)},'behaviorFamilyCoverage':family,'unresolvedApplicableAnimationNames':unresolved,'incompatibleApplicableAnimationNames':bad,'bindings':bindings,'resolutionFormat':resolution.get('format'),'proofBoundary':'This proves character compatibility for every retail playeranim rule potentially selected by the supplied selector profile. It does not claim a named weapon has this profile unless concreteWeapon contains separately hash-pinned retail WeaponDef evidence.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['summary'],indent=2,sort_keys=True));return 0 if out['allRequiredTracksCompatible'] else 2
if __name__=='__main__':raise SystemExit(main())
