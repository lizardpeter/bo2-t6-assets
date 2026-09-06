#!/usr/bin/env python3
import importlib.util, struct
from pathlib import Path

P=Path(__file__).with_name('t6_weapon_xasset_structural_probe_v1.py')
s=importlib.util.spec_from_file_location('probe',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)

class Raw:
    @staticmethod
    def decode_zone_pointer(v, blocks):
        if v==0:return {'kind':'null','valid_for_declared_block_size':True}
        if v==0xffffffff:return {'kind':'following','valid_for_declared_block_size':True}
        if v==0xfffffffe:return {'kind':'insert','valid_for_declared_block_size':True}
        e=(v-1)&0xffffffff; b=e>>29; o=e&0x1fffffff
        return {'kind':'packed','block':b,'offset':o,'valid_for_declared_block_size': b<len(blocks) and o<blocks[b]}
    @staticmethod
    def parse_front(data):
        # synthetic fixed front: one weapon row, body at 72
        header=struct.unpack_from('<I',data,68)[0]
        return {'_blocks':[4096]*8,'asset_count':1,'asset_body_stream_raw_offset':72,
                'assets':[{'index':0,'type_index':25,'type':'WEAPON','header_raw_u32':header,'header':Raw.decode_zone_pointer(header,[4096]*8)}]}

def make(name_following=True, duplicate=False):
    body=bytearray(72+716+128)
    struct.pack_into('<I',body,68,0xffffffff)
    st=72
    struct.pack_into('<i',body,st+4,1)
    struct.pack_into('<i',body,st+468,0)
    # bools already zero
    if name_following:
        struct.pack_into('<I',body,st,0xffffffff)
    else:
        struct.pack_into('<I',body,st,101) # packed TEMP offset 100
    struct.pack_into('<I',body,st+8,0xffffffff)
    struct.pack_into('<I',body,st+12,201)
    cur=st+716
    if name_following:
        nm=b'mp7_mp\0';body[cur:cur+len(nm)]=nm;cur+=len(nm)
    # WeaponDef enum prefix: pat=handleclip(16), wt=bullet(0), wc=smg(2), pen=3, impact=4, inv=5, ft=Full Auto(0), clip=7
    struct.pack_into('<8i',body,cur+24,16,0,2,3,4,5,0,7)
    if duplicate:
        # append a second valid WVD candidate after current buffer extension
        st2=len(body);body.extend(b'\0'*(716+128));struct.pack_into('<I',body,st2,0xffffffff);struct.pack_into('<i',body,st2+4,1);struct.pack_into('<I',body,st2+8,0xffffffff);struct.pack_into('<I',body,st2+12,301);struct.pack_into('<i',body,st2+468,0)
        nm=b'other_mp\0';c2=st2+716;body[c2:c2+len(nm)]=nm;struct.pack_into('<8i',body,c2+len(nm)+24,1,0,2,0,0,0,0,0)
    return bytes(body)

x=m.probe(make(True),Raw)
assert x['summary']['bindableStructuralCandidates']==1 and x['summary']['exactCardinalityBindings']==1 and x['summary']['exactInternalNames']==1 and x['summary']['exactDirectSelectors']==1,x['summary']
b=x['bindings'][0]['weaponVariantDef'];assert b['internalName']=='mp7_mp';assert b['selector']['selector']=={'weaponclass':'smg','playerAnimType':'handleclip'}

y=m.probe(make(False),Raw)
assert y['summary']['exactCardinalityBindings']==1 and y['summary']['exactInternalNames']==0 and y['summary']['exactDirectSelectors']==1,y['summary']
b=y['bindings'][0]['weaponVariantDef'];assert b['internalNameStatus']=='unresolved-packed-name-pointer';assert b['internalNamePointer']['decoded']['block']==0 and b['internalNamePointer']['decoded']['offset']==100

z=m.probe(make(True,True),Raw)
assert z['summary']['structuralCandidates'] > z['summary']['bindableStructuralCandidates'],z['summary']
assert z['summary']['bindableStructuralCandidates']==2 and z['summary']['exactCardinalityBindings']==0,z['summary']

# A packed top-level WEAPON header means its body is not inline here; the probe
# must not cardinality-bind even if coincidental WVD-shaped bytes exist later.
class PackedHeaderRaw(Raw):
    @staticmethod
    def parse_front(data):
        return {'_blocks':[4096]*8,'asset_count':1,'asset_body_stream_raw_offset':72,
                'assets':[{'index':0,'type_index':25,'type':'WEAPON','header_raw_u32':101,
                           'header':Raw.decode_zone_pointer(101,[4096]*8)}]}

w=m.probe(make(True),PackedHeaderRaw)
assert w['summary']['weaponAssets']==1 and w['summary']['exactCardinalityBindings']==0,w['summary']
assert w['front']['packedWeaponAssetCount']==1,w['front']

print('t6_weapon_xasset_structural_probe_v1: PASS')
