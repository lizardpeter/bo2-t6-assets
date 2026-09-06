#!/usr/bin/env python3
"""Collect the minimal retail source bundle for the SEAL6 SMG gold character.

This is intentionally a *collector*, not an exporter. It reduces the local BO2
installation to the exact bytes/normalized sidecars needed to finish one
source-closed textured + animated character without copying multi-GB archives.

It performs four independently gated stages:
1. verify/decrypt the exact retail common_mp + faction_seals_mp fastfiles;
2. normalize three retained third-person XAnim canaries at hash-pinned offsets;
3. resolve the gold character's exact GfxImage keys from retail faction/common
   streams, including comma-prefixed alias canonicalization only when the
   canonical image itself is strictly present;
4. collect only raw IPAK spans matching exact (nameHash,dataHash29) pairs.

No texture pixels are promoted here. Raw IPAK spans still require reconstruction,
CRC29 and IWI dimension validation before they may be bound to the model.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
TARGET_SPEC=ROOT/'manifests/nonmap/targets/seal6_smg_gold_image_names_v1.json'

EXPECTED={
    'common_mp.ff':{
        'encryptedSha256':'93fe48b0f0d8cc6844be875ccad94e0cfcf635f62eeff00ac33f2f668a77cb77',
        'expandedSha256':'fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce',
        'expandedBytes':206493911,
    },
    'faction_seals_mp.ff':{
        'encryptedSha256':'1a075434760751551158b7d62cc2761649e2d2c7606b27b3bbe066b998b77c88',
        'expandedSha256':'21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30',
        'expandedBytes':6245916,
    },
}

XANIMS={
    'pb_stand_alert':662933,
    'pb_smg_sprint':5203838,
    'pt_stand_shoot_auto':7851319,
}
SHARED_MATERIALS=[
    ',mc/mtl_c_gen_insidemouth',
    ',mc/mtl_gen_eye_cornea',
    ',mc/mtl_c_gen_mp_datapad',
]


def load_module(filename:str,modname:str):
    p=HERE/filename
    spec=importlib.util.spec_from_file_location(modname,p)
    m=importlib.util.module_from_spec(spec);assert spec.loader is not None;spec.loader.exec_module(m);return m

FF=load_module('bo2_t6_fastfile.py','bo2ff')
IMG=load_module('t6_gfximage_exact_key_scan_v1.py','imgscan')
MAT=load_module('t6_material_texturedef_audit_v1.py','mataudit')
XAN=load_module('t6_xanim_normalize_v1.py','xannorm')
IPAK=load_module('t6_ipak_exact_slice_collect_v1.py','ipakslice')


def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def sha_file(p:Path,chunk:int=8*1024*1024)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while True:
            b=f.read(chunk)
            if not b:break
            h.update(b)
    return h.hexdigest()

def find_one(root:Path,basename:str)->Path:
    hits=[p for p in root.rglob('*') if p.is_file() and p.name.lower()==basename.lower()]
    if len(hits)!=1:raise RuntimeError(f'{basename}: expected exactly one file below {root}, got {len(hits)}: {hits[:5]}')
    return hits[0]

def verify_expand(path:Path):
    exp=EXPECTED[path.name.lower()]
    enc=path.read_bytes();esh=sha_bytes(enc)
    if esh!=exp['encryptedSha256']:raise RuntimeError(f'{path.name}: encrypted SHA mismatch {esh} != {exp["encryptedSha256"]}')
    expanded,audit,summary=FF.decrypt_fastfile_bytes(enc)
    xsh=sha_bytes(expanded)
    if xsh!=exp['expandedSha256'] or len(expanded)!=exp['expandedBytes']:
        raise RuntimeError(f'{path.name}: expanded mismatch bytes={len(expanded)} sha={xsh}')
    return expanded,{'path':str(path),'encryptedBytes':len(enc),'encryptedSha256':esh,'expandedBytes':len(expanded),'expandedSha256':xsh,'records':len(audit),'zoneName':summary['zoneName']}

def exact_cstring_positions(data:bytes,name:str):
    b=name.encode('latin1');out=[];pos=0
    while True:
        p=data.find(b,pos)
        if p<0:break
        if p+len(b)<len(data) and data[p+len(b)]==0 and (p==0 or data[p-1]==0):out.append(p)
        pos=p+1
    return out

def scan_material(data:bytes,requested:str):
    variants=[requested]
    if requested.startswith(','):variants.append(requested[1:])
    rows=[]
    for name in dict.fromkeys(variants):
        for p in exact_cstring_positions(data,name):
            st=p-112
            if st<0:continue
            try:doc=MAT.audit(data,st,name)
            except Exception:continue
            rows.append({'requestedName':requested,'serializedName':name,'nameStart':p,'material':doc})
    # Identical duplicates are okay; conflicting exact material tables are not.
    fps={(r['serializedName'],r['material']['source']['materialFixedSha256'],r['material']['source']['textureTableSha256']) for r in rows}
    if len(fps)>1:
        raise RuntimeError(f'{requested}: conflicting strict common Material definitions: {sorted(fps)}')
    return rows

def scan_image_with_alias_policy(data:bytes,target:dict):
    requested=target['name'];variants=[requested]
    if target.get('allowCanonicalWithoutLeadingComma') and requested.startswith(','):variants.append(requested[1:])
    attempts=[];strong=[];shells=[]
    for name in dict.fromkeys(variants):
        row=IMG.scan_one(data,name);attempts.append({'serializedCandidate':name,'scan':row})
        if row['exactStreamedKey'] is not None:strong.append((name,row['exactStreamedKey']))
        shells.extend((name,x) for x in row['aliasShells'])
    keys={(h['nameHash'],h['dataHash29'],tuple(h['dimensions'])) for _,h in strong}
    if len(keys)>1:raise RuntimeError(f'{requested}: alias variants resolve to conflicting exact GfxImage keys: {sorted(keys)}')
    chosen=strong[0] if strong else None
    return {'target':target,'attempts':attempts,
            'resolution':({'status':'exact-streamed-key','requestedName':requested,'serializedName':chosen[0],**chosen[1]} if chosen else
                          {'status':'exact-alias-shell-only' if shells else 'unresolved','requestedName':requested,'serializedName':shells[0][0] if shells else None,'aliasShells':[x for _,x in shells]})}

def write_json(path:Path,obj):
    text=json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n';path.write_text(text,encoding='utf-8');return sha_bytes(text.encode())

def collect_ipak_slices(game_root:Path,out:Path,resolved_images:list[dict]):
    # Deduplicate by exact retail key, retaining every usage/name in metadata.
    by_pair={}
    for row in resolved_images:
        r=row['resolution']
        if r['status']!='exact-streamed-key':continue
        pair=(int(r['nameHash']),int(r['dataHash29']))
        ent=by_pair.setdefault(pair,{'nameHash':pair[0],'dataHash29':pair[1],'dimensions':r['dimensions'],'usages':[]})
        if tuple(ent['dimensions'])!=tuple(r['dimensions']):raise RuntimeError(f'pair {pair}: dimension conflict')
        ent['usages'].append({'requestedName':r['requestedName'],'serializedName':r['serializedName'],'material':row['target'].get('material'),'semantic':row['target'].get('semantic'),'role':row['target'].get('role')})
    pairs=set(by_pair)
    archives=IPAK.discover_archives(game_root,['patch_mp.ipak','mp.ipak','base.ipak'])
    if not archives:raise RuntimeError('no patch_mp.ipak/mp.ipak/base.ipak found below game root')
    slice_dir=out/'ipak_slices';slice_dir.mkdir(parents=True,exist_ok=True)
    archive_rows=[];matches=[]
    for rank,path in enumerate(archives):
        idx=IPAK.IPakIndex(path);hits=idx.find_pairs(pairs)
        archive_rows.append({'path':str(path),'basename':path.name,'bytes':path.stat().st_size,'precedenceRank':rank,'matchedEntries':len(hits)})
        for h in hits:
            pair=(h['nameHash'],h['dataHash29']);meta=by_pair[pair];blob=idx.read_span(h)
            fn=f'{h["nameHash"]:08X}_{h["dataHash29"]:08X}__{path.name}.ipakspan';op=slice_dir/fn;op.write_bytes(blob)
            matches.append({'key':meta,'archive':archive_rows[-1],'indexEntry':h,'slice':{'path':str(op.relative_to(out)),'bytes':len(blob),'sha256':sha_bytes(blob)}})
    matched_pairs={(m['indexEntry']['nameHash'],m['indexEntry']['dataHash29']) for m in matches}
    return {'format':'t6-character-gold-ipak-slices-v1','archives':archive_rows,'matches':matches,
            'summary':{'exactPairs':len(pairs),'pairsMatched':len(matched_pairs),'pairsUnmatched':len(pairs-matched_pairs),'rawSlices':len(matches)},
            'unmatched':[{'nameHash':p[0],'dataHash29':p[1],**by_pair[p]} for p in sorted(pairs-matched_pairs)],
            'proofBoundary':'Raw spans only. Pixel promotion requires later IPAK block reconstruction, CRC29 and IWI dimension validation.'}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('game_root',type=Path);ap.add_argument('output_dir',type=Path);ap.add_argument('--no-zip',action='store_true');a=ap.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    common_path=find_one(a.game_root,'common_mp.ff');faction_path=find_one(a.game_root,'faction_seals_mp.ff')
    common,common_src=verify_expand(common_path);faction,faction_src=verify_expand(faction_path)

    # Exact normalized retail XAnim canaries.
    anim_dir=a.output_dir/'xanim';anim_dir.mkdir(exist_ok=True);anims=[]
    for expected_name,start in XANIMS.items():
        doc=XAN.normalize(common,start)
        if doc.get('name')!=expected_name:raise RuntimeError(f'XAnim offset {start}: got {doc.get("name")!r}, expected {expected_name!r}')
        doc['expandedSha256']=common_src['expandedSha256'];op=anim_dir/(expected_name+'.json');jsha=write_json(op,doc)
        delta=doc.get('delta') or {};has_delta=any(delta.get(k) for k in ('trans','quat2','quat'))
        anims.append({'name':expected_name,'assetFixedStart':start,'frames':doc['header']['numframes'],'framerate':doc['header']['framerate'],'tracks':len(doc['boneTracks']),
                      'hasDeltaPart':has_delta,'serializedSha256':doc['assetSerializedSha256'],'normalizedFile':str(op.relative_to(a.output_dir)),'normalizedSha256':jsha})

    # Strict shared Material rows from common_mp.
    common_materials=[]
    for name in SHARED_MATERIALS:common_materials.extend(scan_material(common,name))
    write_json(a.output_dir/'common_materials.json',{'format':'t6-character-gold-common-materials-v1','rows':common_materials,'summary':{'requested':len(SHARED_MATERIALS),'strictRows':len(common_materials)}})

    spec=json.loads(TARGET_SPEC.read_text())
    image_rows=[]
    for target in spec['names']:
        stream=faction if target.get('sourceHint')=='faction_seals_mp' else common
        image_rows.append(scan_image_with_alias_policy(stream,target))
    image_doc={'format':'t6-character-gold-gfximage-keys-v1','body':spec['body'],'rows':image_rows,
               'summary':{'targets':len(image_rows),'exactStreamedKeys':sum(r['resolution']['status']=='exact-streamed-key' for r in image_rows),
                          'aliasShellOnly':sum(r['resolution']['status']=='exact-alias-shell-only' for r in image_rows),
                          'unresolved':sum(r['resolution']['status']=='unresolved' for r in image_rows)}}
    write_json(a.output_dir/'gfximage_keys.json',image_doc)

    ipak_doc=collect_ipak_slices(a.game_root,a.output_dir,image_rows);write_json(a.output_dir/'ipak_slices.json',ipak_doc)
    manifest={'format':'t6-character-gold-collection-v1','body':spec['body'],'sourceFastfiles':{'commonMp':common_src,'factionSealsMp':faction_src},'animations':anims,
              'materials':{'commonRequested':SHARED_MATERIALS,'strictCommonRows':len(common_materials)},'images':image_doc['summary'],'ipak':ipak_doc['summary'],
              'proofBoundary':'Collection only. Geometry/skin proof lives separately. IPAK slices are not pixel proof until reconstructed+CRC/dimension checked. XAnim clips are normalized from exact hash-pinned common_mp retail bytes.'}
    write_json(a.output_dir/'gold_collection_manifest.json',manifest)
    if not a.no_zip:
        zp=a.output_dir.with_suffix('.zip')
        with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(a.output_dir.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(a.output_dir.parent))
        manifest['zip']={'path':str(zp),'bytes':zp.stat().st_size,'sha256':sha_file(zp)};write_json(a.output_dir/'gold_collection_manifest.json',manifest)
    print(json.dumps({'output':str(a.output_dir),'animations':len(anims),**image_doc['summary'],**ipak_doc['summary'],'zip':manifest.get('zip')},indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
