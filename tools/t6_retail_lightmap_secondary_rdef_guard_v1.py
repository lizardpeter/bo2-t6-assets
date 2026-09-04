#!/usr/bin/env python3
"""Fail-closed retained-retail RDEF guard for T6 lightmapSamplerSecondary.

Scans every strictly valid inline DXBC container discoverable in the five pinned
expanded retail worlds. Any shader reflecting lightmapSamplerSecondary must
contain exactly one TEXTURE and one SAMPLER RDEF entry, each at bind point 13
with bind count 1. This is deliberately broader than the 173 slot-4 layered
shader population used by the directional-lightmap arithmetic proof.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

SOURCES = {
    'mp_nuketown_2020': ('mp/mp_nuketown_2020.expanded.bin', '7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'),
    'mp_raid': ('mp/mp_raid.expanded.bin', 'd3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8'),
    'mp_hijacked': ('mp/mp_hijacked.expanded.bin', '8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b'),
    'zm_prison': ('zm_prison.expanded.bin', 'e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487'),
    'zm_tomb': ('zm_tomb.expanded.bin', '4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219'),
}
INPUT_TEXTURE=2
INPUT_SAMPLER=3
DIM_UNKNOWN=0
DIM_TEXTURE2D=4
NAME='lightmapSamplerSecondary'

def jhash(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',',':'), allow_nan=False).encode()).hexdigest()

def u32(b,o):
    if o < 0 or o+4 > len(b): raise ValueError('u32 outside range')
    return struct.unpack_from('<I',b,o)[0]

def cstr(b,o):
    if o < 0 or o >= len(b): raise ValueError('string offset outside range')
    e=b.find(b'\0',o)
    if e < 0: raise ValueError('unterminated string')
    return b[o:e].decode('utf-8')

def rdef_resources(blob):
    if len(blob)<32 or blob[:4]!=b'DXBC': raise ValueError('missing DXBC')
    total=u32(blob,24); count=u32(blob,28)
    if total!=len(blob) or 32+4*count>len(blob): raise ValueError('DXBC header mismatch')
    offsets=[u32(blob,32+4*i) for i in range(count)]
    if len(offsets)!=len(set(offsets)): raise ValueError('duplicate chunk offsets')
    rdef=None; occupied=[]
    for off in offsets:
        if off<32+4*count or off+8>len(blob): raise ValueError('chunk offset outside DXBC')
        size=u32(blob,off+4); end=off+8+size
        if end>len(blob): raise ValueError('chunk outside DXBC')
        for a,b in occupied:
            if not (end<=a or off>=b): raise ValueError('overlapping DXBC chunks')
        occupied.append((off,end))
        if blob[off:off+4]==b'RDEF':
            if rdef is not None: raise ValueError('multiple RDEF chunks')
            rdef=blob[off+8:end]
    if rdef is None or len(rdef)<28: raise ValueError('missing/malformed RDEF')
    rc,ro=struct.unpack_from('<II',rdef,8); minor=rdef[16]; major=rdef[17]
    es=40 if (major,minor)>=(5,1) else 32
    if ro+rc*es>len(rdef): raise ValueError('RDEF table outside chunk')
    out=[]
    for i in range(rc):
        off=ro+i*es
        no,it,rt,dim,ns,bp,bc,flags=struct.unpack_from('<IIIIIIII',rdef,off)
        out.append({'name':cstr(rdef,no),'inputType':it,'dimension':dim,'bindPoint':bp,'bindCount':bc})
    return out

def scan_map(path):
    data=path.read_bytes(); pos=0; unique={}
    while True:
        i=data.find(b'DXBC',pos)
        if i<0: break
        pos=i+4
        if i+32>len(data): continue
        try:
            total=u32(data,i+24)
            if total<32 or i+total>len(data): continue
            blob=data[i:i+total]; resources=rdef_resources(blob)
        except (ValueError,UnicodeDecodeError,struct.error):
            continue
        hh=hashlib.sha256(blob).hexdigest()
        old=unique.setdefault(hh,(blob,resources))
        if old[0]!=blob: raise ValueError('SHA collision with differing DXBC bytes')
    secondary={}
    for hh,(blob,resources) in unique.items():
        rr=[x for x in resources if x['name']==NAME]
        if rr: secondary[hh]=(len(blob),rr)
    return unique,secondary

def build(root:Path):
    all_secondary={}; maps=[]
    for name,(rel,expected_sha) in SOURCES.items():
        path=root/rel; data_sha=hashlib.sha256(path.read_bytes()).hexdigest()
        if data_sha!=expected_sha: raise ValueError(f'{name}: expanded SHA mismatch {data_sha}')
        valid,secondary=scan_map(path)
        for hh,(size,rr) in secondary.items():
            if hh in all_secondary and all_secondary[hh][:2]!=(size,rr): raise ValueError('secondary shader collision')
            if hh not in all_secondary: all_secondary[hh]=(size,rr,set())
            all_secondary[hh][2].add(name)
        maps.append({'map':name,'validDxbcCount':len(valid),'secondaryShaderCount':len(secondary)})
    rows=[]
    for hh,(size,rr,names) in sorted(all_secondary.items()):
        tex=[x for x in rr if x['inputType']==INPUT_TEXTURE]
        sam=[x for x in rr if x['inputType']==INPUT_SAMPLER]
        if len(rr)!=2 or len(tex)!=1 or len(sam)!=1: raise ValueError(f'{hh}: secondary RDEF entry multiplicity')
        if tex[0]['dimension']!=DIM_TEXTURE2D or sam[0]['dimension']!=DIM_UNKNOWN: raise ValueError(f'{hh}: secondary RDEF dimensions')
        if tex[0]['bindPoint']!=13 or tex[0]['bindCount']!=1: raise ValueError(f'{hh}: secondary texture binding')
        if sam[0]['bindPoint']!=13 or sam[0]['bindCount']!=1: raise ValueError(f'{hh}: secondary sampler binding')
        rows.append({'sha256':hh,'bytes':size,'maps':sorted(names)})
    if len(rows)!=4531: raise ValueError(f'unique secondary shader count {len(rows)} != 4531')
    expected_maps={
        'mp_nuketown_2020':(1972,1185),'mp_raid':(3064,1961),'mp_hijacked':(2299,1380),
        'zm_prison':(3920,2522),'zm_tomb':(2839,1061)}
    for m in maps:
        if (m['validDxbcCount'],m['secondaryShaderCount'])!=expected_maps[m['map']]: raise ValueError(f"{m['map']}: census mismatch")
    summary={'retainedMapCount':5,'uniqueSecondaryShaderCount':4531,'bindingFailureCount':0,
             'textureBindPoint':13,'textureBindCount':1,'textureDimension':'TEXTURE2D',
             'samplerBindPoint':13,'samplerBindCount':1,'samplerDimension':'UNKNOWN',
             'shaderRowsSha256':jhash(rows)}
    return {'format':'t6-retail-lightmap-secondary-rdef-guard-v1',
            'producer':'tools/t6_retail_lightmap_secondary_rdef_guard_v1.py',
            'sources':{n:{'file':rel,'sha256':sha} for n,(rel,sha) in SOURCES.items()},
            'mapCoverage':maps,
            'binding':{'name':NAME,'texture':{'inputType':'TEXTURE','dimension':'TEXTURE2D','bindPoint':13,'bindCount':1},
                       'sampler':{'inputType':'SAMPLER','dimension':'UNKNOWN','bindPoint':13,'bindCount':1}},
            'summary':summary,
            'proofBoundary':'Strict retained-byte DXBC/RDEF guard over every valid embedded shader discovered in the five pinned expanded retail worlds. Every unique shader reflecting lightmapSamplerSecondary must expose exactly one TEXTURE2D and one SAMPLER entry at bind point 13 with bind count 1. This is intentionally broader than the 173 slot-4 layered shaders and therefore fail-closes the reflected resource identity used by the directional-lightmap proof. RDEF reflection alone does not prove shader arithmetic.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    d=build(a.root);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__': main()
