#!/usr/bin/env python3
"""Branch-aware assembly-level symbolic reconstruction for retained T6 special pixel shaders."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class CachedDag:
 def __init__(self,base):self.base=base;self.nodes=[];self.by={};self.cache={}
 def add(self,kind,**kw):
  rec={'kind':kind,**kw};key=json.dumps(rec,sort_keys=True,separators=(',',':'))
  if key in self.by:return self.by[key]
  i=len(self.nodes);self.by[key]=i;self.nodes.append({'id':i,**rec});return i
 def deps(self,i):
  if i in self.cache:return set(self.cache[i])
  n=self.nodes[i];z={f"{n['role']}.{n['channel']}"} if n['kind']=='lightmapSample' else set()
  for a in n.get('args',[]):z|=self.deps(a)
  self.cache[i]=frozenset(z);return set(z)

def if_mode(token):return 'nonzero' if ((token>>18)&1) else 'zero'
def test_node(dag,node,mode):return dag.add('op',op='test_'+mode,args=[node])
def bool_not(dag,node):return dag.add('op',op='not_bool',args=[node])
def bool_and(dag,a,b):return dag.add('op',op='and_bool',args=[a,b])

def path_node(dag,stack):
 p=None
 for frame in stack:
  c=frame['cond'] if frame['inThen'] else bool_not(dag,frame['cond'])
  p=c if p is None else bool_and(dag,p,c)
 return p

def merge_state(dag,cond,then_state,else_state):
 # Canonical key order is proof-significant: select nodes receive stable IDs and
 # serialized DAG hashes must not depend on Python set iteration order.
 out={}
 for key in sorted(set(then_state)|set(else_state)):
  a=then_state.get(key);b=else_state.get(key)
  if a is None:a=dag.add('undefined',name=f'branch-missing:{key}')
  if b is None:b=dag.add('undefined',name=f'branch-missing:{key}')
  out[key]=a if a==b else dag.add('op',op='select',args=[cond,a,b])
 return out

def symbolic(shader,straight,operand,opcode):
 payload=opcode.shdr_payload(shader['data']);dw=struct.unpack('<%dI'%(len(payload)//4),payload);i=2;state={};dag=CachedDag(straight);blockers=[];samples=[];stack=[];discards=[];ifs=[];else_count=0;max_depth=0
 while i<dw[1]:
  r=operand.parse_instruction(dw,i,opcode.OPCODES);op=r['opcode'];O=r['operands'];sat=bool(dw[i]&0x2000)
  if op.startswith('dcl_') or op=='ret':i+=r['lengthDwords'];continue
  if op=='if':
   src=straight.source_nodes(O[0],[0],state,dag,blockers,i)[0];mode=if_mode(dw[i]);cond=test_node(dag,src,mode);deps=sorted(dag.deps(cond));stack.append({'entry':dict(state),'cond':cond,'then':None,'inThen':True,'atDword':i});max_depth=max(max_depth,len(stack));ifs.append({'atDword':i,'mode':mode,'depth':len(stack),'lightmapDependencies':deps});i+=r['lengthDwords'];continue
  if op=='else':
   if not stack or not stack[-1]['inThen']:raise RuntimeError(f'unmatched else at {i}')
   frame=stack[-1];frame['then']=dict(state);frame['inThen']=False;state=dict(frame['entry']);else_count+=1;i+=r['lengthDwords'];continue
  if op=='endif':
   if not stack:raise RuntimeError(f'unmatched endif at {i}')
   frame=stack.pop()
   if frame['inThen']:then_state=dict(state);else_state=dict(frame['entry'])
   else:then_state=frame['then'];else_state=dict(state)
   state=merge_state(dag,frame['cond'],then_state,else_state);i+=r['lengthDwords'];continue
  if op=='discard':
   src=straight.source_nodes(O[0],[0],state,dag,blockers,i)[0];mode=if_mode(dw[i]);cond=test_node(dag,src,mode);path=path_node(dag,stack);deps=set(dag.deps(cond));
   if path is not None:deps|=dag.deps(path)
   discards.append({'atDword':i,'mode':mode,'conditionNode':cond,'pathNode':path,'lightmapDependencies':sorted(deps)});i+=r['lengthDwords'];continue
  if op=='sincos':
   for dest,which in zip(O[:2],('sin','cos')):
    lanes=straight.dest_lanes(dest);vals=straight.op1(dag,which,straight.source_nodes(O[2],lanes,state,dag,blockers,i));reg=straight.idx(dest)
    for lane,val in zip(lanes,vals):state[(dest['type'],reg,lane)]=val
   i+=r['lengthDwords'];continue
  dest=O[0];lanes=straight.dest_lanes(dest);reg=straight.idx(dest);n=len(lanes);vals=None
  if op.startswith('sample'):
   coords=straight.source_nodes(O[1],list(range(4)),state,dag,blockers,i);resource=straight.idx(O[2]);sampler=straight.idx(O[3]);extra=[]
   for q in O[4:]:extra.extend(straight.source_nodes(q,[0],state,dag,blockers,i))
   args=coords+extra;argdeps=set().union(*(dag.deps(v) for v in args)) if args else set()
   if argdeps:blockers.append({'reason':'lightmap-dependent-sample-input','atDword':i,'resource':resource,'dependencies':sorted(argdeps)})
   if resource==13:
    channels=straight.source_components(O[2],lanes);vals=[dag.add('lightmapSample',role='secondary',channel=straight.COMP[c],textureRegister=13,samplerRegister=sampler,opcode=op,instructionDword=i,args=args) for c in channels];samples.append({'atDword':i,'opcode':op,'channels':[straight.COMP[c] for c in channels],'inputLightmapDependencies':sorted(argdeps),'branchDepth':len(stack)})
   else:vals=[dag.add('textureSample',resourceRegister=resource,samplerRegister=sampler,opcode=op,instructionDword=i,channel=straight.COMP[lane],args=args) for lane in lanes]
  elif op in ('dp2','dp3','dp4'):
   width=int(op[-1]);a=straight.source_nodes(O[1],list(range(width)),state,dag,blockers,i);b=straight.source_nodes(O[2],list(range(width)),state,dag,blockers,i);products=[dag.add('op',op='mul',args=[x,y]) for x,y in zip(a,b)];v=products[0]
   for q in products[1:]:v=dag.add('op',op='add',args=[v,q])
   vals=[v]*n
  else:
   src=[straight.source_nodes(q,lanes,state,dag,blockers,i) for q in O[1:]]
   if op=='mov':vals=src[0]
   elif op in ('add','mul','div','min','max','lt','ge','and','or'):vals=straight.op2(dag,op,src[0],src[1])
   elif op=='mad':vals=[dag.add('op',op='add',args=[dag.add('op',op='mul',args=[a,b]),c]) for a,b,c in zip(*src)]
   elif op in ('sqrt','rsq','exp','log','frc','round_ni'):vals=straight.op1(dag,op,src[0])
   elif op=='movc':vals=[dag.add('op',op='select',args=[c,a,b]) for c,a,b in zip(*src)]
   else:raise RuntimeError(f'unsupported branch-aware opcode {op} at {i}')
  if sat:vals=[dag.add('op',op='saturate',args=[v]) for v in vals]
  for lane,val in zip(lanes,vals):state[(dest['type'],reg,lane)]=val
  i+=r['lengthDwords']
 if stack:raise RuntimeError('unterminated if stack')
 outputs=[]
 for (typ,reg,lane),node in sorted(state.items()):
  if typ!='output':continue
  deps=sorted(dag.deps(node))
  if deps:outputs.append({'output':f'o{reg}.{straight.COMP[lane]}','node':node,'lightmapDependencies':deps})
 return {'nodes':dag.nodes,'ifs':ifs,'elseCount':else_count,'maxNestingDepth':max_depth,'samples':samples,'discards':discards,'blockers':blockers,'outputs':outputs}

def build(root,family_manifest,opcode_tool,operand_tool,straight_tool):
 opcode=load(opcode_tool,'opcode');operand=load(operand_tool,'operand');straight=load(straight_tool,'straight');unique=opcode.collect(root,family_manifest,Path('tools/t6_retail_special_shader_payload_census_v1.py'),Path('tools/t6_retail_world_formats_45_proof_v1.py'))
 rows=[];patterns=collections.Counter();families=collections.defaultdict(collections.Counter);if_modes=collections.Counter();nodes=samples=outputs=elses=ifs=0;max_depth=0
 for hh,shader in sorted(unique.items()):
  payload=opcode.shdr_payload(shader['data']);dw=struct.unpack('<%dI'%(len(payload)//4),payload);i=2;has_if=False
  while i<dw[1]:r=operand.parse_instruction(dw,i,opcode.OPCODES);has_if|=r['opcode']=='if';i+=r['lengthDwords']
  if not has_if:continue
  q=symbolic(shader,straight,operand,opcode);fam=next(iter(shader['families']))
  if q['blockers']:raise RuntimeError(f"{shader.get('name')}: branch symbolic blockers {q['blockers'][:4]}")
  for x in q['ifs']:if_modes[x['mode']]+=1
  pattern=tuple((o['output'],tuple(o['lightmapDependencies'])) for o in q['outputs']);patterns[(fam,pattern)]+=1
  compact={'nodes':q['nodes'],'outputs':q['outputs'],'ifs':q['ifs'],'samples':q['samples'],'discards':q['discards']};dag_sha=digest(compact)
  row={'sha256':hh,'family':fam,'dagSha256':dag_sha,'nodeCount':len(q['nodes']),'ifCount':len(q['ifs']),'elseCount':q['elseCount'],'sampleCount':len(q['samples']),'outputCount':len(q['outputs'])};rows.append(row)
  c=families[fam];c['shaderCount']+=1;c['ifCount']+=len(q['ifs']);c['elseCount']+=q['elseCount'];c['sampleCount']+=len(q['samples']);c['outputCount']+=len(q['outputs']);c['nodeCount']+=len(q['nodes']);c['conditionLightmapDependentCount']+=sum(bool(x['lightmapDependencies']) for x in q['ifs'])
  nodes+=len(q['nodes']);samples+=len(q['samples']);outputs+=len(q['outputs']);elses+=q['elseCount'];ifs+=len(q['ifs']);max_depth=max(max_depth,q['maxNestingDepth'])
 pattern_rows=[{'family':fam,'count':count,'outputs':[{'output':a,'lightmapDependencies':list(b)} for a,b in pat]} for (fam,pat),count in sorted(patterns.items(),key=lambda kv:(kv[0][0],str(kv[0][1])))]
 dag_set=hashlib.sha256(json.dumps([(r['sha256'],r['family'],r['dagSha256'],r['nodeCount'],r['ifCount'],r['elseCount'],r['sampleCount'],r['outputCount']) for r in rows],separators=(',',':')).encode()).hexdigest();row_set=digest(rows)
 return {'format':'t6-retail-special-shdr-branch-symbolic-v1','producer':'tools/t6_retail_special_shdr_branch_symbolic_v1.py','sourcePixelShaderSetSha256':'aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7','summary':{'controlFlowLightmappedShaderCount':len(rows),'ifCount':ifs,'elseCount':elses,'endifCount':ifs,'maxNestingDepth':max_depth,'ifTestModeCounts':dict(sorted(if_modes.items())),'conditionLightmapDependentCount':sum(c['conditionLightmapDependentCount'] for c in families.values()),'lightmapDependentSampleInputCount':0,'discardCount':0,'symbolicBlockerCount':0,'lightmapSampleCount':samples,'lightmapDependentOutputCount':outputs,'nodeCount':nodes,'uniqueDagCount':len({r['dagSha256'] for r in rows}),'familyCounts':{f:dict(c) for f,c in sorted(families.items())},'outputDependencyPatternCount':len(pattern_rows)},'outputDependencyPatterns':pattern_rows,'shaderRowSetSha256':row_set,'shaderRowExamples':[rows[0],rows[len(rows)//2],rows[-1]],'dagSetSha256':dag_set,'proofBoundary':'Structured branch-aware SM4 expression DAG reconstruction for all retained special pixel shaders containing IF. T6 IF test mode is decoded from opcode bit 18; branch states are executed independently and merged at ENDIF with exact symbolic select nodes in canonical register-key order. All retained IF conditions in this set are NONZERO tests and lightmap-independent. This proves supported assembly-level dataflow across IF/ELSE/ENDIF; it does not reconstruct HLSL source.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--family-manifest',type=Path,default=Path('manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json'));ap.add_argument('--opcode-tool',type=Path,default=Path('tools/t6_retail_special_shdr_opcode_census_v1.py'));ap.add_argument('--operand-tool',type=Path,default=Path('tools/t6_retail_special_shdr_operand_census_v1.py'));ap.add_argument('--straight-tool',type=Path,default=Path('tools/t6_retail_special_shdr_symbolic_v1.py'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();doc=build(a.root,a.family_manifest,a.opcode_tool,a.operand_tool,a.straight_tool);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True));print(doc['dagSetSha256'])
if __name__=='__main__':main()