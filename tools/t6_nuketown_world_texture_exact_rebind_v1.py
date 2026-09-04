#!/usr/bin/env python3
"""Rebind Nuketown GfxWorld first color/normal textures with exact T6 image identity.

This stage corrects the older name-hash-only preview path. For each retained
world material it resolves the first color/normal image from an inline GfxImage
or an already-proven packed-pointer alias. Streamed IPAK payloads are promoted
as exact only when the retained image identity is uniquely known and the payload
is found by exact (nameHash,dataHash) key, or by a unique dataHash alias with
matching CRC and dimensions. $identitynormalmap is admitted only through the
already-proven FastFile loader-address identity. If the exact payload is absent,
an existing preview binding may remain for user-facing visibility but is marked
explicitly as unverified rather than counted as solved.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
STATIC=HERE/'t6_nuketown_static_xmodel_texture_apply_v2.py'
spec=importlib.util.spec_from_file_location('statictex',STATIC)
st=importlib.util.module_from_spec(spec);spec.loader.exec_module(st)
base=st.base
SEMANTICS=((2,'color'),(5,'normal'))
IDENTITY_BLOCK=5;IDENTITY_OFFSET=514620;IDENTITY_NAME='$identitynormalmap'

def sha_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def generated_components(name):
    if not name.startswith('*') or '(' not in name or not name.endswith(')'):return None
    return name[name.find('(')+1:-1].split(':')

def packed_key(im):
    p=(im or {}).get('pointer') or {}
    if not (im or {}).get('inline') and p.get('kind')=='offset':return (p.get('block'),p.get('offset'))
    return None

def build_component_anchors(mats):
    by={m['name']:m for m in mats};anchors={};conflicts=[];aligned=0
    for m in mats:
        cs=generated_components(m['name'])
        if not cs or not all(c in by for c in cs):continue
        for sem in sorted({t.get('semantic') for t in m.get('textures',[])}):
            g=[t for t in m.get('textures',[]) if t.get('semantic')==sem];c=[]
            for n in cs:c.extend(t for t in by[n].get('textures',[]) if t.get('semantic')==sem)
            if len(g)!=len(c):continue
            aligned+=len(g)
            for a,b in zip(g,c):
                for src,dst in ((a,b),(b,a)):
                    si=src.get('image') or {};di=dst.get('image') or {};k=packed_key(si)
                    n=di.get('name') if di.get('inline') else None
                    if k is None or not n:continue
                    old=anchors.get(k)
                    if old is not None and old!=n:conflicts.append((k,old,n))
                    else:anchors[k]=n
    if conflicts:raise ValueError(f'component anchor conflicts {conflicts[:3]}')
    return anchors,aligned

def load_order_map(path):
    d=json.loads(path.read_text());out={}
    for r in d.get('promotions',[]):
        k=(r['block'],r['virtualOffset']);n=r['image']
        if k in out and out[k]!=n:raise ValueError('order-map conflict')
        out[k]=n
    return out

def global_image_identities(world_mats,static_doc):
    ids=collections.defaultdict(set)
    def add(im):
        if not (im or {}).get('inline') or not im.get('name'):return
        dh=im.get('streamedPart0Hash29');nh=im.get('hash')
        dims=(im.get('width'),im.get('height'),im.get('depth'))
        ids[im['name']].add((nh,dh,dims))
    for m in world_mats:
        for t in m.get('textures',[]):add(t.get('image') or {})
    for m in static_doc.get('materials',[]):
        for t in m.get('textures',[]):add(t.get('image') or {})
    amb={n:sorted(v,key=str) for n,v in ids.items() if len(v)>1}
    if amb:raise ValueError(f'ambiguous GfxImage identities: {list(amb.items())[:3]}')
    return {n:next(iter(v)) for n,v in ids.items() if v}

def first_sem(m,sem):return next((t for t in m.get('textures',[]) if t.get('semantic')==sem),None)

def resolve_image(t,anchors,order_map,ids):
    if not t:return None,'semantic-absent'
    im=t.get('image') or {}
    if im.get('inline') and im.get('name'):return im,'inline'
    k=packed_key(im)
    if not k:return None,'unresolved'
    if k==(IDENTITY_BLOCK,IDENTITY_OFFSET):return {'name':IDENTITY_NAME,'identityNormal':True},'identitynormal'
    n=anchors.get(k) or order_map.get(k)
    if not n:return None,'packed-unresolved'
    ident=ids.get(n)
    if not ident:return None,'packed-name-no-identity'
    nh,dh,dims=ident
    return {'name':n,'hash':nh,'streamedPart0Hash29':dh,'width':dims[0],'height':dims[1],'depth':dims[2],'inline':False,'resolvedPackedPointer':{'block':k[0],'offset':k[1]}},'packed-anchor'

def existing_identity_texture(js):
    found=[]
    for ti,t in enumerate(js.get('textures',[])):
        if t.get('name')!=IDENTITY_NAME:continue
        si=t.get('source')
        if not isinstance(si,int) or si>=len(js.get('images',[])):continue
        ex=((js['images'][si].get('extras') or {}).get('T6') or {})
        if ex.get('identityResolution')=='loader-address-proof' and ex.get('block')==IDENTITY_BLOCK and ex.get('virtualOffset')==IDENTITY_OFFSET:found.append(ti)
    if len(found)!=1:raise ValueError(f'identity texture count {found}')
    return found[0]

def current_binding(g,kind):
    if kind=='color':return (g.get('pbrMetallicRoughness') or {}).get('baseColorTexture')
    return g.get('normalTexture')

def bind(g,kind,ti):
    if kind=='color':
        p=g.setdefault('pbrMetallicRoughness',{});p['baseColorTexture']={'index':ti,'texCoord':0};p['baseColorFactor']=[1,1,1,1]
    else:g['normalTexture']={'index':ti,'texCoord':0,'scale':1.0}

def build(glb,world_path,static_path,order_path,ipak_path,out,manifest):
    world=json.loads(world_path.read_text())['materials'];by={m['name']:m for m in world};static_doc=json.loads(static_path.read_text())
    anchors,aligned=build_component_anchors(world);order=load_order_map(order_path);anchors.update({k:v for k,v in order.items() if k not in anchors})
    ids=global_image_identities(world,static_doc)
    js,binbuf=base.read_glb(glb);data,data_sec,by_pair,by_name,by_data,lzo=st.read_ipak(ipak_path);identity_ti=existing_identity_texture(js)
    cache={};stats=collections.Counter();rows=[]
    # Helpers copied from static stage's exact decode/write path.
    images=js.setdefault('images',[]);textures=js.setdefault('textures',[]);samplers=js.setdefault('samplers',[]);bvs=js.setdefault('bufferViews',[]);sampler_cache={}
    def sampler_for(flags):
        key=(bool(flags&0x40),bool(flags&0x80))
        if key in sampler_cache:return sampler_cache[key]
        samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':33071 if key[0] else 10497,'wrapT':33071 if key[1] else 10497});sampler_cache[key]=len(samplers)-1;return sampler_cache[key]
    def add_payload(name,im,e,resolution):
        key=(name,e[0])
        if key in cache:return cache[key],resolution+'-reuse'
        iwi=st.extract_entry(data,data_sec,e,lzo);fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
        if (w,h,d)!=(im['width'],im['height'],im['depth']):raise ValueError(f'{name}: dimensions {(w,h,d)} != {(im["width"],im["height"],im["depth"])}')
        png,meta=st.iwi_top_png(iwi,normal_semantic=False)
        # normal callers re-decode below because BC5 needs reconstructed Z
        while len(binbuf)%4:binbuf.append(0)
        off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_world_exact_PNG'});bvi=len(bvs)-1
        images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':ipak_path.name,'identityResolution':resolution,'ipakDataHash':e[0],'ipakNameHash':e[1],'expectedNameHash':im.get('hash'),'expectedStreamedDataHash':im.get('streamedPart0Hash29'),'iwiSha256':hashlib.sha256(iwi).hexdigest(),'pngSha256':hashlib.sha256(png).hexdigest(),**meta}}});ii=len(images)-1;si=sampler_for(meta['flags']);textures.append({'name':name,'sampler':si,'source':ii});ti=len(textures)-1;cache[key]=(ti,iwi,e,meta);return cache[key],resolution
    # Need material names present in GLB, not all 327 catalog entries.
    for mi,g in enumerate(js.get('materials',[])):
        src=by.get(g.get('name'))
        if not src:continue
        for sem,kind in SEMANTICS:
            t=first_sem(src,sem);im,state=resolve_image(t,anchors,order,ids);old=current_binding(g,kind)
            if state=='semantic-absent':stats[(kind,'semantic-absent')]+=1;continue
            if im is None:
                stats[(kind,state)]+=1
                if old is not None:g.setdefault('extras',{}).setdefault('T6',{}).setdefault('previewUnverifiedBindings',[]).append({'kind':kind,'reason':state,'previousBindingRetained':True})
                continue
            if state=='identitynormal':
                bind(g,kind,identity_ti);resolution='fastfile-identitynormal';stats[(kind,'exact-content-bound')]+=1
            else:
                name=im['name'];nh=im.get('hash') if im.get('hash') is not None else base.r_hash_string(name);dh=im.get('streamedPart0Hash29')
                if dh is None:
                    stats[(kind,'identity-known/no-local-payload')]+=1
                    if old is not None:g.setdefault('extras',{}).setdefault('T6',{}).setdefault('previewUnverifiedBindings',[]).append({'kind':kind,'reason':'missing-streamed-data-hash','previousBindingRetained':True})
                    continue
                e=by_pair.get((nh,dh));resolution='ipak-exact-name+data-hash'
                if e is None:
                    aliases=by_data.get(dh,[])
                    if len(aliases)==1:
                        e=aliases[0];resolution='ipak-unique-data-hash-alias'
                    else:
                        stats[(kind,'identity-known/no-local-payload')]+=1
                        if old is not None:g.setdefault('extras',{}).setdefault('T6',{}).setdefault('previewUnverifiedBindings',[]).append({'kind':kind,'reason':'exact-payload-absent','previousBindingRetained':True,'expectedDataHash':dh})
                        continue
                key=(name,e[0],kind)
                if key in cache:ti=cache[key][0]
                else:
                    iwi=st.extract_entry(data,data_sec,e,lzo);fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
                    if (w,h,d)!=(im['width'],im['height'],im['depth']):raise ValueError(f'{name}: exact-content dimensions mismatch')
                    png,meta=st.iwi_top_png(iwi,normal_semantic=(kind=='normal'))
                    while len(binbuf)%4:binbuf.append(0)
                    off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_world_exact_{kind}_PNG'});bvi=len(bvs)-1
                    images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':ipak_path.name,'identityResolution':resolution,'ipakDataHash':e[0],'ipakNameHash':e[1],'expectedNameHash':nh,'expectedStreamedDataHash':dh,'iwiSha256':hashlib.sha256(iwi).hexdigest(),'pngSha256':hashlib.sha256(png).hexdigest(),**meta}}});ii=len(images)-1;si=sampler_for(meta['flags']);textures.append({'name':name,'sampler':si,'source':ii});ti=len(textures)-1;cache[key]=(ti,iwi,e,meta)
                bind(g,kind,ti);stats[(kind,'exact-content-bound')]+=1
            g.setdefault('extras',{}).setdefault('T6',{}).setdefault('worldExactBindings',[]).append({'kind':kind,'semantic':sem,'image':im.get('name'),'identityResolution':resolution})
            rows.append({'materialIndex':mi,'material':g.get('name'),'kind':kind,'image':im.get('name'),'resolution':resolution})
    js.setdefault('extras',{}).setdefault('T6',{})['worldTextureExactRebindV1']={'anchors':len(anchors),'uniqueImageIdentities':len(ids),'newPayloads':len(cache),'summary':{f'{a}:{b}':n for (a,b),n in stats.items()},'proofBoundary':'World first semantic textures are exact only on proven image identity plus exact IPAK pair or unique dataHash alias with CRC/dimensions, or the loader-address-proven identity normal. Existing old preview bindings are retained only when exact content is unavailable and are explicitly marked unverified.'}
    base.write_glb(out,js,binbuf);j2,b2=base.read_glb(out)
    if j2['buffers'][0]['byteLength']!=len(b2):raise ValueError('GLB buffer mismatch')
    man={'format':'t6-nuketown-world-texture-exact-rebind-v1','inputGlb':{'file':glb.name,'bytes':glb.stat().st_size,'sha256':sha_file(glb)},'worldCatalog':{'file':world_path.name,'sha256':sha_file(world_path)},'staticCatalog':{'file':static_path.name,'sha256':sha_file(static_path)},'orderMap':{'file':order_path.name,'sha256':sha_file(order_path)},'ipak':{'file':ipak_path.name,'bytes':ipak_path.stat().st_size,'sha256':sha_file(ipak_path)},'outputGlb':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha_file(out)},'summary':{'anchors':len(anchors),'uniqueImageIdentities':len(ids),'newPayloads':len(cache),**{f'{a}:{b}':n for (a,b),n in stats.items()}},'bindings':rows,'validation':{'glbReparse':'pass','bufferByteLengthMatches':'pass'},'proofBoundary':'Exact/preview distinction is preserved; old preview bindings are never counted as exact.'};manifest.write_text(json.dumps(man,indent=2,sort_keys=True)+'\n');return man

def main():
    a=argparse.ArgumentParser();a.add_argument('--glb',type=Path,required=True);a.add_argument('--world',type=Path,required=True);a.add_argument('--static',type=Path,required=True);a.add_argument('--order-map',type=Path,required=True);a.add_argument('--ipak',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);q=a.parse_args();m=build(q.glb,q.world,q.static,q.order_map,q.ipak,q.out,q.manifest);print(json.dumps(m['summary'],indent=2));print(json.dumps(m['outputGlb'],indent=2))
if __name__=='__main__':main()
