#!/usr/bin/env python3
"""Extract exact target T6 SndAlias variants from expanded retail FastFiles.

Bank names may be supplied explicitly or discovered from the expanded retail
bytes. Discovery only nominates printable ``*.all`` strings; a candidate is not
admitted unless the existing fail-closed SndBank/SndAliasList structural parser
validates the complete section.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from typing import Any
from t6_sndalias_expanded_census_v1 import compile_bank_regex,parse_sndbank_alias_section,snd_hash_name,semantic_digest

FORMAT='t6-sndalias-target-extract-v2'
BANK_DISCOVERY_RE=re.compile(rb'(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]{1,96}\.all)\x00')

def bank_candidates(blob:bytes,bank_bases:list[str],discover:bool)->list[tuple[str,int,str]]:
    found:dict[int,tuple[str,int,str]]={}
    if bank_bases:
        pattern=compile_bank_regex(bank_bases)
        for m in pattern.finditer(blob):
            found[m.start(1)]=(m.group(1).decode('ascii'),m.start(1),'explicit')
    if discover:
        for m in BANK_DISCOVERY_RE.finditer(blob):
            bank=m.group(1).decode('ascii')
            off=m.start(1)
            old=found.get(off)
            found[off]=(bank,off,'explicit+discovered' if old else 'discovered')
    return [found[k] for k in sorted(found)]

def extract_source(label:str,path:Path,bank_bases:list[str],discover:bool,target_by_id:dict[int,str])->tuple[list[dict[str,Any]],list[dict[str,Any]],dict[str,Any]]:
    blob=path.read_bytes(); found=[]; sections=[]
    candidates=bank_candidates(blob,bank_bases,discover)
    rejected=0
    for bank,off,nomination in candidates:
        lists,aliases,end,issues,learned=parse_sndbank_alias_section(blob,bank,off)
        if not lists or not aliases or issues:
            rejected+=1
            continue
        sections.append({'source':label,'bankName':bank,'bankNameOffset':off,'nomination':nomination,'aliasListCount':len(lists),'aliasOccurrenceCount':len(aliases),'endingCursor':end})
        for a in aliases:
            aid=int(a['alias_list_id'])&0xffffffff
            if aid not in target_by_id: continue
            kept={k:v for k,v in a.items() if not k.endswith('_ptr')}
            kept.update({'source':label,'bankName':bank,'bankNameOffset':off,'targetAliasName':target_by_id[aid],'aliasIdHex':f'{aid:08X}','assetIdHex':f"{int(a['asset_id'])&0xffffffff:08X}",'semanticDigest':semantic_digest(a)})
            found.append(kept)
    meta={'source':label,'candidateBankStringCount':len(candidates),'validatedSndBankSectionCount':len(sections),'rejectedCandidateCount':rejected,'validatedBankNames':sorted({s['bankName'] for s in sections})}
    return found,sections,meta

def build(sources:list[tuple[str,Path]],targets:list[str],bank_bases:list[str],discover:bool=False)->dict[str,Any]:
    if not bank_bases and not discover:
        raise ValueError('at least one explicit bank base or discovery mode is required')
    target_by_id={}
    for n in targets:
        h=snd_hash_name(n)
        old=target_by_id.get(h)
        if old is not None and old!=n: raise ValueError(f'target hash collision {old!r} vs {n!r}')
        target_by_id[h]=n
    occurrences=[];sections=[];source_meta=[]
    for label,path in sources:
        f,s,m=extract_source(label,path,bank_bases,discover,target_by_id);occurrences+=f;sections+=s;source_meta.append(m)
    by_name={n:[] for n in targets}
    for o in occurrences: by_name[o['targetAliasName']].append(o)
    missing=[n for n,v in by_name.items() if not v]
    aliases=[]
    for n in sorted(targets):
        vals=by_name[n]; ids=sorted({x['assetIdHex'] for x in vals if x['assetIdHex']!='00000000'})
        aliases.append({'aliasName':n,'aliasIdHex':f'{snd_hash_name(n):08X}','occurrenceCount':len(vals),'uniqueNonzeroAssetIds':ids,'zeroAssetIdOccurrenceCount':sum(x['assetIdHex']=='00000000' for x in vals),'occurrences':vals})
    return {
      'format':FORMAT,
      'summary':{'sourceCount':len(sources),'targetAliasCount':len(targets),'foundTargetAliasCount':len(targets)-len(missing),'missingTargetAliasCount':len(missing),'targetAliasOccurrenceCount':len(occurrences),'candidateBankStringCount':sum(m['candidateBankStringCount'] for m in source_meta),'validatedSndBankSectionCount':len(sections),'rejectedCandidateCount':sum(m['rejectedCandidateCount'] for m in source_meta)},
      'bankNomination':{'explicitBankBases':bank_bases,'discoverRetailAllStrings':discover},
      'sources':[{'label':l,'path':str(p),'bytes':p.stat().st_size} for l,p in sources],
      'sourceBankCensus':source_meta,
      'missingTargetAliases':missing,'aliases':aliases,'validatedSections':sections,
      'proofBoundary':'Targets are exact SND_HashName identities. Explicit bank names and/or printable *.all strings from the exact expanded retail bytes only nominate candidate sections. A candidate is admitted only after full structural SndBank/SndAliasList validation. All target variants and raw playback fields are retained. No runtime variant selection, physical-bank payload join, patch precedence, or meaning is inferred from a discovered string alone.',
    }

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--expanded',action='append',required=True,help='LABEL=PATH');ap.add_argument('--target',action='append',default=[]);ap.add_argument('--target-file',type=Path);ap.add_argument('--bank-base',action='append',default=[]);ap.add_argument('--discover-bank-bases',action='store_true');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    targets=list(a.target)
    if a.target_file: targets += [x.strip() for x in a.target_file.read_text().splitlines() if x.strip()]
    targets=list(dict.fromkeys(targets))
    if not targets: raise SystemExit('no targets')
    if not a.bank_base and not a.discover_bank_bases: raise SystemExit('provide --bank-base and/or --discover-bank-bases')
    sources=[]
    for spec in a.expanded:
        if '=' not in spec: raise SystemExit('--expanded must be LABEL=PATH')
        l,p=spec.split('=',1);sources.append((l,Path(p)))
    d=build(sources,targets,a.bank_base,a.discover_bank_bases)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps(d['summary'],indent=2,sort_keys=True))
    for m in d['sourceBankCensus']: print('BANKS',m['source'],m['validatedBankNames'])
    for x in d['aliases']: print(x['aliasIdHex'],x['aliasName'],'occ',x['occurrenceCount'],'assetIds',x['uniqueNonzeroAssetIds'])
    if d['missingTargetAliases']:
        print('MISSING',d['missingTargetAliases'])
        return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
