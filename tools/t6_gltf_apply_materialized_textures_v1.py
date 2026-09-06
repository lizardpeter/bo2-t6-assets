#!/usr/bin/env python3
"""Embed verified materialized T6 texture PNGs into a character GLB.

The native T6 material dependency graph remains in the binding-plan sidecar.
This exporter maps only its explicitly selected glTF visualization baseColor and
normal roles. It does not invent roughness/metalness/specular values or translate
special T6 shader behavior silently.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

class ApplyError(RuntimeError):pass

def sha_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def read_glb(path:Path):
 b=path.read_bytes()
 if len(b)<20:raise ApplyError('GLB too small')
 magic,ver,total=struct.unpack_from('<4sII',b,0)
 if magic!=b'glTF' or ver!=2 or total!=len(b):raise ApplyError('invalid GLB2 header')
 o=12;js=None;bins=[]
 while o<total:
  if o+8>total:raise ApplyError('truncated GLB chunk header')
  n,t=struct.unpack_from('<I4s',b,o);o+=8
  if o+n>total:raise ApplyError('GLB chunk outside file')
  c=b[o:o+n];o+=n
  if t==b'JSON':
   if js is not None:raise ApplyError('multiple JSON chunks')
   js=json.loads(c)
  elif t==b'BIN\0':bins.append(c)
 if js is None or len(bins)!=1:raise ApplyError('expected one JSON and one BIN chunk')
 return js,bytearray(bins[0])
def write_glb(path:Path,js:dict,binbuf:bytearray):
 while len(binbuf)%4:binbuf.append(0)
 if not js.get('buffers'):js['buffers']=[{}]
 js['buffers'][0]={'byteLength':len(binbuf)}
 jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8')
 while len(jb)%4:jb+=b' '
 total=12+8+len(jb)+8+len(binbuf);out=bytearray(struct.pack('<4sII',b'glTF',2,total));out+=struct.pack('<I4s',len(jb),b'JSON')+jb;out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(out)
def load_json(p:Path):return json.loads(p.read_text(encoding='utf-8-sig'))
def png_dims(p:Path):
 b=p.read_bytes()
 if len(b)<24 or b[:8]!=b'\x89PNG\r\n\x1a\n' or b[12:16]!=b'IHDR':raise ApplyError(f'invalid PNG: {p}')
 return struct.unpack_from('>II',b,16)

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--glb',type=Path,required=True);ap.add_argument('--binding-plan',type=Path,required=True);ap.add_argument('--materialized-manifest',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args()
 js,binbuf=read_glb(a.glb);plan=load_json(a.binding_plan);matdoc=load_json(a.materialized_manifest)
 if plan.get('format')!='t6-character-material-binding-plan-v1':raise ApplyError(f'unsupported binding plan {plan.get("format")!r}')
 if matdoc.get('format') not in ('t6-ipak-iwi-materialization-v1','t6-ipak-iwi-materialization-v3'):raise ApplyError(f'unsupported materialization manifest {matdoc.get("format")!r}')
 texrows={r['image']:r for r in matdoc.get('textures',[])}
 if len(texrows)!=len(matdoc.get('textures',[])):raise ApplyError('duplicate materialized image names')
 root=a.materialized_manifest.parent
 for name,r in texrows.items():
  p=root/r['pngFile']
  if not p.is_file():raise ApplyError(f'{name}: PNG missing: {p}')
  if sha_file(p)!=r['pngSha256']:raise ApplyError(f'{name}: PNG SHA-256 mismatch')
  dims=png_dims(p);iwi=r.get('iwi') or {}
  if iwi.get('width') and dims!=(int(iwi['width']),int(iwi['height'])):raise ApplyError(f'{name}: PNG dimensions {dims} != IWI {(iwi.get("width"),iwi.get("height"))}')
 gltf_mats=js.get('materials') or [];name_to_mi={}
 for i,m in enumerate(gltf_mats):
  n=m.get('name')
  if not isinstance(n,str) or not n:raise ApplyError(f'GLB material {i} unnamed')
  if n in name_to_mi:raise ApplyError(f'duplicate GLB material {n}')
  name_to_mi[n]=i
 plan_mats={m['material']:m for m in plan.get('materials',[])};used={r['material'] for r in plan.get('surfaceBindings',[])};missing=sorted(used-set(name_to_mi))
 if missing:raise ApplyError(f'GLB missing plan materials: {missing}')
 bvs=js.setdefault('bufferViews',[]);images=js.setdefault('images',[]);textures=js.setdefault('textures',[]);samplers=js.setdefault('samplers',[]);sampler_cache={};texture_cache={};embedded=[];bindings=[]
 def sampler_for(flags:int):
  key=(bool(flags&0x40),bool(flags&0x80))
  if key in sampler_cache:return sampler_cache[key]
  samplers.append({'magFilter':9729,'minFilter':9987,'wrapS':33071 if key[0] else 10497,'wrapT':33071 if key[1] else 10497,'extras':{'T6':{'iwiClampS':key[0],'iwiClampT':key[1]}}});sampler_cache[key]=len(samplers)-1;return sampler_cache[key]
 def texture_for(name:str,expected_key:dict|None=None):
  if name in texture_cache:
   row=texrows[name]
   if expected_key is not None and (int(row['nameHash'])!=int(expected_key['nameHash']) or (int(row['dataHash'])&0x1fffffff)!=(int(expected_key['dataHash'])&0x1fffffff)):raise ApplyError(f'{name}: cached materialized exact key does not match binding plan')
   return texture_cache[name]
  row=texrows.get(name)
  if row is None:raise ApplyError(f'{name}: not present in materialization manifest')
  if expected_key is not None and (int(row['nameHash'])!=int(expected_key['nameHash']) or (int(row['dataHash'])&0x1fffffff)!=(int(expected_key['dataHash'])&0x1fffffff)):raise ApplyError(f'{name}: materialized exact key does not match binding plan')
  p=root/row['pngFile'];png=p.read_bytes()
  while len(binbuf)%4:binbuf.append(0)
  off=len(binbuf);binbuf.extend(png);bvs.append({'buffer':0,'byteOffset':off,'byteLength':len(png),'name':f'T6_{name}_PNG'});bvi=len(bvs)-1;images.append({'name':name,'bufferView':bvi,'mimeType':'image/png','extras':{'T6':{'retailIwiSha256':row['iwiSha256'],'pngSha256':row['pngSha256'],'nameHash':row['nameHash'],'dataHash':row['dataHash'],'crc29Validated':row.get('crc29Validated'),'exactKeyValidated':row.get('exactKeyValidated'),'sourceRepository':row.get('repository')}}});ii=len(images)-1;flags=int((row.get('iwi') or {}).get('flags',0));si=sampler_for(flags);textures.append({'name':name,'source':ii,'sampler':si});ti=len(textures)-1;texture_cache[name]=ti;embedded.append({'image':name,'textureIndex':ti,'pngBytes':len(png),'pngSha256':row['pngSha256'],'sourceRepository':row.get('repository')});return ti
 for name in sorted(used):
  pm=plan_mats[name];gm=gltf_mats[name_to_mi[name]];v=pm['gltfVisualization'];applied=[];bc=v.get('baseColor')
  if bc:
   ti=texture_for(bc['image'],bc.get('exactStreamKey'));gm.setdefault('pbrMetallicRoughness',{})['baseColorTexture']={'index':ti,'texCoord':0};applied.append({'role':'baseColor','image':bc['image'],'mode':bc['mode'],'textureIndex':ti})
  nm=v.get('normal')
  if nm:
   ti=texture_for(nm['image'],nm.get('exactStreamKey'));gm['normalTexture']={'index':ti,'texCoord':0,'scale':1.0};applied.append({'role':'normal','image':nm['image'],'mode':nm['mode'],'textureIndex':ti})
  ex=gm.setdefault('extras',{}).setdefault('T6',{});ex['nativeMaterialSlots']=pm.get('slots',[]);ex['nativeSlotStructuralFields']=pm.get('nativeSlotStructuralFields');ex['gltfVisualizationMapping']=v;ex['visualPbrTexturesBound']=bool(bc and nm);ex['nativeShaderGraphPreservedInBindingPlan']=True;bindings.append({'material':name,'materialIndex':name_to_mi[name],'shaderApproximation':v.get('shaderApproximation',False),'applied':applied})
 js.setdefault('extras',{}).setdefault('T6',{})['materializedTextureApplyV1']={'bindingPlanSha256':sha_file(a.binding_plan),'materializationManifestSha256':sha_file(a.materialized_manifest),'materializationFormat':matdoc.get('format'),'usedMaterialCount':len(used),'boundMaterialCount':len(bindings),'uniqueEmbeddedPngCount':len(embedded),'nativeShaderGraphPolicy':'PBR visualization fields only; native slots preserved in material extras/binding sidecar'}
 write_glb(a.out,js,binbuf);js2,b2=read_glb(a.out)
 if js2['buffers'][0]['byteLength']!=len(b2):raise ApplyError('output GLB buffer length mismatch')
 outdoc={'format':'t6-gltf-materialized-texture-apply-v1','inputGlb':{'path':str(a.glb),'bytes':a.glb.stat().st_size,'sha256':sha_file(a.glb)},'bindingPlan':{'path':str(a.binding_plan),'sha256':sha_file(a.binding_plan)},'materialization':{'path':str(a.materialized_manifest),'sha256':sha_file(a.materialized_manifest),'format':matdoc.get('format')},'outputGlb':{'path':str(a.out),'bytes':a.out.stat().st_size,'sha256':sha_file(a.out)},'summary':{'usedMaterials':len(used),'boundMaterials':len(bindings),'uniqueEmbeddedPngs':len(embedded),'baseColorBindings':sum(any(x['role']=='baseColor' for x in b['applied']) for b in bindings),'normalBindings':sum(any(x['role']=='normal' for x in b['applied']) for b in bindings),'shaderApproximationMaterials':sum(bool(b['shaderApproximation']) for b in bindings)},'embeddedImages':embedded,'bindings':bindings,'validation':{'glbReparse':True,'bufferByteLengthMatches':True},'proofBoundary':'The source IWI remains authoritative retail pixel data. Embedded PNGs are verified top-mip derivatives. Only binding-plan-selected visualization roles are mapped into standard glTF PBR; native T6 shader slots are retained as metadata.'};a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(outdoc,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(outdoc['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
