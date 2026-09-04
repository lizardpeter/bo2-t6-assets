#!/usr/bin/env python3
"""Repair Nuketown static-XModel primitive material slots from retained retail proof.

This stage changes only GLB primitive slots whose current material name starts with
`material_surface_`.  Every non-generic primitive in a proof-covered mesh must already
match the retained XModel LOD material sequence exactly or the stage aborts.

If a proven target material name already exists uniquely in the GLB, the primitive is
repointed to it. If the exact target name is absent, a neutral identity-only material
shell is created; similarly named variants are never substituted.
"""
from __future__ import annotations
import argparse, base64, collections, hashlib, json, struct, zlib
from pathlib import Path

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()

def read_glb(path:Path):
    b=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b): raise ValueError('invalid GLB2')
    o=12; js=None; bins=[]
    while o<total:
        ln,typ=struct.unpack_from('<I4s',b,o);o+=8; ch=b[o:o+ln];o+=ln
        if typ==b'JSON': js=json.loads(ch)
        elif typ==b'BIN\0': bins.append(ch)
    if js is None or len(bins)!=1: raise ValueError('expected one JSON and one BIN')
    return js,bytearray(bins[0])

def write_glb(path:Path,js,binbuf:bytearray):
    js.setdefault('buffers',[{}])[0]['byteLength']=len(binbuf)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    jb+=b' ' * ((4-len(jb)%4)%4)
    bb=bytes(binbuf); bb+=b'\0'*((4-len(bb)%4)%4)
    total=12+8+len(jb)+8+len(bb)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total))
    out+=struct.pack('<I4s',len(jb),b'JSON')+jb
    out+=struct.pack('<I4s',len(bb),b'BIN\0')+bb
    path.write_bytes(out)

def generic(n): return isinstance(n,str) and n.startswith('material_surface_')

def load_proof(path:Path):
    if path.name.endswith('.zlib.b64'):
        raw=zlib.decompress(base64.b64decode(path.read_text().strip()))
        return json.loads(raw),raw
    raw=path.read_bytes(); return json.loads(raw),raw

def build(inp:Path,proof_path:Path,out:Path,manifest:Path):
    js,binbuf=read_glb(inp); proof,proof_raw=load_proof(proof_path)
    rows=proof['models']; by_x=collections.defaultdict(list)
    for r in rows: by_x[r['xassetIndex']].append(r)
    mats=js.setdefault('materials',[])
    name_to_indices=collections.defaultdict(list)
    for i,m in enumerate(mats): name_to_indices[m.get('name')].append(i)
    repairs=[]; validated=[]; created=[]; affected_meshes=set()
    before_generic=0
    for mesh_index,mesh in enumerate(js.get('meshes',[])):
        ex=mesh.get('extras') or {}; xa=ex.get('xassetIndex'); lod=ex.get('lod',0)
        if xa is None: continue
        rs=[r for r in by_x.get(xa,[]) if r.get('lod')==lod]
        if not rs:
            if any(isinstance(p.get('material'),int) and generic(mats[p['material']].get('name')) for p in mesh.get('primitives',[])):
                raise ValueError(f'{mesh_index}:{mesh.get("name")}: generic material but no proof row')
            continue
        exact=[r for r in rs if r.get('glbMeshName')==mesh.get('name')]
        if exact: row=exact[0]
        elif len(rs)==1: row=rs[0]
        else: raise ValueError(f'{mesh_index}:{mesh.get("name")}: ambiguous proof rows')
        if row.get('surfaceCount')!=len(row.get('materials',[])):
            raise ValueError('proof surface/material count mismatch')
        start=row.get('surfaceIndex',0)
        for prim_index,p in enumerate(mesh.get('primitives',[])):
            mid=p.get('material')
            if not isinstance(mid,int) or not 0<=mid<len(mats): raise ValueError('invalid primitive material')
            actual=mats[mid].get('name')
            si=(p.get('extras') or {}).get('surfaceIndex')
            if not isinstance(si,int): raise ValueError(f'{mesh_index}:{prim_index}: missing surfaceIndex')
            rel=si-start
            if not 0<=rel<len(row['materials']): raise ValueError(f'{mesh_index}:{prim_index}: surface outside proof row')
            expected=row['materials'][rel]
            if generic(actual):
                before_generic+=1
                inds=name_to_indices.get(expected,[])
                if len(inds)>1: raise ValueError(f'{expected}: duplicate GLB material identities {inds}')
                if len(inds)==1:
                    target=inds[0]; resolution='reuse-existing-exact-name-material'
                else:
                    target=len(mats)
                    mats.append({'name':expected,'pbrMetallicRoughness':{'baseColorFactor':[0.5,0.5,0.5,1.0],'metallicFactor':0.0,'roughnessFactor':1.0},'extras':{'T6':{'identityResolution':'xmodel-material-handle-proof','textureResolution':'unresolved-neutral','sourceProof':proof_path.name}}})
                    name_to_indices[expected].append(target)
                    created.append({'materialIndex':target,'material':expected})
                    resolution='created-identity-only-neutral-material'
                p['material']=target
                affected_meshes.add(mesh_index)
                repairs.append({'meshIndex':mesh_index,'mesh':mesh.get('name'),'xassetIndex':xa,'primitiveIndex':prim_index,'surfaceIndex':si,'fromMaterial':actual,'toMaterial':expected,'toMaterialIndex':target,'resolution':resolution})
            elif actual==expected:
                validated.append({'meshIndex':mesh_index,'primitiveIndex':prim_index,'surfaceIndex':si,'material':actual})
            else:
                raise ValueError(f'{mesh_index}:{mesh.get("name")} surface {si}: existing {actual!r} != proof {expected!r}')
    if not repairs: raise ValueError('no generic slots repaired')
    after_generic=0
    for mesh in js.get('meshes',[]):
        for p in mesh.get('primitives',[]):
            mid=p.get('material')
            if isinstance(mid,int) and generic(mats[mid].get('name')): after_generic+=1
    if after_generic: raise ValueError(f'{after_generic} generic primitive references remain')
    affected_nodes=sum(1 for n in js.get('nodes',[]) if n.get('mesh') in affected_meshes)
    inherited=collections.Counter()
    for r in repairs:
        tm=mats[r['toMaterialIndex']]; pbr=tm.get('pbrMetallicRoughness') or {}
        if pbr.get('baseColorTexture') is not None: inherited['color']+=1
        if tm.get('normalTexture') is not None: inherited['normal']+=1
        if pbr.get('baseColorTexture') is not None or tm.get('normalTexture') is not None: inherited['any']+=1
    js.setdefault('extras',{}).setdefault('T6',{})['xmodelMaterialSlotRepairV1']={'sourceProof':proof_path.name,'validatedExistingSlots':len(validated),'repairedGenericSlots':len(repairs),'affectedMeshes':len(affected_meshes),'affectedPlacedNodes':affected_nodes,'identityOnlyMaterialsCreated':len(created),'genericPrimitiveReferencesAfter':after_generic,'repairedSlotsInheritingColorTexture':inherited['color'],'repairedSlotsInheritingNormalTexture':inherited['normal'],'repairedSlotsInheritingAnyTexture':inherited['any'],'proofBoundary':'Only material_surface_* primitive slots are rewritten. Every non-generic slot in proof-covered meshes must already equal the retained XModel LOD material sequence exactly. Missing exact target names create neutral identity-only shells; no similarly named substitution.'}
    write_glb(out,js,binbuf)
    j2,b2=read_glb(out)
    if j2['buffers'][0]['byteLength']!=len(b2): raise ValueError('buffer byteLength mismatch')
    man={'format':'t6-nuketown-xmodel-material-slot-repair-v1','inputGlb':{'file':inp.name,'bytes':inp.stat().st_size,'sha256':sha(inp)},'proof':{'file':proof_path.name,'storedBytes':proof_path.stat().st_size,'storedSha256':sha(proof_path),'rawJsonBytes':len(proof_raw),'rawJsonSha256':hashlib.sha256(proof_raw).hexdigest(),'playableStaticModelCount':proof.get('playableStaticModelCount'),'playableLod0MaterialSlotCount':proof.get('playableLod0MaterialSlotCount')},'outputGlb':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out)},'summary':{'validatedExistingSlots':len(validated),'repairedGenericSlots':len(repairs),'affectedMeshes':len(affected_meshes),'affectedPlacedNodes':affected_nodes,'identityOnlyMaterialsCreated':len(created),'genericPrimitiveReferencesAfter':after_generic,'repairedSlotsInheritingColorTexture':inherited['color'],'repairedSlotsInheritingNormalTexture':inherited['normal'],'repairedSlotsInheritingAnyTexture':inherited['any']},'createdIdentityOnlyMaterials':created,'repairs':repairs,'validation':{'allExistingNonGenericSlotsMatchProof':True,'genericPrimitiveReferencesAfter':after_generic,'glbReparse':'pass','bufferByteLengthMatches':'pass'},'proofBoundary':'Exact XModel material-handle slot repair only; no material-name guessing.'}
    manifest.write_text(json.dumps(man,indent=2,sort_keys=True)+'\n')
    print(json.dumps(man['summary'],indent=2));print(json.dumps(man['outputGlb'],indent=2))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--glb',type=Path,required=True);ap.add_argument('--proof',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args();build(a.glb,a.proof,a.out,a.manifest)
if __name__=='__main__':main()
