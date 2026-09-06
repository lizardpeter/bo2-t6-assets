#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;TOOL=HERE/'t6_weapon_playeranim_precedence_v1.py'
def run(spec,out):return subprocess.run([sys.executable,str(TOOL),'--spec',str(spec),'--out',str(out)],capture_output=True,text=True)
def main():
 with tempfile.TemporaryDirectory() as td:
  r=Path(td);base=r/'base.json';patch=r/'patch.json';names=r/'overrides.csv';spec=r/'spec.json';out=r/'out.json'
  base.write_text(json.dumps({'format':'t6-weapon-playeranim-selector-layer-v1','weapons':[{'weapon':'a_mp','selectorStatus':'exact-inline-weapdef-prefix','selector':{'weaponclass':'smg','playerAnimType':'default'}},{'weapon':'b_mp','selectorStatus':'exact-inline-weapdef-prefix','selector':{'weaponclass':'rifle','playerAnimType':'rearclip'}}]}));patch.write_text(json.dumps({'format':'t6-weapon-playeranim-selector-layer-v1','weapons':[]}));names.write_text('order,internal_name\n1,a_mp\n')
  spec.write_text(json.dumps({'layers':[{'name':'base','selectorManifest':'base.json'},{'name':'patch','selectorManifest':'patch.json','overrideNamesCsv':'overrides.csv'},{'name':'late','unknownWeaponAssetCount':1,'sourceSha256':'1'*64}]}));q=run(spec,out);assert q.returncode==2,(q.stdout,q.stderr);d=json.loads(out.read_text());a=next(x for x in d['weapons'] if x['weapon']=='a_mp');b=next(x for x in d['weapons'] if x['weapon']=='b_mp');assert a['namedOverrideResolved'] is False;assert b['namedOverrideResolved'] is True;assert not a['readyForFinalNamedWeaponSelector'] and not b['readyForFinalNamedWeaponSelector']
  patch.write_text(json.dumps({'format':'t6-weapon-playeranim-selector-layer-v1','weapons':[{'weapon':'a_mp','selectorStatus':'exact-inline-weapdef-prefix','selector':{'weaponclass':'smg','playerAnimType':'handleclip'}}]}));spec.write_text(json.dumps({'layers':[{'name':'base','selectorManifest':'base.json'},{'name':'patch','selectorManifest':'patch.json','overrideNamesCsv':'overrides.csv'}]}));q=run(spec,out);assert q.returncode==0,(q.stdout,q.stderr);d=json.loads(out.read_text());a=next(x for x in d['weapons'] if x['weapon']=='a_mp');assert a['selector']=={'weaponclass':'smg','playerAnimType':'handleclip'};assert all(x['readyForFinalNamedWeaponSelector'] for x in d['weapons'])
 print('t6_weapon_playeranim_precedence_v1: PASS');return 0
if __name__=='__main__':raise SystemExit(main())
