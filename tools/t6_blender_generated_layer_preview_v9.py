#!/usr/bin/env python3
"""Blender generated-layer preview v9: opt-in exact-state visual diagnostics.

Default mode preserves v8 unchanged. Diagnostic modes route one independently
proven T6 state to Emission so Blender scene lighting cannot obscure inspection:

- generated-diffuse: exact generated RGB after the retail shader's RGB square;
- directional-lightmap: exact retained directional secondary-lightmap RGB;
- reconstructed-normal: exact reconstructed T6 world normal, visualized as
  0.5*N+0.5 solely for display.

Diagnostic modes are NOT a claim that the selected state is final retail color.
They never multiply diffuse/lightmap/specular/reflection together and never map
T6 specular into generic PBR semantics.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v8 as v8

bpy=v1.bpy
BlenderLayerPreviewError=v1.BlenderLayerPreviewError
FORMAT='t6-blender-generated-layer-preview-v9'
MODES=('default','generated-diffuse','directional-lightmap','reconstructed-normal')
_BASE_BUILD_V8=v8._build_material_v8
_ACTIVE_VISUAL_MODE='default'

def _nodes_with_label(material,label:str):return [n for n in material.node_tree.nodes if n.label==label]
def _one_node(material,label:str):
 rows=_nodes_with_label(material,label)
 if len(rows)!=1:return None
 return rows[0]
def _socket(outputs,*names):
 for name in names:
  value=outputs.get(name)
  if value is not None:return value
 return None

def _disconnect_surface(tree,output):
 surface=output.inputs.get('Surface')
 if surface is None:raise BlenderLayerPreviewError('Material Output exposes no Surface input')
 for link in list(surface.links):tree.links.remove(link)
 return surface

def _emission_route(material,color_socket,*,mode:str,source_label:str,display_transform:str='identity'):
 tree=material.node_tree;nodes,links=tree.nodes,tree.links
 outputs=[n for n in nodes if getattr(n,'type',None)=='OUTPUT_MATERIAL']
 if len(outputs)!=1:raise BlenderLayerPreviewError(f'{material.name!r}: Material Output count {len(outputs)}, expected 1')
 color=color_socket
 if display_transform=='normal_to_rgb':
  scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.label='T6 DIAGNOSTIC normal * 0.5';links.new(color,scale.inputs[0]);si=scale.inputs.get('Scale')
  if si is None:raise BlenderLayerPreviewError('Blender Vector Math SCALE exposes no Scale input')
  si.default_value=0.5
  add=nodes.new('ShaderNodeVectorMath');add.operation='ADD';add.label='T6 DIAGNOSTIC normal visualization = 0.5*N+0.5';links.new(scale.outputs['Vector'],add.inputs[0]);add.inputs[1].default_value=(0.5,0.5,0.5);color=add.outputs['Vector']
 elif display_transform!='identity':raise BlenderLayerPreviewError(f'unsupported diagnostic display transform {display_transform!r}')
 emission=nodes.new('ShaderNodeEmission');emission.label=f'T6 DIAGNOSTIC emission: {mode}'
 color_input=emission.inputs.get('Color');strength=emission.inputs.get('Strength')
 if color_input is None:raise BlenderLayerPreviewError('Emission node exposes no Color input')
 links.new(color,color_input)
 if strength is not None:strength.default_value=1.0
 surface=_disconnect_surface(tree,outputs[0]);links.new(emission.outputs['Emission'],surface)
 material['T6_visual_diagnostic_mode']=mode;material['T6_visual_diagnostic_source_label']=source_label;material['T6_visual_diagnostic_display_transform']=display_transform
 material['T6_visual_diagnostic_warning']='diagnostic state display only; not final T6 material/lightmap/specular/reflection composition'

def _apply_visual_mode(material,details:dict,mode:str)->dict:
 if mode=='default':return {**details,'visualDiagnosticApplied':False,'visualDiagnosticMode':'default','visualDiagnosticUnavailableReason':None}
 if mode=='generated-diffuse':
  label='T6 encoded RGB square (retail shader)';node=_one_node(material,label)
  if node is None:return {**details,'visualDiagnosticApplied':False,'visualDiagnosticMode':mode,'visualDiagnosticUnavailableReason':'exact generated diffuse RGB-square node unavailable'}
  sock=_socket(node.outputs,'Vector','Color','Value')
  if sock is None:raise BlenderLayerPreviewError(f'{material.name!r}: generated diffuse diagnostic node has no usable output')
  _emission_route(material,sock,mode=mode,source_label=label);return {**details,'visualDiagnosticApplied':True,'visualDiagnosticMode':mode,'visualDiagnosticUnavailableReason':None}
 if mode=='directional-lightmap':
  label='T6 exact directional secondary-lightmap RGB';node=_one_node(material,label)
  if node is None:return {**details,'visualDiagnosticApplied':False,'visualDiagnosticMode':mode,'visualDiagnosticUnavailableReason':'exact directional lightmap state unavailable for material'}
  sock=_socket(node.outputs,'Vector','Color','Value')
  if sock is None:raise BlenderLayerPreviewError(f'{material.name!r}: directional diagnostic node has no usable output')
  _emission_route(material,sock,mode=mode,source_label=label);return {**details,'visualDiagnosticApplied':True,'visualDiagnosticMode':mode,'visualDiagnosticUnavailableReason':None}
 if mode=='reconstructed-normal':
  label='T6 retail normalize(rawNormal)';node=_one_node(material,label)
  if node is None:return {**details,'visualDiagnosticApplied':False,'visualDiagnosticMode':mode,'visualDiagnosticUnavailableReason':'exact reconstructed T6 normal unavailable for material'}
  sock=_socket(node.outputs,'Vector')
  if sock is None:raise BlenderLayerPreviewError(f'{material.name!r}: reconstructed normal node has no Vector output')
  _emission_route(material,sock,mode=mode,source_label=label,display_transform='normal_to_rgb');return {**details,'visualDiagnosticApplied':True,'visualDiagnosticMode':mode,'visualDiagnosticUnavailableReason':None}
 raise BlenderLayerPreviewError(f'unsupported visual diagnostic mode {mode!r}')

def _build_material_v9(blender_material,gltf_material:dict,technique:str,recipe:dict|None,image_cache:dict):
 details=_BASE_BUILD_V8(blender_material,gltf_material,technique,recipe,image_cache)
 return _apply_visual_mode(blender_material,details,_ACTIVE_VISUAL_MODE)

def apply_preview(input_path:Path,output_blend:Path,*,recipes:Path|None=None,strict:bool=False,visual_mode:str='default')->dict:
 global _ACTIVE_VISUAL_MODE
 if visual_mode not in MODES:raise BlenderLayerPreviewError(f'visual_mode must be one of {MODES}, got {visual_mode!r}')
 if bpy is None:raise BlenderLayerPreviewError("this adapter must run inside Blender's Python")
 old=v8._build_material_v8;_ACTIVE_VISUAL_MODE=visual_mode;v8._build_material_v8=_build_material_v9
 try:result=v8.apply_preview(input_path,output_blend,recipes=recipes,strict=strict)
 finally:v8._build_material_v8=old;_ACTIVE_VISUAL_MODE='default'
 applied=sum(1 for row in result.get('rebuilt',[]) if bool(row.get('visualDiagnosticApplied')));unavailable=sum(1 for row in result.get('rebuilt',[]) if row.get('visualDiagnosticMode')==visual_mode and not bool(row.get('visualDiagnosticApplied')) and visual_mode!='default')
 result['format']=FORMAT;result['baseFormat']=v8.FORMAT;result['visualDiagnosticMode']=visual_mode;result['visualDiagnosticAppliedMaterialCount']=applied;result['visualDiagnosticUnavailableMaterialCount']=unavailable
 result['visualDiagnosticPolicy']='default preserves v8. Diagnostic modes route one independently proven state to Emission; reconstructed-normal applies only 0.5*N+0.5 display encoding. No diagnostic mode is claimed to be final retail shading.'
 result['proofBoundary']=str(result.get('proofBoundary') or '')+' v9 adds opt-in visual inspection only; it does not introduce a final lighting composition.'
 report=output_blend.with_suffix(output_blend.suffix+'.t6_preview.json');report.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');return result

def _argv()->list[str]:return [] if '--' not in sys.argv else sys.argv[sys.argv.index('--')+1:]
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output_blend',type=Path);p.add_argument('--recipes',type=Path);p.add_argument('--strict',action='store_true');p.add_argument('--visual-mode',choices=MODES,default='default');a=p.parse_args(_argv());r=apply_preview(a.input,a.output_blend,recipes=a.recipes,strict=a.strict,visual_mode=a.visual_mode);print(json.dumps({'out':r['output'],'visualDiagnosticMode':r['visualDiagnosticMode'],'visualDiagnosticAppliedMaterialCount':r['visualDiagnosticAppliedMaterialCount'],'visualDiagnosticUnavailableMaterialCount':r['visualDiagnosticUnavailableMaterialCount']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
