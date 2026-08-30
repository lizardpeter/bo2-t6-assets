#!/usr/bin/env python3
"""Stage 18D: direct T6 WeaponAttachmentUnique -> XModel dependency resolver.

Authority: expanded retail T6 common_mp XFile bytes. No OpenAssetTools executable.
The external T6_Assets.h layout is used only as a struct-layout cross-check.

Proof scope:
- locate exact 424-byte PC WeaponAttachmentUnique records by their inline names
- recover all 95-slot unique tables for the canonical player-facing common_mp roots
- parse the five XModel reference fields from every unique record
- locate every newly serialized 248-byte XModel fixed record directly in the raw stream
- biject those raw definitions to the 112 packed XMODEL XAsset headers by load/destination order
- resolve every packed unique-model reference by exact XAsset pointer identity
"""
from __future__ import annotations
import argparse, bisect, csv, ctypes, importlib.util, json, struct
from collections import defaultdict
from pathlib import Path

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
WAU_SIZE = 424
UNIQUE_SLOTS = 95
UNIQUE_ARRAY_BYTES = UNIQUE_SLOTS * 4
XMODEL_SIZE = 248
MODEL_FIELDS = ["viewModel", "viewModelAdditional", "viewModelADS", "worldModel", "worldModelAdditional"]

class Vec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class WeaponAttachmentUnique(ctypes.Structure):
    _fields_ = [
        ("szInternalName", ctypes.c_uint32), ("attachmentType", ctypes.c_int32),
        ("siblingLink", ctypes.c_int32), ("childLink", ctypes.c_int32),
        ("combinedAttachmentTypeMask", ctypes.c_int32), ("szAltWeaponName", ctypes.c_uint32),
        ("altWeaponIndex", ctypes.c_uint32), ("szDualWieldWeaponName", ctypes.c_uint32),
        ("dualWieldWeaponIndex", ctypes.c_uint32), ("hideTags", ctypes.c_uint32),
        ("viewModel", ctypes.c_uint32), ("viewModelAdditional", ctypes.c_uint32),
        ("viewModelADS", ctypes.c_uint32), ("worldModel", ctypes.c_uint32),
        ("worldModelAdditional", ctypes.c_uint32), ("viewModelTag", ctypes.c_uint32),
        ("worldModelTag", ctypes.c_uint32),
        ("viewModelOffsets", Vec3), ("worldModelOffsets", Vec3),
        ("viewModelRotations", Vec3), ("worldModelRotations", Vec3),
        ("viewModelAddOffsets", Vec3), ("worldModelAddOffsets", Vec3),
        ("viewModelAddRotations", Vec3), ("worldModelAddRotations", Vec3),
        ("weaponCamo", ctypes.c_uint32),
        ("disableBaseWeaponAttachment", ctypes.c_bool), ("disableBaseWeaponClip", ctypes.c_bool),
        ("overrideBaseWeaponAttachmentOffsets", ctypes.c_bool),
        ("viewModelOffsetBaseAttachment", Vec3), ("worldModelOffsetBaseAttachment", Vec3),
        ("overlayMaterial", ctypes.c_uint32), ("overlayMaterialLowRes", ctypes.c_uint32),
        ("overlayReticle", ctypes.c_int32), ("iFirstRaiseTime", ctypes.c_int32),
        ("iAltRaiseTime", ctypes.c_int32), ("iAltDropTime", ctypes.c_int32),
        ("iReloadAmmoAdd", ctypes.c_int32), ("iReloadStartAdd", ctypes.c_int32),
        ("bSegmentedReload", ctypes.c_bool), ("szXAnims", ctypes.c_uint32),
        ("animationOverrides", ctypes.c_int32 * 3), ("locationDamageMultipliers", ctypes.c_uint32),
        ("soundOverrides", ctypes.c_int32),
        ("fireSound", ctypes.c_uint32), ("fireSoundPlayer", ctypes.c_uint32),
        ("fireLoopSound", ctypes.c_uint32), ("fireLoopSoundPlayer", ctypes.c_uint32),
        ("fireLoopEndSound", ctypes.c_uint32), ("fireLoopEndSoundPlayer", ctypes.c_uint32),
        ("fireStartSound", ctypes.c_uint32), ("fireStopSound", ctypes.c_uint32),
        ("fireStartSoundPlayer", ctypes.c_uint32), ("fireStopSoundPlayer", ctypes.c_uint32),
        ("fireLastSound", ctypes.c_uint32), ("fireLastSoundPlayer", ctypes.c_uint32),
        ("fireKillcamSound", ctypes.c_uint32), ("fireKillcamSoundPlayer", ctypes.c_uint32),
        ("effectOverrides", ctypes.c_int32), ("viewFlashEffect", ctypes.c_uint32),
        ("worldFlashEffect", ctypes.c_uint32), ("tracerType", ctypes.c_uint32),
        ("enemyTracerType", ctypes.c_uint32), ("adsDofStart", ctypes.c_float),
        ("adsDofEnd", ctypes.c_float), ("iAmmoIndex", ctypes.c_int32), ("iClipIndex", ctypes.c_int32),
        ("bOverrideLeftHandIK", ctypes.c_bool), ("bOverrideLeftHandProneIK", ctypes.c_bool),
        ("ikLeftHandOffset", Vec3), ("ikLeftHandRotation", Vec3),
        ("ikLeftHandProneOffset", Vec3), ("ikLeftHandProneRotation", Vec3),
        ("customFloat0", ctypes.c_float), ("customFloat1", ctypes.c_float), ("customFloat2", ctypes.c_float),
        ("customBool0", ctypes.c_int32), ("customBool1", ctypes.c_int32), ("customBool2", ctypes.c_int32),
    ]

class XModelLodInfo(ctypes.Structure):
    _fields_ = [("dist", ctypes.c_float), ("numsurfs", ctypes.c_uint16), ("surfIndex", ctypes.c_uint16), ("partBits", ctypes.c_uint32 * 5)]

class XModel(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_uint32),
        ("numBones", ctypes.c_uint8), ("numRootBones", ctypes.c_uint8), ("numsurfs", ctypes.c_uint8), ("lodRampType", ctypes.c_uint8),
        ("boneNames", ctypes.c_uint32), ("parentList", ctypes.c_uint32), ("quats", ctypes.c_uint32), ("trans", ctypes.c_uint32),
        ("partClassification", ctypes.c_uint32), ("baseMat", ctypes.c_uint32), ("surfs", ctypes.c_uint32), ("materialHandles", ctypes.c_uint32),
        ("lodInfo", XModelLodInfo * 4), ("collSurfs", ctypes.c_uint32), ("numCollSurfs", ctypes.c_int32),
        ("contents", ctypes.c_int32), ("boneInfo", ctypes.c_uint32), ("radius", ctypes.c_float), ("mins", Vec3), ("maxs", Vec3),
        ("numLods", ctypes.c_uint16), ("collLod", ctypes.c_int16), ("himipInvSqRadii", ctypes.c_uint32),
        ("memUsage", ctypes.c_int32), ("flags", ctypes.c_uint32), ("bad", ctypes.c_bool), ("physPreset", ctypes.c_uint32),
        ("numCollmaps", ctypes.c_uint8), ("collmaps", ctypes.c_uint32), ("physConstraints", ctypes.c_uint32),
        ("lightingOriginOffset", Vec3), ("lightingOriginRange", ctypes.c_float),
    ]

assert ctypes.sizeof(WeaponAttachmentUnique) == WAU_SIZE
assert ctypes.sizeof(XModel) == XMODEL_SIZE

def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("t6raw", path)
    m = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(m); return m

def cstring(data: bytes, pos: int, maxlen: int = 256):
    end = data.find(b"\0", pos, min(len(data), pos + maxlen + 1))
    if end < 0 or end == pos: return None
    b = data[pos:end]
    if any(c < 32 or c > 126 for c in b): return None
    return b.decode("ascii")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--stream',type=Path,required=True)
    ap.add_argument('--raw-parser',type=Path,required=True)
    ap.add_argument('--roots',type=Path,required=True)
    ap.add_argument('--outdir',type=Path,required=True)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)
    data=args.stream.read_bytes(); raw=load_module(args.raw_parser); front=raw.parse_front(data)
    block_sizes=[x['bytes'] for x in front['block_sizes']]
    proof=json.loads(args.roots.read_text())
    roots=sorted([r for r in proof['weapon_variant_roots'] if r.get('status')=='exact_inline_fixed_record'],key=lambda r:r['raw_struct_offset'])
    root_offsets=[r['raw_struct_offset'] for r in roots]

    def valid_ptr(v):
        if v in (0,PTR_FOLLOWING,PTR_INSERT): return True
        q=raw.decode_zone_pointer(v,block_sizes)
        return q.get('kind')=='packed' and q.get('valid_for_declared_block_size')

    waus=[]; pos=0
    while True:
        h=data.find(b'au_',pos)
        if h<0: break
        nm=cstring(data,h)
        if not nm: pos=h+3; continue
        st=h-WAU_SIZE
        if st>=0:
            w=WeaponAttachmentUnique.from_buffer_copy(data[st:st+WAU_SIZE])
            ptr_fields=['hideTags','viewModel','viewModelAdditional','viewModelADS','worldModel','worldModelAdditional','weaponCamo','overlayMaterial','overlayMaterialLowRes','szXAnims','locationDamageMultipliers','viewFlashEffect','worldFlashEffect','tracerType','enemyTracerType']
            if w.szInternalName in (PTR_FOLLOWING,PTR_INSERT) and 0<=w.attachmentType<30 and all(valid_ptr(getattr(w,f)) for f in ptr_fields):
                i=bisect.bisect_right(root_offsets,st)-1
                if i>=0:
                    waus.append({'name_pos':h,'raw_struct_offset':st,'internal_name':nm,'attachmentType':w.attachmentType,'root':roots[i]['internal_name'],'struct':w})
        pos=h+3
    waus.sort(key=lambda x:x['raw_struct_offset'])

    grouped=defaultdict(list)
    for w in waus: grouped[w['root']].append(w)
    canonical_waus=[]; unique_table_rows=[]; slot_mismatches=[]
    for r in roots:
        group=sorted(grouped.get(r['internal_name'],[]),key=lambda x:x['raw_struct_offset'])
        if not group: continue
        uoff=group[0]['raw_struct_offset']-UNIQUE_ARRAY_BYTES
        vals=struct.unpack_from('<95I',data,uoff)
        nz=[i for i,v in enumerate(vals) if v]
        if len(nz)!=len(group) or any(vals[i] not in (PTR_FOLLOWING,PTR_INSERT) for i in nz):
            slot_mismatches.append(r['internal_name']); continue
        for slot,w in zip(nz,group):
            w['unique_slot']=slot; w['unique_table_raw_offset']=uoff; canonical_waus.append(w)
            unique_table_rows.append({'weapon_internal_name':r['internal_name'],'unique_slot':slot,'attachment_unique_internal_name':w['internal_name'],'attachment_type':w['attachmentType'],'raw_wau_struct_offset':w['raw_struct_offset'],'raw_unique_table_offset':uoff})

    def parse_xmodel_at(st):
        if st<0 or st+XMODEL_SIZE>=len(data): return None
        x=XModel.from_buffer_copy(data[st:st+XMODEL_SIZE])
        if x.name not in (PTR_FOLLOWING,PTR_INSERT): return None
        if not (1<=x.numBones<=200 and 1<=x.numRootBones<=x.numBones and 1<=x.numsurfs<=100 and x.lodRampType in (0,1) and 1<=x.numLods<=4): return None
        ptrs=['boneNames','parentList','quats','trans','partClassification','baseMat','surfs','materialHandles','collSurfs','boneInfo','himipInvSqRadii','physPreset','collmaps','physConstraints']
        if not all(valid_ptr(getattr(x,f)) for f in ptrs): return None
        nm=cstring(data,st+XMODEL_SIZE)
        if not nm: return None
        return {'raw_struct_offset':st,'raw_name_offset':st+XMODEL_SIZE,'name':nm,'numBones':x.numBones,'numRootBones':x.numRootBones,'numsurfs':x.numsurfs,'numLods':x.numLods}

    inline_models=[]; inline_misses=[]
    for idx,wrec in enumerate(canonical_waus):
        w=wrec['struct']; expected=[f for f in MODEL_FIELDS if getattr(w,f) in (PTR_FOLLOWING,PTR_INSERT)]
        if not expected: continue
        nextst=canonical_waus[idx+1]['raw_struct_offset'] if idx+1<len(canonical_waus) else min(len(data),wrec['raw_struct_offset']+2_000_000)
        found=[]; p=wrec['name_pos']+len(wrec['internal_name'])+1
        while len(found)<len(expected) and p<nextst:
            h=data.find(b'\xff\xff\xff\xff',p,nextst)
            if h<0: break
            xm=parse_xmodel_at(h)
            if xm: found.append(xm)
            p=h+1
        if len(found)!=len(expected):
            inline_misses.append({'attachment_unique':wrec['internal_name'],'expected_fields':expected,'found':len(found)})
            continue
        for role,xm in zip(expected,found):
            inline_models.append({'weapon':wrec['root'],'unique_slot':wrec['unique_slot'],'attachment_unique':wrec['internal_name'],'model_role':role,**xm})

    packed_assets=sorted([a for a in front['assets'] if a['type']=='XMODEL' and a['header'].get('kind')=='packed'],key=lambda a:a['header']['offset'])
    inline_models.sort(key=lambda x:x['raw_struct_offset'])
    if len(inline_models)!=len(packed_assets):
        raise RuntimeError(f'inline WAU XModels {len(inline_models)} != packed XMODEL headers {len(packed_assets)}')

    ptr_to_model={}; model_asset_rows=[]; rank_deltas=[]
    for rank,(xm,a) in enumerate(zip(inline_models,packed_assets)):
        rawptr=int(a['header_raw'],16); ptr_to_model[rawptr]=xm['name']; delta=xm['raw_struct_offset']-a['header']['offset']; rank_deltas.append(delta)
        model_asset_rows.append({'rank':rank,'xasset_index':a['index'],'xasset_header_raw':a['header_raw'],'virtual_offset':a['header']['offset'],'model_name':xm['name'],'raw_xmodel_struct_offset':xm['raw_struct_offset'],'raw_minus_virtual_offset':delta,'num_bones':xm['numBones'],'num_root_bones':xm['numRootBones'],'num_surfaces':xm['numsurfs'],'num_lods':xm['numLods']})

    inline_by_au_role={(x['attachment_unique'],x['model_role']):x for x in inline_models}
    asset_by_name={r['model_name']:r for r in model_asset_rows}
    model_edges=[]; unresolved=[]; packed_ref_count=0; inline_ref_count=0
    for wrec in canonical_waus:
        w=wrec['struct']
        for role in MODEL_FIELDS:
            v=getattr(w,role)
            if v==0: continue
            if v in (PTR_FOLLOWING,PTR_INSERT):
                rec=inline_by_au_role.get((wrec['internal_name'],role))
                if not rec:
                    unresolved.append((wrec['internal_name'],role,f'0x{v:08X}')); continue
                asset=asset_by_name[rec['name']]; inline_ref_count+=1
                model_edges.append({'weapon_internal_name':wrec['root'],'unique_slot':wrec['unique_slot'],'attachment_unique_internal_name':wrec['internal_name'],'attachment_type':wrec['attachmentType'],'model_role':role,'reference_kind':'inline','xasset_header_raw':asset['xasset_header_raw'],'virtual_offset':asset['virtual_offset'],'model_name':rec['name'],'raw_wau_struct_offset':wrec['raw_struct_offset'],'raw_xmodel_struct_offset':rec['raw_struct_offset']})
            else:
                packed_ref_count+=1; nm=ptr_to_model.get(v)
                if not nm:
                    unresolved.append((wrec['internal_name'],role,f'0x{v:08X}')); continue
                asset=asset_by_name[nm]
                model_edges.append({'weapon_internal_name':wrec['root'],'unique_slot':wrec['unique_slot'],'attachment_unique_internal_name':wrec['internal_name'],'attachment_type':wrec['attachmentType'],'model_role':role,'reference_kind':'packed_exact_xasset_pointer','xasset_header_raw':f'0x{v:08X}','virtual_offset':asset['virtual_offset'],'model_name':nm,'raw_wau_struct_offset':wrec['raw_struct_offset'],'raw_xmodel_struct_offset':asset['raw_xmodel_struct_offset']})

    def write_csv(name,rows):
        if not rows: return
        with (args.outdir/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    write_csv('common_mp_player_attachment_uniques.csv',unique_table_rows)
    write_csv('common_mp_attachment_xmodel_assets.csv',model_asset_rows)
    write_csv('common_mp_player_attachment_unique_models.csv',model_edges)

    mp7=[r for r in model_edges if r['weapon_internal_name']=='mp7_mp']
    manifest={
        'stage':'18D WeaponAttachmentUnique -> XModel proof',
        'authority':'raw expanded common_mp XFile; no OpenAssetTools executable',
        'struct_sizes_pc32':{'WeaponAttachmentUnique':WAU_SIZE,'WeaponAttachmentUnique_pointer_slots':UNIQUE_SLOTS,'XModel':XMODEL_SIZE},
        'canonical_player_roots_input':len(roots),
        'attachment_capable_roots_with_unique_tables':len({r['weapon_internal_name'] for r in unique_table_rows}),
        'unique_table_slot_mismatches':slot_mismatches,
        'attachment_unique_records':len(unique_table_rows),
        'inline_xmodel_fields_expected':len(inline_models),
        'packed_xmodel_xasset_headers':len(packed_assets),
        'inline_xmodel_parse_misses':inline_misses,
        'exact_xmodel_identities':len(model_asset_rows),
        'attachment_unique_model_edges':len(model_edges),
        'inline_model_edges':inline_ref_count,
        'packed_model_edges':packed_ref_count,
        'unresolved_model_edges':len(unresolved),
        'unresolved':unresolved,
        'load_order_bijection':{
            'method':'112 raw WAU-child XModel definitions ordered by serialized creation position paired to the 112 packed XMODEL XAsset headers ordered by decoded VIRTUAL destination. Later packed WAU model fields resolve by exact header-pointer identity.',
            'raw_minus_virtual_min':min(rank_deltas),
            'raw_minus_virtual_max':max(rank_deltas),
            'small_negative_step_count':sum(b<a for a,b in zip(rank_deltas,rank_deltas[1:])),
        },
        'mp7_model_edges':mp7,
    }
    (args.outdir/'attachment_unique_xmodel_proof.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='mp7_model_edges'},indent=2))

if __name__=='__main__': main()
