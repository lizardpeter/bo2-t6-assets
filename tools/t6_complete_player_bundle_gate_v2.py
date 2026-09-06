#!/usr/bin/env python3
"""Named-weapon complete-player gate for the universal T6 assembly model.

v2 wraps the proven v1 complete-player gate and adds the missing concrete join:
a named weapon must have a final precedence-resolved retail playeranim selector,
and that selector must exactly match the third-person character compatibility
profile used by the bundle evidence.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;V1=HERE/'t6_complete_player_bundle_gate_v1.py'
def load(p:Path):
 d=json.loads(p.read_text(encoding='utf-8-sig'))
 if not isinstance(d,dict):raise ValueError(f'{p}: expected object')
 return d
def sha(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--requirements',type=Path,required=True);ap.add_argument('--first-person-plan',type=Path,required=True);ap.add_argument('--full-body-bundle',type=Path);ap.add_argument('--assembly-evidence',type=Path);ap.add_argument('--third-person-animation-evidence',type=Path,required=True);ap.add_argument('--weapon-selector-precedence',type=Path,required=True);ap.add_argument('--weapon',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 with tempfile.TemporaryDirectory() as td:
  v1out=Path(td)/'v1.json';cmd=[sys.executable,str(V1),'--requirements',str(a.requirements),'--first-person-plan',str(a.first_person_plan),'--third-person-animation-evidence',str(a.third_person_animation_evidence),'--out',str(v1out)]
  if a.full_body_bundle:cmd+=['--full-body-bundle',str(a.full_body_bundle)]
  if a.assembly_evidence:cmd+=['--assembly-evidence',str(a.assembly_evidence)]
  q=subprocess.run(cmd,capture_output=True,text=True)
  if q.returncode not in (0,2):raise RuntimeError(f'v1 gate failed unexpectedly: {q.stderr or q.stdout}')
  base=load(v1out)
 prec=load(a.weapon_selector_precedence)
 if prec.get('format')!='t6-weapon-playeranim-precedence-v1':raise ValueError('unsupported weapon selector precedence format')
 wr=next((x for x in prec.get('weapons',[]) if isinstance(x,dict) and x.get('weapon')==a.weapon),None)
 anim=load(a.third_person_animation_evidence);profile=anim.get('selectorProfile',{}).get('selectors',{});sel=wr.get('selector') if wr else None
 selector_final=bool(wr and wr.get('readyForFinalNamedWeaponSelector') is True and isinstance(sel,dict))
 selector_matches=bool(selector_final and profile.get('weaponclass')==sel.get('weaponclass') and profile.get('playerAnimType')==sel.get('playerAnimType') and profile.get('nextWeaponclass',sel.get('weaponclass'))==sel.get('weaponclass') and profile.get('nextPlayerAnimType',sel.get('playerAnimType'))==sel.get('playerAnimType'))
 named_gate=selector_final and selector_matches
 base_ready=bool(base.get('summary',{}).get('readyForCompletePlayerBundle'))
 ready=base_ready and named_gate
 next_actions=list(base.get('nextActions',[]))
 if not selector_final:next_actions.append(f'resolve final retail selector for named weapon {a.weapon} across all later WEAPON layers')
 elif not selector_matches:next_actions.append(f'regenerate third-person compatibility evidence for {a.weapon} selector {sel}')
 out={'format':'t6-complete-player-bundle-gate-v2','weapon':a.weapon,'baseGate':base,'weaponSelectorPrecedence':{'path':str(a.weapon_selector_precedence),'sha256':sha(a.weapon_selector_precedence),'record':wr},'thirdPersonAnimationEvidence':{'path':str(a.third_person_animation_evidence),'sha256':sha(a.third_person_animation_evidence),'selectorProfile':profile},'summary':{**base.get('summary',{}),'finalNamedWeaponSelectorGate':selector_final,'namedWeaponSelectorMatchesCharacterCompatibilityGate':selector_matches,'readyForCompleteNamedWeaponPlayerBundle':ready},'nextActions':next_actions,'proofBoundary':'v2 requires both v1 complete-player closure and an exact final named-weapon selector after layer precedence; generic class/profile compatibility alone can never satisfy the named-weapon gate.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['summary'],indent=2,sort_keys=True));return 0 if ready else 2
if __name__=='__main__':raise SystemExit(main())
