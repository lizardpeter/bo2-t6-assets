#!/usr/bin/env python3
"""Production T6 world export pipeline v37: exact final-RGB term coverage diagnostic.

v37 preserves v36 visual bytes.  When the exact final-output sidecars exist it
classifies every syntactic top-level o0.rgb leaf by exact node identity against
already-proven final term families.  v37 is diagnostic (strict=False): unknown
terms remain explicitly unclassified rather than forcing a guessed final formula.

The v2 classifier independently validates every sidecar node reference against
the authoritative full-output DAG before classification.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_generated_final_output_rgb_term_coverage_v2 as coverage
import t6_oat_world_textured_export_pipeline_v36 as v36
from t6_material_wgpu_state_v2 import DEFAULT_SHADOWMAP_BIAS,DEFAULT_SHADOWMAP_SCALE
FORMAT='t6-oat-world-textured-export-pipeline-manifest-v37'
class OatTexturedPipelineV37Error(RuntimeError):pass
def _sha(b):return hashlib.sha256(b).hexdigest()
def _jb(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def _rec(p,b=None):
 b=p.read_bytes() if b is None else b;return {'file':p.name,'path':str(p),'bytes':len(b),'sha256':_sha(b)}
def _path(r,label):
 if not isinstance(r,dict):raise OatTexturedPipelineV37Error(f'missing {label} record')
 p=Path(str(r.get('path') or ''))
 if not p.is_file():raise OatTexturedPipelineV37Error(f'{label} does not exist: {p}')
 return p
def run_oat_textured_pipeline(**kw):
 r=v36.run_oat_textured_pipeline(**kw)
 if r.get('format')!=v36.FORMAT:raise OatTexturedPipelineV37Error(f"unexpected v36 base manifest {r.get('format')!r}")
 out=Path(kw['output_dir']);name=str(kw['map_name']);o=r.get('outputs',{})
 old=_path(o.get('oatPortableTexturedGlb'),'v36 portable GLB');gb=old.read_bytes();new=out/f'{name}.world_oat_portable_textured_v37.glb';new.write_bytes(gb)
 if old!=new and old.is_file():old.unlink()
 o['oatPortableTexturedGlb']=_rec(new,gb)
 gr=o.get('oatPortableTexturedGltf');had_gltf=isinstance(gr,dict)
 if had_gltf:
  oldg=_path(gr,'v36 portable glTF');g=oldg.read_bytes();newg=out/f'{name}.world_oat_portable_textured_v37.gltf';newg.write_bytes(g)
  if oldg!=newg and oldg.is_file():oldg.unlink()
  o['oatPortableTexturedGltf']=_rec(newg,g)
 required=[('generatedFinalOutputRgbTopology','v36 topology'),('generatedFinalOutputDiffuseDirectionalProductProbe','v35 diffuse-directional'),('generatedFinalOutputSpecularReflectionJoin','v34 specular-reflection'),('generatedSlot4FinalOutputSymbolic','final-output DAG'),('generatedFinalOutputRgbSquareAnchor','v26 RGB-square'),('generatedFinalOutputDirectionalLightmapAnchor','v28 directional'),('generatedFinalOutputSpecularStateAnchor','v30 specular'),('generatedFinalOutputReflectionSampleIndex','v33 reflection index')]
 doc=None
 if isinstance(o.get('generatedSlot4FinalOutputSymbolic'),dict):
  docs=[]
  for key,label in required:
   rec=o.get(key)
   if not isinstance(rec,dict):raise OatTexturedPipelineV37Error(f'final-output DAG exists but {label} sidecar is absent')
   docs.append(json.loads(_path(rec,label+' sidecar').read_text()))
  try:d1=coverage.build(*docs,strict=False);d2=coverage.build(*docs,strict=False)
  except Exception as e:raise OatTexturedPipelineV37Error(f'final RGB term coverage classification failed: {e}') from e
  b1=_jb(d1);b2=_jb(d2)
  if d1!=d2 or b1!=b2:raise OatTexturedPipelineV37Error('final RGB term coverage regeneration was not byte-identical')
  doc=d1;p=out/f'{name}.generated_final_output_rgb_term_coverage_v2.json';p.write_bytes(b1);o['generatedFinalOutputRgbTermCoverage']=_rec(p,b1)
 s=None if doc is None else doc['summary'];pf=None if doc is None else doc['authoritativeDagPreflight'];r.setdefault('stats',{})['generatedFinalOutputRgbTermCoverage']=s
 r.setdefault('validation',{}).update({'v37FinalRgbTermCoverageGenerated':doc is not None,'v37FinalRgbTermCoverageDeterministic':None if doc is None else True,'v37FinalRgbSyntacticLeafCount':None if s is None else int(s['syntacticLeafCount']),'v37FinalRgbCoveredLeafCount':None if s is None else int(s['coveredLeafCount']),'v37FinalRgbUnclassifiedLeafCount':None if s is None else int(s['unclassifiedLeafCount']),'v37FinalRgbFullyCoveredLaneCount':None if s is None else int(s['fullyCoveredRgbLaneCount']),'v37FinalRgbFullyCoveredShaderCount':None if s is None else int(s['fullyCoveredShaderCount']),'v37AuthoritativeDagNodeReferenceCheckCount':None if pf is None else int(pf['nodeReferenceCheckCount']),'v37AllReferencedNodesExist':None if pf is None else bool(pf['allReferencedNodesExist']),'v37VisualGlbByteIdenticalToV36':True,'v37VisualGltfByteIdenticalToV36':True if had_gltf else None})
 r.setdefault('policies',{})['v37FinalRgbTermCoverage']='diagnostically classify each v36 top-level o0.rgb syntactic leaf only by exact node identity against previously proven direct/standalone term families after an independent authoritative-DAG node-reference preflight; unclassified leaves remain explicit and do not fail v37 or imply a guessed formula'
 oldm=r.pop('manifest',None)
 if isinstance(oldm,dict):
  p=Path(str(oldm.get('path') or ''))
  if p.is_file():p.unlink()
 r['format']=FORMAT;mb=_jb(r);mp=out/f'{name}.world_oat_textured_export_manifest_v37.json';mp.write_bytes(mb);r['manifest']=_rec(mp,mb);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--map',dest='map_name',required=True);p.add_argument('--surfaces',type=Path,required=True);p.add_argument('--vd0',type=Path,required=True);p.add_argument('--vd1',type=Path,required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--materials',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--asset-pointer-base',type=lambda v:int(v,0),required=True);p.add_argument('--oat-material-root',type=Path,required=True);p.add_argument('--oat-shader-root',type=Path);p.add_argument('--dds-root',type=Path,required=True);p.add_argument('--format-registry',type=Path,required=True);p.add_argument('--lightmap-catalog',type=Path);p.add_argument('--reflection-probe-catalog',type=Path);p.add_argument('--generated-shader-recipes',type=Path);p.add_argument('--generated-shader-expanded-world',type=Path);p.add_argument('--generated-normal-basis-proof',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--write-gltf',action='store_true');p.add_argument('--sm-polygon-offset-bias',type=int,default=DEFAULT_SHADOWMAP_BIAS);p.add_argument('--sm-polygon-offset-scale',type=float,default=DEFAULT_SHADOWMAP_SCALE)
 for f in ('unresolved-world-materials','missing-oat-materials','missing-dds','missing-preview-textures','missing-dependency-textures','missing-lightmap-dds','missing-reflection-probe-dds'):p.add_argument('--allow-'+f,action='store_true')
 a=p.parse_args();r=run_oat_textured_pipeline(map_name=a.map_name,surfaces_path=a.surfaces,vd0_path=a.vd0,vd1_path=a.vd1,indices_path=a.indices,materials_path=a.materials,catalog_path=a.catalog,prefix_path=a.prefix,asset_pointer_array_virtual_base=a.asset_pointer_base,oat_material_root=a.oat_material_root,oat_shader_root=a.oat_shader_root,dds_root=a.dds_root,output_dir=a.out_dir,format_registry_path=a.format_registry,lightmap_catalog_path=a.lightmap_catalog,reflection_probe_catalog_path=a.reflection_probe_catalog,generated_shader_recipe_manifest_path=a.generated_shader_recipes,generated_shader_expanded_world_path=a.generated_shader_expanded_world,generated_normal_basis_proof_path=a.generated_normal_basis_proof,write_gltf=a.write_gltf,shadowmap_bias=a.sm_polygon_offset_bias,shadowmap_scale=a.sm_polygon_offset_scale,allow_unresolved_world_materials=a.allow_unresolved_world_materials,allow_missing_oat_materials=a.allow_missing_oat_materials,allow_missing_dds=a.allow_missing_dds,allow_missing_preview_textures=a.allow_missing_preview_textures,allow_missing_dependency_textures=a.allow_missing_dependency_textures,allow_missing_lightmap_dds=a.allow_missing_lightmap_dds,allow_missing_reflection_probe_dds=a.allow_missing_reflection_probe_dds);print(json.dumps({'format':r['format'],'glb':r['outputs']['oatPortableTexturedGlb'],'rgbTermCoverage':r['outputs'].get('generatedFinalOutputRgbTermCoverage'),'manifest':r['manifest']},indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
