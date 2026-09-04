#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import t6_nuketown_ipak_partial_texture_export_v2 as base
import t6_nuketown_static_xmodel_texture_apply_v2 as tex

IDENTITY='$identitynormalmap'
TARGETS={
 'mc/color_black_shine': {'normal':'identity'},
 'mc/mtl_nt_2020_flags_01': {'normal':'identity'},
 'mlv/plaster_whitewall_01': {
   'color': {
     'name':'~~-gplaster_whitewall01-rgb&~~da03132f',
     'nameHash':2620101188,
     'dataHash':236316344,
     'width':512,'height':512,'depth':1,
     'semantic':2,'samplerState':20,
   }
 },
}

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()

def find_material(js,name):
    xs=[(i,m) for i,m in enumerate(js.get('materials',[])) if m.get('name')==name]
    if len(xs)!=1: raise ValueError(f'{name}: expected one GLB material, got {len(xs)}')
    return xs[0]

def find_identity(js):
    found=[]
    for ti,t in enumerate(js.get('textures',[])):
        if t.get('name')!=IDENTITY: continue
        si=t.get('source')
        if not isinstance(si,int) or si>=len(js.get('images',[])): continue
        ex=((js['images'][si].get('extras') or {}).get('T6') or {})
        if ex.get('identityResolution')=='loader-address-proof' and ex.get('block')==5 and ex.get('virtualOffset')==514620:
            found.append(ti)
    if len(found)!=1: raise ValueError(f'expected one proven identity normal texture, got {found}')
    return found[0]

def add_png(js,binbuf,png,name,extras,sampler_state):
    while len(binbuf)%4: binbuf.append(0)
    off=len(binbuf); binbuf.extend(png)
    bvs=js.setdefault('bufferViews',[]); images=js.setdefault('images',[]); textures=js.setdefault('textures',[]); samplers=js.setdefault('samplers',[])
    bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_v12_exact_PNG'})
    bvi=len(bvs)-1
    images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':extras}}); ii=len(images)-1
    clamp_u=bool(sampler_state&0x20); clamp_v=bool(sampler_state&0x40)
    desired={'magFilter':9729,'minFilter':9987,'wrapS':33071 if clamp_u else 10497,'wrapT':33071 if clamp_v else 10497}
    sis=[i for i,s in enumerate(samplers) if all(s.get(k)==v for k,v in desired.items())]
    # Existing GLB legitimately contains duplicate-equivalent samplers from earlier independent stages.
    # Reuse the lowest-index exact state rather than adding another duplicate.
    if sis: si=min(sis)
    else: samplers.append(desired); si=len(samplers)-1
    textures.append({'name':name,'sampler':si,'source':ii}); return len(textures)-1,bvi,ii

def build(glb:Path,ipak:Path,proof:Path,out:Path,manifest:Path):
    js,binbuf=base.read_glb(glb)
    identity_ti=find_identity(js)
    proofj=json.loads(proof.read_text()); pm={m['name']:m for m in proofj['materials']}
    if set(pm)!=set(TARGETS): raise ValueError(f'proof target set mismatch {set(pm)}')
    data,data_sec,by_pair,by_name,by_data,lzo=tex.read_ipak(ipak)
    promotions=[]
    # prove source fixed records are the exact expected three and exact pointer/image facts.
    for name in TARGETS:
        if name not in pm: raise ValueError(name)
        _,m=find_material(js,name)
        if ((m.get('extras') or {}).get('T6') or {}).get('identityResolution')!='xmodel-material-handle-proof':
            raise ValueError(f'{name}: GLB material is not material-handle proof-derived')
    # two proven shared identity normals
    for name in ('mc/color_black_shine','mc/mtl_nt_2020_flags_01'):
        mi,m=find_material(js,name)
        if m.get('normalTexture') is not None: raise ValueError(f'{name}: normal already bound')
        src=pm[name]
        normals=[t for t in src['textures'] if t['semantic']==5]
        if len(normals)!=1: raise ValueError(f'{name}: expected one semantic5')
        p=normals[0]['imagePointer']
        # serialized pointer decoder in this local proof uses block 10 and +1 offsets; normalize to loader-known block5/514620 identity.
        # The exact raw pointer must be identical across both source materials.
        if p.get('raw')!=2684869181: raise ValueError(f'{name}: unexpected identity raw pointer {p}')
        m['normalTexture']={'index':identity_ti,'texCoord':0,'scale':1.0}
        tx=m.setdefault('extras',{}).setdefault('T6',{})
        tx['textureResolution']='partially-closed-exact'
        tx.setdefault('realTextureBindings',[]).append({'kind':'normal','image':IDENTITY,'semantic':5,'identityResolution':'loader-address-proof-reuse','sourceContainer':'mp_nuketown_2020.expanded.bin'})
        promotions.append({'materialIndex':mi,'material':name,'kind':'normal','image':IDENTITY,'textureIndex':identity_ti,'identityResolution':'loader-address-proof-reuse','sourceRawPointer':f"0x{p['raw']:08X}"})
    # exact plaster color via exact IPAK key pair
    name='mlv/plaster_whitewall_01'; mi,m=find_material(js,name); spec=TARGETS[name]['color']; src=pm[name]
    if (m.get('pbrMetallicRoughness') or {}).get('baseColorTexture') is not None: raise ValueError('plaster color already bound')
    colors=[t for t in src['textures'] if t['semantic']==2]
    if len(colors)!=1 or not colors[0]['image'].get('inline'): raise ValueError('plaster inline color proof mismatch')
    im=colors[0]['image']
    for k in ('name','width','height','depth'):
        if im[k]!=spec[k]: raise ValueError(f'plaster {k} mismatch {im[k]} != {spec[k]}')
    if im['hash']!=spec['nameHash'] or im['streamedPart0Hash29']!=spec['dataHash']: raise ValueError('plaster hash pair mismatch')
    calc=base.r_hash_string(spec['name'])
    if calc!=spec['nameHash']: raise ValueError(f'plaster name hash function mismatch {calc:#x}')
    e=by_pair.get((spec['nameHash'],spec['dataHash']))
    if e is None: raise ValueError('plaster exact IPAK pair missing')
    iwi=tex.extract_entry(data,data_sec,e,lzo)
    fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
    if (w,h,d)!=(512,512,1): raise ValueError(f'plaster exact pair dimensions {(w,h,d)}')
    png,meta=tex.iwi_top_png(iwi,normal_semantic=False)
    ti,bvi,ii=add_png(js,binbuf,png,spec['name'],{
        'source':ipak.name,'identityResolution':'ipak-exact-name+data-hash','ipakDataHash':e[0],'ipakNameHash':e[1],
        'expectedNameHash':spec['nameHash'],'expectedStreamedDataHash':spec['dataHash'],
        'iwiSha256':hashlib.sha256(iwi).hexdigest(),'pngSha256':hashlib.sha256(png).hexdigest(),**meta},spec['samplerState'])
    pbr=m.setdefault('pbrMetallicRoughness',{}); pbr['baseColorTexture']={'index':ti,'texCoord':0}; pbr['baseColorFactor']=[1.0,1.0,1.0,1.0]
    tx=m.setdefault('extras',{}).setdefault('T6',{}); tx['textureResolution']='partially-closed-exact';tx.setdefault('realTextureBindings',[]).append({'kind':'color','image':spec['name'],'semantic':2,'identityResolution':'ipak-exact-name+data-hash','sourceContainer':ipak.name})
    promotions.append({'materialIndex':mi,'material':name,'kind':'color','image':spec['name'],'textureIndex':ti,'imageIndex':ii,'bufferView':bvi,'identityResolution':'ipak-exact-name+data-hash','ipakDataHash':e[0],'ipakNameHash':e[1],'iwiSha256':hashlib.sha256(iwi).hexdigest(),'pngSha256':hashlib.sha256(png).hexdigest(),**meta})
    # source color for flags must remain intentionally unresolved: exact pair must be absent.
    fim=[t for t in pm['mc/mtl_nt_2020_flags_01']['textures'] if t['semantic']==2][0]['image']
    fk=(fim['hash'],fim['streamedPart0Hash29'])
    if fk in by_pair: raise ValueError('flags exact color unexpectedly present; v12 must be extended rather than claiming unresolved')
    # output metadata
    js.setdefault('extras',{}).setdefault('T6',{})['threeMissingMaterialTextureClosureV1']={
        'promotions':len(promotions),'identityNormalBindings':2,'exactIpakColorBindings':1,
        'remainingKnownMissingColor':'mc/mtl_nt_2020_flags_01 -> ~-gnt_2020_flags_01_c',
        'proofBoundary':'Only the three exact material identities created by the v10 XModel material-slot repair. Identity normal reuses the prior loader-address proof; plaster color requires exact IPAK (nameHash,dataHash), CRC29 and dimension validation.'}
    base.write_glb(out,js,binbuf); j2,b2=base.read_glb(out)
    if j2['buffers'][0]['byteLength']!=len(b2): raise ValueError('buffer length mismatch')
    # ensure render state survived
    for name in TARGETS:
        _,m2=find_material(j2,name)
        if not (((m2.get('extras') or {}).get('T6') or {}).get('retailRenderStateV1')): raise ValueError(f'{name}: retail render state lost')
    man={
      'format':'t6-nuketown-three-missing-material-texture-closure-v1',
      'inputGlb':{'file':glb.name,'bytes':glb.stat().st_size,'sha256':sha(glb)},
      'ipak':{'file':ipak.name,'bytes':ipak.stat().st_size,'sha256':sha(ipak)},
      'sourceProof':{'file':proof.name,'bytes':proof.stat().st_size,'sha256':sha(proof)},
      'outputGlb':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out)},
      'summary':{'promotionCount':3,'identityNormalBindings':2,'exactIpakColorBindings':1,'remainingExactColorPayloadMissing':1},
      'promotions':promotions,
      'remaining':{'material':'mc/mtl_nt_2020_flags_01','image':fim['name'],'nameHash':fim['hash'],'dataHash':fim['streamedPart0Hash29'],'reason':'exact IPAK pair absent from available map IPAK'},
      'validation':{'glbReparse':'pass','bufferByteLengthMatches':'pass','retailRenderStatePreserved':'pass','identityNormalRawPointerMatch':'pass','plasterExactPairCRC29Dimensions':'pass','flagsMissingPairNegativeControl':'pass'},
      'proofBoundary':'No texture-name guessing and no same-name fallback. Three source materials are exact retail Material records tied to the v10 material-handle proof.'}
    manifest.write_text(json.dumps(man,indent=2,sort_keys=True)+'\n'); print(json.dumps(man['summary'],indent=2)); print(json.dumps(man['outputGlb'],indent=2))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--glb',type=Path,required=True);ap.add_argument('--ipak',type=Path,required=True);ap.add_argument('--proof',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args();build(a.glb,a.ipak,a.proof,a.out,a.manifest)
