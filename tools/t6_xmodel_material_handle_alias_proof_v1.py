#!/usr/bin/env python3
"""Prove T6 XModel Material** handle aliases from exact VIRTUAL pointer fields.

T6 PC32 XModel.materialHandles is a numsurfs-long Material* pointer array in the
normal VIRTUAL block. On the cross-word-size loader path every serialized 4-byte
pointer field is registered in the pointer lookup before the elements are walked.
A later packed Material* can therefore target an earlier materialHandles[i]
field. This tool proves that relationship directly from retail bytes.

Direct FOLLOWING/INSERT handle identities are recovered from the serialized
Material asset at that handle. Nested T6 thermalMaterial INSERT/FOLLOWING assets
are consumed recursively so the next XModel handle starts at the correct raw
position. Packed handles are promoted only when their decoded VIRTUAL offset is
exactly a proven direct materialHandles[] field. No material-name correlation is
used to resolve packed handles.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE
XMODEL_FIXED=248
MATERIAL_HANDLES_PTR_OFF=36
PTR_BYTES=4

class ProofError(RuntimeError): pass

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()

def load_json(p:Path):return json.loads(p.read_text(encoding='utf-8-sig'))
def ptr(v:int)->dict:
    v&=0xffffffff
    if v==0:return {'kind':'null','raw':v,'rawHex':'0x00000000'}
    if v==FOLLOWING:return {'kind':'following','raw':v,'rawHex':'0xffffffff'}
    if v==INSERT:return {'kind':'insert','raw':v,'rawHex':'0xfffffffe'}
    x=(v-1)&0xffffffff
    return {'kind':'packed','raw':v,'rawHex':f'0x{v:08x}','block':x>>29,'offset':x&0x1fffffff}

def catalog_rows(doc):
    if isinstance(doc,list): return [r for r in doc if isinstance(r,dict)]
    out=[]
    if isinstance(doc,dict):
        for v in doc.values():
            if isinstance(v,list):out.extend(r for r in v if isinstance(r,dict))
    return out

def consume_material(by_start:dict[int,dict],pos:int,stack:tuple[int,...]=())->tuple[dict,int,list[dict]]:
    if pos in stack:raise ProofError(f'thermal material recursion cycle at raw {pos}')
    row=by_start.get(pos)
    if row is None:raise ProofError(f'no material/import row at raw 0x{pos:x}')
    if row.get('kind') not in ('material','import-stub'):
        raise ProofError(f'raw 0x{pos:x} is not material/import-stub: {row.get("kind")!r}')
    q=int(row['end']);nested=[]
    therm=(row.get('thermalPointer') or {}).get('kind')
    if row.get('kind')=='material' and therm in ('following','insert'):
        child,end,grand=consume_material(by_start,q,stack+(pos,))
        nested=[child,*grand];q=end
    return row,q,nested

def read_model(data:bytes,mesh_path:Path,catalog:dict[int,dict],virtual_base:int)->dict:
    mesh=load_json(mesh_path)
    if mesh.get('format')!='t6-xmodel-mesh-normalized-v1':raise ProofError(f'{mesh_path}: unsupported mesh format')
    name=mesh['identity']['name'];start=int(mesh['source']['assetFixedStart']);end=int(mesh['source']['meshOwnedSerializedEnd']);ns=int(mesh['xmodel']['numSurfs'])
    if start<0 or start+XMODEL_FIXED>len(data):raise ProofError(f'{name}: fixed record outside stream')
    hp=struct.unpack_from('<I',data,start+MATERIAL_HANDLES_PTR_OFF)[0]
    if hp not in (FOLLOWING,INSERT):raise ProofError(f'{name}: materialHandles pointer not inline: {ptr(hp)}')
    raw_start=end;raw_end=raw_start+ns*PTR_BYTES
    if raw_end>len(data):raise ProofError(f'{name}: material handle array truncated')
    vals=list(struct.unpack_from('<'+'I'*ns,data,raw_start))
    p=raw_end;direct={};direct_rows=[]
    for i,v in enumerate(vals):
        if v in (FOLLOWING,INSERT):
            row,q,nested=consume_material(catalog,p)
            direct[i]=row['name']
            direct_rows.append({'slotIndex':i,'fieldVirtualOffset':virtual_base+i*4,'fieldRawValue':f'0x{v:08x}','material':row['name'],'materialKind':row['kind'],'materialRawStart':int(row['start']),'materialRawEndIncludingNested':q,'nestedThermalMaterials':[x['name'] for x in nested]})
            p=q
    return {'model':name,'meshSidecar':str(mesh_path),'assetFixedStart':start,'meshOwnedSerializedEnd':end,'numSurfs':ns,'materialHandlesPointerRaw':f'0x{hp:08x}','handleArrayRawStart':raw_start,'handleArrayRawEnd':raw_end,'handleArrayVirtualBase':virtual_base,'handleRawValues':[f'0x{x:08x}' for x in vals],'directSlots':direct_rows,'directByIndex':direct,'rawAfterDirectMaterialAssets':p}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--expanded',type=Path,required=True)
    ap.add_argument('--material-catalog',type=Path,required=True)
    ap.add_argument('--spec',type=Path,required=True)
    ap.add_argument('--mesh-root',type=Path,help='base directory for relative mesh paths; defaults to spec directory')
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    data=a.expanded.read_bytes();spec=load_json(a.spec);catrows=catalog_rows(load_json(a.material_catalog));by_start={int(r['start']):r for r in catrows if isinstance(r.get('start'),int)}
    mesh_root=(a.mesh_root or a.spec.parent).resolve()
    models=[]
    for m in spec['models']:
        mp=Path(m['mesh'])
        if not mp.is_absolute(): mp=mesh_root/mp
        models.append(read_model(data,mp,by_start,int(m['materialHandleVirtualBase'])))
    owners={}
    for m in models:
        for r in m['directSlots']:
            off=int(r['fieldVirtualOffset'])
            if off in owners:raise ProofError(f'duplicate direct owner VIRTUAL 0x{off:x}')
            owners[off]={'model':m['model'],'slotIndex':r['slotIndex'],'material':r['material'],'materialRawStart':r['materialRawStart']}
    all_packed=[]
    for m in models:
        for i,s in enumerate(m['handleRawValues']):
            d=ptr(int(s,16))
            if d['kind']=='packed' and d['block']==5:all_packed.append({'fromModel':m['model'],'fromSlot':i,'offset':d['offset'],'rawHex':d['rawHex']})
    hits={m['model']:0 for m in models}
    for x in all_packed:
        o=owners.get(x['offset'])
        if o:hits[o['model']]+=1
    min_hits=int(spec.get('minimumObservedAliasHitsPerOwnerModel',1))
    for m in models:
        if m['model'] in set(spec.get('ownerModelsRequiredObserved',[])) and hits[m['model']]<min_hits:
            raise ProofError(f"{m['model']}: virtual base has only {hits[m['model']]} observed alias hits (<{min_hits})")
    target_name=spec['targetModel'];target=next((m for m in models if m['model']==target_name),None)
    if target is None:raise ProofError(f'target model not in spec: {target_name}')
    assignments=[];packed_resolved=0;direct_resolved=0
    for i,s in enumerate(target['handleRawValues']):
        v=int(s,16);d=ptr(v)
        if d['kind'] in ('following','insert'):
            mat=target['directByIndex'].get(i)
            if mat is None:raise ProofError(f'{target_name} slot {i}: direct pointer has no parsed material')
            assignments.append({'surfaceIndex':i,'materialName':mat,'materialPointerRaw':s,'evidence':'direct-inline-material-asset','ownerModel':target_name,'ownerSlotIndex':i,'ownerFieldVirtualOffset':target['handleArrayVirtualBase']+4*i});direct_resolved+=1
        elif d['kind']=='packed':
            if d['block']!=5:raise ProofError(f'{target_name} slot {i}: packed material not VIRTUAL: {d}')
            o=owners.get(d['offset'])
            if o is None:raise ProofError(f'{target_name} slot {i}: packed VIRTUAL 0x{d["offset"]:x} has no proven direct material handle owner')
            assignments.append({'surfaceIndex':i,'materialName':o['material'],'materialPointerRaw':s,'evidence':'exact-xmodel-materialHandles-field-alias','ownerModel':o['model'],'ownerSlotIndex':o['slotIndex'],'ownerFieldVirtualOffset':d['offset'],'ownerMaterialRawStart':o['materialRawStart']});packed_resolved+=1
        else:raise ProofError(f'{target_name} slot {i}: unsupported material handle {d}')
    expected=spec.get('expectedTargetMaterialSequence')
    if expected is not None:
        got=[x['materialName'] for x in assignments]
        if got!=expected:raise ProofError('independently resolved target material sequence does not match expected benchmark sequence')
    summary={'models':len(models),'targetModel':target_name,'targetSurfaceCount':len(assignments),'targetDirectHandles':direct_resolved,'targetPackedHandles':packed_resolved,'targetAllHandlesExact':len(assignments)==target['numSurfs'],'ownerAliasHitCounts':hits}
    out={'format':'t6-xmodel-material-handle-alias-proof-v1','authority':'expanded retail T6 XModel Material** serialization + exact VIRTUAL pointer-field ownership; no material-name correlation used for packed resolution','source':{'expandedPath':str(a.expanded),'expandedBytes':len(data),'expandedSha256':hashlib.sha256(data).hexdigest(),'materialCatalogPath':str(a.material_catalog),'materialCatalogSha256':sha256_file(a.material_catalog),'specPath':str(a.spec),'specSha256':sha256_file(a.spec)},'rules':{'XModelFixedBytes':XMODEL_FIXED,'materialHandlesPointerOffset':MATERIAL_HANDLES_PTR_OFF,'serializedPointerBytes':PTR_BYTES,'directHandle':'FOLLOWING/INSERT -> serialized Material asset identity','packedHandle':'decoded VIRTUAL offset must equal an exact proven direct materialHandles[i] pointer field','nestedThermal':'consumed recursively before the next XModel direct handle'},'summary':summary,'models':[{k:v for k,v in m.items() if k not in ('directByIndex','handleRawValues')} for m in models],'targetAssignments':assignments,'proofBoundary':'Packed Material identities are promoted only when their VIRTUAL offset equals a direct XModel.materialHandles[] field whose Material identity is parsed from the retail serialized asset. Nested thermal materials are recursively consumed to maintain raw positioning. No material-name correlation is used for packed resolution.'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
