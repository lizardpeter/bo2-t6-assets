#!/usr/bin/env python3
"""Production T6 world export pipeline v49: corrected OAT argument provenance.

v49 deliberately branches from stable v46, superseding provisional v47/v48.
Those versions assumed legacy `code.*` RHS spelling and treated omitted sampler
assignments as errors. Current OAT round-trip behavior instead uses
`constant.*`/`sampler.*` and auto-creates missing same-accessor code arguments.

Whenever the authoritative final-output DAG exists, v49 emits deterministic:
- cbuffer signature v2 with current OAT namespaces;
- texture-resource binding v2 retaining exact omissions;
- pinned T6 code-constant and code-sampler source tables;
- corrected exact code-constant identity v2;
- corrected exact code-sampler identity v2.

Visual GLB/glTF bytes remain identical to v46.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_code_constant_source_table_v1 as const_table
import t6_code_sampler_source_table_v1 as sampler_table
import t6_generated_final_output_cbuffer_signature_v2 as cb2
import t6_generated_final_output_code_constant_identity_v2 as cid2
import t6_generated_final_output_texture_resource_binding_v2 as tb2
import t6_generated_final_output_code_sampler_identity_v2 as sid2
import t6_oat_world_textured_export_pipeline_v46 as v46
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v49'
class OatTexturedPipelineV49Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV49Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV49Error(f'{label} does not exist: {p}')
 return p

def _twice(label,fn):
 a=fn();b=fn();ab=_jb(a);bb=_jb(b)
 if a!=b or ab!=bb:raise OatTexturedPipelineV49Error(f'{label} regeneration was not byte-identical')
 return a,ab

def run_oat_textured_pipeline(**kw):
 r=v46.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v46.FORMAT:raise OatTexturedPipelineV49Error(f"unexpected v46 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v46 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v49.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v46 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v49.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 final_rec=o.get('generatedSlot4FinalOutputSymbolic');docs={}
 if isinstance(final_rec,dict):
  shader_root=kw.get('oat_shader_root');source_root=kw.get('oat_source_root')
  if shader_root is None:raise OatTexturedPipelineV49Error('final-output DAG exists but oat_shader_root is absent for corrected OAT argument provenance')
  if source_root is None:raise OatTexturedPipelineV49Error('final-output DAG exists but oat_source_root is absent for pinned T6 source tables')
  final=json.loads(_path(final_rec,'authoritative final-output DAG').read_text());shader_root=Path(shader_root);source_root=Path(source_root)
  try:
   docs['cbuffer'],cbb=_twice('corrected cbuffer signature',lambda:cb2.build(final,shader_root))
   docs['texture'],tbb=_twice('corrected texture-resource binding',lambda:tb2.build(final,oat_root=shader_root))
   docs['constTable'],ctb=_twice('pinned T6 code-constant table',lambda:const_table.build_from_root(source_root,verify_pinned_blobs=True))
   docs['samplerTable'],stb=_twice('pinned T6 code-sampler table',lambda:sampler_table.build_from_root(source_root,verify_pinned_blobs=True))
   docs['constIdentity'],cib=_twice('corrected code-constant identity',lambda:cid2.build(docs['cbuffer'],docs['constTable']))
   docs['samplerIdentity'],sib=_twice('corrected code-sampler identity',lambda:sid2.build(docs['texture'],docs['samplerTable']))
  except Exception as e:
   if isinstance(e,OatTexturedPipelineV49Error):raise
   raise OatTexturedPipelineV49Error(f'corrected OAT argument provenance failed: {e}') from e
  specs=(('generatedFinalOutputCbufferSignatureV2','generated_final_output_cbuffer_signature_v2.json',cbb),('generatedFinalOutputTextureResourceBindingV2','generated_final_output_texture_resource_binding_v2.json',tbb),('t6CodeConstantSourceTableV49','t6_code_constant_source_table_v1_v49.json',ctb),('t6CodeSamplerSourceTableV49','t6_code_sampler_source_table_v1_v49.json',stb),('generatedFinalOutputCodeConstantIdentityV2','generated_final_output_code_constant_identity_v2.json',cib),('generatedFinalOutputCodeSamplerIdentityV2','generated_final_output_code_sampler_identity_v2.json',sib))
  for key,suffix,payload in specs:
   p=out/f'{name}.{suffix}';p.write_bytes(payload);o[key]=_rec(p,payload)
 stats=r.setdefault('stats',{});validation=r.setdefault('validation',{})
 stats['v49CorrectedCbufferSignature']=None if not docs else docs['cbuffer']['summary'];stats['v49CorrectedTextureBinding']=None if not docs else docs['texture']['summary'];stats['v49CorrectedCodeConstantIdentity']=None if not docs else docs['constIdentity']['summary'];stats['v49CorrectedCodeSamplerIdentity']=None if not docs else docs['samplerIdentity']['summary']
 validation.update({'v49CorrectedArgumentProvenanceGenerated':bool(docs),'v49CorrectedArgumentProvenanceDeterministic':None if not docs else True,'v49PinnedOatSourceTablesVerified':None if not docs else True,'v49ExplicitCodeConstantAssignmentCount':None if not docs else int(docs['constIdentity']['summary']['explicitCodeConstantAssignmentCount']),'v49ImplicitSameAccessorCodeConstantAssignmentCount':None if not docs else int(docs['constIdentity']['summary']['implicitSameAccessorCodeConstantAssignmentCount']),'v49ExplicitCodeSamplerAssignmentCount':None if not docs else int(docs['samplerIdentity']['summary']['explicitCodeSamplerAssignmentCount']),'v49ImplicitSameAccessorCodeSamplerAssignmentCount':None if not docs else int(docs['samplerIdentity']['summary']['implicitSameAccessorCodeSamplerAssignmentCount']),'v49UnresolvedUnassignedSamplerBindingCount':None if not docs else int(docs['samplerIdentity']['summary']['unresolvedUnassignedSamplerBindingCount']),'v49VisualGlbByteIdenticalToV46':True,'v49VisualGltfByteIdenticalToV46':True if had_gltf else None})
 r.setdefault('policies',{})['v49CorrectedOatArgumentProvenance']='supersede provisional v47/v48 source classification with current OAT material./constant./sampler. namespaces and source-closed CommonShaderArgCreator same-accessor auto-create rules; pinned T6 enum/accessor tables required; implicit array constants stay unresolved without RDEF type-element proof; runtime code values/resources and final lighting remain separate; visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v49.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--oat-source-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,oat_source_root=a.oat_source_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'cbufferV2':r['outputs'].get('generatedFinalOutputCbufferSignatureV2'),'textureV2':r['outputs'].get('generatedFinalOutputTextureResourceBindingV2'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
