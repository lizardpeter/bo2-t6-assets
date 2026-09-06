#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
MATRIX=HERE/'t6_playeranim_selection_matrix_v1.py'
COMPAT=HERE/'t6_player_weapon_animation_compatibility_v1.py'

def run(cmd):
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode not in (0,2):raise AssertionError((r.returncode,r.stdout,r.stderr))
 return r

def main():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)
  script=root/'playeranim.script';types=root/'playeranimtypes.txt';matrix=root/'matrix.json';res=root/'resolution.json';prof=root/'profile.json';out=root/'compat.json'
  script.write_text('''DEFINES\nset weaponclass autofire = mg AND smg\nANIMATIONS\nSTATE COMBAT\n{\n idle\n {\n  weaponclass autofire\n  {\n   both pb_auto_idle\n  }\n  default\n  {\n   both pb_default_idle\n  }\n }\n}\nEVENTS\nfireweapon\n{\n vehicle_name pbr\n {\n  torso pt_vehicle_fire\n }\n weaponclass autofire\n {\n  torso pt_auto_fire\n }\n default\n {\n  torso pt_default_fire\n }\n}\n''',encoding='latin1')
  types.write_text('none\ndefault\nturned\n',encoding='latin1')
  r=run([sys.executable,str(MATRIX),'--playeranim',str(script),'--playeranimtypes',str(types),'--out',str(matrix)]);assert r.returncode==0
  m=json.loads(matrix.read_text());assert m['summary']['animationDirectives']==5;assert m['aliases']['weaponclass']['autofire']['acceptedValues']==['mg','smg'];assert [x['animation'] for x in m['rules']]==['pb_auto_idle','pb_default_idle','pt_vehicle_fire','pt_auto_fire','pt_default_fire']
  def row(n):return {'name':n,'bindingClass':'exact-track-subset','trackCount':4,'matchedTrackCount':4,'extraAnimationTrackCount':0,'rawStructOffset':1,'numFrames':10,'frameRate':30.0}
  resolution={'format':'t6-playeranim-retail-resolution-v1','sources':{'playeranim':{'sha256':'1'*64},'xanimInventory':{'sha256':'2'*64},'skeleton':{'sha256':'3'*64}},'resolved':[row(n) for n in ['pb_auto_idle','pb_default_idle','pt_auto_fire','pt_default_fire']], 'unresolved':[{'name':'pt_vehicle_fire'}]}
  res.write_text(json.dumps(resolution))
  profile={'format':'t6-playeranim-selector-profile-v1','id':'test-smg','selectors':{'weaponclass':'smg','nextWeaponclass':'smg','playerAnimType':'default','nextPlayerAnimType':'default'},'forbiddenConditionKeys':['vehicle_name','mounted','vehicle_seat_to'],'requiredBehaviorFamilies':['idle/stance','weapon-ready/fire/reload'],'concreteWeapon':None}
  prof.write_text(json.dumps(profile))
  r=run([sys.executable,str(COMPAT),'--matrix',str(matrix),'--resolution',str(res),'--profile',str(prof),'--body-model','test_body','--out',str(out)]);assert r.returncode==0,(r.stdout,r.stderr)
  d=json.loads(out.read_text());assert d['allRequiredTracksCompatible'] is True;assert d['weaponSelectionMetadataResolvedFromRetail'] is False;assert d['summary']['applicableRules']==4;assert d['summary']['uniqueApplicableAnimations']==4;assert d['summary']['unresolvedApplicableAnimations']==0;assert 'pt_vehicle_fire' not in {x['name'] for x in d['bindings']}
 print('t6_playeranim_universal_matrix_v1: PASS');return 0
if __name__=='__main__':raise SystemExit(main())
