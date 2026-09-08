#!/usr/bin/env python3
"""Extract exact target T6 SndAlias variants from expanded retail FastFiles."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from t6_sndalias_expanded_census_v1 import compile_bank_regex,parse_sndbank_alias_section,snd_hash_name,semantic_digest

FORMAT='t6-sndalias-target-extract-v1'

def extract_source(label:str,path:Path,bank_bases:list[str],target_by_id:dict[int,str])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    blob=path.read_bytes(); pattern=compile_bank_regex(bank_bases); found=[]; sections=[]
    for match in pattern.finditer(blob):
        bank=match.group(1).decode('ascii')
        lists,aliases,end,issues,learned=parse_sndbank_alias_section(blob,bank,match.start(1))
        if not lists or not aliases or issues: continue
        sections.append({'source':label,'bankName':bank,'bankNameOffset':match.start(1),'aliasListCount':len(lists),'aliasOccurrenceCount':len(aliases),'endingCursor':end})
        for a in aliases:
            aid=int(a['alias_list_id'])&0xffffffff
            if aid not in target_by_id: continue
            kept={k:v for k,v in a.items() if not k.endswith('_ptr')}
            kept.update({'source':label,'bankName':bank,'bankNameOffset':match.start(1),'targetAliasName':target_by_id[aid],'aliasIdHex':f'{aid:08X}','assetIdHex':f"{int(a['asset_id'])&0xffffffff:08X}",'semanticDigest':semantic_digest(a)})
            found.append(kept)
    return found,sections

def build(sources:list[tuple[str,Path]],targets:list[str],bank_bases:list[str])->dict[str,Any]:
    target_by_id={}
    for n in targets:
        h=snd_hash_name(n)
        old=target_by_id.get(h)
        if old is not None and old!=n: raise ValueError(f'target hash collision {old!r} vs {n!r}')
        target_by_id[h]=n
    occurrences=[];sections=[]
    for label,path in sources:
        f,s=extract_source(label,path,bank_bases,target_by_id);occurrences+=f;sections+=s
    by_name={n:[] for n in targets}
    for o in occurrences: by_name[o['targetAliasName']].append(o)
    missing=[n for n,v in by_name.items() if not v]
    aliases=[]
    for n in sorted(targets):
        vals=by_name[n]; ids=sorted({x['assetIdHex'] for x in vals if x['assetIdHex']!='00000000'})
        aliases.append({'aliasName':n,'aliasIdHex':f'{snd_hash_name(n):08X}','occurrenceCount':len(vals),'uniqueNonzeroAssetIds':ids,'zeroAssetIdOccurrenceCount':sum(x['assetIdHex']=='00000000' for x in vals),'occurrences':vals})
    return {
      'format':FORMAT,
      'summary':{'sourceCount':len(sources),'targetAliasCount':len(targets),'foundTargetAliasCount':len(targets)-len(missing),'missingTargetAliasCount':len(missing),'targetAliasOccurrenceCount':len(occurrences),'validatedSndBankSectionCount':len(sections)},
      'bankBases':bank_bases,'sources':[{'label':l,'path':str(p),'bytes':p.stat().st_size} for l,p in sources],
      'missingTargetAliases':missing,'aliases':aliases,'validatedSections':sections,
      'proofBoundary':'Targets are exact SND_HashName identities. Only structurally validated SndBank/SndAliasList sections are admitted. All target variants and raw playback fields are retained. No runtime variant selection, physical-bank payload join, or patch precedence is inferred.',
    }

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--expanded',action='append',required=True,help='LABEL=PATH');ap.add_argument('--target',action='append',default=[]);ap.add_argument('--target-file',type=Path);ap.add_argument('--bank-base',action='append',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    targets=list(a.target)
    if a.target_file: targets += [x.strip() for x in a.target_file.read_text().splitlines() if x.strip()]
    targets=list(dict.fromkeys(targets))
    if not targets: raise SystemExit('no targets')
    sources=[]
    for spec in a.expanded:
        if '=' not in spec: raise SystemExit('--expanded must be LABEL=PATH')
        l,p=spec.split('=',1);sources.append((l,Path(p)))
    d=build(sources,targets,a.bank_base)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps(d['summary'],indent=2,sort_keys=True))
    for x in d['aliases']: print(x['aliasIdHex'],x['aliasName'],'occ',x['occurrenceCount'],'assetIds',x['uniqueNonzeroAssetIds'])
    if d['missingTargetAliases']:
        print('MISSING',d['missingTargetAliases'])
        return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
