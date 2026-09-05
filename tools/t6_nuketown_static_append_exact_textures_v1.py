#!/usr/bin/env python3
from __future__ import annotations

import argparse, copy, hashlib, json, struct
from pathlib import Path

EXPECTED_MATERIALS=344
EXPECTED_MESHES=297
EXPECTED_INSTANCES=1943

def sha_file(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def read_glb(path:Path):
    data=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',data,0)
    if magic!=b'glTF' or ver!=2 or total!=len(data): raise ValueError('invalid GLB')
    off=12; root=None; binbuf=None
    while off<len(data):
        n,t=struct.unpack_from('<I4s',data,off);off+=8;chunk=data[off:off+n];off+=n
        if t==b'JSON':root=json.loads(chunk.rstrip(b' \0'))
        elif t==b'BIN\0':
            if binbuf is not None:raise ValueError('multiple BIN chunks')
            binbuf=bytes(chunk)
    if root is None or binbuf is None:raise ValueError('missing JSON/BIN')
    return root,binbuf

def write_glb(path:Path,root:dict,binbuf:bytearray):
    while len(binbuf)%4:binbuf.append(0)
    outroot=copy.deepcopy(root);outroot['buffers']=[{'byteLength':len(binbuf)}]
    jb=json.dumps(outroot,separators=(',',':'),ensure_ascii=False).encode()
    while len(jb)%4:jb+=b' '
    out=bytearray(struct.pack('<4sII',b'glTF',2,12+8+len(jb)+8+len(binbuf)))
    out+=struct.pack('<I4s',len(jb),b'JSON')+jb
    out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
    path.write_bytes(out)

def sampler_key(flags:int):return bool(flags&0x40),bool(flags&0x80)
def sampler_doc(key):return {'magFilter':9729,'minFilter':9987,'wrapS':33071 if key[0] else 10497,'wrapT':33071 if key[1] else 10497}

def build(in_glb:Path, expected_input_sha:str, targets_path:Path, report_path:Path, payload_dir:Path, source_label:str, out_glb:Path, manifest_path:Path, expected_bindings:int, expected_colors:int, expected_normals:int, expected_unique:int, expected_existing_images:int):
    actual=sha_file(in_glb)
    if actual!=expected_input_sha:raise ValueError(f'input SHA {actual} != {expected_input_sha}')
    targets=json.loads(targets_path.read_text());report=json.loads(report_path.read_text())
    root,original_bin=read_glb(in_glb);before=copy.deepcopy(root)
    mats=root.get('materials',[]);meshes=root.get('meshes',[]);nodes=[n for n in root.get('nodes',[]) if 'mesh' in n]
    if (len(mats),len(meshes),len(nodes))!=(EXPECTED_MATERIALS,EXPECTED_MESHES,EXPECTED_INSTANCES):raise ValueError('authoritative scene counts changed')
    existing_images=list(root.get('images',[]));existing_textures=list(root.get('textures',[]));existing_samplers=list(root.get('samplers',[]));existing_bvs=list(root.get('bufferViews',[]))
    if len(existing_images)!=expected_existing_images or len(existing_textures)!=expected_existing_images:raise ValueError('unexpected pre-existing texture tier count')
    exact={r['name']:r for r in report.get('rows',[]) if r.get('status')=='validated'}
    bindings=[r for r in targets.get('bindings',[]) if r['image'] in exact]
    colors=sum(r['gltfRole']=='baseColorTexture' for r in bindings);normals=sum(r['gltfRole']=='normalTexture' for r in bindings);needed=sorted({r['image'] for r in bindings})
    if (len(bindings),colors,normals,len(needed))!=(expected_bindings,expected_colors,expected_normals,expected_unique):raise ValueError(f'promotion boundary mismatch {(len(bindings),colors,normals,len(needed))}')
    if len({(r['material'],r['gltfRole']) for r in bindings})!=len(bindings):raise ValueError('duplicate material/role target')
    existing_names={i.get('name') for i in existing_images}
    overlap=sorted(existing_names & set(needed))
    if overlap:raise ValueError(f'new tier overlaps existing images: {overlap}')
    mat_index={m.get('name'):i for i,m in enumerate(mats)}
    if len(mat_index)!=len(mats):raise ValueError('material names not unique')
    images=root.setdefault('images',[]);textures=root.setdefault('textures',[]);samplers=root.setdefault('samplers',[]);bvs=root.setdefault('bufferViews',[]);binbuf=bytearray(original_bin)
    sampler_cache={}
    for i,s in enumerate(samplers):
        for key in ((False,False),(True,False),(False,True),(True,True)):
            if s==sampler_doc(key):sampler_cache[key]=i
    texture_by_image={};embedded=[]
    for name in needed:
        row=exact[name];png_path=payload_dir/row['pngFile'];png=png_path.read_bytes()
        if len(png)!=int(row['pngBytes']) or sha_bytes(png)!=row['pngSha256']:raise ValueError(f'{name}: PNG proof mismatch')
        while len(binbuf)%4:binbuf.append(0)
        off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_{source_label}_exact_PNG'});bvi=len(bvs)-1
        images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':source_label,'identityResolution':'exact-nameHash+dataHash','nameHash':row['hash'],'dataHash':row['dataHash'],'iwiSha256':row['iwiSha256'],'pngSha256':row['pngSha256'],'crc29Validated':bool(row['crc29Validated']),'iwi27Validated':bool(row['iwi27Validated']),'dimensionsValidated':bool(row['dimensionsValidated']),'width':row['width'],'height':row['height'],'depth':row['depth']}}});ii=len(images)-1
        key=sampler_key(int(row['flags']))
        if key not in sampler_cache:samplers.append(sampler_doc(key));sampler_cache[key]=len(samplers)-1
        textures.append({'name':name,'sampler':sampler_cache[key],'source':ii});texture_by_image[name]=len(textures)-1
        embedded.append({'image':name,'textureIndex':texture_by_image[name],'nameHash':row['hash'],'dataHash':row['dataHash'],'iwiSha256':row['iwiSha256'],'pngSha256':row['pngSha256'],'pngBytes':row['pngBytes']})
    promotions=[]
    for b in bindings:
        name=b['image'];row=exact[name]
        if int(b['aliasHash'])!=int(row['hash']) or int(b['aliasDataHash'])!=int(row['dataHash']):raise ValueError(f"{b['material']}: identity mismatch")
        mi=mat_index.get(b['material'])
        if mi is None:raise ValueError(f"missing material {b['material']}")
        m=mats[mi];ti=texture_by_image[name];role=b['gltfRole']
        if role=='baseColorTexture':
            pbr=m.setdefault('pbrMetallicRoughness',{})
            if pbr.get('baseColorTexture') is not None:raise ValueError(f"{b['material']}: base color already bound")
            pbr['baseColorTexture']={'index':ti,'texCoord':0};pbr['baseColorFactor']=[1.0,1.0,1.0,1.0];kind='color'
        elif role=='normalTexture':
            if m.get('normalTexture') is not None:raise ValueError(f"{b['material']}: normal already bound")
            m['normalTexture']={'index':ti,'texCoord':0,'scale':1.0};kind='normal'
        else:raise ValueError(f'unsupported role {role}')
        proof={'kind':kind,'gltfRole':role,'image':name,'semantic':b['rawSemantic'],'retailTextureIndex':b['textureIndex'],'sourceContainer':source_label,'identityResolution':'exact-nameHash+dataHash','nameHash':row['hash'],'dataHash':row['dataHash'],'iwiSha256':row['iwiSha256'],'pngSha256':row['pngSha256']}
        m.setdefault('extras',{}).setdefault('T6',{}).setdefault('realTextureBindings',[]).append(proof);promotions.append({'materialIndex':mi,'material':b['material'],**proof,'textureIndex':ti})
    # No geometry or already-embedded texture data may change.
    if root['nodes']!=before['nodes'] or root['meshes']!=before['meshes'] or root['accessors']!=before['accessors']:raise ValueError('geometry/placement changed')
    if root['bufferViews'][:len(existing_bvs)]!=existing_bvs:raise ValueError('existing bufferViews changed')
    if root['images'][:len(existing_images)]!=existing_images or root['textures'][:len(existing_textures)]!=existing_textures or root['samplers'][:len(existing_samplers)]!=existing_samplers:raise ValueError('existing texture tier changed')
    if bytes(binbuf[:len(original_bin)])!=original_bin:raise ValueError('input BIN prefix changed')
    if [m.get('name') for m in mats]!=[m.get('name') for m in before['materials']]:raise ValueError('material order changed')
    root.setdefault('extras',{}).setdefault('T6',{})['appendExactTextureTierV1']={'source':source_label,'promotionCount':len(promotions),'colorPromotions':colors,'normalPromotions':normals,'uniqueImages':len(needed)}
    write_glb(out_glb,root,binbuf);check,checkbin=read_glb(out_glb)
    if check['nodes']!=before['nodes'] or check['meshes']!=before['meshes'] or check['accessors']!=before['accessors']:raise ValueError('output geometry regression')
    if checkbin[:len(original_bin)]!=original_bin:raise ValueError('output BIN prefix regression')
    if check.get('images',[])[:len(existing_images)]!=existing_images or check.get('textures',[])[:len(existing_textures)]!=existing_textures:raise ValueError('output prior texture tier regression')
    manifest={'format':'t6-nuketown-static-append-exact-textures-v1','sourceContainer':source_label,'inputGlb':{'file':in_glb.name,'bytes':in_glb.stat().st_size,'sha256':actual},'targets':{'file':targets_path.name,'sha256':sha_file(targets_path)},'payloadReport':{'file':report_path.name,'sha256':sha_file(report_path)},'summary':{'promotionCount':len(promotions),'colorPromotions':colors,'normalPromotions':normals,'uniqueImageCount':len(needed),'existingImageCount':len(existing_images),'outputImageCount':len(check.get('images',[])),'materials':len(mats),'meshDefinitions':len(meshes),'meshInstances':len(nodes)},'embeddedImages':embedded,'promotions':promotions,'validation':{'inputSha':'pass','nodePlacementIdentity':'pass','meshPrimitiveIdentity':'pass','accessorIdentity':'pass','preexistingBufferViewIdentity':'pass','preexistingImageTextureSamplerPrefixIdentity':'pass','inputBinExactPrefix':'pass','materialNameOrderIdentity':'pass','payloadPngSha256':'pass','nameDataHashPairs':'pass','sameNameFallbacks':0,'filenameRoleInference':0},'outputGlb':{'file':out_glb.name,'bytes':out_glb.stat().st_size,'sha256':sha_file(out_glb)}}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');return manifest

def main():
    a=argparse.ArgumentParser();a.add_argument('--glb',type=Path,required=True);a.add_argument('--expected-input-sha',required=True);a.add_argument('--targets',type=Path,required=True);a.add_argument('--payload-report',type=Path,required=True);a.add_argument('--payload-dir',type=Path,required=True);a.add_argument('--source-label',required=True);a.add_argument('--expected-bindings',type=int,required=True);a.add_argument('--expected-colors',type=int,required=True);a.add_argument('--expected-normals',type=int,required=True);a.add_argument('--expected-unique',type=int,required=True);a.add_argument('--expected-existing-images',type=int,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);q=a.parse_args()
    m=build(q.glb,q.expected_input_sha,q.targets,q.payload_report,q.payload_dir,q.source_label,q.out,q.manifest,q.expected_bindings,q.expected_colors,q.expected_normals,q.expected_unique,q.expected_existing_images);print(json.dumps({'summary':m['summary'],'outputGlb':m['outputGlb'],'validation':m['validation']},indent=2))
if __name__=='__main__':main()
