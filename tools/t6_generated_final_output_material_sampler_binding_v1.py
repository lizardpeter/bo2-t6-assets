#!/usr/bin/env python3
"""Bind final-output material.* texture sources to exact OAT texture definitions.

For each exact final-output material owner and sampled resource whose current OAT
`.tech` source is `material.<property>`, this tool:
1. computes T6 R_HashString(property, 0);
2. reopens every exact source OAT Material JSON referenced by that material's
   reconstructed dependency graph;
3. reads the original MaterialTextureDef JSON property name or nameHash at the
   exact sourceTextureIndex;
4. joins candidates by exact property hash while cross-checking image identity.

Exactly one candidate is promoted as a resolved sampled image. Multiple matches
remain explicit ambiguity; zero matches fail closed. No layer-priority/runtime
lookup rule is invented.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any
from t6_dxbc_material_constant_binding_v1 import t6_r_hash_string
FORMAT='t6-generated-final-output-material-sampler-binding-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
TEXTURE_FORMAT='t6-generated-final-output-texture-resource-binding-v2'
MATERIAL_FORMAT='t6-material-texture-manifest-v1'
class MaterialSamplerBindingError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _index(rows:list[dict],key:str,label:str)->dict:
 out={}
 for row in rows:
  name=str(row.get(key) or '')
  if not name or name in out:raise MaterialSamplerBindingError(f'invalid/duplicate {label} {name!r}')
  out[name]=row
 return out

def _shader_index(doc:dict)->dict:
 out={}
 for row in doc.get('shaders',[]):
  sha=str(row.get('sha256') or '')
  if not sha or sha in out:raise MaterialSamplerBindingError(f'invalid/duplicate texture-binding shader {sha!r}')
  out[sha]=row
 return out

def _assignment(resource:dict,technique:str)->dict:
 rows=[r for r in resource.get('techniqueAssignments',[]) if str(r.get('techniqueSet') or '')==technique]
 if len(rows)!=1:raise MaterialSamplerBindingError(f"{resource.get('resource')}: TechniqueSet {technique!r} assignment count {len(rows)}, expected 1")
 return rows[0]

def _texture_property(original:dict)->tuple[int,str|None]:
 if original.get('name') not in (None,''):
  name=str(original['name']);return t6_r_hash_string(name,0),name
 if original.get('nameHash') is None:raise MaterialSamplerBindingError('OAT texture definition has neither name nor nameHash')
 value=original['nameHash'];h=int(value,0) if isinstance(value,str) else int(value);return h&0xffffffff,None

def _candidate_rows(material_row:dict,oat_root:Path,source_name:str)->list[dict]:
 expected=t6_r_hash_string(source_name,0);out=[];cache={}
 for layer in material_row.get('layers',[]):
  src=layer.get('sourceOatMaterial') or {};rel=str(src.get('file') or '')
  if not rel:raise MaterialSamplerBindingError(f"{material_row.get('material')!r}: layer {layer.get('layerIndex')} lacks sourceOatMaterial.file")
  path=Path(oat_root)/rel
  if path not in cache:
   if not path.is_file():raise MaterialSamplerBindingError(f'exact OAT material source missing: {path}')
   raw=path.read_bytes()
   if src.get('sha256') and hashlib.sha256(raw).hexdigest()!=str(src['sha256']):raise MaterialSamplerBindingError(f'OAT material source hash changed: {rel}')
   doc=json.loads(raw.decode('utf-8'))
   if doc.get('_game')!='t6' or doc.get('_type')!='material':raise MaterialSamplerBindingError(f'{rel}: not a T6 material JSON')
   cache[path]=doc
  doc=cache[path];textures=doc.get('textures',[])
  if not isinstance(textures,list):raise MaterialSamplerBindingError(f'{rel}: textures is not a list')
  for dep in layer.get('textures',[]):
   idx=int(dep.get('sourceTextureIndex',-1))
   if not 0<=idx<len(textures):raise MaterialSamplerBindingError(f'{rel}: sourceTextureIndex {idx} outside texture table')
   original=textures[idx];prop_hash,prop_name=_texture_property(original)
   if str(original.get('image') or '')!=str(dep.get('imageAsset') or ''):raise MaterialSamplerBindingError(f"{material_row.get('material')!r} layer {layer.get('layerIndex')} texture {idx}: manifest/OAT image identity mismatch")
   if prop_hash!=expected:continue
   out.append({'layerIndex':int(layer.get('layerIndex',0)),'layer':layer.get('layer'),'sourceOatMaterialFile':rel,'sourceOatMaterialSha256':src.get('sha256'),'sourceTextureIndex':idx,'generatedTextureIndex':int(dep.get('textureIndex',-1)),'propertyName':prop_name,'propertyHash':prop_hash,'propertyHashHex':f'0x{prop_hash:08x}','semantic':original.get('semantic'),'imageAsset':original.get('image'),'sourceTexture':dep.get('sourceTexture'),'samplerState':copy.deepcopy(original.get('samplerState'))})
 return out

def build(final_doc:dict,texture_doc:dict,material_manifest:dict,*,oat_material_root:Path)->dict:
 if final_doc.get('format')!=FINAL_FORMAT:raise MaterialSamplerBindingError(f"unexpected final-output format {final_doc.get('format')!r}")
 if texture_doc.get('format')!=TEXTURE_FORMAT:raise MaterialSamplerBindingError(f"unexpected texture-binding format {texture_doc.get('format')!r}")
 if material_manifest.get('format')!=MATERIAL_FORMAT:raise MaterialSamplerBindingError(f"unexpected material manifest format {material_manifest.get('format')!r}")
 owners=_index(final_doc.get('materials',[]),'material','final-output material');materials=_index(material_manifest.get('materials',[]),'material','material manifest row');shaders=_shader_index(texture_doc);rows=[];unique=ambiguous=bindings=0;candidate_hist=Counter()
 for material in sorted(owners):
  owner=owners[material];sha=str(owner.get('pixelShaderSha256') or '');technique=str(owner.get('techniqueSet') or '')
  if material not in materials:raise MaterialSamplerBindingError(f'{material!r}: absent from exact OAT material manifest')
  shader=shaders.get(sha)
  if shader is None:raise MaterialSamplerBindingError(f'{material!r}: shader {sha} absent from texture binding')
  bound=[]
  for resource in shader.get('resources',[]):
   assignment=_assignment(resource,technique)
   if str(assignment.get('sourceClass') or '')!='material':continue
   source_name=str(assignment.get('sourceName') or '')
   if not source_name:raise MaterialSamplerBindingError(f"{material!r} {resource.get('resource')}: material source has no property name")
   candidates=_candidate_rows(materials[material],Path(oat_material_root),source_name)
   if not candidates:raise MaterialSamplerBindingError(f"{material!r} {resource.get('resource')}: material.{source_name} hash matched zero reconstructed texture definitions")
   bindings+=1;candidate_hist[len(candidates)]+=1;status='unique' if len(candidates)==1 else 'ambiguous';unique+=int(status=='unique');ambiguous+=int(status=='ambiguous')
   bound.append({'resource':resource.get('resource'),'resourceRegisters':copy.deepcopy(resource.get('resourceRegisters',[])),'sampleNodeIds':copy.deepcopy(resource.get('sampleNodeIds',[])),'techniqueSet':technique,'sourceExpression':assignment.get('sourceExpression'),'sourceName':source_name,'sourcePropertyHash':t6_r_hash_string(source_name,0),'sourcePropertyHashHex':f'0x{t6_r_hash_string(source_name,0):08x}','status':status,'candidateCount':len(candidates),'resolvedTexture':copy.deepcopy(candidates[0]) if len(candidates)==1 else None,'candidates':candidates})
  rows.append({'material':material,'techniqueSet':technique,'pixelShaderSha256':sha,'materialSamplerBindingCount':len(bound),'bindings':bound})
 summary={'materialCount':len(rows),'materialSamplerBindingCount':bindings,'uniqueMaterialSamplerBindingCount':unique,'ambiguousMaterialSamplerBindingCount':ambiguous,'allMaterialSamplerBindingsUnique':ambiguous==0,'candidateCountHistogram':{str(k):v for k,v in sorted(candidate_hist.items())}}
 return {'format':FORMAT,'sourceFinalOutputFormat':FINAL_FORMAT,'sourceTextureBindingFormat':TEXTURE_FORMAT,'sourceMaterialManifestFormat':MATERIAL_FORMAT,'materials':rows,'summary':summary,'rowsSha256':_jhash(rows),'proofBoundary':'Exact per-material .tech material.<property> -> T6 property hash -> original OAT MaterialTextureDef name/nameHash rows at exact reconstructed component texture indices, with exact source Material JSON hash and GfxImage identity cross-checks. Unique candidate is resolved; multiple candidates remain explicit ambiguity. No runtime duplicate-hash selection policy is invented.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--texture-binding',type=Path,required=True);p.add_argument('--material-manifest',type=Path,required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.texture_binding.read_text()),json.loads(a.material_manifest.read_text()),oat_material_root=a.oat_material_root);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
