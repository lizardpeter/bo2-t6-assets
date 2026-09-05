#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
import t6_blender_scalar_dag_nodes_v1 as compiler

class Socket:
 def __init__(self):self.default_value=None
class Sockets:
 def __init__(self,n=4):self.x=[Socket() for _ in range(n)]
 def __getitem__(self,i):return self.x[i]
class Node:
 def __init__(self,t):self.type=t;self.operation=None;self.label="";self.inputs=Sockets();self.outputs=Sockets(2)
class Nodes:
 def __init__(self):self.created=[]
 def new(self,t):n=Node(t);self.created.append(n);return n
class Links:
 def __init__(self):self.created=[]
 def new(self,a,b):self.created.append((a,b))

def _sha(d):return hashlib.sha256(json.dumps({"format":d["format"],"root":d["root"],"nodes":d["nodes"]},sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _dag():
 d={"format":"t6-generated-height-weight-dag-v1","root":4,"nodeCount":5,"ordering":"reachable child-before-parent; operation argument order preserved","nodes":[{"id":0,"kind":"sample","resource":"normalMapSampler1","channel":"x","sampler":"s2"},{"id":1,"kind":"lit","value":2.0},{"id":2,"kind":"mul","args":[0,1]},{"id":3,"kind":"lit","value":-1.0},{"id":4,"kind":"add","args":[2,3]}]};d["forensicDagSha256"]=_sha(d);return d
def main():
 n=Nodes();l=Links();sample=Socket();out=compiler.compile_scalar_dag(n,l,_dag(),label_prefix="T6 normal decode",sample_sockets={("normalMapSampler1","x"):sample})
 assert out is n.created[-1].outputs[0]
 assert [x.operation for x in n.created if x.type=="ShaderNodeMath"]==["MULTIPLY","ADD"]
 vals=[x.outputs[0].default_value for x in n.created if x.type=="ShaderNodeValue"]
 assert vals==[2.0,-1.0]
 assert len(l.created)==4
 try:compiler.compile_scalar_dag(Nodes(),Links(),_dag(),label_prefix="bad",sample_sockets={})
 except compiler.BlenderScalarDagError as exc:assert "no exact sample socket" in str(exc)
 else:raise AssertionError("unbound scalar sample accepted")
 print("PASS: reusable exact Blender scalar DAG compiler v1")
if __name__=="__main__":main()
