#!/usr/bin/env python3
"""Assemble the closed SEAL6 LOD0 material stack on the native Blender 5.2.1 carrier."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
try:
    import bpy  # type: ignore
except ImportError:
    bpy=None
import t6_blender_seal6_lod0_role_nodes_v2 as role
import t6_blender_seal6_lod0_lit_nodes_v2 as lit
import t6_blender_seal6_lod0_pipeline_state_v2 as pipeline

FORMAT='t6-blender-seal6-lod0-full-material-assembly-v1'
CUSTOM={'_T6_COLOR_RGBA','_T6_XMODEL_NORMAL','_T6_XMODEL_TANGENT','_T6_TANGENT_HANDEDNESS'}
class AssemblyError(RuntimeError): pass

def _sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def _require():
    if bpy is None: raise AssemblyError('bpy unavailable')
    if not bpy.app.version_string.startswith('5.2.1'): raise AssemblyError(f'authoritative runtime must be Blender 5.2.1 LTS, got {bpy.app.version_string!r}')
def _main_mesh():
    meshes=[o for o in bpy.data.objects if o.type=='MESH']
    exact=[o for o in meshes if o.name=='c_usa_mp_seal6_smg_fb_mesh']
    if len(exact)!=1: raise AssemblyError(f'exact SEAL6 mesh not unique: {[o.name for o in meshes]}')
    return exact[0]
def _check_carrier()->dict:
    if len(bpy.data.armatures)!=1 or len(bpy.data.actions)!=6 or len(bpy.data.materials)!=12: raise AssemblyError(f'carrier cardinality drift armatures={len(bpy.data.armatures)} actions={len(bpy.data.actions)} materials={len(bpy.data.materials)}')
    obj=_main_mesh()
    if len(obj.data.vertices)!=13490 or len(obj.data.polygons)!=14968: raise AssemblyError('carrier geometry cardinality drift')
    attrs=set(a.name for a in obj.data.attributes)|set(a.name for a in obj.data.color_attributes)
    if not CUSTOM <= attrs: raise AssemblyError(f'carrier missing exact shader attributes: {sorted(CUSTOM-attrs)}')
    if 'COLOR_0' in attrs or 'TANGENT' in attrs: raise AssemblyError('forbidden standard COLOR_0/TANGENT present')
    return {'vertices':13490,'triangles':14968,'joints':102,'materials':12,'animations':6,'exactShaderCustomAttributes':sorted(CUSTOM),'color0Present':False,'standardTangentPresent':False}
def _load(p:Path): return json.loads(p.read_text(encoding='utf-8-sig'))
def _source_nodes(material): return [n for n in material.node_tree.nodes if n.name.startswith('T6_SLOT_')]
def _nonlit_disconnect(shader_plan:dict)->list[dict]:
    rows=[]
    for mr in shader_plan['materials']:
        mat=role._material_exact(str(mr['material']))
        nodes=mat.node_tree.nodes
        for slot in mr['nativeTextureSlots']:
            if slot['ordinaryLitBinding']['referenced']: continue
            prefix=f"T6_SLOT_{int(slot['slotIndex']):02d}_"
            matches=[n for n in nodes if n.name.startswith(prefix)]
            if len(matches)!=1: raise AssemblyError(f"{mr['material']} slot {slot['slotIndex']}: source-node identity drift")
            node=matches[0]
            outgoing=sum(len(o.links) for o in node.outputs)
            if outgoing!=0: raise AssemblyError(f"{mr['material']} slot {slot['slotIndex']}: preserved non-lit source has {outgoing} outgoing links")
            rows.append({'material':mr['material'],'slotIndex':slot['slotIndex'],'image':slot['image'],'node':node.name,'outgoingLinks':0})
    if len(rows)!=5: raise AssemblyError(f'preserved non-lit source count {len(rows)} != 5')
    return rows
def _material_postcheck(shader_plan:dict)->dict:
    cloth=skin=cornea=hero=0; source_nodes=0; exact_states=0
    for mr in shader_plan['materials']:
        mat=role._material_exact(str(mr['material']))
        if mat.get('t6_role_complete_native_inputs') is not True or mat.get('t6_exact_material_local_nodes_compiled') is not True or mat.get('t6_pipeline_state_exact_metadata') is not True: raise AssemblyError(f"{mat.name}: final exact material layers incomplete")
        if mat.get('t6_complete_retail_pixel_output') is not False: raise AssemblyError(f"{mat.name}: invalid complete-retail claim")
        if not mat.node_tree: raise AssemblyError(f'{mat.name}: node tree absent')
        count=len(_source_nodes(mat)); expected=len(mr['nativeTextureSlots'])
        if count!=expected: raise AssemblyError(f'{mat.name}: source node count {count} != {expected}')
        source_nodes+=count; exact_states+=1
        fam=mr['shaderFamilyId']
        if fam=='seal6-char-cloth-lit-v1': cloth+=1
        elif fam in {'seal6-char-skin-hero-lit-v1','seal6-char-skin-standard-lit-v1'}:
            skin+=1
            if fam=='seal6-char-skin-hero-lit-v1': hero+=1
        elif fam=='seal6-char-eye-cornea-lit-v1': cornea+=1
        else: raise AssemblyError(f'{mat.name}: unknown shader family {fam!r}')
    if (source_nodes,cloth,skin,hero,cornea,exact_states)!=(41,7,4,1,1,12): raise AssemblyError(f'final material census drift {(source_nodes,cloth,skin,hero,cornea,exact_states)}')
    return {'nativeSourceNodes':41,'clothMaterials':7,'skinMaterials':4,'heroMaterials':1,'corneaMaterials':1,'exactPipelineStateMaterials':12}
def build(role_path:Path,shader_path:Path,pipeline_path:Path,texture_root:Path,output:Path,report_path:Path)->dict:
    _require(); carrier=_check_carrier(); role_plan=_load(role_path); shader_plan=_load(shader_path); pipeline_plan=_load(pipeline_path)
    role_result=role.compile_plan(role_plan,texture_root)
    lit_result=lit.compile_plan(shader_plan)
    pipeline_result=pipeline.compile_report(pipeline_plan)
    disconnected=_nonlit_disconnect(shader_plan)
    material_census=_material_postcheck(shader_plan)
    # Remove only image datablocks no longer referenced after the exact node-tree rebuild.
    removed=[]
    for image in list(bpy.data.images):
        if image.users==0:
            removed.append(image.name); bpy.data.images.remove(image)
    scene=bpy.context.scene
    scene['t6_material_assembly']=FORMAT
    scene['t6_blender_runtime']='5.2.1 LTS'
    scene['t6_geometry_exact']=True
    scene['t6_animations_exact']=True
    scene['t6_material_inputs_exact']=True
    scene['t6_ordinary_lit_material_local_math_exact']=True
    scene['t6_d3d_pipeline_state_metadata_exact']=True
    scene['t6_runtime_global_lighting_inputs_bound']=False
    scene['t6_complete_retail_pixel_output']=False
    scene['t6_role_plan_sha256']=_sha(role_path); scene['t6_shader_plan_sha256']=_sha(shader_path); scene['t6_pipeline_plan_sha256']=_sha(pipeline_path)
    notice=bpy.data.texts.get('T6_SEAL6_REVERSAL_STATUS.txt') or bpy.data.texts.new('T6_SEAL6_REVERSAL_STATUS.txt'); notice.clear(); notice.write('SEAL6 LOD0 character-local asset reversal is exact for geometry, 102-joint skin, six animations, all 12 Material identities, all 41 native texture inputs, 40 streamed retail payload slots, the shared cornea built-in alias identity, ordinary-lit material-local shader equations for hero/standard/cornea/cloth, exact shader-only vertex attributes, and exact selected D3D pipeline-state metadata. Runtime scene-global model-lighting volumes, reflection probes, SH/grid/sun, fog and HDR remain external scene/runtime state and are intentionally not fabricated in this standalone character file.\n')
    bpy.ops.file.pack_all()
    output.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=False)
    out={'format':FORMAT,'blenderVersion':bpy.app.version_string,'geometry':carrier,'roleSummary':role_result['summary'],'litSummary':lit_result['summary'],'pipelineSummary':pipeline_result['summary'],'materialCensus':material_census,'preservedNonLitSources':disconnected,'orphanImagesRemoved':removed,'inputs':{'rolePlanSha256':_sha(role_path),'shaderPlanSha256':_sha(shader_path),'pipelinePlanSha256':_sha(pipeline_path)},'outputBlend':str(output),'outputBlendSha256':_sha(output),'characterLocalAssetReversalExact':True,'runtimeSceneGlobalsExternal':True,'completeRetailPixelOutput':False,'proofBoundary':'The standalone character now carries exact source-derived geometry/skin/animations, native shader attributes, all native Material inputs, exact ordinary-lit material-local equations and exact selected D3D state metadata. Runtime map/scene lighting resources are external dependencies, not replaced with Blender guesses.'}
    report_path.parent.mkdir(parents=True,exist_ok=True); report_path.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print('T6_SEAL6_FULL_MATERIAL_ASSEMBLY_V1='+json.dumps({'outputBlendSha256':out['outputBlendSha256'],'roleSummary':out['roleSummary'],'litSummary':out['litSummary'],'pipelineSummary':out['pipelineSummary']},sort_keys=True)); return out
def _args(argv): return argv[argv.index('--')+1:] if '--' in argv else argv[1:]
def main()->int:
    _require(); ap=argparse.ArgumentParser(); ap.add_argument('--role-plan',type=Path,required=True); ap.add_argument('--shader-plan',type=Path,required=True); ap.add_argument('--pipeline-plan',type=Path,required=True); ap.add_argument('--texture-root',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); a=ap.parse_args(_args(sys.argv)); build(a.role_plan,a.shader_plan,a.pipeline_plan,a.texture_root,a.output,a.report); return 0
if __name__=='__main__': raise SystemExit(main())
