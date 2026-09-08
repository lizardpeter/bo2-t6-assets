#!/usr/bin/env python3
"""Collect exact direct weapon/attachment audio aliases from an R2 raw package."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any

FORMAT='t6-weapon-direct-audio-plan-v1'
SOURCE={
 'repository':'Laupetin/OpenAssetTools',
 'commit':'9dca965366541504b71fa8cfb7ac049cb9b717e1',
 'path':'src/Common/Game/T6/CommonT6.h',
 'symbol':'T6::Common::SND_HashName',
}

def snd_hash_name(text:str)->int:
    if not text:return 0
    result=0x1505
    for c in text.lower().encode('latin1',errors='ignore'):
        result=(c+0x1003F*result)&0xffffffff
    return result or 1

def add(refs:dict[str,list[dict[str,Any]]],value:str,occ:dict[str,Any])->None:
    for alias in value.splitlines():
        alias=alias.strip()
        if alias: refs.setdefault(alias,[]).append(occ)

def build(raw:dict[str,Any])->dict[str,Any]:
    if raw.get('format')!='t6-mp7-r2-raw-package-v1':
        raise ValueError('unexpected raw package format')
    refs:dict[str,list[dict[str,Any]]]={}
    for copy in raw['weapon']['physicalCopies']:
        for row in copy['rows']:
            if 'sound' in row['name'].lower() and row['value']:
                add(refs,row['value'],{'kind':'weapon','zone':copy['zone'],'field':row['name'],'rowIndex':row['rowIndex']})
    for rec in raw['attachmentUnique']['records']:
        for copy in rec['copies']:
            for row in copy['rows']:
                if 'sound' in row['name'].lower() and row['value']:
                    add(refs,row['value'],{'kind':'attachmentUnique','identity':rec['name'],'zone':copy['zone'],'field':row['name'],'rowIndex':row['rowIndex']})
    for rec in raw['attachments']['records']:
        for copy in rec['physicalCopies']:
            for row in copy['rows']:
                if 'sound' in row['name'].lower() and row['value']:
                    add(refs,row['value'],{'kind':'attachment','identity':rec['name'],'zone':copy['zone'],'field':row['name'],'rowIndex':row['rowIndex']})
    aliases=[]
    seen_hash:dict[int,str]={}
    for name in sorted(refs):
        hid=snd_hash_name(name)
        old=seen_hash.get(hid)
        if old is not None and old!=name:
            raise ValueError(f'SND_HashName collision among direct references: {old!r} vs {name!r} -> {hid:08X}')
        seen_hash[hid]=name
        aliases.append({'aliasName':name,'aliasIdHex':f'{hid:08X}','referenceOccurrenceCount':len(refs[name]),'references':refs[name]})
    return {
      'format':FORMAT,
      'hashAuthority':SOURCE,
      'summary':{
        'uniqueDirectAliasNameCount':len(aliases),
        'uniqueDirectAliasIdCount':len(seen_hash),
        'referenceOccurrenceCount':sum(len(v) for v in refs.values()),
        'hashCollisionCount':0,
        'animationNotetrackAliasesIncluded':False,
      },
      'aliases':aliases,
      'proofBoundary':'Direct non-empty fields whose authored field name contains sound are preserved from the exact R2-native weapon, AttachmentUnique, and generic attachment records. T6 alias IDs use the source-pinned SND_HashName algorithm. XAnim notify/notetrack audio is intentionally excluded and must be joined separately.',
    }

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--raw-package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    d=build(json.loads(a.raw_package.read_text(encoding='utf-8')))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(d['summary'],indent=2,sort_keys=True))
    for x in d['aliases']: print(x['aliasIdHex'],x['aliasName'],x['referenceOccurrenceCount'])
    return 0
if __name__=='__main__':raise SystemExit(main())
