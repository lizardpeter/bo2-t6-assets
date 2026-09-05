#!/usr/bin/env python3
from __future__ import annotations
from types import SimpleNamespace
import t6_generated_normal_sample_decode_dag_v2 as decode
import t6_generated_normal_sample_decode_dag_v1 as v1

class Comp:
 @staticmethod
 def symbolic(blob,opcode,operand,inspect):
  return SimpleNamespace(n=[
   {"kind":"sample","resource":"normalMapSampler","channel":"x","sampler":"s1"}, #0
   {"kind":"lit","value":2.0}, #1
   {"kind":"mul","args":[0,1]}, #2
   {"kind":"lit","value":-1.0}, #3
   {"kind":"add","args":[2,3]}, #4 base x
   {"kind":"sample","resource":"normalMapSampler","channel":"y","sampler":"s1"}, #5
   {"kind":"mul","args":[5,1]}, #6
   {"kind":"add","args":[6,3]}, #7 base y
   {"kind":"sample","resource":"normalMapSampler1","channel":"x","sampler":"s2"}, #8
   {"kind":"mul","args":[8,1]}, #9
   {"kind":"add","args":[9,3]}, #10 secondary x
   {"kind":"input","name":"TEXCOORD7.x"}, #11
   {"kind":"dot","args":[10,11]}, #12
   {"kind":"sample","resource":"normalMapSampler1","channel":"y","sampler":"s2"}, #13
   {"kind":"mul","args":[13,1]}, #14
   {"kind":"add","args":[14,3]}, #15
   {"kind":"input","name":"TEXCOORD7.y"}, #16
   {"kind":"dot","args":[15,16]}, #17
   {"kind":"input","name":"COLOR.y"}, #18
  ])
 @staticmethod
 def mode_sig(ts):return "b"
 @staticmethod
 def sequence(d,mode,channel):return [(0,[18])]
 @staticmethod
 def specs(ts):return [(1,"b",("n",))]
 @staticmethod
 def value_resources(d,root):
  seen=set();out=set()
  def f(i):
   if i in seen:return
   seen.add(i);n=d.n[i]
   if n["kind"]=="sample":out.add(n["resource"])
   for c in n.get("args",[]):f(c)
  f(root);return out
 @staticmethod
 def input_deps(d,root):
  seen=set();out=set()
  def f(i):
   if i in seen:return
   seen.add(i);n=d.n[i]
   if n["kind"]=="input":out.add(n["name"])
   for c in n.get("args",[]):f(c)
  f(root);return out

class Normal:
 explicit=True
 @staticmethod
 def base_pair(comp,d):return [4,7] if Normal.explicit else None
 @staticmethod
 def current_pair(comp,d,L,w):return [12,17]
 @staticmethod
 def sample_channels(comp,d,root,res):
  seen=set();out=set()
  def f(i):
   if i in seen:return
   seen.add(i);n=d.n[i]
   if n["kind"]=="sample" and n["resource"]==res:out.add(n["channel"])
   for c in n.get("args",[]):f(c)
  f(root);return out

def main():
 dummy=object();Normal.explicit=True
 r=decode.extract_normal_decode_dags(b"DXBC-baseline-fixture","lit_sm_r0c0n0_b1c1n1",modules=(Comp,Normal,dummy,dummy,dummy))
 assert r["format"]==decode.FORMAT
 b=r["baseline"];assert b["mode"]=="explicit_normal" and b["normalResource"]=="normalMapSampler" and b["sampleChannels"]==["x","y"]
 assert [c["decodeRoot"] for c in b["components"]]==[4,7]
 assert r["layers"][0]["transformMode"]=="transform2x2"
 for c in b["components"]:
  assert abs(v1.evaluate_decode_component(c["forensicDag"],0.0)+1.0)<1e-12
  assert abs(v1.evaluate_decode_component(c["forensicDag"],0.5)-0.0)<1e-12
  assert abs(v1.evaluate_decode_component(c["forensicDag"],1.0)-1.0)<1e-12
 Normal.explicit=False
 z=decode.extract_normal_decode_dags(b"DXBC-baseline-fixture","lit_sm_r0c0_b1c1n1",modules=(Comp,Normal,dummy,dummy,dummy))
 assert z["baseline"]=={"mode":"zero","normalResource":None,"sampleChannels":[],"components":[],"decodePairSha256":None}
 print("PASS: exact T6 generated normal base baseline decode DAG v2")
if __name__=="__main__":main()
