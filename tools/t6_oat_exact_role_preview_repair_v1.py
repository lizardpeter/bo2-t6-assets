#!/usr/bin/env python3
"""Repair portable glTF preview bindings from exact OAT texture role names.

Some T6 techniques expose multiple textures under the same broad OAT semantic.
For portable preview, the shader argument/role name can be more specific than the
broad semantic (for example Normal_Map may be emitted with semantic colorMap).

This map-agnostic stage only changes an existing binding when one exact canonical
OAT role resolves uniquely:
  base color: colorMap, else Diffuse_Map/DiffuseMap
  normal: normalMap/Normal_Map
It never chooses by image filename and never touches layered/generated materials.
"""
from __future__ import annotations
import argparse, hashlib, io, json, struct, zipfile
from pathlib import Path
from PIL import Image
import numpy as np

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(p.read_bytes())

def read_glb(path):
    b=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b): raise ValueError('invalid GLB2')
    o=12; js=None; bins=[]
    while o<total:
        n,t=struct.unpack_from('<I4s',b,o);o+=8;c=b[o:o+n];o+=n
        if t==b'JSON':js=json.loads(c)
        elif t==b'BIN\0':bins.append(c)
    if js is None or len(bins)!=1:raise ValueError('expected JSON + one BIN')
    return js,bytearray(bins[0])

def write_glb(path,js,binbuf):
    while len(binbuf)%4:binbuf.append(0)
    js['buffers'][0]['byteLength']=len(binbuf)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode();jb+=b' '*((-len(jb))%4)
    total=12+8+len(jb)+8+len(binbuf)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total));out+=struct.pack('<I4s',len(jb),b'JSON')+jb;out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
    path.write_bytes(out)

def sampler_key(st):
    st=st or {};return(bool(st.get('clampU')),bool(st.get('clampV')),st.get('filter'),st.get('mipMap'))
def sampler_obj(st):
    st=st or {};f=st.get('filter','linear');m=st.get('mipMap','linear')
    mag=9728 if f=='nearest' else 9729
    minf=9728 if f=='nearest' and m=='disabled' else 9729 if m=='disabled' else 9984 if f=='nearest' else 9987
    return {'magFilter':mag,'minFilter':minf,'wrapS':33071 if st.get('clampU') else 10497,'wrapT':33071 if st.get('clampV') else 10497}

def dds_png(dds,normal):
    im=Image.open(io.BytesIO(dds));im.load();arr=np.asarray(im.convert('RGBA')).copy();recon=False
    if normal and int(arr[...,2].max())<=2:
        x=arr[...,0].astype(np.float32)/127.5-1.;y=arr[...,1].astype(np.float32)/127.5-1.;z=np.sqrt(np.maximum(0.,1.-x*x-y*y));arr[...,2]=np.clip(np.rint((z*.5+.5)*255),0,255).astype(np.uint8);arr[...,3]=255;recon=True
    out=io.BytesIO();Image.fromarray(arr,'RGBA').save(out,format='PNG',compress_level=1,optimize=False)
    return out.getvalue(),recon

def role_name(t):return str(t.get('name') or '').replace('-','_').lower()
def choose_roles(doc):
    ts=doc.get('textures',[])
    exact_color=[t for t in ts if role_name(t)=='colormap']
    exact_diff=[t for t in ts if role_name(t) in ('diffuse_map','diffusemap')]
    exact_norm=[t for t in ts if role_name(t) in ('normalmap','normal_map')]
    color=exact_color[0] if len(exact_color)==1 else exact_diff[0] if len(exact_diff)==1 else None
    normal=exact_norm[0] if len(exact_norm)==1 else None
    return color,normal

def build(inp,archive,out,manifest):
    js,binbuf=read_glb(inp);z=zipfile.ZipFile(archive)
    material_paths={};image_paths={}
    for original in z.namelist():
        n=original.replace('\\','/')
        if n.startswith('oat_dump/materials/') and n.endswith('.json'):material_paths[n[len('oat_dump/materials/'):-5]]=original
        elif n.startswith('oat_dump/images/') and n.lower().endswith('.dds'):image_paths[n[len('oat_dump/images/'):-4]]=original
    images=js.setdefault('images',[]);textures=js.setdefault('textures',[]);samplers=js.setdefault('samplers',[]);bvs=js.setdefault('bufferViews',[])
    samp_cache={};tex_cache={};changes=[];missing=[]
    def ensure(image,role,st,normal):
        key=(image,normal,sampler_key(st))
        if key in tex_cache:return tex_cache[key]
        for ti,t in enumerate(textures):
            if t.get('name')!=image:continue
            si=t.get('source')
            if not isinstance(si,int) or si>=len(images):continue
            ex=((images[si].get('extras') or {}).get('T6') or {})
            sem=ex.get('semantic')
            if (normal and sem in ('normalMap','Normal_Map')) or (not normal and sem in ('colorMap','Diffuse_Map')):
                tex_cache[key]=ti;return ti
        zp=image_paths.get(image)
        if not zp:return None
        dds=z.read(zp);png,recon=dds_png(dds,normal)
        while len(binbuf)%4:binbuf.append(0)
        off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_OAT_ROLE_{image}_PNG'});bvi=len(bvs)-1
        images.append({'name':image,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'sourceArchive':archive.name,'sourceDDS':zp.replace('\\','/'),'sourceDdsSha256':sha_bytes(dds),'pngSha256':sha_bytes(png),'semantic':role,'roleBasedPreview':True,'normalZReconstructed':recon}}});ii=len(images)-1
        sk=sampler_key(st)
        if sk not in samp_cache:samplers.append(sampler_obj(st));samp_cache[sk]=len(samplers)-1
        textures.append({'name':image,'source':ii,'sampler':samp_cache[sk]});ti=len(textures)-1;tex_cache[key]=ti;return ti
    def bound_name(binding):
        if not binding:return None
        ti=binding.get('index')
        if not isinstance(ti,int) or ti>=len(textures):return None
        si=textures[ti].get('source')
        return images[si].get('name') if isinstance(si,int) and si<len(images) else None
    for mi,m in enumerate(js.get('materials',[])):
        name=m.get('name','')
        if name.startswith('*') or name not in material_paths:continue
        doc=json.loads(z.read(material_paths[name]).decode());color,normal=choose_roles(doc)
        for target,t,normal_flag in (('baseColorTexture',color,False),('normalTexture',normal,True)):
            if t is None:continue
            image=t.get('image');role=t.get('name') or t.get('semantic');ti=ensure(image,role,t.get('samplerState'),normal_flag)
            if ti is None:
                missing.append({'materialIndex':mi,'material':name,'target':target,'role':role,'image':image});continue
            old=(m.get('pbrMetallicRoughness') or {}).get('baseColorTexture') if not normal_flag else m.get('normalTexture')
            old_name=bound_name(old)
            if old_name==image:continue
            if not normal_flag:
                p=m.setdefault('pbrMetallicRoughness',{});p['baseColorTexture']={'index':ti,'texCoord':0};p['baseColorFactor']=[1.,1.,1.,1.]
            else:m['normalTexture']={'index':ti,'texCoord':0,'scale':1.0}
            m.setdefault('extras',{}).setdefault('T6',{}).setdefault('oatRolePreviewRepairV1',[]).append({'target':target,'exactOatRole':role,'image':image,'previousImage':old_name})
            changes.append({'materialIndex':mi,'material':name,'target':target,'exactOatRole':role,'previousImage':old_name,'image':image})
    js.setdefault('extras',{}).setdefault('T6',{})['oatExactRolePreviewRepairV1']={'changes':len(changes),'missingExactRolePayloads':len(missing),'policy':'exact OAT shader-role names only; generated/layered materials untouched; no image filename inference'}
    write_glb(out,js,binbuf);j2,b2=read_glb(out)
    if j2['buffers'][0]['byteLength']!=len(b2):raise ValueError('buffer mismatch')
    doc={'format':'t6-oat-exact-role-preview-repair-v1','input':{'file':inp.name,'bytes':inp.stat().st_size,'sha256':sha_file(inp)},'archive':{'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha_file(archive)},'output':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha_file(out)},'summary':{'bindingChanges':len(changes),'missingExactRolePayloads':len(missing)},'changes':changes,'missing':missing,'validation':{'glbReparse':'pass','bufferByteLengthMatches':'pass'},'proofBoundary':'Portable preview repair from exact OAT shader role names only. No filename classification and no layered shader blend invention.'}
    manifest.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2));print(json.dumps(changes,indent=2));print(json.dumps(doc['output'],indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--glb',type=Path,required=True);ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args();build(a.glb,a.archive,a.out,a.manifest)
