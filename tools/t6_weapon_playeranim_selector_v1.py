#!/usr/bin/env python3
"""Extract retail T6 WeaponDef player-animation selector metadata.

This tool deliberately separates one zone layer from final weapon precedence.
It only promotes selector fields when a WeaponVariantDef is exact-inline by
internal name and its reusable weapDef is serialized FOLLOWING/INSERT directly
behind the internal-name string. Packed/inherited WeaponDef pointers remain
unresolved at this layer.
"""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
INV_PATH=HERE/'t6_raw_xasset_inventory_v2.py'
PLAYER_ANIM_TYPES=['none','default','other','sniper','m203','hold','briefcase','reviver','radio','dualwield','remotecontrol','crossbow','minigun','beltfed','g11','rearclip','handleclip','rearclipsniper','ballisticknife','singleknife','nopump','hatchet','grimreaper','zipline','riotshield','tablet','turned','screecher','staff']
WEAP_TYPES=['bullet','grenade','projectile','binoculars','gas','bomb','mine','melee','riotshield']
WEAP_CLASSES=['rifle','mg','smg','spread','pistol','grenade','rocketlauncher','turret','non-player','gas','item','melee','Killstreak Alt Stored Weapon','pistol spread']
FIRE_TYPES=['Full Auto','Single Shot','2-Round Burst','3-Round Burst','4-Round Burst','5-Round Burst','Stacked Fire','Minigun','Charge Shot','Jetgun']

def load_inv():
    spec=importlib.util.spec_from_file_location('t6_raw_xasset_inventory_v2',INV_PATH)
    if spec is None or spec.loader is None: raise RuntimeError(f'cannot import {INV_PATH}')
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(1<<20),b''): h.update(x)
    return h.hexdigest()

def names_from(path:Path)->list[str]:
    if path.suffix.lower()=='.csv':
        with path.open('r',encoding='utf-8-sig',newline='') as f:
            return [x for r in csv.DictReader(f) for x in [r.get('internal_name') or r.get('name')] if x]
    d=json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(d,list): return [str(x) for x in d]
    if isinstance(d,dict):
        for key in ('weapon_variant_roots','exact_common_mp_roots','weapons'):
            v=d.get(key)
            if isinstance(v,list):
                if key=='weapon_variant_roots': return [str(x.get('internal_name')) for x in v if isinstance(x,dict) and x.get('internal_name')]
                return [str(x) for x in v]
        p=d.get('common_mp_player_root_proof')
        if isinstance(p,dict) and isinstance(p.get('exact_common_mp_roots'),list): return [str(x) for x in p['exact_common_mp_roots']]
    raise ValueError(f'{path}: cannot find weapon names')

def enum_name(seq:list[str],v:int)->str|None: return seq[v] if 0<=v<len(seq) else None

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('expanded',type=Path); ap.add_argument('--zone',required=True); ap.add_argument('--roots',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    inv=load_inv(); data=a.expanded.read_bytes(); front=inv.parse_front(data); blocks=front['_blocks']; names=names_from(a.roots); rows=[]
    for name in names:
        wvd=inv.locate_wvd(data,name,blocks); base={'weapon':name,'zone':a.zone,'wvdStatus':wvd.get('status')}
        if wvd.get('status')!='exact_inline_fixed_record': rows.append({**base,'selectorStatus':'unresolved-wvd','detail':wvd}); continue
        internal=int(wvd['raw_internal_name_offset']); ptr=wvd['weapDef']; kind=ptr['decoded']['kind']
        base.update({'wvdRawOffset':wvd['raw_struct_offset'],'wvdRawSize':wvd['raw_struct_size'],'wvdFixedSha256':sha256_bytes(data[wvd['raw_struct_offset']:wvd['raw_struct_offset']+wvd['raw_struct_size']]),'internalNameRawOffset':internal,'weapDefPointerRaw':ptr['raw'],'weapDefPointerKind':kind})
        if kind not in ('following','insert'):
            rows.append({**base,'selectorStatus':'unresolved-packed-weapdef','weapDefPointer':ptr['decoded']}); continue
        wd=internal+len(name.encode('latin1'))+1
        if wd+56>len(data): rows.append({**base,'selectorStatus':'truncated-weapdef-prefix'}); continue
        vals={k:struct.unpack_from('<i',data,wd+off)[0] for k,off in [('playerAnimTypeIndex',24),('weaponTypeIndex',28),('weaponClassIndex',32),('penetrateTypeIndex',36),('impactTypeIndex',40),('inventoryTypeIndex',44),('fireTypeIndex',48),('clipTypeIndex',52)]}
        pat=enum_name(PLAYER_ANIM_TYPES,vals['playerAnimTypeIndex']); wt=enum_name(WEAP_TYPES,vals['weaponTypeIndex']); wc=enum_name(WEAP_CLASSES,vals['weaponClassIndex']); ft=enum_name(FIRE_TYPES,vals['fireTypeIndex'])
        sane=pat is not None and wt is not None and wc is not None and ft is not None
        rows.append({**base,'selectorStatus':'exact-inline-weapdef-prefix' if sane else 'invalid-enum-range','weaponDefRawOffset':wd,'weaponDefPrefix56Sha256':sha256_bytes(data[wd:wd+56]),**vals,'playerAnimType':pat,'weaponType':wt,'weaponClass':wc,'fireType':ft,'selector':{'weaponclass':wc,'playerAnimType':pat} if sane else None})
    counts={}; profiles={}
    for r in rows:
        counts[r['selectorStatus']]=counts.get(r['selectorStatus'],0)+1
        if r.get('selector'):
            key=f"{r['weaponClass']}|{r['playerAnimType']}"; profiles[key]=profiles.get(key,0)+1
    out={'format':'t6-weapon-playeranim-selector-layer-v1','authority':'hash-pinned expanded retail T6 PC WeaponVariantDef -> inline WeaponDef fixed prefix','zone':a.zone,'source':{'expanded':str(a.expanded),'bytes':len(data),'sha256':sha256_file(a.expanded),'roots':str(a.roots),'rootsSha256':sha256_file(a.roots)},'structureProof':{'weaponVariantDefPc32FixedSize':inv.WVD_SIZE,'serializedOrder':'WeaponVariantDef fixed -> szInternalName FOLLOWING string -> reusable weapDef when FOLLOWING/INSERT','weaponDefPc32Offsets':{'playerAnimType':24,'weapType':28,'weapClass':32,'fireType':48},'playerAnimTypeNames':PLAYER_ANIM_TYPES,'weaponClassNames':WEAP_CLASSES},'summary':{'requested':len(names),'statusCounts':counts,'exactSelectors':sum(bool(r.get('selector')) for r in rows),'selectorProfileCounts':dict(sorted(profiles.items()))},'weapons':rows,'precedenceBoundary':'This is one zone-layer observation only. A named weapon is not final until later common_patch_mp/patch_mp overrides are resolved.'}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out['summary'],indent=2,sort_keys=True)); return 0 if out['summary']['exactSelectors']==len(names) else 2
if __name__=='__main__': raise SystemExit(main())
