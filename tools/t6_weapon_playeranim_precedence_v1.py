#!/usr/bin/env python3
"""Resolve T6 weapon player-animation selectors across ordered retail layers.

Fail-closed rules:
- a later named weapon override replaces the current selector only when that
  layer has an exact selector proof;
- a known later override with missing/unresolved selector blocks that weapon;
- an unidentified later WEAPON XAsset blocks final promotion globally until its
  identity is proven or explicitly excluded from the requested weapon.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

def load(p:Path): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def selector_rows(d:dict)->dict[str,dict]:
 out={}
 if d.get('format')=='t6-weapon-playeranim-selector-layer-v1':
  for r in d.get('weapons',[]):
   if isinstance(r,dict) and isinstance(r.get('weapon'),str): out[r['weapon']]=r
 elif d.get('format')=='t6-weapon-playeranim-selector-layer-summary-v1':
  for n,pair in d.get('selectors',{}).items():
   if isinstance(pair,list) and len(pair)==2: out[n]={'weapon':n,'selectorStatus':'summary-exact','weaponClass':pair[0],'playerAnimType':pair[1],'selector':{'weaponclass':pair[0],'playerAnimType':pair[1]}}
 return out
def csv_names(p:Path)->list[str]:
 with p.open('r',encoding='utf-8-sig',newline='') as f:return [x for r in csv.DictReader(f) for x in [r.get('internal_name') or r.get('weapon') or r.get('name')] if x]
def exact(r):return isinstance(r,dict) and isinstance(r.get('selector'),dict) and r.get('selectorStatus') in ('exact-inline-weapdef-prefix','summary-exact','exact')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();spec=load(a.spec);root=a.spec.parent
 current={};history={};global_blockers=[];layers=[]
 for index,L in enumerate(spec.get('layers',[])):
  name=L['name'];m=None;rows={};mp=L.get('selectorManifest')
  if mp:
   path=(root/mp).resolve() if not Path(mp).is_absolute() else Path(mp);m=load(path);rows=selector_rows(m)
  override=set(rows)
  cp=L.get('overrideNamesCsv')
  if cp:
   path=(root/cp).resolve() if not Path(cp).is_absolute() else Path(cp);override.update(csv_names(path))
  explicit=L.get('overrideNames') or [];override.update(str(x) for x in explicit)
  for w in sorted(override):
   r=rows.get(w);history.setdefault(w,[]).append({'layer':name,'layerIndex':index,'hasSelectorRow':r is not None,'selectorStatus':r.get('selectorStatus') if r else 'known-override-selector-not-provided','selector':r.get('selector') if r else None})
   if exact(r):current[w]={'selector':r['selector'],'sourceLayer':name,'sourceLayerIndex':index,'blocked':False}
   else:current[w]={'selector':None,'sourceLayer':name,'sourceLayerIndex':index,'blocked':True,'blockReason':'later-named-override-selector-unresolved'}
  unknown=int(L.get('unknownWeaponAssetCount',0) or 0)
  if unknown:
   global_blockers.append({'layer':name,'layerIndex':index,'unknownWeaponAssetCount':unknown,'sourceSha256':L.get('sourceSha256'),'reason':'unidentified later WEAPON XAsset could override an earlier named weapon'})
  layers.append({'name':name,'index':index,'selectorRows':len(rows),'knownOverrideNames':len(override),'unknownWeaponAssetCount':unknown})
 weapons=[]
 for w in sorted(set(current)|set(history)):
  c=current.get(w,{});ready=bool(c.get('selector')) and not c.get('blocked') and not global_blockers
  weapons.append({'weapon':w,'selector':c.get('selector'),'selectorSourceLayer':c.get('sourceLayer'),'namedOverrideResolved':bool(c.get('selector')) and not c.get('blocked'),'globallyBlockedByUnknownLaterWeaponAssets':bool(global_blockers),'readyForFinalNamedWeaponSelector':ready,'history':history.get(w,[])})
 out={'format':'t6-weapon-playeranim-precedence-v1','authority':'ordered retail selector evidence with fail-closed override handling','spec':{'path':str(a.spec),'sha256':sha(a.spec)},'layers':layers,'globalBlockers':global_blockers,'summary':{'weaponsSeen':len(weapons),'namedOverrideSelectorsResolved':sum(x['namedOverrideResolved'] for x in weapons),'readyForFinalNamedWeaponSelector':sum(x['readyForFinalNamedWeaponSelector'] for x in weapons),'globalUnknownWeaponBlockers':sum(x['unknownWeaponAssetCount'] for x in global_blockers)},'weapons':weapons,'proofBoundary':'No named weapon is final when a later known override lacks exact selector evidence or any later unidentified WEAPON XAsset remains capable of overriding it.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['summary'],indent=2,sort_keys=True));return 0 if not global_blockers and all(x['readyForFinalNamedWeaponSelector'] for x in weapons) else 2
if __name__=='__main__':raise SystemExit(main())
