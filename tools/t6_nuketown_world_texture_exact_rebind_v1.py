#!/usr/bin/env python3
"""Rebind Nuketown GfxWorld first-layer textures using exact retail IPAK identity.

Exact streamed payloads require the T6 key pair (GfxImage.hash,
GfxImage.streamedParts[0].hash).  A unique data-hash-only alias is admitted as
exact-content evidence only after CRC and dimension validation.  Missing or
unresolved payloads retain the prior preview binding but are explicitly marked
unverified; they are not counted as exact.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
SBASE=HERE/'t6_nuketown_static_xmodel_texture_apply_v2.py'
spec=importlib.util.spec_from_file_location('staticv2',SBASE);sv=importlib.util.module_from_spec(spec);spec.loader.exec_module(sv)
base=sv.base
IDENTITY=(5,514620);IDENTITY_NAME='$identitynormalmap'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def first_sem(m,sem): return next((t for t in m.get('textures',[]) if t.get('semantic')==sem),None)
def pkey(im):
    p=(im or {}).get('pointer') or {}
    if not (im or {}).get('inline') and p.get('kind')=='offset': return (p.get('block'),p.get('offset'))
    return None

def compounds(name):
    if not name.startswith('*') or '(' not in name or not name.endswith(')'):return None
    return name[name.find('(')+1:-1].split(':')

def build_anchors(world):
    wb={m['name']:m for m in world};anchors={};conf=[]
    for m in world:
        cs=compounds(m['name'])
        if not cs or not all(c in wb for c in cs):continue
        for sem in sorted({t.get('semantic') for t in m.get('textures',[])}):
            gen=[t for t in m.get('textures',[]) if t.get('semantic')==sem];cc=[]
            for c in cs:cc.extend(t for t in wb[c].get('textures',[]) if t.get('semantic')==sem)
            if len(gen)!=len(cc):continue
            for g,e in zip(gen,cc):
                for a,b in ((g,e),(e,g)):
                    ai=a.get('image') or {};bi=b.get('image') or {};k=pkey(ai);n=bi.get('name') if bi.get('inline') else None
                    if not k or not n:continue
                    if k in anchors and anchors[k]!=n:conf.append((k,anchors[k],n))
                    else:anchors[k]=n
    if conf:raise ValueError(f'component anchor conflicts: {conf[:3]}')
    return anchors

def global_image_meta(stream,world,static):
    meta=collections.defaultdict(set)
    def add(im):
        if not(im.get('inline') and im.get('name') and im.get('streaming') and im.get('streamedPartCount')):return
        s=im.get('start')
        dh=(struct.unpack_from('<I',stream,s+40)[0]&0x1fffffff) if s is not None else im.get('streamedPart0Hash29')
        meta[im['name']].add((im.get('hash'),dh,(im.get('width'),im.get('height'),im.get('depth'))))
    for m in world:
        for t in m.get('textures',[]):add(t.get('image') or {})
    for m in static:
        if m.get('status')=='located':
            for t in m.get('textures',[]):add(t.get('image') or {})
    bad={n:v for n,v in meta.items() if len(v)>1}
    if bad:raise ValueError(f'ambiguous global image identities: {list(bad.items())[:3]}')
    return {n:next(iter(v)) for n,v in meta.items()}

def exact_existing_texture(js,name,dh):
    found=[]
    for ti,t in enumerate(js.get('textures',[])):
        if t.get('name')!=name:continue
        si=t.get('source')
        if not isinstance(si,int) or si>=len(js.get('images',[])):continue
        ex=((js['images'][si].get('extras') or {}).get('T6') or {})
        if ex.get('ipakDataHash')==dh or ex.get('expectedStreamedDataHash')==dh or ex.get('streamedPartHash29')==dh:
            found.append(ti)
    return found[0] if found else None

def identity_texture(js):
    found=[]
    for ti,t in enumerate(js.get('textures',[])):
        if t.get('name')!=IDENTITY_NAME:continue
        si=t.get('source');ex=((js['images'][si].get('extras') or {}).get('T6') or {}) if isinstance(si,int) and si<len(js.get('images',[])) else {}
        if ex.get('identityResolution')=='loader-address-proof' and ex.get('block')==5 and ex.get('virtualOffset')==514620:found.append(ti)
    if len(found)!=1:raise ValueError(f'expected one proven identity texture, got {found}')
    return found[0]

def build(glb,world_path,static_path,order_path,stream_path,ipak_path,out,manifest):
    world=json.loads(world_path.read_text())['materials'];wb={m['name']:m for m in world};static=json.loads(static_path.read_text())['materials'];stream=stream_path.read_bytes()
    anchors=build_anchors(world)
    order=json.loads(order_path.read_text())
    for k,v in order.items():
        key=(5,int(k));name=v['image']
        if key in anchors and anchors[key]!=name:raise ValueError(f'order/component conflict {key}')
        anchors[key]=name
    meta=global_image_meta(stream,world,static)
    js,binbuf=base.read_glb(glb);identity_ti=identity_texture(js)
    data,data_sec,by_pair,by_name,by_data,lzo=sv.read_ipak(ipak_path)
    images=js.setdefault('images',[]);textures=js.setdefault('textures',[]);samplers=js.setdefault('samplers',[]);bvs=js.setdefault('bufferViews',[])
    cache={};sampler_cache={};rows=[];counts=collections.Counter();new_payloads=0
    def sampler_for(flags):
        key=(bool(flags&0x40),bool(flags&0x80))
        if key in sampler_cache:return sampler_cache[key]
        samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':33071 if key[0] else 10497,'wrapT':33071 if key[1] else 10497});sampler_cache[key]=len(samplers)-1;return sampler_cache[key]
    def resolve(m,sem):
        t=first_sem(m,sem)
        if not t:return {'state':'semantic-absent','texture':None}
        im=t.get('image') or {}
        if im.get('inline') and im.get('name'):
            s=im['start'];return {'state':'identity-known','texture':t,'name':im['name'],'nh':im['hash'],'dh':struct.unpack_from('<I',stream,s+40)[0]&0x1fffffff,'dims':(im['width'],im['height'],im['depth']),'sourceKind':'inline'}
        k=pkey(im)
        if sem==5 and k==IDENTITY:return {'state':'identitynormal','texture':t,'name':IDENTITY_NAME,'ptr':k}
        name=anchors.get(k)
        if not name:return {'state':'packed-unresolved','texture':t,'ptr':k}
        ident=meta.get(name)
        if not ident:return {'state':'anchor-name-no-inline-identity','texture':t,'name':name,'ptr':k}
        nh,dh,dims=ident;return {'state':'identity-known','texture':t,'name':name,'nh':nh,'dh':dh,'dims':dims,'sourceKind':'packed-anchor','ptr':k}
    def ensure_payload(r,sem):
        nonlocal new_payloads
        if r['state']=='identitynormal':return identity_ti,'fastfile-identitynormal',None
        if r['state']!='identity-known':return None,None,None
        name,nh,dh,dims=r['name'],r['nh'],r['dh'],r['dims'];entry=by_pair.get((nh,dh));resolution='ipak-exact-pair'
        if entry is None:
            al=by_data.get(dh,[])
            if len(al)!=1:return None,None,None
            entry=al[0];resolution='ipak-unique-data-hash-alias'
        iwi=sv.extract_entry(data,data_sec,entry,lzo);fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
        if (w,h,d)!=tuple(dims):raise ValueError(f'{name}: exact-content dimensions mismatch {(w,h,d)} != {dims}')
        ti=exact_existing_texture(js,name,dh)
        if ti is not None:return ti,'reuse-'+resolution,entry
        key=(name,sem,entry[0])
        if key in cache:return cache[key],resolution,entry
        png,md=sv.iwi_top_png(iwi,normal_semantic=(sem==5));iwi_sha=hashlib.sha256(iwi).hexdigest();png_sha=hashlib.sha256(png).hexdigest()
        while len(binbuf)%4:binbuf.append(0)
        off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_world_exact_PNG'});bvi=len(bvs)-1
        images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'source':ipak_path.name,'identityResolution':resolution,'ipakDataHash':entry[0],'ipakNameHash':entry[1],'expectedImageHash':nh,'expectedStreamedDataHash':dh,'iwiSha256':iwi_sha,'pngSha256':png_sha,**md}}});ii=len(images)-1;si=sampler_for(md['flags']);textures.append({'name':name,'sampler':si,'source':ii});ti=len(textures)-1;cache[key]=ti;new_payloads+=1;return ti,resolution,entry
    for mi,g in enumerate(js.get('materials',[])):
        m=wb.get(g.get('name'))
        if not m:continue
        for sem,kind in ((2,'color'),(5,'normal')):
            r=resolve(m,sem);ti,resolution,entry=ensure_payload(r,sem)
            old=((g.get('pbrMetallicRoughness') or {}).get('baseColorTexture') if kind=='color' else g.get('normalTexture'))
            if ti is not None:
                if kind=='color':
                    p=g.setdefault('pbrMetallicRoughness',{});p['baseColorTexture']={'index':ti,'texCoord':0};p['baseColorFactor']=[1.0,1.0,1.0,1.0]
                else:g['normalTexture']={'index':ti,'texCoord':0,'scale':1.0}
                status='exact-content-bound';counts[(kind,status)]+=1
                g.setdefault('extras',{}).setdefault('T6',{})[f'{kind}ExactWorldV1']={'image':r.get('name'),'identityResolution':resolution,'expectedDataHash':r.get('dh'),'runtimeKeyExact':('exact-pair' in resolution or resolution=='fastfile-identitynormal')}
            else:
                status='preview-retained-unverified' if old else r['state'];counts[(kind,status)]+=1
                if old:g.setdefault('extras',{}).setdefault('T6',{})[f'{kind}LegacyPreviewStatus']='retained-unverified-no-exact-payload-in-local-ipak'
            rows.append({'materialIndex':mi,'material':g.get('name'),'kind':kind,'resolutionState':r['state'],'image':r.get('name'),'expectedNameHash':r.get('nh'),'expectedDataHash':r.get('dh'),'bindingStatus':status,'bindingResolution':resolution,'oldTextureIndex':old.get('index') if old else None,'newTextureIndex':ti})
    js.setdefault('extras',{}).setdefault('T6',{})['worldTextureExactRebindV1']={'anchors':len(anchors),'globalUniqueImageIdentities':len(meta),'newPayloads':new_payloads,'proofBoundary':'Exact first-layer GfxWorld rebind. Runtime-exact IPAK pair preferred; unique data-hash alias accepted only as exact-content after CRC/dimension checks. Missing/unresolved entries preserve prior preview binding but are explicitly unverified.'}
    base.write_glb(out,js,binbuf);js2,bin2=base.read_glb(out)
    if js2['buffers'][0]['byteLength']!=len(bin2):raise ValueError('GLB buffer mismatch')
    doc={'format':'t6-nuketown-world-texture-exact-rebind-v1','input':{'file':glb.name,'bytes':glb.stat().st_size,'sha256':sha(glb)},'output':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out)},'inputs':{'worldCatalog':{'file':world_path.name,'sha256':sha(world_path)},'staticCatalog':{'file':static_path.name,'sha256':sha(static_path)},'orderMap':{'file':order_path.name,'sha256':sha(order_path)},'expandedStream':{'file':stream_path.name,'sha256':sha(stream_path)},'ipak':{'file':ipak_path.name,'sha256':sha(ipak_path)}},'summary':{'anchors':len(anchors),'uniqueImageIdentities':len(meta),'newPayloads':new_payloads,'counts':{f'{k[0]}:{k[1]}':v for k,v in counts.items()}},'rows':rows,'proofBoundary':'Exact runtime IPAK key pair or unique exact-content data-hash alias with CRC+dimension validation. Unavailable/unresolved world bindings are retained only as preview and marked unverified.'}
    manifest.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');return doc

def main():
    a=argparse.ArgumentParser();a.add_argument('--glb',type=Path,required=True);a.add_argument('--world',type=Path,required=True);a.add_argument('--static',type=Path,required=True);a.add_argument('--order',type=Path,required=True);a.add_argument('--stream',type=Path,required=True);a.add_argument('--ipak',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--manifest',type=Path,required=True);q=a.parse_args();d=build(q.glb,q.world,q.static,q.order,q.stream,q.ipak,q.out,q.manifest);print(json.dumps(d['summary'],indent=2));print(json.dumps(d['output'],indent=2))
if __name__=='__main__':main()
