#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import struct
from pathlib import Path

from t6_zone_core import (
    GFX_WORLD_VD0_STRIDE,
    MaterialWorldVertexFormat,
    WORLD_VERTEX_FORMATS,
    align_up,
    decode_world_vd0_vertex,
    decode_world_vd1_vertex,
)


class AuditError(RuntimeError):
    pass


def audit(map_name: str, surfaces_path: Path, vd0_path: Path, vd1_path: Path) -> dict:
    surfaces_doc=json.loads(surfaces_path.read_text())
    surfaces=surfaces_doc['surfaces']
    vd0=vd0_path.read_bytes(); vd1=vd1_path.read_bytes()
    if len(surfaces)!=5614: raise AuditError(f'surface count {len(surfaces)} != 5614')
    if len(vd0)!=5285088: raise AuditError(f'vd0 bytes {len(vd0)} != 5285088')
    if len(vd1)!=33764: raise AuditError(f'vd1 bytes {len(vd1)} != 33764')

    groups=collections.defaultdict(list)
    for s in surfaces: groups[int(s['vertexDataOffset0'])].append(s)
    offs=sorted(groups)
    records=[]; bad=[]; format_group_counts=collections.Counter()

    for gi,off in enumerate(offs):
        gs=groups[off]
        next0=offs[gi+1] if gi+1<len(offs) else len(vd0)
        span0=next0-off
        candidates=[n for n in range(max(0,span0//GFX_WORLD_VD0_STRIDE-2),span0//GFX_WORLD_VD0_STRIDE+2) if align_up(GFX_WORLD_VD0_STRIDE*n,16)==span0]
        stored=sorted({int(s['vertexCount']) for s in gs if int(s['vertexCount'])>0})
        if len(candidates)!=1:
            bad.append({'offset0':off,'reason':'vd0 span does not uniquely determine vertex count','span':span0,'candidates':candidates,'storedCounts':stored}); continue
        vc=candidates[0]
        if stored and stored!=[vc]:
            bad.append({'offset0':off,'reason':'stored vertexCount disagrees with vd0 span','spanVertexCount':vc,'storedCounts':stored}); continue

        fmts=sorted({int(s['worldVertFormat']) for s in gs})
        if len(fmts)!=1:
            bad.append({'offset0':off,'reason':'mixed live world vertex formats','formats':fmts}); continue
        fmt=fmts[0]
        try: enum_fmt=MaterialWorldVertexFormat(fmt)
        except ValueError:
            bad.append({'offset0':off,'reason':'invalid worldVertFormat','format':fmt}); continue
        spec=WORLD_VERTEX_FORMATS[enum_fmt]

        off1s=sorted({int(s['vertexDataOffset1']) for s in gs})
        if len(off1s)!=1:
            bad.append({'offset0':off,'reason':'mixed vd1 offsets','offsets':off1s}); continue
        off1=off1s[0]
        later=[min(int(s['vertexDataOffset1']) for s in groups[o]) for o in offs[gi+1:]]
        next1=next((x for x in later if x>off1),len(vd1))
        used0=vc*GFX_WORLD_VD0_STRIDE
        if span0!=align_up(used0,16):
            bad.append({'offset0':off,'reason':'vd0 span mismatch','span':span0,'expected':align_up(used0,16)}); continue
        if off<0 or off+used0>len(vd0):
            bad.append({'offset0':off,'reason':'vd0 group outside buffer'}); continue

        used1=vc*spec.vd1_stride
        span1=next1-off1 if spec.vd1_stride else 0
        if spec.vd1_stride:
            if off1<0 or off1+used1>len(vd1):
                bad.append({'offset0':off,'offset1':off1,'reason':'vd1 group outside buffer','format':fmt}); continue
            if span1!=align_up(used1,4):
                bad.append({'offset0':off,'reason':'vd1 span mismatch','format':fmt,'span':span1,'expected':align_up(used1,4)}); continue

        firsts=sorted({int(s['firstVertex']) for s in gs})
        if len(firsts)!=1:
            bad.append({'offset0':off,'reason':'mixed firstVertex','values':firsts}); continue

        samples=[]
        for vi in range(min(vc,3)):
            a=off+GFX_WORLD_VD0_STRIDE*vi
            v=decode_world_vd0_vertex(vd0[a:a+GFX_WORLD_VD0_STRIDE])
            if spec.vd1_stride:
                b=off1+spec.vd1_stride*vi
                v.update(decode_world_vd1_vertex(vd1[b:b+spec.vd1_stride],fmt))
            samples.append(v)
        format_group_counts[fmt]+=1
        records.append({
            'groupIndex':gi,'vd0Offset':off,'vd1Offset':off1,'vertexCount':vc,
            'worldVertFormat':fmt,'formatName':enum_fmt.name,'vd1Stride':spec.vd1_stride,
            'vd1Fields':list(spec.vd1_fields),'surfaceCount':len(gs),
            'surfaceIndices':[int(s['index']) for s in gs],
            'lightmapIndices':[],
            'materials':sorted({s['material'] for s in gs}),'samples':samples,
        })

    lm_raw=[]
    for row in records:
        off=int(row['vd0Offset']); vc=int(row['vertexCount'])
        for i in range(vc): lm_raw.append(struct.unpack_from('<HH',vd0,off+i*GFX_WORLD_VD0_STRIDE+32))
    format_table={}
    observed=set(format_group_counts)
    for key,spec in WORLD_VERTEX_FORMATS.items():
        fmt=int(key)
        format_table[str(fmt)]={'name':key.name,'uvCount':spec.uv_count,'normalCount':spec.normal_count,'vd1Stride':spec.vd1_stride,'vd1Fields':list(spec.vd1_fields),'validation':'direct live retail byte proof' if fmt in observed else 'T6 enum/formula; not observed in fixture'}
    lightmap={'encoding':'2xUNORM16 little-endian','sampleCount':len(lm_raw)}
    if lm_raw:
        lightmap.update({'rawMin':[min(a for a,_ in lm_raw),min(b for _,b in lm_raw)],'rawMax':[max(a for a,_ in lm_raw),max(b for _,b in lm_raw)]})
    return {
        'format':'t6-world-vertex-proof-v1','map':map_name,
        'source':{'surfaces':str(surfaces_path),'vd0':str(vd0_path),'vd1':str(vd1_path),'materialFormatSource':'live GfxSurface->Material->TechniqueSet.worldVertFormat'},
        'surfaceCount':len(surfaces),'uniqueVertexGroups':len(groups),'vd0Bytes':len(vd0),'vd1Bytes':len(vd1),
        'vd0StrideBytes':GFX_WORLD_VD0_STRIDE,'formatTable':format_table,
        'observedFormatGroupCounts':{str(k):v for k,v in sorted(format_group_counts.items())},
        'badGroupCount':len(bad),'badGroups':bad,'lightmapUV':lightmap,
        'materialFormatCount':len({s['material'] for s in surfaces}),'groups':records,
        'proofBoundary':'world vertex formats come directly from the loaded retail Material TechniqueSet for each GfxSurface; no serialized asset-pointer reconstruction is used',
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--map',required=True); ap.add_argument('--surfaces',type=Path,required=True); ap.add_argument('--vd0',type=Path,required=True); ap.add_argument('--vd1',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    r=audit(a.map,a.surfaces,a.vd0,a.vd1); a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'surfaces':r['surfaceCount'],'groups':r['uniqueVertexGroups'],'bad':r['badGroupCount'],'formats':r['observedFormatGroupCounts']},indent=2))
    raise SystemExit(0 if r['badGroupCount']==0 else 2)

if __name__=='__main__': main()
