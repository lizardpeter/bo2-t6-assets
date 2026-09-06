#!/usr/bin/env python3
from __future__ import annotations
import t6_blender_generated_layer_preview_v9 as v9

class Socket:
 def __init__(self,name):self.name=name;self.links=[];self.default_value=None
class Sockets:
 def __init__(self,names):self.rows=[Socket(n) for n in names];self.by={s.name:s for s in self.rows}
 def get(self,name):return self.by.get(name)
 def __getitem__(self,key):return self.rows[key] if isinstance(key,int) else self.by[key]
class Node:
 def __init__(self,typ,label='',inputs=(),outputs=()):self.type=typ;self.label=label;self.inputs=Sockets(inputs);self.outputs=Sockets(outputs);self.operation=None
class Nodes(list):
 def new(self,typ):
  if typ=='ShaderNodeEmission':n=Node('EMISSION',inputs=('Color','Strength'),outputs=('Emission',))
  elif typ=='ShaderNodeVectorMath':n=Node('VECTOR_MATH',inputs=('Vector','Vector_001','Scale'),outputs=('Vector','Value'))
  else:raise AssertionError(typ)
  self.append(n);return n
class Link:
 def __init__(self,a,b):self.a=a;self.b=b
class Links(list):
 def new(self,a,b):
  link=Link(a,b);self.append(link);b.links.append(link);return link
 def remove(self,link):
  super().remove(link)
  if link in link.b.links:link.b.links.remove(link)
class Tree:
 def __init__(self,nodes):self.nodes=Nodes(nodes);self.links=Links()
class Mat(dict):
 def __init__(self,nodes):super().__init__();self.name='fixture';self.node_tree=Tree(nodes)

def material(source_label,source_outputs=('Vector',)):
 out=Node('OUTPUT_MATERIAL',inputs=('Surface',),outputs=());src=Node('VECTOR_MATH',label=source_label,outputs=source_outputs);old=Node('BSDF',outputs=('BSDF',));m=Mat([out,src,old]);m.node_tree.links.new(old.outputs['BSDF'],out.inputs['Surface']);return m,src,out

def main()->int:
 m,src,out=material('T6 encoded RGB square (retail shader)');details=v9._apply_visual_mode(m,{'x':1},'generated-diffuse')
 assert details['visualDiagnosticApplied'] is True and m['T6_visual_diagnostic_mode']=='generated-diffuse'
 surface=out.inputs['Surface'];assert len(surface.links)==1 and surface.links[0].a.name=='Emission'
 emission=[n for n in m.node_tree.nodes if n.type=='EMISSION'];assert len(emission)==1 and len(emission[0].inputs['Color'].links)==1 and emission[0].inputs['Color'].links[0].a is src.outputs['Vector']

 m2,_,_=material('unrelated');d2=v9._apply_visual_mode(m2,{},'directional-lightmap');assert d2['visualDiagnosticApplied'] is False and 'unavailable' in d2['visualDiagnosticUnavailableReason']
 m3,_,_=material('unrelated');d3=v9._apply_visual_mode(m3,{'a':2},'default');assert d3['visualDiagnosticApplied'] is False and not [n for n in m3.node_tree.nodes if n.type=='EMISSION']

 m4,src4,out4=material('T6 retail normalize(rawNormal)');d4=v9._apply_visual_mode(m4,{},'reconstructed-normal');assert d4['visualDiagnosticApplied'] is True
 assert any(n.label=='T6 DIAGNOSTIC normal visualization = 0.5*N+0.5' for n in m4.node_tree.nodes)
 assert len(out4.inputs['Surface'].links)==1 and out4.inputs['Surface'].links[0].a.name=='Emission'
 print('PASS: Blender v9 exact-state visual diagnostic routing');return 0
if __name__=='__main__':raise SystemExit(main())
