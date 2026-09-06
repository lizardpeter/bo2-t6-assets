#!/usr/bin/env python3
"""Production T6 world export pipeline v51: renderer-neutral final-output replay contract.

v51 preserves v50 visual bytes. It assembles the authoritative final slot-4 DAG
with corrected cbuffer/texture provenance, exact T6 code input identities, and
per-material sampled-image ownership into one replay contract.

If the retained generated MaterialConstantDef archive exists, exact material
cbuffer values are regenerated against corrected cbuffer signature v2 first.
Otherwise the replay contract remains valid but reports those static material
values as blockers.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_generated_final_output_material_cbuffer_values_v3 as matvals
import t6_generated_final_output_replay_contract_v1 as replay
import t6_oat_world_textured_export_pipeline_v50 as v50
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v51'
class OatTexturedPipelineV51Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV51Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV51Error(f'{label} does not exist: {p}')
 return p

def _twice(label,fn):
 a=fn();b=fn();ab=_jb(a);bb=_jb(b)
 if a!=b or ab!=bb:raise OatTexturedPipelineV51Error(f'{label} regeneration was not byte-identical')
 return a,ab

def run_oat_textured_pipeline(**kw):
 r=v50.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v50.FORMAT:raise OatTexturedPipelineV51Error(f"unexpected v50 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v50 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v51.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v50 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v51.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)

 keys={'final':'generatedSlot4FinalOutputSymbolic','cb':'generatedFinalOutputCbufferSignatureV2','cc':'generatedFinalOutputCodeConstantIdentityV2','tex':'generatedFinalOutputTextureResourceBindingV2','cs':'generatedFinalOutputCodeSamplerIdentityV2','ms':'generatedFinalOutputMaterialSamplerBinding'}
 present={k:isinstance(o.get(v),dict) for k,v in keys.items()};contract=None;values=None
 if present['final']:
  if not all(present.values()):raise OatTexturedPipelineV51Error(f'partial replay prerequisites: {present}')
  docs={k:json.loads(_path(o[v],f'replay prerequisite {k}').read_text()) for k,v in keys.items()}
  const_rec=o.get('generatedRetailMaterialConstants')
  if isinstance(const_rec,dict):
   constants=json.loads(_path(const_rec,'retail generated MaterialConstantDef archive').read_text())
   try:values,vb=_twice('corrected material cbuffer values v3',lambda:matvals.build(docs['final'],docs['cb'],constants))
   except Exception as e:
    if isinstance(e,OatTexturedPipelineV51Error):raise
    raise OatTexturedPipelineV51Error(f'corrected material cbuffer values failed: {e}') from e
   vp=out/f'{name}.generated_final_output_material_cbuffer_values_v3.json';vp.write_bytes(vb);o['generatedFinalOutputMaterialCbufferValuesV3']=_rec(vp,vb)
  try:contract,rb=_twice('final-output replay contract',lambda:replay.build(docs['final'],docs['cb'],docs['cc'],docs['tex'],docs['cs'],docs['ms'],values))
  except Exception as e:
   if isinstance(e,OatTexturedPipelineV51Error):raise
   raise OatTexturedPipelineV51Error(f'final-output replay contract failed: {e}') from e
  rp=out/f'{name}.generated_final_output_replay_contract_v1.json';rp.write_bytes(rb);o['generatedFinalOutputReplayContract']=_rec(rp,rb)
 s=None if contract is None else contract['summary'];vs=None if values is None else values['summary'];stats=r.setdefault('stats',{});stats['generatedFinalOutputMaterialCbufferValuesV3']=vs;stats['generatedFinalOutputReplayContract']=s
 val=r.setdefault('validation',{});val.update({'v51ReplayContractGenerated':contract is not None,'v51ReplayContractDeterministic':None if contract is None else True,'v51CorrectedMaterialValuesGenerated':values is not None,'v51CorrectedMaterialValuesDeterministic':None if values is None else True,'v51ReplayProgramCount':None if s is None else int(s['programCount']),'v51ReplayMaterialCount':None if s is None else int(s['materialCount']),'v51ReplayIdentityCompleteMaterialCount':None if s is None else int(s['replayIdentityCompleteMaterialCount']),'v51ReplayMaterialStaticStateCompleteCount':None if s is None else int(s['materialStaticStateCompleteCount']),'v51ReplayDynamicEngineInputIdentityCompleteCount':None if s is None else int(s['dynamicEngineInputIdentityCompleteCount']),'v51ReplayMaterialRequiringDynamicInputsCount':None if s is None else int(s['materialRequiringRuntimeDynamicInputsCount']),'v51ReplayBlockerCounts':None if s is None else s['blockerCounts'],'v51VisualGlbByteIdenticalToV50':True,'v51VisualGltfByteIdenticalToV50':True if had_gltf else None})
 r.setdefault('policies',{})['v51FinalOutputReplayContract']='preserve exact final slot-4 shader DAG once per CSO and bind each material owner to corrected material literals/images plus exact dynamic T6 code constant/sampler identities; ambiguities/missing inputs remain explicit blockers; no arithmetic evaluation, algebraic normalization, physical relabeling, or generic PBR remap; visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v51.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--oat-source-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,oat_source_root=a.oat_source_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'replayContract':r['outputs'].get('generatedFinalOutputReplayContract'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
