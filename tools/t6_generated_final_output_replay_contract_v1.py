#!/usr/bin/env python3
"""Renderer-neutral replay contract for generated T6 slot-4 final output.

This contract does not reinterpret the retail shader. It preserves each exact
symbolic shader DAG once per CSO SHA and binds every generated material owner to
its known input state:
- material cbuffer inputs -> exact retained float32 values when supplied;
- T6 code constants -> exact enum/accessor/update-frequency identity, runtime dynamic;
- material texture inputs -> exact per-material GfxImage when uniquely resolved;
- T6 code samplers -> exact MaterialTextureSource identity, runtime dynamic;
- unresolved/ambiguous inputs -> explicit blockers.

No arithmetic is folded, reordered, reassociated, physically renamed, or mapped
to generic PBR semantics. A contract can be program-identity complete while
still requiring dynamic engine values/resources from the eventual runtime.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-replay-contract-v1'
FINAL_FORMAT='t6-generated-slot4-final-output-symbolic-v3'
CB_FORMAT='t6-generated-final-output-cbuffer-signature-v2'
CODE_CONST_FORMAT='t6-generated-final-output-code-constant-identity-v2'
TEX_FORMAT='t6-generated-final-output-texture-resource-binding-v2'
CODE_SAMPLER_FORMAT='t6-generated-final-output-code-sampler-identity-v2'
MAT_SAMPLER_FORMAT='t6-generated-final-output-material-sampler-binding-v1'
MAT_VALUES_FORMAT='t6-generated-final-output-material-cbuffer-values-v3'
class ReplayContractError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _index(rows:list[dict],key:str,label:str)->dict:
 out={}
 for row in rows:
  value=str(row.get(key) or '')
  if not value or value in out:raise ReplayContractError(f'invalid/duplicate {label} {value!r}')
  out[value]=row
 return out

def _by_sha(doc:dict,label:str)->dict:return _index(doc.get('shaders',[]),'sha256',label)
def _assignment(rows:list[dict],technique:str,label:str)->dict|None:
 matches=[r for r in rows if str(r.get('techniqueSet') or '')==technique]
 if len(matches)>1:raise ReplayContractError(f'{label}: TechniqueSet {technique!r} has {len(matches)} assignments')
 return matches[0] if matches else None

def _material_values(doc:dict|None)->dict:
 if doc is None:return {}
 if doc.get('format')!=MAT_VALUES_FORMAT:raise ReplayContractError(f"unexpected material-values format {doc.get('format')!r}")
 return _index(doc.get('materials',[]),'material','material-value row')
def _material_samplers(doc:dict)->dict:return _index(doc.get('materials',[]),'material','material-sampler row')

def _code_const_assignment(shader:dict,symbol:str,technique:str)->dict|None:
 rows=[r for r in shader.get('assignments',[]) if str(r.get('symbol') or '')==symbol and str(r.get('techniqueSet') or '')==technique]
 if len(rows)>1:raise ReplayContractError(f'{symbol}/{technique}: duplicate code-constant identities')
 return rows[0] if rows else None

def _material_value(row:dict|None,symbol:str)->dict|None:
 if row is None:return None
 rows=[r for r in row.get('resolvedMaterialBindings',[]) if str(r.get('symbol') or '')==symbol]
 if len(rows)>1:raise ReplayContractError(f"{row.get('material')} {symbol}: duplicate material cbuffer values")
 return rows[0] if rows else None

def _material_sampler(row:dict|None,resource:str)->dict|None:
 if row is None:return None
 rows=[r for r in row.get('bindings',[]) if str(r.get('resource') or '')==resource]
 if len(rows)>1:raise ReplayContractError(f"{row.get('material')} {resource}: duplicate material sampler bindings")
 return rows[0] if rows else None

def _shader_external_symbols(shader:dict)->list[str]:
 return sorted({str(n.get('name')) for n in shader.get('nodes',[]) if n.get('kind')=='symbol' and not str(n.get('name') or '').startswith('cb')})

def build(final_doc:dict,cb_doc:dict,code_const_doc:dict,texture_doc:dict,code_sampler_doc:dict,material_sampler_doc:dict,material_values_doc:dict|None=None)->dict:
 expected=((final_doc,FINAL_FORMAT,'final-output'),(cb_doc,CB_FORMAT,'cbuffer'),(code_const_doc,CODE_CONST_FORMAT,'code-constant'),(texture_doc,TEX_FORMAT,'texture'),(code_sampler_doc,CODE_SAMPLER_FORMAT,'code-sampler'),(material_sampler_doc,MAT_SAMPLER_FORMAT,'material-sampler'))
 for doc,fmt,label in expected:
  if doc.get('format')!=fmt:raise ReplayContractError(f"unexpected {label} format {doc.get('format')!r}")
 shaders=_by_sha(final_doc,'final shader');cb_by=_by_sha(cb_doc,'cbuffer shader');cc_by=_by_sha(code_const_doc,'code-constant shader');tex_by=_by_sha(texture_doc,'texture shader');cs_by=_by_sha(code_sampler_doc,'code-sampler shader')
 owners=_index(final_doc.get('materials',[]),'material','final material');mv_by=_material_values(material_values_doc);ms_by=_material_samplers(material_sampler_doc)
 # All proof sidecars must cover every final shader exactly; extra rows are also rejected.
 final_shas=set(shaders)
 for label,index in (('cbuffer',cb_by),('code-constant',cc_by),('texture',tex_by),('code-sampler',cs_by)):
  if set(index)!=final_shas:raise ReplayContractError(f'{label} shader identity set differs from final DAG')

 programs=[]
 for sha,row in sorted(shaders.items()):
  programs.append({'pixelShaderSha256':sha,'shaderModel':row.get('shaderModel'),'techniqueSets':copy.deepcopy(row.get('techniqueSets',[])),'nodes':copy.deepcopy(row.get('nodes',[])),'outputs':copy.deepcopy(row.get('outputs',[])),'samples':copy.deepcopy(row.get('samples',[])),'branches':copy.deepcopy(row.get('branches',[])),'discards':copy.deepcopy(row.get('discards',[])),'externalNonCbufferSymbols':_shader_external_symbols(row),'programSha256':_jhash({'nodes':row.get('nodes',[]),'outputs':row.get('outputs',[]),'samples':row.get('samples',[]),'branches':row.get('branches',[]),'discards':row.get('discards',[])})})

 materials=[];blocker_counts=Counter();dynamic_const_slots=set();dynamic_sampler_slots=set();static_cb=static_tex=0
 for material,owner in sorted(owners.items()):
  sha=str(owner.get('pixelShaderSha256') or '');technique=str(owner.get('techniqueSet') or '')
  if sha not in shaders or not technique:raise ReplayContractError(f'{material!r}: invalid shader/TechniqueSet owner identity')
  cbshader=cb_by[sha];ccshader=cc_by[sha];csshader=cs_by[sha];mv=mv_by.get(material);ms=ms_by.get(material)
  cbuffer_inputs=[];material_state_complete=True;dynamic_identity_complete=True;source_identity_complete=True
  for item in cbshader.get('usedCbufferSymbols',[]):
   symbol=str(item.get('symbol') or '');assignment=_assignment(item.get('techniqueAssignments',[]),technique,f'{material}/{symbol}')
   if assignment is None:raise ReplayContractError(f'{material}/{symbol}: TechniqueSet assignment absent from corrected cbuffer proof')
   source_class=str(assignment.get('sourceClass') or '')
   base={'symbol':symbol,'nodeIds':copy.deepcopy(item.get('nodeIds',[])),'buffer':copy.deepcopy(item.get('buffer')),'variable':copy.deepcopy(item.get('variable')),'source':copy.deepcopy(assignment)}
   value=_material_value(mv,symbol)
   code=_code_const_assignment(ccshader,symbol,technique)
   if source_class=='material':
    if value is None:
     base.update({'bindingKind':'materialConstantUnresolved','staticValueResolved':False});material_state_complete=False;source_identity_complete=False;blocker_counts['materialConstantValueMissing']+=1
    else:
     mc=copy.deepcopy(value.get('materialConstant'));base.update({'bindingKind':'retailMaterialConstant','staticValueResolved':True,'materialConstant':mc});static_cb+=1
   elif code is not None:
    base.update({'bindingKind':'t6CodeConstantDynamic','staticValueResolved':False,'dynamicIdentity':copy.deepcopy(code)});dynamic_const_slots.add((int(code['resolvedEnumValue']),str(code.get('accessor')),str(code.get('arrayIndex'))))
   else:
    base.update({'bindingKind':'unresolvedCbufferSource','staticValueResolved':False});source_identity_complete=False;dynamic_identity_complete=False;blocker_counts['cbufferSourceUnresolved']+=1
   cbuffer_inputs.append(base)

  texture_inputs=[]
  for resource in csshader.get('resources',[]):
   name=str(resource.get('resource') or '');assignment=_assignment(resource.get('techniqueAssignments',[]),technique,f'{material}/{name}')
   if assignment is None:raise ReplayContractError(f'{material}/{name}: TechniqueSet assignment absent from corrected code-sampler proof')
   base={'resource':name,'sampleNodeIds':copy.deepcopy(resource.get('sampleNodeIds',[])),'resourceRegisters':copy.deepcopy(resource.get('resourceRegisters',[])),'samplerNames':copy.deepcopy(resource.get('samplerNames',[])),'samplerRegisters':copy.deepcopy(resource.get('samplerRegisters',[])),'opcodes':copy.deepcopy(resource.get('opcodes',[])),'channels':copy.deepcopy(resource.get('channels',[])),'source':{k:copy.deepcopy(v) for k,v in assignment.items() if k not in ('codeSamplerIdentity',)}}
   code=assignment.get('codeSamplerIdentity')
   matbinding=_material_sampler(ms,name)
   if code is not None:
    base.update({'bindingKind':'t6CodeSamplerDynamic','runtimeResourceResolved':False,'dynamicIdentity':copy.deepcopy(code)});dynamic_sampler_slots.add((int(code['enumValue']),str(code.get('accessor'))))
   elif str(assignment.get('sourceClass') or '')=='material':
    if matbinding is None:
     base.update({'bindingKind':'materialSamplerUnresolved','runtimeResourceResolved':False});material_state_complete=False;source_identity_complete=False;blocker_counts['materialSamplerBindingMissing']+=1
    elif matbinding.get('status')=='unique' and isinstance(matbinding.get('resolvedTexture'),dict):
     base.update({'bindingKind':'retailMaterialTexture','runtimeResourceResolved':True,'resolvedTexture':copy.deepcopy(matbinding['resolvedTexture'])});static_tex+=1
    else:
     base.update({'bindingKind':'materialSamplerAmbiguous','runtimeResourceResolved':False,'candidates':copy.deepcopy(matbinding.get('candidates',[]))});material_state_complete=False;source_identity_complete=False;blocker_counts['materialSamplerAmbiguous']+=1
   else:
    base.update({'bindingKind':'unresolvedTextureSource','runtimeResourceResolved':False});source_identity_complete=False;dynamic_identity_complete=False;blocker_counts['textureSourceUnresolved']+=1
   texture_inputs.append(base)
  blockers=sum(1 for row in cbuffer_inputs if row['bindingKind'] in ('materialConstantUnresolved','unresolvedCbufferSource'))+sum(1 for row in texture_inputs if row['bindingKind'] in ('materialSamplerUnresolved','materialSamplerAmbiguous','unresolvedTextureSource'))
  identity_complete=source_identity_complete and dynamic_identity_complete
  materials.append({'material':material,'techniqueSet':technique,'pixelShaderSha256':sha,'cbufferInputs':cbuffer_inputs,'textureInputs':texture_inputs,'materialStaticStateComplete':material_state_complete,'dynamicEngineInputIdentityComplete':dynamic_identity_complete,'sourceIdentityComplete':source_identity_complete,'programIdentityComplete':True,'replayIdentityComplete':identity_complete and material_state_complete,'runtimeDynamicInputsStillRequired':any(row['bindingKind']=='t6CodeConstantDynamic' for row in cbuffer_inputs) or any(row['bindingKind']=='t6CodeSamplerDynamic' for row in texture_inputs),'blockerCount':blockers})

 summary={'programCount':len(programs),'materialCount':len(materials),'programIdentityCompleteMaterialCount':sum(1 for m in materials if m['programIdentityComplete']),'materialStaticStateCompleteCount':sum(1 for m in materials if m['materialStaticStateComplete']),'dynamicEngineInputIdentityCompleteCount':sum(1 for m in materials if m['dynamicEngineInputIdentityComplete']),'sourceIdentityCompleteCount':sum(1 for m in materials if m['sourceIdentityComplete']),'replayIdentityCompleteMaterialCount':sum(1 for m in materials if m['replayIdentityComplete']),'materialRequiringRuntimeDynamicInputsCount':sum(1 for m in materials if m['runtimeDynamicInputsStillRequired']),'uniqueDynamicCodeConstantSlotCount':len(dynamic_const_slots),'uniqueDynamicCodeSamplerSlotCount':len(dynamic_sampler_slots),'resolvedStaticMaterialCbufferBindingCount':static_cb,'resolvedStaticMaterialTextureBindingCount':static_tex,'blockerCounts':dict(sorted(blocker_counts.items()))}
 return {'format':FORMAT,'sourceFormats':{'finalOutput':FINAL_FORMAT,'cbuffer':CB_FORMAT,'codeConstants':CODE_CONST_FORMAT,'textureBindings':TEX_FORMAT,'codeSamplers':CODE_SAMPLER_FORMAT,'materialSamplers':MAT_SAMPLER_FORMAT,'materialValues':None if material_values_doc is None else MAT_VALUES_FORMAT},'programs':programs,'materials':materials,'summary':summary,'programsSha256':_jhash(programs),'materialsSha256':_jhash(materials),'proofBoundary':'Renderer-neutral identity/state contract over the exact generated slot-4 symbolic DAG. Exact material literals/images are bound when proven; T6 engine code constants/samplers remain declared dynamic slots with exact identities. Ambiguities and missing identities remain blockers. Arithmetic, sampling topology, branches, discards, and shader-native inputs are preserved without evaluation, PBR remap, or physical relabeling.'}

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer',type=Path,required=True);p.add_argument('--code-constants',type=Path,required=True);p.add_argument('--textures',type=Path,required=True);p.add_argument('--code-samplers',type=Path,required=True);p.add_argument('--material-samplers',type=Path,required=True);p.add_argument('--material-values',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.cbuffer.read_text()),json.loads(a.code_constants.read_text()),json.loads(a.textures.read_text()),json.loads(a.code_samplers.read_text()),json.loads(a.material_samplers.read_text()),None if a.material_values is None else json.loads(a.material_values.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
