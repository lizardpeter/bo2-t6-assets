#!/usr/bin/env python3
"""Compile exact T6 character material/image identities into a glTF binding plan.

Inputs remain independently authoritative. This compiler only joins evidence:
- MaterialTextureDef slots from expanded retail material serialization;
- exact XAsset-header and MaterialTextureDef VIRTUAL alias proofs;
- exact comma-import -> full GfxImage resolution;
- exact streamed (nameHash,dataHash) extraction targets;
- XModel surface->material assignments from the retained character proof.

The T6 shader graph is not collapsed into PBR silently. Standard Diffuse_Map and
Normal_Map slots are selected when their exact slot-name hashes are present.
Special shaders are retained with all dependencies and any fallback glTF binding
is explicitly marked visualization-only.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

DIFFUSE_HASH=0xF039EC2D
NORMAL_HASH=0x942CBFF0
SPEC_GLOSS_HASH=0x8C297E80
MASK_HASH=0x003D4F14
RADIANT_DIFFUSE_HASH=0xD29BFA97

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def norm_mat(s:str)->str:return s[1:] if s.startswith(',') else s
def u32(v):return int(v,0) if isinstance(v,str) else int(v)
def load(path:Path):return json.loads(path.read_text(encoding='utf-8-sig'))

def main()->int:
 ap=argparse.ArgumentParser()
 ap.add_argument('--materials',type=Path,required=True)
 ap.add_argument('--surface-proof',type=Path,required=True)
 ap.add_argument('--exact-keys',type=Path,required=True)
 ap.add_argument('--header-alias-proof',type=Path,required=True)
 ap.add_argument('--image-run-proof',type=Path,required=True)
 ap.add_argument('--material-alias-proof',type=Path,required=True)
 ap.add_argument('--import-resolution',type=Path,required=True)
 ap.add_argument('--shared-identity-proof',type=Path,required=True)
 ap.add_argument('--lod',type=int,default=0)
 ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args()
 mats=load(a.materials);surfproof=load(a.surface_proof);keys=load(a.exact_keys);hproof=load(a.header_alias_proof);runproof=load(a.image_run_proof);vproof=load(a.material_alias_proof);imports=load(a.import_resolution);shared=load(a.shared_identity_proof)
 idx_name={}
 for g in runproof.get('groups',[]):
  for im in g.get('imageSequence',g.get('images',[])):idx_name[int(im['assetIndex'])]=im['name']
 aliases={}
 for r in hproof.get('results',hproof.get('xassetHeaderSlots',[])):
  res=r.get('resolution') or r
  if res.get('classification')=='xasset-header-slot' or 'assetIndex' in res:
   ai=int(res['assetIndex']);name=idx_name.get(ai)
   if name is None:raise SystemExit(f'IMAGE asset index {ai} not named by run proof')
   aliases[(norm_mat(r['material']),int(r['slotIndex']))]=name
 for p in vproof.get('proofs',[]):
  if not p.get('exactAliasProven'):continue
  u=p['laterUse'];aliases[(norm_mat(u['material']),int(u['slotIndex']))]=p['exactIdentity']
 la=shared['laterAlias'];aliases[(norm_mat(la['material']),int(la['slotIndex']))]=shared['resolvedIdentity']
 import_map={p['importIdentity']:p['targetName'] for p in imports.get('promotions',[])}
 exact_rows=keys.get('exactBaseIpakKeys',keys.get('exactStreamKeyImages',[]));exact={}
 for r in exact_rows:
  name=r.get('image') or r.get('name');sp=r.get('streamedPart0') or {}
  exact[name]={'nameHash':u32(r.get('nameHash',r.get('nameHashHex'))),'dataHash':u32(sp.get('dataHash',sp.get('dataHashHex',r.get('dataHash',r.get('dataHashHex')))))&0x1fffffff,'repository':sp.get('repositoryHint') or r.get('repository'),'width':r.get('width'),'height':r.get('height')}
 material_rows=[];slot_total=0;identity_total=0;stream_total=0
 for m in mats['materials']:
  name=norm_mat(m['name']);slots=[]
  for s in m.get('slots',[]):
   slot_total+=1;ident=None;source=None
   if s['imageStatus']=='inline-definition':ident=s['image']['name'];source='inline-retail-GfxImage'
   elif s['imageStatus']=='packed-reference':ident=aliases.get((name,int(s['index'])));source='exact-packed-alias-proof' if ident else None
   elif s['imageStatus']=='null':source='null'
   if ident and ident.startswith(','):
    promoted=import_map.get(ident)
    if promoted:ident=promoted;source+='+exact-comma-import-resolution'
    else:ident=ident[1:];source+='+identity-only-comma-import'
   if ident:identity_total+=1
   key=exact.get(ident) if ident else None
   if key:stream_total+=1
   sh=u32(s['slotNameHash'])
   role={DIFFUSE_HASH:'Diffuse_Map',NORMAL_HASH:'Normal_Map',SPEC_GLOSS_HASH:'SpecularAndGloss',MASK_HASH:'Mask',RADIANT_DIFFUSE_HASH:'radiantDiffuseMap0'}.get(sh)
   slots.append({'index':int(s['index']),'slotNameHash':sh,'slotNameHashHex':f'0x{sh:08x}','slotRole':role,'semanticRaw':int(s['semanticRaw']),'semanticName':s['semanticName'],'samplerStateRaw':int(s['samplerStateRaw']),'image':ident,'identityEvidence':source,'exactStreamKey':key})
  if any(x['image'] is None and x['identityEvidence']!='null' for x in slots):raise SystemExit(f'{name}: unresolved texture identity')
  diffuse=next((x for x in slots if x['slotNameHash']==DIFFUSE_HASH and x['image']),None)
  normal=next((x for x in slots if x['slotNameHash']==NORMAL_HASH and x['image']),None)
  if diffuse is None:
   diffuse=next((x for x in slots if x['semanticRaw']==2 and x['image']),None)
   diffuse_mode='visualization-fallback-first-color-semantic' if diffuse else None
  else:diffuse_mode='exact-Diffuse_Map-slot'
  if normal is None:
   normal=next((x for x in slots if x['semanticRaw']==5 and x['image']),None)
   normal_mode='visualization-fallback-first-normal-semantic' if normal else None
  else:normal_mode='exact-Normal_Map-slot'
  material_rows.append({'material':name,'sourceMaterialName':m['name'],'textureCount':int(m['textureCount']),'slots':slots,'gltfVisualization':{'baseColor':({'image':diffuse['image'],'mode':diffuse_mode,'slotIndex':diffuse['index'],'slotNameHashHex':diffuse['slotNameHashHex'],'exactStreamKey':diffuse['exactStreamKey']} if diffuse else None),'normal':({'image':normal['image'],'mode':normal_mode,'slotIndex':normal['index'],'slotNameHashHex':normal['slotNameHashHex'],'exactStreamKey':normal['exactStreamKey']} if normal else None),'shaderApproximation':diffuse_mode!='exact-Diffuse_Map-slot' or (normal is not None and normal_mode!='exact-Normal_Map-slot')}})
 bymat={m['material']:m for m in material_rows};surfaces=[]
 for r in surfproof['bodyMaterials']['surfaceAssignments']:
  if int(r['lod'])!=a.lod:continue
  mat=norm_mat(r['materialName'])
  if mat not in bymat:raise SystemExit(f'surface {r["surfaceIndex"]}: material {mat} not in material manifest')
  surfaces.append({'surfaceIndex':int(r['surfaceIndex']),'lod':int(r['lod']),'material':mat,'materialPointerRaw':r['materialPointerRaw'],'materialIdentityEvidence':r['evidence'],'gltfVisualization':bymat[mat]['gltfVisualization']})
 used=sorted({r['material'] for r in surfaces});missing_visual=[]
 for name in used:
  v=bymat[name]['gltfVisualization']
  for role in ('baseColor','normal'):
   if not v.get(role) or not v[role].get('exactStreamKey'):missing_visual.append({'material':name,'role':role,'binding':v.get(role)})
 doc={'format':'t6-character-material-binding-plan-v1','authority':'join of exact retail MaterialTextureDef identities/aliases/imports and exact IPAK stream keys; glTF role selection separated from native shader graph','sourceManifests':[{'path':str(p),'sha256':sha(p)} for p in (a.materials,a.surface_proof,a.exact_keys,a.header_alias_proof,a.image_run_proof,a.material_alias_proof,a.import_resolution,a.shared_identity_proof)],'slotRoleEvidence':{'Diffuse_Map':{'hashHex':'0xf039ec2d','status':'known T6 semantic hash; used for standard PBR baseColor selection'},'Normal_Map':{'hashHex':'0x942cbff0','status':'known T6 semantic hash; used for standard PBR normal selection'},'specialShaders':'All native texture slots are retained even when no standard PBR role is assigned.'},'summary':{'materialTextureSlots':slot_total,'identityResolvedSlots':identity_total,'exactStreamKeySlots':stream_total,'materials':len(material_rows),'lod':a.lod,'lodSurfaces':len(surfaces),'lodUniqueMaterials':len(used),'visualBindingsMissingExactStreamKey':len(missing_visual),'nativeIdentityClosure':identity_total==slot_total,'visualPbrTextureClosure':len(missing_visual)==0},'materials':material_rows,'surfaceBindings':surfaces,'missingVisualBindings':missing_visual,'proofBoundary':'Native T6 material identity is the complete slot list. glTF baseColor/normal fields are an interoperability mapping: standard Diffuse_Map/Normal_Map hashes are preferred; any fallback is explicitly marked shaderApproximation and never replaces the native dependency graph.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(doc['summary'],indent=2,sort_keys=True));return 2 if missing_visual else 0
if __name__=='__main__':raise SystemExit(main())
