#!/usr/bin/env python3
"""Direct assembly-level symbolic DAG reconstruction for branch-free retained T6 special pixel shaders."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path
COMP='xyzw'

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class Dag:
 def __init__(self):self.nodes=[];self.by={}
 def add(self,kind,**kw):
  rec={'kind':kind,**kw};key=json.dumps(rec,sort_keys=True,separators=(',',':'))
  if key in self.by:return self.by[key]
  i=len(self.nodes);self.by[key]=i;self.nodes.append({'id':i,**rec});return i
 def deps(self,i):
  n=self.nodes[i];z={f"{n['role']}.{n['channel']}"} if n['kind']=='lightmapSample' else set()
  for a in n.get('args',[]):z|=self.deps(a)
  return z

def idx(o):return o['indices'][0].get('immediate32') if o['indices'] else None

def dest_lanes(o):
 c=o['component'];n=c['numComponents']
 if n==2 and c.get('selectionMode')=='mask':return [i for i in range(4) if c['mask']&(1<<i)]
 if n==1:return [0]
 raise RuntimeError(f"unsupported destination component shape: {c}")

def source_components(o,lanes):
 c=o['component'];n=c['numComponents']
 if o['type'] in ('immediate32','immediate64'):return [None]*len(lanes)
 if n==0:return [None]*len(lanes)
 if n==1:return [0]*len(lanes)
 mode=c.get('selectionMode')
 if mode=='select1':return [c['select']]*len(lanes)
 if mode=='swizzle':return [c['swizzle'][lane] for lane in lanes]
 if mode=='mask':return lanes
 raise RuntimeError(f"unsupported source component shape: {c}")

def apply_modifier(dag,node,o):
 for e in o['extensions']:
  m=e['modifier']
  if m=='neg':node=dag.add('op',op='neg',args=[node])
  elif m=='abs':node=dag.add('op',op='abs',args=[node])
  elif m=='absneg':node=dag.add('op',op='neg',args=[dag.add('op',op='abs',args=[node])])
  elif m!='none':raise RuntimeError(f'unsupported operand modifier {m}')
 return node

def source_nodes(o,lanes,state,dag,blockers,at):
 typ=o['type']
 if typ=='immediate32':
  lit=o['literalDwords']
  if len(lit)==1:return [dag.add('literal32',bits=f'{lit[0]:08x}') for _ in lanes]
  if len(lit)!=4:raise RuntimeError(f'unexpected immediate32 width {len(lit)}')
  return [dag.add('literal32',bits=f'{lit[l]:08x}') for l in lanes]
 comps=source_components(o,lanes)
 if typ=='input':return [apply_modifier(dag,dag.add('symbol',name=f'v{idx(o)}.{COMP[c]}'),o) for c in comps]
 if typ=='constant_buffer':
  if len(o['indices'])!=2:raise RuntimeError('constant-buffer operand does not have two indices')
  base=f"cb{o['indices'][0]['immediate32']}[{o['indices'][1]['immediate32']}]"
  return [apply_modifier(dag,dag.add('symbol',name=f'{base}.{COMP[c]}'),o) for c in comps]
 if typ in ('temp','output'):
  reg=idx(o);out=[]
  for c in comps:
   key=(typ,reg,c)
   if key not in state:
    blockers.append({'reason':'read-before-write','atDword':at,'register':f'{typ}:{reg}.{COMP[c]}'})
    node=dag.add('undefined',name=f'{typ}:{reg}.{COMP[c]}')
   else:node=state[key]
   out.append(apply_modifier(dag,node,o))
  return out
 if typ in ('resource','sampler'):return [dag.add('symbol',name=f'{typ}:{idx(o)}') for _ in lanes]
 raise RuntimeError(f'unsupported source operand type {typ}')

def op1(dag,op,a):return [dag.add('op',op=op,args=[x]) for x in a]
def op2(dag,op,a,b):return [dag.add('op',op=op,args=[x,y]) for x,y in zip(a,b)]

def symbolic(shader,operand,opcode):
 payload=opcode.shdr_payload(shader['data']);dw=struct.unpack('<%dI'%(len(payload)//4),payload);i=2;state={};dag=Dag();blockers=[];samples=[];has_cf=False;side=[]
 while i<dw[1]:
  r=operand.parse_instruction(dw,i,opcode.OPCODES);op=r['opcode'];O=r['operands'];sat=bool(dw[i]&0x2000)
  if op.startswith('dcl_') or op=='ret':i+=r['lengthDwords'];continue
  if op in ('if','else','endif'):has_cf=True;i+=r['lengthDwords'];continue
  if op=='discard':
   cond=source_nodes(O[0],[0],state,dag,blockers,i);deps=set().union(*(dag.deps(n) for n in cond));side.append({'op':'discard','atDword':i,'lightmapDependencies':sorted(deps)})
   if deps:blockers.append({'reason':'lightmap-dependent-discard','atDword':i,'dependencies':sorted(deps)})
   i+=r['lengthDwords'];continue
  if op=='sincos':
   for dest,which in zip(O[:2],('sin','cos')):
    lanes=dest_lanes(dest);vals=op1(dag,which,source_nodes(O[2],lanes,state,dag,blockers,i));reg=idx(dest)
    for lane,val in zip(lanes,vals):state[(dest['type'],reg,lane)]=val
   i+=r['lengthDwords'];continue
  dest=O[0];lanes=dest_lanes(dest);reg=idx(dest);n=len(lanes);vals=None
  if op.startswith('sample'):
   coords=source_nodes(O[1],list(range(4)),state,dag,blockers,i);resource=idx(O[2]);sampler=idx(O[3]);extra=[]
   for q in O[4:]:extra.extend(source_nodes(q,[0],state,dag,blockers,i))
   args=coords+extra;argdeps=set().union(*(dag.deps(v) for v in args)) if args else set()
   if argdeps:blockers.append({'reason':'lightmap-dependent-sample-input','atDword':i,'resource':resource,'dependencies':sorted(argdeps)})
   if resource==13:
    channels=source_components(O[2],lanes)
    vals=[dag.add('lightmapSample',role='secondary',channel=COMP[c],textureRegister=13,samplerRegister=sampler,opcode=op,instructionDword=i,args=args) for c in channels]
    samples.append({'atDword':i,'opcode':op,'resourceRegister':13,'samplerRegister':sampler,'destLanes':[COMP[x] for x in lanes],'channels':[COMP[x] for x in channels],'inputLightmapDependencies':sorted(argdeps)})
   else:vals=[dag.add('textureSample',resourceRegister=resource,samplerRegister=sampler,opcode=op,instructionDword=i,channel=COMP[lane],args=args) for lane in lanes]
  elif op in ('dp2','dp3','dp4'):
   width=int(op[-1]);a=source_nodes(O[1],list(range(width)),state,dag,blockers,i);b=source_nodes(O[2],list(range(width)),state,dag,blockers,i);products=[dag.add('op',op='mul',args=[x,y]) for x,y in zip(a,b)];v=products[0]
   for q in products[1:]:v=dag.add('op',op='add',args=[v,q])
   vals=[v]*n
  else:
   src=[source_nodes(q,lanes,state,dag,blockers,i) for q in O[1:]]
   if op=='mov':vals=src[0]
   elif op in ('add','mul','div','min','max','lt','ge','and','or'):vals=op2(dag,op,src[0],src[1])
   elif op=='mad':vals=[dag.add('op',op='add',args=[dag.add('op',op='mul',args=[a,b]),c]) for a,b,c in zip(*src)]
   elif op in ('sqrt','rsq','exp','log','frc','round_ni'):vals=op1(dag,op,src[0])
   elif op=='movc':vals=[dag.add('op',op='select',args=[c,a,b]) for c,a,b in zip(*src)]
   else:raise RuntimeError(f'unsupported straight-line opcode {op} at {i}')
  if sat:vals=[dag.add('op',op='saturate',args=[v]) for v in vals]
  for lane,val in zip(lanes,vals):state[(dest['type'],reg,lane)]=val
  i+=r['lengthDwords']
 outputs=[]
 for (typ,reg,lane),node in sorted(state.items()):
  if typ!='output':continue
  deps=sorted(dag.deps(node))
  if deps:outputs.append({'output':f'o{reg}.{COMP[lane]}','node':node,'lightmapDependencies':deps})
 return {'hasControlFlow':has_cf,'samples':samples,'blockers':blockers,'outputs':outputs,'nodes':dag.nodes,'sideEffects':side}

def build(root,family_manifest,opcode_tool,operand_tool):
 opcode=load(opcode_tool,'opcode');operand=load(operand_tool,'operand');unique=opcode.collect(root,family_manifest,Path('tools/t6_retail_special_shader_payload_census_v1.py'),Path('tools/t6_retail_world_formats_45_proof_v1.py'))
 rows=[];patterns=collections.Counter();families=collections.defaultdict(collections.Counter);node_count=sample_count=output_count=0
 for hh,shader in sorted(unique.items()):
  q=symbolic(shader,operand,opcode);fam=next(iter(shader['families']))
  if q['hasControlFlow'] or not q['samples']:continue
  if q['blockers']:raise RuntimeError(f"{shader.get('name')}: symbolic blockers {q['blockers'][:4]}")
  pattern=tuple((o['output'],tuple(o['lightmapDependencies'])) for o in q['outputs']);patterns[(fam,pattern)]+=1
  compact={'nodes':q['nodes'],'outputs':q['outputs'],'samples':q['samples'],'sideEffects':q['sideEffects']};dag_sha=digest(compact)
  rows.append({'sha256':hh,'name':shader.get('name'),'family':fam,'sampleCount':len(q['samples']),'nodeCount':len(q['nodes']),'outputCount':len(q['outputs']),'dagSha256':dag_sha,'outputPattern':[{'output':a,'lightmapDependencies':list(b)} for a,b in pattern]})
  families[fam]['shaderCount']+=1;families[fam]['sampleCount']+=len(q['samples']);families[fam]['nodeCount']+=len(q['nodes']);families[fam]['outputCount']+=len(q['outputs']);node_count+=len(q['nodes']);sample_count+=len(q['samples']);output_count+=len(q['outputs'])
 pattern_rows=[{'family':fam,'count':count,'outputs':[{'output':a,'lightmapDependencies':list(b)} for a,b in pat]} for (fam,pat),count in sorted(patterns.items(),key=lambda kv:(kv[0][0],str(kv[0][1])))]
 set_sha=hashlib.sha256(json.dumps([(r['sha256'],r['family'],r['dagSha256'],r['nodeCount'],r['outputCount'],r['sampleCount']) for r in rows],separators=(',',':')).encode()).hexdigest()
 return {'format':'t6-retail-special-shdr-symbolic-v1','producer':'tools/t6_retail_special_shdr_symbolic_v1.py','sourcePixelShaderSetSha256':'aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7','summary':{'branchFreeLightmappedShaderCount':len(rows),'symbolicBlockerCount':0,'lightmapSampleCount':sample_count,'lightmapDependentOutputCount':output_count,'nodeCount':node_count,'uniqueDagCount':len({r['dagSha256'] for r in rows}),'familyCounts':{f:dict(c) for f,c in sorted(families.items())},'outputDependencyPatternCount':len(pattern_rows),'lightmapDependentSampleInputCount':0,'lightmapDependentDiscardCount':0},'outputDependencyPatterns':pattern_rows,'shaderRows':rows,'dagSetSha256':set_sha,'proofBoundary':'Direct straight-line SM4 expression DAG reconstruction from retained SHDR tokens for special pixel shaders that have no if/else/endif and directly sample t13. Every t13 sample remains a distinct symbolic atom keyed by its instruction DWORD; coordinates, LOD, bias and derivative inputs are independently checked for lightmap dependency. This proves supported assembly-level dataflow, not reconstructed HLSL, and excludes control-flow shaders.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--opcode-tool',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));ap.add_argument('--operand-tool',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();doc=build(a.root,a.family_manifest,a.opcode_tool,a.operand_tool);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True));print(doc['dagSetSha256'])
if __name__=='__main__':main()
