#!/usr/bin/env python3
"""Diagnose strict XModel catalog gaps in current retail mp_carrier.

This is evidence-only. It does not promote relaxed headers. A near-header is
reported only when its name resolves exactly from the proven map StringTable (or
is an exact FOLLOWING string), its pointer fields decode as legal zone pointers,
and its scalar fields are structurally bounded. Every difference from the v6
strict validator is emitted as an explicit rejection reason.
"""
from __future__ import annotations

import argparse, hashlib, json, math, struct
from pathlib import Path

from t6_clipmap_normalize_v5 import ASSET_TYPE_XMODEL, parse_top_level_xasset_table
from t6_clipmap_normalize_v6 import (
    XMODEL_FIXED_SIZE, PTR_FOLLOWING, PTR_INSERT,
    walk_map_prefix_stringtable, parse_xmodel_fixed,
)


def u32(d,o): return struct.unpack_from('<I',d,o)[0]
def i32(d,o): return struct.unpack_from('<i',d,o)[0]
def packed(raw):
    if raw in (0,PTR_FOLLOWING,PTR_INSERT): return None
    enc=(raw-1)&0xffffffff
    return enc>>29, enc&0x1fffffff
def valid_ptr(raw):
    if raw in (0,PTR_FOLLOWING,PTR_INSERT): return True
    p=packed(raw)
    return p is not None and 0 <= p[0] < 8

def cstring(d,pos,max_len=300):
    end=d.find(b'\0',pos,min(len(d),pos+max_len+1))
    if end < 0 or end == pos: return None
    b=d[pos:end]
    if any(c < 32 or c >= 127 for c in b): return None
    return b.decode('ascii')

def resolved_name(d,pos,logical):
    raw=u32(d,pos)
    if raw == PTR_FOLLOWING:
        return cstring(d,pos+XMODEL_FIXED_SIZE), 'following'
    p=packed(raw)
    if p and p[0] == 5:
        name=logical.get(p[1])
        if isinstance(name,str) and name and all(32 <= ord(c) < 127 for c in name):
            return name, 'packed_virtual_stringtable_alias'
    return None, None

def rejection_reasons(d,pos,logical):
    reasons=[]
    name,name_source=resolved_name(d,pos,logical)
    if name is None: reasons.append('name_not_exactly_resolved')
    nb,nr,ns,ramp=struct.unpack_from('<BBBB',d,pos+4)
    if nb < 1: reasons.append('numBones_lt_1')
    if nr < 1: reasons.append('numRootBones_lt_1')
    if nr > nb: reasons.append('numRootBones_gt_numBones')
    if ns < 1: reasons.append('numSurfs_lt_1')
    if ramp not in (0,1): reasons.append('lodRampType_not_0_or_1')
    ptr_offsets=(8,12,16,20,24,28,32,36,152,164,200,216,224,228)
    bad_ptr=[off for off in ptr_offsets if not valid_ptr(u32(d,pos+off))]
    if bad_ptr: reasons.append('invalid_pointer_encoding:'+','.join(map(str,bad_ptr)))
    for off,label in ((8,'boneNames'),(24,'partClassification'),(28,'baseMat'),(32,'surfs'),(36,'materialHandles'),(164,'boneInfo')):
        if u32(d,pos+off)==0: reasons.append(label+'_null')
    if nb-nr > 0:
        for off,label in ((12,'parentList'),(16,'quats'),(20,'trans')):
            if u32(d,pos+off)==0: reasons.append(label+'_null_for_nonroots')
    ncs=i32(d,pos+156)
    if not (0 <= ncs <= 100): reasons.append('numCollSurfs_out_of_range')
    if ncs and u32(d,pos+152)==0: reasons.append('collSurfs_null_with_count')
    radius=struct.unpack_from('<f',d,pos+168)[0]
    mins=struct.unpack_from('<3f',d,pos+172); maxs=struct.unpack_from('<3f',d,pos+184)
    nl,cl=struct.unpack_from('<Hh',d,pos+196)
    bad=d[pos+212]; ncm=d[pos+220]
    light=struct.unpack_from('<3f',d,pos+232); lrange=struct.unpack_from('<f',d,pos+244)[0]
    vals=(radius,*mins,*maxs,*light,lrange)
    if not all(math.isfinite(x) for x in vals): reasons.append('nonfinite_scalar')
    if math.isfinite(radius) and radius <= 0: reasons.append('radius_nonpositive')
    if math.isfinite(lrange) and lrange < 0: reasons.append('lightingOriginRange_negative')
    if all(math.isfinite(x) for x in (*mins,*maxs)) and any(mins[i] > maxs[i] for i in range(3)): reasons.append('bounds_inverted')
    if not (1 <= nl <= 4): reasons.append('numLods_not_1_to_4')
    if not (-1 <= cl <= 3): reasons.append('collLod_out_of_range')
    if bad not in (0,1): reasons.append('bad_flag_not_bool')
    if ncm > 32: reasons.append('numCollmaps_gt_32')
    if ncm and u32(d,pos+224)==0: reasons.append('collmaps_null_with_count')
    expected=0; prev=-1.0
    for i in range(4):
        b=pos+40+i*28
        dist=struct.unpack_from('<f',d,b)[0]
        n,sidx=struct.unpack_from('<HH',d,b+4)
        if not math.isfinite(dist) or dist < 0: reasons.append(f'lod{i}_invalid_dist')
        if i < nl and 1 <= nl <= 4:
            if n < 1: reasons.append(f'lod{i}_numSurfs_lt_1')
            if sidx != expected: reasons.append(f'lod{i}_surfIndex_not_contiguous')
            if math.isfinite(dist) and dist <= 0: reasons.append(f'lod{i}_dist_nonpositive')
            if math.isfinite(dist) and dist < prev: reasons.append(f'lod{i}_dist_decreased')
            expected += n; prev=dist
        else:
            if n != 0: reasons.append(f'lod{i}_inactive_numSurfs_nonzero')
            if sidx != 0: reasons.append(f'lod{i}_inactive_surfIndex_nonzero')
    if 1 <= nl <= 4 and expected != ns: reasons.append('lod_surface_sum_ne_numSurfs')
    return name,name_source,reasons,{
        'numBones':nb,'numRootBones':nr,'numSurfs':ns,'lodRampType':ramp,
        'numLods':nl,'collLod':cl,'numCollSurfs':ncs,'radius':radius,
        'numCollmaps':ncm,'namePointerRaw':u32(d,pos),
    }

def near_candidate(d,pos,logical):
    if pos < 0 or pos+XMODEL_FIXED_SIZE > len(d): return None
    name,source=resolved_name(d,pos,logical)
    if name is None: return None
    nb,nr,ns,ramp=struct.unpack_from('<BBBB',d,pos+4)
    if nb > 240 or nr > nb or ns > 160 or ramp not in (0,1): return None
    if any(not valid_ptr(u32(d,pos+off)) for off in (8,12,16,20,24,28,32,36,152,164,200,216,224,228)): return None
    ncs=i32(d,pos+156); nl,cl=struct.unpack_from('<Hh',d,pos+196)
    if not (-1 <= ncs <= 256 and 0 <= nl <= 4 and -1 <= cl <= 3): return None
    radius=struct.unpack_from('<f',d,pos+168)[0]
    mins=struct.unpack_from('<3f',d,pos+172); maxs=struct.unpack_from('<3f',d,pos+184)
    lrange=struct.unpack_from('<f',d,pos+244)[0]
    if not all(math.isfinite(x) for x in (radius,*mins,*maxs,lrange)): return None
    return name,source

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('expanded',type=Path); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    d=a.expanded.read_bytes(); table=parse_top_level_xasset_table(d); prefix=walk_map_prefix_stringtable(d,table); logical=prefix['logicalToText']
    xindices=[i for i,e in enumerate(table['entries']) if e['type']==ASSET_TYPE_XMODEL]
    strict=[]; near=[]
    pos=prefix['sourceEnd']; limit=len(d)-XMODEL_FIXED_SIZE
    while pos <= limit:
        # Only parse positions whose leading pointer can resolve as an exact model name.
        rp=u32(d,pos)
        plausible = rp==PTR_FOLLOWING or ((lambda p: p is not None and p[0]==5 and p[1] in logical)(packed(rp)))
        if plausible:
            rec=parse_xmodel_fixed(d,pos,logical)
            if rec is not None:
                strict.append(rec); pos += XMODEL_FIXED_SIZE; continue
            nc=near_candidate(d,pos,logical)
            if nc is not None:
                name,source,reasons,scalars=rejection_reasons(d,pos,logical)
                near.append({'fixedSourceStart':pos,'name':name,'nameSource':source,'strictRejectionReasons':reasons,'scalars':scalars})
        pos += 1
    strict_names={r['name'] for r in strict}
    near_only=[r for r in near if r['name'] not in strict_names]
    out={
      'format':'t6-mp-carrier-xmodel-catalog-gap-probe-v1',
      'source':{'expandedBytes':len(d),'expandedSha256':hashlib.sha256(d).hexdigest()},
      'expectedTopLevelXModelCount':len(xindices),
      'strictRecognizedCount':len(strict),
      'strictGapCount':len(xindices)-len(strict),
      'strictFirstLast':[strict[0]['name'] if strict else None,strict[-1]['name'] if strict else None],
      'nearCandidateCount':len(near),
      'nearOnlyCount':len(near_only),
      'nearOnly':near_only,
      'seal6Strict':[dict(r, strictOrdinal=i) for i,r in enumerate(strict) if 'seal6' in r['name'].lower()],
      'seal6NearOnly':[r for r in near_only if 'seal6' in (r['name'] or '').lower()],
      'stringTableProof':prefix['assets']['stringTable'],
      'proofBoundary':'Diagnostic only. No relaxed header is promoted. Near candidates require exact StringTable/FOLLOWING name resolution, legal zone-pointer encodings, bounded core counts, and finite fixed scalars. Rejection reasons are the exact differences from the current strict v6 XModel validator.'
    }
    a.out.parent.mkdir(parents=True,exist_ok=True); text=json.dumps(out,indent=2,sort_keys=True)+'\n'; a.out.write_text(text)
    print(json.dumps({'expected':len(xindices),'strict':len(strict),'gap':len(xindices)-len(strict),'nearOnly':len(near_only),'seal6Strict':[(x['strictOrdinal'],x['name'],x['fixedSourceStart']) for x in out['seal6Strict']],'seal6NearOnly':[(x['name'],x['fixedSourceStart'],x['strictRejectionReasons']) for x in out['seal6NearOnly']]},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
