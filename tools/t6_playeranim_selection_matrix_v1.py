#!/usr/bin/env python3
"""Compile retail T6 mp/playeranim.script into a reusable selection matrix.

This preserves the game script's first-match rule order and conditions instead of
binding animations to one character or one weapon. Character skeleton
compatibility and concrete WeaponDef metadata are intentionally separate layers.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

FORMAT='t6-playeranim-selection-matrix-v1'
ANIM_RE=re.compile(r'^\s*(both|torso|legs|turret)\s+([A-Za-z0-9_./+\-]+)\b(.*)$',re.I)
SET_RE=re.compile(r'^\s*set\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_./+\-]+)\s*=\s*(.*?)\s*$',re.I)
STATE_RE=re.compile(r'^STATE\s+(.+)$',re.I)
CONDITION_KEYS={
 'playeranimtype':'playerAnimType','nextplayeranimtype':'nextPlayerAnimType',
 'weaponclass':'weaponclass','nextweaponclass':'nextWeaponclass',
 'position':'position','enemy_weapon':'enemy_weapon','underwater':'underwater',
 'mounted':'mounted','movestatus':'movestatus','underhand':'underhand','leaning':'leaning',
 'weapon_position':'weapon_position','direction':'direction','perk':'perk','attachment':'attachment',
 'riotshieldnext':'riotshieldnext','cac':'cac','stance':'stance','slope':'slope',
 'vehicle_name':'vehicle_name','vehicle_seat_to':'vehicle_seat_to',
 'nextstance':'nextStance','nextmovestatus':'nextMoveStatus','nextdirection':'nextDirection',
}
MOVEMENT_FAMILY={
 'idle':'idle/stance','idlecr':'crouch/prone','idleprone':'crouch/prone',
 'walk':'walk/run/sprint','walkbk':'walk/run/sprint','run':'walk/run/sprint','runbk':'walk/run/sprint',
 'walkcr':'crouch/prone','walkcrbk':'crouch/prone','runcr':'crouch/prone','runcrbk':'crouch/prone',
 'walkprone':'crouch/prone','walkpronebk':'crouch/prone','straferight':'walk/run/sprint','strafeleft':'walk/run/sprint',
 'turnright':'turn/aim','turnleft':'turn/aim','sprint':'walk/run/sprint',
}
EVENT_FAMILY={
 'fireweapon':'weapon-ready/fire/reload','reload':'weapon-ready/fire/reload','dropweapon':'weapon-ready/fire/reload','raiseweapon':'weapon-ready/fire/reload',
 'jump':'jump/fall/land','jumpbk':'jump/fall/land','land':'jump/fall/land',
 'crouch_to_prone':'crouch/prone','prone_to_crouch':'crouch/prone','prone_to_stand':'crouch/prone','prone_to_sprint':'crouch/prone','crouch_to_stand':'crouch/prone','stand_to_crouch':'crouch/prone',
 'meleeattack':'melee','meleeleft':'melee','knife_melee':'melee',
 'pain':'death/reaction','death':'death/reaction','shellshock':'death/reaction',
}

def sha256(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def clean(raw:str)->str:
 return raw.split('//',1)[0].replace('\x00','').strip()

def split_values(expr:str)->dict:
 toks=re.split(r'\s+(AND|NOT)\s+',expr.strip(),flags=re.I)
 positive=[];negative=[];mode='AND'
 for t in toks:
  u=t.strip()
  if not u:continue
  if u.upper() in ('AND','NOT'):
   mode=u.upper();continue
  (negative if mode=='NOT' else positive).append(u)
  mode='AND'
 return {'acceptedValues':positive,'excludedValues':negative}

def parse_condition_header(header:str, aliases:dict, player_types:list[str])->dict:
 h=header.strip()
 if h.lower()=='default':return {'raw':header,'default':True,'clauses':[]}
 clauses=[]
 for raw_clause in [x.strip() for x in h.split(',') if x.strip()]:
  parts=raw_clause.split(None,1); key_raw=parts[0]; key=CONDITION_KEYS.get(key_raw.lower(),key_raw)
  expr=parts[1].strip() if len(parts)>1 else ''
  vals=split_values(expr) if expr else {'acceptedValues':[],'excludedValues':[]}
  alias_expansions=[]
  expanded=[]
  for v in vals['acceptedValues']:
   a=aliases.get(key.lower(),{}).get(v)
   if a:
    exp=list(a['acceptedValues'])
    if a['allExcept']:
     if key.lower() in ('playeranimtype','nextplayeranimtype'):
      exp=[x for x in player_types if x not in a['excludedValues']]
     else: exp=[]
    alias_expansions.append({'alias':v,'acceptedValues':exp,'excludedValues':a['excludedValues'],'allExcept':a['allExcept']})
    expanded.extend(exp)
   else: expanded.append(v)
  clauses.append({'key':key,'raw':raw_clause,**vals,'expandedAcceptedValues':list(dict.fromkeys(expanded)),'aliasExpansions':alias_expansions})
 return {'raw':header,'default':False,'clauses':clauses}

def parse_aliases(lines:list[str], player_types:list[str])->dict:
 out={}
 for raw in lines:
  s=clean(raw); m=SET_RE.match(s)
  if not m:continue
  key,name,expr=m.groups(); vals=split_values(expr); all_except=bool(vals['acceptedValues'] and vals['acceptedValues'][0].lower()=='all')
  accepted=[] if all_except else vals['acceptedValues']
  out.setdefault(key.lower(),{})[name]={'name':name,'rawExpression':expr,'acceptedValues':accepted,'excludedValues':vals['excludedValues'],'allExcept':all_except}
 return out

def next_significant(lines:list[str],i:int)->str:
 for j in range(i+1,len(lines)):
  s=clean(lines[j])
  if s:return s
 return ''

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--playeranim',type=Path,required=True);ap.add_argument('--playeranimtypes',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 raw=a.playeranim.read_text(encoding='latin1'); lines=raw.splitlines()
 player_types=[x.strip().replace('\x00','') for x in a.playeranimtypes.read_text(encoding='latin1').splitlines() if x.strip().replace('\x00','')]
 aliases=parse_aliases(lines,player_types)
 section=None; stack=[]; rules=[]; anim_directives=0
 for i,rawline in enumerate(lines):
  line_no=i+1;s=clean(rawline)
  if not s:continue
  up=s.upper()
  if up=='ANIMATIONS':section='ANIMATIONS';stack=[];continue
  if up=='EVENTS':section='EVENTS';stack=[];continue
  if s=='{':continue
  if s.startswith('}'):
   for _ in range(s.count('}')):
    if stack:stack.pop()
   continue
  if next_significant(lines,i)=='{':
   stack.append({'header':s,'line':line_no});continue
  m=ANIM_RE.match(s)
  if not (section and m):continue
  part,name,mods=m.groups(); context={'section':section}
  condition_headers=[]
  if section=='ANIMATIONS':
   state=None;movement=None;rest=[]
   for b in stack:
    sm=STATE_RE.match(b['header'])
    if sm and state is None:state=sm.group(1).strip();continue
    if state is not None and movement is None:movement=b['header'].strip();continue
    rest.append(b)
   context.update({'state':state,'movement':movement})
   condition_headers=rest
   fam=MOVEMENT_FAMILY.get((movement or '').lower())
  else:
   event=stack[0]['header'].strip() if stack else None
   context['event']=event
   condition_headers=stack[1:]
   fam=EVENT_FAMILY.get((event or '').lower())
  conditions=[parse_condition_header(x['header'],aliases,player_types)|{'line':x['line']} for x in condition_headers]
  rule={'ruleIndex':len(rules),'line':line_no,'part':part.lower(),'animation':name,'modifiers':mods.strip(),'context':context,'conditionBlocks':conditions,'source':rawline.rstrip(),'behaviorFamilies':[fam] if fam else []}
  rules.append(rule);anim_directives+=1
 weapon_literals=set();condition_keys={}
 for r in rules:
  for b in r['conditionBlocks']:
   for c in b['clauses']:
    condition_keys[c['key']]=condition_keys.get(c['key'],0)+1
    if c['key'].lower() in ('weaponclass','nextweaponclass'):
     weapon_literals.update(c['expandedAcceptedValues'] or c['acceptedValues'])
 for arow in aliases.get('weaponclass',{}).values():weapon_literals.update(arow['acceptedValues'])
 doc={'format':FORMAT,'authority':'direct retail mp/playeranim.script rule structure; no weapon or character identity inference','sources':{'playeranim':{'path':str(a.playeranim),'bytes':a.playeranim.stat().st_size,'sha256':sha256(a.playeranim)},'playeranimtypes':{'path':str(a.playeranimtypes),'bytes':a.playeranimtypes.stat().st_size,'sha256':sha256(a.playeranimtypes)}},'selectionSemantics':{'firstMatchWins':True,'ruleOrderPreserved':True,'weaponAndCharacterMetadataRemainExternal':True,'conditionValueANDIsPreservedAsRetailChoiceList':True,'defaultBlocksPreserved':True},'playerAnimTypes':player_types,'aliases':aliases,'weaponClassValuesObserved':sorted(x for x in weapon_literals if x and '=' not in x),'summary':{'animationDirectives':anim_directives,'rules':len(rules),'behaviorFamilyCounts':{},'conditionKeyCounts':condition_keys},'rules':rules}
 for r in rules:
  for f in r['behaviorFamilies']:doc['summary']['behaviorFamilyCounts'][f]=doc['summary']['behaviorFamilyCounts'].get(f,0)+1
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
