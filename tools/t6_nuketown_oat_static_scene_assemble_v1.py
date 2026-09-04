#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, itertools, json, math, struct
from pathlib import Path

METER=0.0254
C=((1.0,0.0,0.0),(0.0,0.0,1.0),(0.0,-1.0,0.0))
CT=tuple(zip(*C))
RECOVERED={221:'dest_nt_nuked_male_01_d0',230:'dest_nt_nuked_female_01_d0',262:'nt_2020_flag_nuclear_01',263:'nt_2020_flag_nuclear_02',273:'dest_nt_nuked_female_02_d0',274:'dest_nt_nuked_female_03_d0',306:'nt_2020_flag_england_01'}

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def mm(a,b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def mv(a,v): return [sum(a[i][k]*v[k] for k in range(3)) for i in range(3)]
def tr(a): return [list(x) for x in zip(*a)]

def read_glb(p:Path):
    b=p.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b): raise ValueError(f'{p}: invalid GLB')
    o=12; js=None; bins=[]
    while o<total:
        n,t=struct.unpack_from('<I4s',b,o); o+=8; c=b[o:o+n]; o+=n
        if t==b'JSON': js=json.loads(c.rstrip(b' \0'))
        elif t==b'BIN\0': bins.append(c)
    if js is None or len(bins)!=1: raise ValueError(f'{p}: expected one JSON/BIN')
    return js,bins[0]

def write_glb(p:Path,js,binbuf:bytearray):
    while len(binbuf)%4: binbuf.append(0)
    js['buffers']=[{'byteLength':len(binbuf)}]
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode()
    while len(jb)%4: jb+=b' '
    out=bytearray(struct.pack('<4sII',b'glTF',2,12+8+len(jb)+8+len(binbuf)))
    out+=struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
    p.write_bytes(out)

def resolve_proof_names(proof):
    out=[]
    for r in proof['models']:
        n=r.get('xmodelName') or RECOVERED.get(int(r['xassetIndex']))
        if not n: raise ValueError(f'unresolved retained XModel xasset {r["xassetIndex"]}')
        out.append(n)
    if len(out)!=297 or len(set(out))!=297: raise ValueError('expected 297 unique playable static XModels')
    return out

def source_bbox_from_oat(js):
    mins=[math.inf]*3; maxs=[-math.inf]*3; found=False; pos_ids=set()
    for mesh in js.get('meshes',[]):
        for pr in mesh.get('primitives',[]):
            if 'POSITION' in pr.get('attributes',{}): pos_ids.add(pr['attributes']['POSITION'])
    for ai in pos_ids:
        a=js['accessors'][ai]
        if 'min' not in a or 'max' not in a: continue
        for q in itertools.product(*zip(a['min'],a['max'])):
            s=mv(CT,q)
            for k in range(3): mins[k]=min(mins[k],s[k]); maxs[k]=max(maxs[k],s[k])
        found=True
    if not found: raise ValueError('model has no bounded POSITION accessor')
    return mins,maxs

def transformed_bbox(local_min,local_max,row,convention):
    axis=[list(map(float,v)) for v in row['axis']]; A=tr(axis) if convention=='basis-vectors' else axis
    origin=list(map(float,row['origin'])); scale=float(row['scale']); mins=[math.inf]*3; maxs=[-math.inf]*3
    for p in itertools.product(*zip(local_min,local_max)):
        w=mv(A,p); w=[origin[k]+scale*w[k] for k in range(3)]
        for k in range(3): mins[k]=min(mins[k],w[k]); maxs[k]=max(maxs[k],w[k])
    return mins,maxs

def calibrate_axis(rows,model_bounds):
    scores={}
    for conv in ('basis-vectors','matrix-rows'):
        errs=[]
        for r in rows[:min(len(rows),512)]:
            b=model_bounds.get(r['model'])
            if not b: continue
            lo,hi=transformed_bbox(*b,r,conv); target_lo=r['mins']; target_hi=r['maxs']
            errs.append(sum(abs(lo[k]-target_lo[k])+abs(hi[k]-target_hi[k]) for k in range(3))/6.0)
        if not errs: raise ValueError('no rows available for axis calibration')
        errs.sort(); scores[conv]={'medianAbsBoundError':errs[len(errs)//2],'meanAbsBoundError':sum(errs)/len(errs),'samples':len(errs)}
    chosen=min(scores,key=lambda x:scores[x]['medianAbsBoundError']); other=next(x for x in scores if x!=chosen)
    if scores[chosen]['medianAbsBoundError'] >= scores[other]['medianAbsBoundError']*0.95: raise ValueError(f'axis convention ambiguous: {scores}')
    return chosen,scores

def gltf_matrix(row,convention):
    axis=[list(map(float,v)) for v in row['axis']]; A=tr(axis) if convention=='basis-vectors' else axis
    Rg=mm(mm(C,A),CT); f=float(row['scale'])*METER; L=[[Rg[i][j]*f for j in range(3)] for i in range(3)]
    t=[x*METER for x in mv(C,list(map(float,row['origin'])))]
    return [L[0][0],L[1][0],L[2][0],0.0,L[0][1],L[1][1],L[2][1],0.0,L[0][2],L[1][2],L[2][2],0.0,t[0],t[1],t[2],1.0]

def build(placements_path,proof_path,model_dir,out_path,manifest_path,expected=1943):
    placements=json.loads(placements_path.read_text()); proof=json.loads(proof_path.read_text()); names=resolve_proof_names(proof); name_set=set(names)
    selected=[r for r in placements['placements'] if r['model'] in name_set]; selected_models={r['model'] for r in selected}
    if len(selected)!=expected: raise ValueError(f'playable model-identity filter yielded {len(selected)} placements, expected {expected}')
    if selected_models!=name_set:
        miss=sorted(name_set-selected_models); raise ValueError(f'{len(miss)} playable XModels have no placement: {miss[:20]}')
    js={'asset':{'version':'2.0','generator':'bo2-t6-assets Nuketown OAT static assembler v1'},'scene':0,'scenes':[{'name':'mp_nuketown_2020_static','nodes':[0]}],'nodes':[{'name':'T6_PLAYABLE_STATIC_ROOT','children':[]}],'meshes':[],'materials':[],'accessors':[],'bufferViews':[],'buffers':[{'byteLength':0}],'extras':{'T6':{'source':'retail GfxWorld.dpvs + OAT v0.33.0 LOD0 XModels'}}}
    binbuf=bytearray(); mat_index={}; model_mesh={}; model_bounds={}; primitive_slots=0; proof_by_name={n:r for n,r in zip(names,proof['models'])}
    for n in names:
        fp=model_dir/(n+'_lod0.glb')
        if not fp.exists(): raise FileNotFoundError(fp)
        src,b=read_glb(fp)
        for node in src.get('nodes',[]):
            if 'mesh' in node and any(k in node for k in ('translation','rotation','scale','matrix')): raise ValueError(f'{n}: transformed mesh node cannot be flattened safely')
        model_bounds[n]=source_bbox_from_oat(src)
        while len(binbuf)%4: binbuf.append(0)
        bin_base=len(binbuf); binbuf.extend(b); bv_base=len(js['bufferViews']); acc_base=len(js['accessors'])
        for bv in src.get('bufferViews',[]):
            q=copy.deepcopy(bv); q['buffer']=0; q['byteOffset']=bin_base+q.get('byteOffset',0); js['bufferViews'].append(q)
        for a in src.get('accessors',[]):
            q=copy.deepcopy(a)
            if 'bufferView' in q: q['bufferView']=bv_base+q['bufferView']
            if 'sparse' in q: raise ValueError(f'{n}: sparse accessor unsupported in static assembler')
            js['accessors'].append(q)
        prims=[]; used=[]
        for mesh in src.get('meshes',[]):
            for pr in mesh.get('primitives',[]):
                q=copy.deepcopy(pr); q['attributes']={k:acc_base+v for k,v in q.get('attributes',{}).items() if not (k.startswith('JOINTS_') or k.startswith('WEIGHTS_'))}
                if 'indices' in q: q['indices']=acc_base+q['indices']
                if 'targets' in q: q['targets']=[{k:acc_base+v for k,v in t.items()} for t in q['targets']]
                smi=q.get('material')
                if smi is None: raise ValueError(f'{n}: primitive without material')
                mn=src['materials'][smi].get('name')
                if not mn: raise ValueError(f'{n}: unnamed primitive material')
                used.append(mn)
                if mn not in mat_index:
                    mat_index[mn]=len(js['materials']); js['materials'].append({'name':mn,'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0.0,'roughnessFactor':1.0},'doubleSided':True})
                q['material']=mat_index[mn]; prims.append(q); primitive_slots+=1
        if used!=proof_by_name[n]['materials']: raise ValueError(f'{n}: OAT LOD0 primitive/material sequence diverged from retained proof')
        model_mesh[n]=len(js['meshes']); js['meshes'].append({'name':n,'primitives':prims,'extras':{'T6':{'xassetIndex':proof_by_name[n]['xassetIndex'],'lod':0}}})
    convention,scores=calibrate_axis(selected,model_bounds)
    for r in selected:
        ni=len(js['nodes']); js['nodes'].append({'name':f'smodel_{r["index"]:04d}_{r["model"]}','mesh':model_mesh[r['model']],'matrix':gltf_matrix(r,convention),'extras':{'T6':{'smodelIndex':r['index'],'cullDist':r['cullDist'],'flags':r['flags'],'sourceOrigin':r['origin'],'sourceScale':r['scale']}}}); js['nodes'][0]['children'].append(ni)
    js['extras']['T6'].update({'fullGfxWorldSmodelCount':placements['smodelCount'],'playablePlacementCount':len(selected),'playableUniqueXModels':len(names),'axisConvention':convention,'axisCalibration':scores,'metersPerGameUnit':METER})
    write_glb(out_path,js,binbuf); check,_=read_glb(out_path)
    if len(check['nodes'])!=expected+1 or len(check['meshes'])!=297: raise ValueError('output structural regression')
    manifest={'format':'t6-nuketown-oat-playable-static-scene-v1','inputs':{'placements':{'file':placements_path.name,'sha256':sha(placements_path)},'proof':{'file':proof_path.name,'sha256':sha(proof_path)}},'summary':{'fullGfxWorldSmodelCount':placements['smodelCount'],'playablePlacementCount':len(selected),'uniquePlayableModels':297,'meshDefinitions':len(js['meshes']),'rootPlusInstanceNodes':len(js['nodes']),'uniqueMaterials':len(js['materials']),'uniqueModelPrimitiveSlots':primitive_slots,'axisConvention':convention,'axisCalibration':scores},'output':{'file':out_path.name,'bytes':out_path.stat().st_size,'sha256':sha(out_path)},'proofBoundary':'Placements are admitted only by exact membership in the independently closed 297-XModel playable set. Mesh geometry comes from exact OAT v0.33.0 LOD0 GLBs whose primitive material sequences match the retained proof. GfxWorld axis interpretation is chosen only by independent smodelInst bounds agreement; ambiguous conventions fail closed.'}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n'); return manifest

def main():
    a=argparse.ArgumentParser(); a.add_argument('--placements',type=Path,required=True); a.add_argument('--proof',type=Path,required=True); a.add_argument('--model-dir',type=Path,required=True); a.add_argument('--out',type=Path,required=True); a.add_argument('--manifest',type=Path,required=True); a.add_argument('--expected',type=int,default=1943); q=a.parse_args(); print(json.dumps(build(q.placements,q.proof,q.model_dir,q.out,q.manifest,q.expected)['summary'],indent=2))
if __name__=='__main__': main()
