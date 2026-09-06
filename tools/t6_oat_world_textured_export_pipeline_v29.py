#!/usr/bin/env python3
"""Production T6 world export pipeline v29: exact I/O semantics + layered normal join.

v29 preserves v28 visual bytes. When the exact final-output DAG exists it:
1. reopens the exact OAT CSOs and emits strict ISGN/OSGN semantic bindings;
2. joins the retained layered-normal reconstruction to exactly one directional
   equation for every generated TechniqueSet that declares a secondary normal.

Both sidecars are regenerated twice and must be byte-identical.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_generated_final_output_io_signature_v1 as io_sig
import t6_generated_final_output_layered_normal_anchor_v1 as normal_anchor
import t6_oat_world_textured_export_pipeline_v28 as v28
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v29'
class OatTexturedPipelineV29Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV29Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV29Error(f'{label} does not exist: {p}')
 return p

def run_oat_textured_pipeline(**kw):
 r=v28.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v28.FORMAT:raise OatTexturedPipelineV29Error(f"unexpected v28 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v28 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v29.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v28 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v29.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 final_rec=o.get('generatedSlot4FinalOutputSymbolic');dir_rec=o.get('generatedFinalOutputDirectionalLightmapAnchor')
 io_doc=normal_doc=None
 if isinstance(final_rec,dict):
  oat=kw.get('oat_shader_root')
  if oat is None:raise OatTexturedPipelineV29Error('final-output DAG exists but oat_shader_root is unavailable for exact ISGN/OSGN binding')
  fd=json.loads(_path(final_rec,'final-output symbolic sidecar').read_text())
  strict=name==io_sig.symbolic_v3.MAP
  try:i1=io_sig.build(fd,oat_root=Path(oat),strict_nuketown=strict);i2=io_sig.build(fd,oat_root=Path(oat),strict_nuketown=strict)
  except Exception as e:raise OatTexturedPipelineV29Error(f'final-output I/O signature binding failed: {e}') from e
  b1=_jb(i1);b2=_jb(i2)
  if i1!=i2 or b1!=b2:raise OatTexturedPipelineV29Error('I/O signature sidecar regeneration was not byte-identical')
  io_doc=i1;p=out/f'{name}.generated_final_output_io_signature_v1.json';p.write_bytes(b1);o['generatedFinalOutputIoSignature']=_rec(p,b1)
  if not isinstance(dir_rec,dict):raise OatTexturedPipelineV29Error('final-output DAG exists but v28 directional anchor sidecar is absent')
  dd=json.loads(_path(dir_rec,'v28 directional anchor sidecar').read_text())
  try:n1=normal_anchor.build(fd,i1,dd,strict=True);n2=normal_anchor.build(fd,i1,dd,strict=True)
  except Exception as e:raise OatTexturedPipelineV29Error(f'layered-normal final-output anchoring failed: {e}') from e
  nb1=_jb(n1);nb2=_jb(n2)
  if n1!=n2 or nb1!=nb2:raise OatTexturedPipelineV29Error('layered-normal anchor regeneration was not byte-identical')
  normal_doc=n1;p=out/f'{name}.generated_final_output_layered_normal_anchor_v1.json';p.write_bytes(nb1);o['generatedFinalOutputLayeredNormalAnchor']=_rec(p,nb1)
 r.setdefault('stats',{})['generatedFinalOutputIoSignature']=None if io_doc is None else io_doc['summary']
 r['stats']['generatedFinalOutputLayeredNormalAnchor']=None if normal_doc is None else normal_doc['summary']
 ns=None if normal_doc is None else normal_doc['summary'];isum=None if io_doc is None else io_doc['summary']
 r.setdefault('validation',{}).update({
  'v29IoSignatureGenerated':io_doc is not None,'v29IoSignatureDeterministic':None if io_doc is None else True,
  'v29InputSymbolCheckCount':None if isum is None else int(isum['inputSymbolCheckCount']),
  'v29LayeredNormalAnchorGenerated':normal_doc is not None,'v29LayeredNormalAnchorDeterministic':None if normal_doc is None else True,
  'v29LayeredNormalTargetShaderCount':None if ns is None else int(ns['layeredNormalTargetShaderCount']),
  'v29AnchoredLayeredNormalShaderCount':None if ns is None else int(ns['anchoredLayeredNormalShaderCount']),
  'v29MissingLayeredNormalTargetShaderCount':None if ns is None else int(ns['missingTargetShaderCount']),
  'v29AmbiguousLayeredNormalTargetShaderCount':None if ns is None else int(ns['ambiguousTargetShaderCount']),
  'v29VisualGlbByteIdenticalToV28':True,'v29VisualGltfByteIdenticalToV28':True if had_gltf else None})
 r.setdefault('policies',{})['v29LayeredNormalFinalOutputJoin']='bind raw vN inputs through exact ISGN semantics, then require one directional equation per secondary-normal TechniqueSet to use TEXCOORD1 + layeredX*TEXCOORD3 + layeredY*TEXCOORD2 followed by raw*rsq(dot(raw,raw)); visual bytes unchanged'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v29.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'ioSignature':r['outputs'].get('generatedFinalOutputIoSignature'),'layeredNormal':r['outputs'].get('generatedFinalOutputLayeredNormalAnchor'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
