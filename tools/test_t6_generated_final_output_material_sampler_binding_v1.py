#!/usr/bin/env python3
from __future__ import annotations
import copy,hashlib,json,tempfile
from pathlib import Path
import t6_generated_final_output_material_sampler_binding_v1 as bind

def write_material(root:Path,name:str,image:str)->tuple[str,str]:
 p=root/(name+'.json');p.parent.mkdir(parents=True,exist_ok=True);doc={'_game':'t6','_type':'material','textures':[{'name':'colorMap','semantic':'colorMap','image':image,'samplerState':{'filter':'LINEAR'}}]};raw=(json.dumps(doc,sort_keys=True)+'\n').encode();p.write_bytes(raw);return p.relative_to(root).as_posix(),hashlib.sha256(raw).hexdigest()

def main()->int:
 with tempfile.TemporaryDirectory(prefix='t6_mat_sampler_') as td:
  root=Path(td);rel0,sha0=write_material(root,'wpc/a','img_a');rel1,sha1=write_material(root,'wpc/b','img_b')
  final={'format':bind.FINAL_FORMAT,'materials':[{'material':'*fixture','techniqueSet':'tech','pixelShaderSha256':'a'*64}]}
  tex={'format':bind.TEXTURE_FORMAT,'shaders':[{'sha256':'a'*64,'resources':[{'resource':'colorMapSampler','resourceRegisters':[0],'sampleNodeIds':[3],'techniqueAssignments':[{'techniqueSet':'tech','sourceClass':'material','sourceNamespace':'material','sourceKind':'material','sourceExpression':'material.colorMap','sourceName':'colorMap'}]}]}]}
  manifest={'format':bind.MATERIAL_FORMAT,'materials':[{'material':'*fixture','layers':[{'layerIndex':0,'layer':'wpc/a','sourceOatMaterial':{'file':rel0,'sha256':sha0},'textures':[{'sourceTextureIndex':0,'textureIndex':0,'imageAsset':'img_a','sourceTexture':'img_a.png'}]}]}]}
  doc=bind.build(final,tex,manifest,oat_material_root=root)
  assert doc['summary']['materialSamplerBindingCount']==1 and doc['summary']['allMaterialSamplerBindingsUnique'] is True
  row=doc['materials'][0]['bindings'][0];assert row['status']=='unique' and row['resolvedTexture']['imageAsset']=='img_a' and row['resolvedTexture']['sourceOatMaterialSha256']==sha0

  amb=copy.deepcopy(manifest);amb['materials'][0]['layers'].append({'layerIndex':1,'layer':'wpc/b','sourceOatMaterial':{'file':rel1,'sha256':sha1},'textures':[{'sourceTextureIndex':0,'textureIndex':1,'imageAsset':'img_b','sourceTexture':'img_b.png'}]})
  doc2=bind.build(final,tex,amb,oat_material_root=root);r=doc2['materials'][0]['bindings'][0];assert r['status']=='ambiguous' and r['candidateCount']==2 and r['resolvedTexture'] is None
  assert doc2['summary']['ambiguousMaterialSamplerBindingCount']==1

  bad=copy.deepcopy(tex);bad['shaders'][0]['resources'][0]['techniqueAssignments'][0]['sourceName']='normalMap';bad['shaders'][0]['resources'][0]['techniqueAssignments'][0]['sourceExpression']='material.normalMap'
  try:bind.build(final,bad,manifest,oat_material_root=root)
  except bind.MaterialSamplerBindingError as exc:assert 'matched zero' in str(exc)
  else:raise AssertionError('missing material sampler property accepted')
 print('PASS: exact generated final-output material sampler binding v1');return 0
if __name__=='__main__':raise SystemExit(main())
