#!/usr/bin/env python3
"""Apply exact T6 material alpha/cull presentation state to a Nuketown GLB.

The source of truth is the retained T6 Material.stateBitsEntry[36] map and the
serialized GfxStateBitsTable in the pinned expanded FastFile stream.

Primary render state selection is fail-closed:
  * Prefer the T6 lit-technique range [TECHNIQUE_LIT_BEGIN=4, TECHNIQUE_LIT_END=26).
    Every present lit technique must point at the same GfxStateBits entry.
  * If a material has no lit technique, UNLIT (2) and EMISSIVE (3) must both be
    present and point at the same state entry.

The chosen state is mapped to glTF presentation as follows:
  * nontrivial blending -> alphaMode=BLEND
  * otherwise alpha test enabled -> alphaMode=MASK
      GFXS_ALPHA_TEST_GE_128 -> alphaCutoff=0.5
      GFXS_ALPHA_TEST_GT_0   -> alphaCutoff=1/255
  * otherwise -> OPAQUE
  * GFXS_CULL_NONE -> doubleSided=true; otherwise false

This stage does not infer material identities or texture identities.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, struct, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import t6_nuketown_static_material_catalog_v1 as cat

TECHNIQUE_UNLIT=2
TECHNIQUE_EMISSIVE=3
TECHNIQUE_LIT_BEGIN=4
TECHNIQUE_LIT_END=26
FOLLOWING=0xFFFFFFFF

GFXS_BLEND_ZERO=1
GFXS_BLEND_ONE=2
GFXS_BLENDOP_DISABLED=0
GFXS_CULL_NONE=1
GFXS_CULL_BACK=2
GFXS_CULL_FRONT=3

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def read_glb(path:Path):
    b=path.read_bytes();magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b):raise ValueError('invalid GLB2')
    o=12;js=None;bins=[]
    while o<total:
        ln,typ=struct.unpack_from('<I4s',b,o);o+=8;ch=b[o:o+ln];o+=ln
        if typ==b'JSON':js=json.loads(ch)
        elif typ==b'BIN\0':bins.append(ch)
    if js is None or len(bins)!=1:raise ValueError('expected one JSON and one BIN')
    return js,bytearray(bins[0])

def write_glb(path:Path,js,binbuf:bytearray):
    js.setdefault('buffers',[{}])[0]['byteLength']=len(binbuf)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    jb+=b' '*((4-len(jb)%4)%4)
    bb=bytes(binbuf);bb+=b'\0'*((4-len(bb)%4)%4)
    total=12+8+len(jb)+8+len(bb)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total))
    out+=struct.pack('<I4s',len(jb),b'JSON')+jb
    out+=struct.pack('<I4s',len(bb),b'BIN\0')+bb
    path.write_bytes(out)

def choose_state_entry(data:bytes,row:dict)->tuple[int,str,list[int]]:
    s=row['rawFixedStart'];count=row['stateBitsCount']
    entries=list(data[s+48:s+84])
    lit=[x for x in entries[TECHNIQUE_LIT_BEGIN:TECHNIQUE_LIT_END] if x!=255]
    for x in lit:
        if x>=count:raise ValueError(f"{row['name']}: lit state entry {x} >= stateBitsCount {count}")
    if lit:
        uniq=sorted(set(lit))
        if len(uniq)!=1:raise ValueError(f"{row['name']}: lit techniques disagree on state bits {uniq}")
        return uniq[0],'lit-technique-consensus',entries
    u=entries[TECHNIQUE_UNLIT];e=entries[TECHNIQUE_EMISSIVE]
    if u==255 or e==255 or u>=count or e>=count or u!=e:
        raise ValueError(f"{row['name']}: no lit state and UNLIT/EMISSIVE do not agree ({u},{e})")
    return u,'unlit-emissive-consensus',entries

def state_table_start(data:bytes,row:dict)->int:
    s=row['rawFixedStart']
    state_ptr=struct.unpack_from('<I',data,s+104)[0]
    const_ptr=struct.unpack_from('<I',data,s+100)[0]
    if row['stateBitsCount'] and state_ptr!=FOLLOWING:
        raise ValueError(f"{row['name']}: stateBitsTable is not FOLLOWING: 0x{state_ptr:08X}")
    if row['constantCount'] and const_ptr!=FOLLOWING:
        raise ValueError(f"{row['name']}: constantTable is not FOLLOWING: 0x{const_ptr:08X}")
    if row['textureCount']:
        p=row.get('rawAfterTextureImages')
        if p is None:raise ValueError(f"{row['name']}: no rawAfterTextureImages")
    else:
        _,p=cat.cstring(data,s+cat.MAT_SIZE)
    p += row['constantCount']*32
    return p

def decode_state(w0:int,w1:int)->dict:
    src=w0&0xF;dst=(w0>>4)&0xF;op=(w0>>8)&0x7
    at_disabled=(w0>>11)&1;at_mode=(w0>>12)&1;cull=(w0>>14)&0x3
    srca=(w0>>16)&0xF;dsta=(w0>>20)&0xF;opa=(w0>>24)&0x7
    nontrivial_blend=(op!=GFXS_BLENDOP_DISABLED) and not (src==GFXS_BLEND_ONE and dst==GFXS_BLEND_ZERO)
    if nontrivial_blend:
        alpha_mode='BLEND';cutoff=None;reason='nontrivial-retail-blend'
    elif not at_disabled:
        alpha_mode='MASK';cutoff=0.5 if at_mode else (1.0/255.0);reason='retail-alpha-test-ge128' if at_mode else 'retail-alpha-test-gt0'
    else:
        alpha_mode='OPAQUE';cutoff=None;reason='retail-alpha-test-disabled-and-no-blend'
    if cull not in (GFXS_CULL_NONE,GFXS_CULL_BACK,GFXS_CULL_FRONT):
        raise ValueError(f'invalid cullFace {cull}')
    return {
        'loadBits0':w0,'loadBits1':w1,'srcBlendRgb':src,'dstBlendRgb':dst,'blendOpRgb':op,
        'alphaTestDisabled':bool(at_disabled),'alphaTestMode':at_mode,'cullFace':cull,
        'srcBlendAlpha':srca,'dstBlendAlpha':dsta,'blendOpAlpha':opa,
        'alphaMode':alpha_mode,'alphaCutoff':cutoff,'doubleSided':cull==GFXS_CULL_NONE,'reason':reason,
    }

def build(inp:Path,stream:Path,out:Path,manifest:Path):
    data=stream.read_bytes();js,binbuf=read_glb(inp);mats=js.get('materials',[])
    rows=[];counts=collections.Counter();changes=collections.Counter();unresolved=[]
    for i,m in enumerate(mats):
        name=m.get('name')
        row=cat.material_row(data,name)
        if row.get('status')!='located' or not row.get('stateBitsCount'):
            unresolved.append({'materialIndex':i,'material':name,'status':row.get('status'),'stateBitsCount':row.get('stateBitsCount')})
            continue
        idx,selection,entries=choose_state_entry(data,row)
        p=state_table_start(data,row)
        end=p+20*row['stateBitsCount']
        if end>len(data):raise ValueError(f'{name}: state table truncated')
        for si in range(row['stateBitsCount']):
            q=p+20*si
            if data[q+8:q+20]!=b'\0'*12:
                raise ValueError(f'{name}: GfxStateBits runtime pointer tail is not zero at row {si}')
        q=p+20*idx;w0,w1=struct.unpack_from('<II',data,q);st=decode_state(w0,w1)
        old_alpha=m.get('alphaMode','OPAQUE');old_cut=m.get('alphaCutoff');old_double=bool(m.get('doubleSided',False))
        new_alpha=st['alphaMode'];new_double=st['doubleSided']
        if new_alpha=='OPAQUE':
            m.pop('alphaMode',None);m.pop('alphaCutoff',None)
        elif new_alpha=='BLEND':
            m['alphaMode']='BLEND';m.pop('alphaCutoff',None)
        else:
            m['alphaMode']='MASK';m['alphaCutoff']=st['alphaCutoff']
        if new_double:m['doubleSided']=True
        else:m.pop('doubleSided',None)
        if old_alpha!=new_alpha:changes['alphaMode']+=1
        if (old_cut if old_alpha=='MASK' else None)!=(st['alphaCutoff'] if new_alpha=='MASK' else None):changes['alphaCutoff']+=1
        if old_double!=new_double:changes['doubleSided']+=1
        counts[(new_alpha,'cullNone' if new_double else 'culled')]+=1
        m.setdefault('extras',{}).setdefault('T6',{})['retailRenderStateV1']={
            'source':'Material.stateBitsEntry + serialized GfxStateBits.loadBits',
            'selection':selection,'stateBitsIndex':idx,'stateBitsTableRawStart':p,
            'loadBits0':f'0x{w0:08X}','loadBits1':f'0x{w1:08X}',
            'alphaMode':new_alpha,'alphaCutoff':st['alphaCutoff'],'doubleSided':new_double,
            'cullFace':st['cullFace'],'alphaTestDisabled':st['alphaTestDisabled'],'alphaTestMode':st['alphaTestMode'],
            'srcBlendRgb':st['srcBlendRgb'],'dstBlendRgb':st['dstBlendRgb'],'blendOpRgb':st['blendOpRgb'],
            'reason':st['reason']}
        rows.append({'materialIndex':i,'material':name,'selection':selection,'stateBitsIndex':idx,
                     'loadBits0':f'0x{w0:08X}','loadBits1':f'0x{w1:08X}',
                     'alphaMode':new_alpha,'alphaCutoff':st['alphaCutoff'],'doubleSided':new_double,
                     'cullFace':st['cullFace'],'alphaTestDisabled':st['alphaTestDisabled'],'alphaTestMode':st['alphaTestMode'],
                     'srcBlendRgb':st['srcBlendRgb'],'dstBlendRgb':st['dstBlendRgb'],'blendOpRgb':st['blendOpRgb']})
    bad=[r for r in unresolved if not (isinstance(r['material'],str) and r['material'].startswith('material_surface_'))]
    if bad:raise ValueError(f'non-generic materials unresolved: {bad[:10]}')
    if len(unresolved)!=7:raise ValueError(f'expected 7 retained generic material-table identities, got {len(unresolved)}')
    referenced={p['material'] for me in js.get('meshes',[]) for p in me.get('primitives',[]) if isinstance(p.get('material'),int)}
    unresolved_refs=[r for r in unresolved if r['materialIndex'] in referenced]
    if unresolved_refs:raise ValueError(f'generic unresolved materials still referenced: {unresolved_refs}')
    summary={
        'materialsResolvedFromRetailState':len(rows),'unreferencedGenericMaterialTableEntries':len(unresolved),
        'alphaModeChanges':changes['alphaMode'],'alphaCutoffChanges':changes['alphaCutoff'],'doubleSidedChanges':changes['doubleSided'],
        'opaqueCulled':counts[('OPAQUE','culled')],'opaqueDoubleSided':counts[('OPAQUE','cullNone')],
        'maskCulled':counts[('MASK','culled')],'maskDoubleSided':counts[('MASK','cullNone')],
        'blendCulled':counts[('BLEND','culled')],'blendDoubleSided':counts[('BLEND','cullNone')],
        'litConsensusMaterials':sum(r['selection']=='lit-technique-consensus' for r in rows),
        'unlitEmissiveConsensusMaterials':sum(r['selection']=='unlit-emissive-consensus' for r in rows),
    }
    js.setdefault('extras',{}).setdefault('T6',{})['retailMaterialRenderStateV1']={**summary,
        'expandedStream':stream.name,
        'proofBoundary':'alphaMode/alphaCutoff/doubleSided only; source is exact retained Material.stateBitsEntry and GfxStateBits.loadBits. No texture-alpha heuristic.'}
    write_glb(out,js,binbuf)
    j2,b2=read_glb(out)
    if j2['buffers'][0]['byteLength']!=len(b2):raise ValueError('buffer byteLength mismatch')
    man={'format':'t6-nuketown-retail-material-render-state-v1',
         'inputGlb':{'file':inp.name,'bytes':inp.stat().st_size,'sha256':sha(inp)},
         'expandedStream':{'file':stream.name,'bytes':stream.stat().st_size,'sha256':sha(stream)},
         'outputGlb':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out)},
         'summary':summary,'unresolvedMaterialTableEntries':unresolved,'materials':rows,
         'validation':{'litTechniqueConsensus':'pass','unlitEmissiveFallbackConsensus':'pass','serializedGfxStateBitsTailZero':'pass','unresolvedOnlyUnreferencedGenericTableEntries':'pass','glbReparse':'pass','bufferByteLengthMatches':'pass'},
         'proofBoundary':'Exact retail render-state presentation mapping; no image-alpha heuristic and no material identity guessing.'}
    manifest.write_text(json.dumps(man,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2));print(json.dumps(man['outputGlb'],indent=2))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--glb',type=Path,required=True);ap.add_argument('--stream',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args();build(a.glb,a.stream,a.out,a.manifest)
if __name__=='__main__':main()
