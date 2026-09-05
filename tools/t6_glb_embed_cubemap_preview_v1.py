#!/usr/bin/env python3
"""Embed a retail DDS cubemap into GLB with a derived Blender preview cube.

The original DDS bytes remain lossless source data in one bufferView. Six PNG
faces and six inward-facing quads are derived authoring previews only. The tool
does not claim that the preview cube reproduces the original T6 sky shader.

Expected source is a legacy DDS cubemap with six equal-size faces serialized in
Direct3D face order: +X, -X, +Y, -Y, +Z, -Z.
"""
from __future__ import annotations
import argparse, hashlib, io, json, struct
from pathlib import Path
from PIL import Image

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FACES = ['+X','-X','+Y','-Y','+Z','-Z']

def align4(b: bytearray):
    while len(b) % 4: b.append(0)

def read_glb(path: Path):
    data = path.read_bytes(); magic, ver, total = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF' or ver != 2 or total != len(data): raise ValueError('invalid GLB2')
    o=12; js=None; bb=None
    while o<total:
        n,t=struct.unpack_from('<II',data,o);o+=8;c=data[o:o+n];o+=n
        if t==JSON_CHUNK: js=json.loads(c.rstrip(b' \0\t\r\n'))
        elif t==BIN_CHUNK: bb=bytearray(c)
    if js is None or bb is None: raise ValueError('missing chunks')
    return data,js,bb

def write_glb(path: Path, js, bb: bytearray):
    align4(bb); js['buffers'][0]['byteLength']=len(bb)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode();jb+=b' '*((-len(jb))%4)
    bd=bytes(bb);bd+=b'\0'*((-len(bd))%4)
    total=12+8+len(jb)+8+len(bd)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total));out+=struct.pack('<II',len(jb),JSON_CHUNK)+jb;out+=struct.pack('<II',len(bd),BIN_CHUNK)+bd
    path.write_bytes(out)

def add_accessor(js,bb,vals,typ,component,name):
    comps={'SCALAR':1,'VEC2':2,'VEC3':3}[typ]
    fmt={5126:'f',5123:'H'}[component]; align4(bb); off=len(bb)
    flat=[]
    for v in vals: flat.extend(v if isinstance(v,(list,tuple)) else [v])
    bb.extend(struct.pack('<'+fmt*len(flat),*flat))
    js.setdefault('bufferViews',[]).append({'buffer':0,'byteOffset':off,'byteLength':struct.calcsize('<'+fmt)*len(flat),'name':name})
    a={'bufferView':len(js['bufferViews'])-1,'componentType':component,'count':len(vals),'type':typ,'name':name}
    if typ=='VEC3' and vals:
        a['min']=[min(v[i] for v in vals) for i in range(3)];a['max']=[max(v[i] for v in vals) for i in range(3)]
    js.setdefault('accessors',[]).append(a);return len(js['accessors'])-1

def d3d_face_dir(face,u,v):
    if face=='+X': return (1,-v,-u)
    if face=='-X': return (-1,-v,u)
    if face=='+Y': return (u,1,v)
    if face=='-Y': return (u,-1,-v)
    if face=='+Z': return (u,-v,1)
    return (-u,-v,-1)

def t6_to_gltf_dir(v):
    x,y,z=v; return (x,z,-y)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--dds',type=Path,required=True)
    ap.add_argument('--image-name',required=True)
    ap.add_argument('--retail-material-name')
    ap.add_argument('--radius',type=float,default=3000.0)
    ap.add_argument('--append-to-active-scene',action='store_true')
    ap.add_argument('--report',type=Path)
    a=ap.parse_args()

    in_bytes,js,bb=read_glb(a.input);dds=a.dds.read_bytes()
    if dds[:4]!=b'DDS ': raise ValueError('not DDS')
    width=struct.unpack_from('<I',dds,16)[0];height=struct.unpack_from('<I',dds,12)[0];caps2=struct.unpack_from('<I',dds,112)[0]
    if caps2 & 0x200 == 0: raise ValueError('DDS is not marked as cubemap')
    if (len(dds)-128)%6: raise ValueError('cubemap payload not divisible into six equal faces')
    face_bytes=(len(dds)-128)//6

    align4(bb);raw_off=len(bb);bb.extend(dds);js.setdefault('bufferViews',[]).append({'buffer':0,'byteOffset':raw_off,'byteLength':len(dds),'name':'T6_RETAIL_CUBEMAP_DDS_'+a.image_name});raw_bv=len(js['bufferViews'])-1
    js.setdefault('samplers',[]).append({'magFilter':9729,'minFilter':9729,'wrapS':33071,'wrapT':33071});sampler=len(js['samplers'])-1
    if 'KHR_materials_unlit' not in js.setdefault('extensionsUsed',[]): js['extensionsUsed'].append('KHR_materials_unlit')

    mats=[];face_hashes=[]
    for fi,face in enumerate(FACES):
        hdr=bytearray(dds[:128]);struct.pack_into('<I',hdr,108,0x1000);struct.pack_into('<I',hdr,112,0)
        one=bytes(hdr)+dds[128+fi*face_bytes:128+(fi+1)*face_bytes]
        im=Image.open(io.BytesIO(one));im.load();buf=io.BytesIO();im.convert('RGBA').save(buf,format='PNG',compress_level=1,optimize=False);png=buf.getvalue()
        align4(bb);off=len(bb);bb.extend(png);js['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_CUBEMAP_{face}_PNG'});bv=len(js['bufferViews'])-1
        js.setdefault('images',[]).append({'name':f'{a.image_name}_{face}','bufferView':bv,'mimeType':'image/png','extras':{'T6':{'previewOnly':True,'sourceCubemap':a.image_name,'face':face,'sourceDdsSha256':hashlib.sha256(dds).hexdigest()}}});ii=len(js['images'])-1
        js.setdefault('textures',[]).append({'name':f'{a.image_name}_{face}','source':ii,'sampler':sampler});ti=len(js['textures'])-1
        js.setdefault('materials',[]).append({'name':f'T6_CUBEMAP_PREVIEW_{a.image_name}_{face}','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1,'baseColorTexture':{'index':ti}},'extensions':{'KHR_materials_unlit':{}},'extras':{'T6':{'previewOnly':True,'retailMaterial':a.retail_material_name,'retailCubemap':a.image_name,'face':face}}});mats.append(len(js['materials'])-1);face_hashes.append(hashlib.sha256(png).hexdigest())

    prims=[];R=a.radius
    for fi,face in enumerate(FACES):
        uvs=[(0,0),(1,0),(1,1),(0,1)];verts=[]
        for uu,vv in uvs:
            d=t6_to_gltf_dir(d3d_face_dir(face,2*uu-1,2*vv-1));verts.append(tuple(x*R for x in d))
        # All quads use inward winding.
        idx=[0,2,1,0,3,2]
        pa=add_accessor(js,bb,verts,'VEC3',5126,f'{face}_POSITION');ua=add_accessor(js,bb,uvs,'VEC2',5126,f'{face}_UV');ia=add_accessor(js,bb,idx,'SCALAR',5123,f'{face}_INDEX')
        prims.append({'attributes':{'POSITION':pa,'TEXCOORD_0':ua},'indices':ia,'material':mats[fi],'mode':4,'extras':{'T6':{'previewOnly':True,'cubemapFace':face}}})
    js.setdefault('meshes',[]).append({'name':'T6 Retail Cubemap Preview '+a.image_name,'primitives':prims,'extras':{'T6':{'previewOnly':True,'sourceCubemapDdsBufferView':raw_bv}}});mesh=len(js['meshes'])-1
    js.setdefault('nodes',[]).append({'name':'T6_RETAIL_CUBEMAP_PREVIEW_'+a.image_name,'mesh':mesh,'extras':{'T6':{'previewOnly':True,'sourceCubemapDdsBufferView':raw_bv,'runtimeNote':'Derived Blender preview only; retain original T6 cubemap/shader semantics at runtime.'}}});node=len(js['nodes'])-1
    if a.append_to_active_scene: js['scenes'][int(js.get('scene',0))].setdefault('nodes',[]).append(node)
    else: js.setdefault('scenes',[]).append({'name':'T6 Cubemap Preview '+a.image_name,'nodes':[node],'extras':{'T6':{'previewOnly':True}}})
    write_glb(a.output,js,bb)
    out=a.output.read_bytes();report={'format':'t6-glb-cubemap-preview-v1','inputSha256':hashlib.sha256(in_bytes).hexdigest(),'outputSha256':hashlib.sha256(out).hexdigest(),'sourceDdsSha256':hashlib.sha256(dds).hexdigest(),'sourceDdsBytes':len(dds),'dimensions':[width,height],'caps2Hex':hex(caps2),'faceOrder':FACES,'facePngSha256':face_hashes,'rawDdsBufferView':raw_bv,'previewNode':node,'policy':'original DDS retained losslessly; six face PNGs and cube are authoring previews only'}
    if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
