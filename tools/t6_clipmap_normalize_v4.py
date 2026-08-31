#!/usr/bin/env python3
"""T6 ClipMap normalized collision exporter v4.

Extends v3 by decoding cStaticModel_s and PhysConstraint records that were
previously preserved only as raw section digests.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path
from t6_clipmap_normalize_v1 import normalize as normalize_v1
from t6_clipmap_normalize_v2 import resolve_planes
from t6_clipmap_normalize_v3 import resolve_leafbrushes
from t6_clipmap_serialized_walker import ptr_kind

CSTATICMODEL_SIZE=84
PHYSCONSTRAINT_SIZE=168
CONSTRAINT_TYPES={0:'NONE',1:'POINT',2:'DISTANCE',3:'HINGE',4:'JOINT',5:'ACTUATOR',6:'FAKE_SHAKE',7:'LAUNCH',8:'ROPE',9:'LIGHT'}
ATTACH_TYPES={0:'WORLD',1:'DYNENT',2:'ENT',3:'BONE'}

def f3(d,o): return list(struct.unpack_from('<3f',d,o))
def i32(d,o): return struct.unpack_from('<i',d,o)[0]
def u32(d,o): return struct.unpack_from('<I',d,o)[0]
def u16(d,o): return struct.unpack_from('<H',d,o)[0]
def f32(d,o): return struct.unpack_from('<f',d,o)[0]
def secmap(w): return {s['name']:s for s in w['sections']}

def _finite(vals,label):
    if not all(math.isfinite(v) for v in vals): raise ValueError(f'non-finite float in {label}')

def decode_static_models(out,walk,data):
    s=secmap(walk).get('clipMap.staticModelList')
    count=int(out['counts']['numStaticModels'])
    if count and not s: raise ValueError('missing clipMap.staticModelList section')
    rows=[]
    if s:
        if s['bytes'] != count*CSTATICMODEL_SIZE: raise ValueError('static model byte count mismatch')
        for i in range(count):
            b=s['start']+i*CSTATICMODEL_SIZE
            origin=f3(data,b+12); axis=[f3(data,b+24+j*12) for j in range(3)]; mn=f3(data,b+60); mx=f3(data,b+72)
            _finite(origin+sum(axis,[])+mn+mx,f'staticModel[{i}]')
            if any(a>c for a,c in zip(mn,mx)): raise ValueError(f'invalid static model bounds {i}')
            rows.append({'index':i,'nextModelInWorldSector':u16(data,b),'xModelPointer':ptr_kind(u32(data,b+4)),'contents':i32(data,b+8),'origin':origin,'invScaledAxis':axis,'absmin':mn,'absmax':mx})
        out['staticModelsSource']={'start':s['start'],'end':s['end'],'bytes':s['bytes'],'sha256':s['sha256'],'recordSize':CSTATICMODEL_SIZE}
    out['staticModels']=rows
    out['unexpandedSections'].pop('clipMap.staticModelList',None)
    out['normalizationStatus']['staticModelFieldsExpanded']=True
    if 'staticModels' not in out['normalizationStatus']['decodedOwnedSections']:
        out['normalizationStatus']['decodedOwnedSections'].append('staticModels')
    return {'count':len(rows),'allBoundsValid':True,'allFloatFieldsFinite':True,'allXModelPointersPacked':all(r['xModelPointer']['kind']=='packed' for r in rows)}

def decode_constraints(out,walk,data):
    s=secmap(walk).get('clipMap.constraints.fixed'); count=int(out['counts']['num_constraints'])
    if count and not s: raise ValueError('missing clipMap.constraints.fixed section')
    rows=[]
    if s:
        if s['bytes'] != count*PHYSCONSTRAINT_SIZE: raise ValueError('constraint byte count mismatch')
        for i in range(count):
            b=s['start']+i*PHYSCONSTRAINT_SIZE
            typ=i32(data,b+4); a1=i32(data,b+8); a2=i32(data,b+24)
            if typ not in CONSTRAINT_TYPES or a1 not in ATTACH_TYPES or a2 not in ATTACH_TYPES: raise ValueError(f'invalid constraint enum at {i}')
            vectors={'offset':f3(data,b+40),'pos':f3(data,b+52),'pos2':f3(data,b+64),'dir':f3(data,b+76),'scale':f3(data,b+116)}
            floats={k:f32(data,b+o) for k,o in [('distance',104),('damp',108),('power',112),('spinScale',128),('minAngle',132),('maxAngle',136)]}
            _finite(sum(vectors.values(),[])+list(floats.values()),f'constraint[{i}]')
            rows.append({'index':i,'targetname':u16(data,b),'type':typ,'typeName':CONSTRAINT_TYPES[typ],'attachPointType1':a1,'attachPointType1Name':ATTACH_TYPES[a1],'targetIndex1':i32(data,b+12),'targetEnt1':u16(data,b+16),'targetBone1Pointer':ptr_kind(u32(data,b+20)),'attachPointType2':a2,'attachPointType2Name':ATTACH_TYPES[a2],'targetIndex2':i32(data,b+28),'targetEnt2':u16(data,b+32),'targetBone2Pointer':ptr_kind(u32(data,b+36)),**vectors,'flags':i32(data,b+88),'timeout':i32(data,b+92),'minHealth':i32(data,b+96),'maxHealth':i32(data,b+100),**floats,'materialPointer':ptr_kind(u32(data,b+140)),'constraintHandle':i32(data,b+144),'ropeIndex':i32(data,b+148),'centityNum':list(struct.unpack_from('<4i',data,b+152))})
        out['constraintsSource']={'start':s['start'],'end':s['end'],'bytes':s['bytes'],'sha256':s['sha256'],'recordSize':PHYSCONSTRAINT_SIZE}
    out['constraints']={'count':count,'records':rows}
    out['unexpandedSections'].pop('clipMap.constraints.fixed',None)
    out['normalizationStatus']['constraintFieldsExpanded']=True
    if 'constraints' not in out['normalizationStatus']['decodedOwnedSections']:
        out['normalizationStatus']['decodedOwnedSections'].append('constraints')
    return {'count':len(rows),'allEnumsValid':True,'allFloatFieldsFinite':True}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('expanded',type=Path); ap.add_argument('--asset-start',type=lambda x:int(x,0),required=True); ap.add_argument('--gfxworld-start',type=lambda x:int(x,0),required=True); ap.add_argument('--plane-source-start',type=lambda x:int(x,0),required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    data=a.expanded.read_bytes(); out,walk=normalize_v1(data,a.asset_start); planes=resolve_planes(out,data,gfxworld_start=a.gfxworld_start,plane_source_start=a.plane_source_start); leaf=resolve_leafbrushes(out,walk,data); sm=decode_static_models(out,walk,data); con=decode_constraints(out,walk,data); out['format']='t6-clipmap-normalized-v4'; out['expandedSha256']=hashlib.sha256(data).hexdigest(); out['normalizationStatus']['unexpandedOwnedSections']=sorted(out['unexpandedSections']); a.out.write_text(json.dumps(out,separators=(',',':'))+'\n'); print(json.dumps({'out':str(a.out),'bytes':a.out.stat().st_size,'sha256':hashlib.sha256(a.out.read_bytes()).hexdigest(),'planesResolved':planes['count'],'leafBrushesResolved':leaf['count'],'staticModels':sm,'constraints':con,'unexpanded':out['unexpandedSections']},indent=2))
if __name__=='__main__': main()
