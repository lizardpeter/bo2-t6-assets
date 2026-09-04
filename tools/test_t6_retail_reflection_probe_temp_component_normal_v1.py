#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

P=Path(__file__).with_name('t6_retail_reflection_probe_temp_component_normal_v1.py')
s=importlib.util.spec_from_file_location('m',P);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m)

class Shared:
 @staticmethod
 def raw_imms(w,src): return src.get('imm')
class Weight:
 DP_WIDTH={}
 @staticmethod
 def eff(src,dcomps):
  c=src.get('comps','x')
  if len(c)==1:return c*len(dcomps)
  if len(c)>=4:return ''.join(c['xyzw'.index(ch)] for ch in dcomps)
  if len(c)==len(dcomps):return c
  raise ValueError
 @staticmethod
 def writer_dests(op,O): return [O[0]]
class Coord:
 SAMPLE_OPS={69:'SAMPLE'}
class Guard:
 INPUT_TEXTURE=2

D=lambda reg,comps:{'type':m.TYPE_TEMP,'idx':[reg],'comps':comps}
T=lambda reg,comps='xxxx':{'type':m.TYPE_TEMP,'idx':[reg],'comps':comps}
CB=lambda vec,comps='xxxx':{'type':m.TYPE_CB,'idx':[2,vec],'comps':comps}
R=lambda bind:{'type':m.TYPE_RESOURCE,'idx':[bind],'comps':''}
S=lambda:{'type':6,'idx':[0],'comps':''}
IMM=lambda bits:{'type':m.TYPE_IMM32,'idx':[],'comps':'x','imm':(bits,)}

writers={
 (1,'x'):(1,0,69,D(1,'x'),[D(1,'x'),T(8),R(0),S()]),
 (2,'y'):(2,0,69,D(2,'y'),[D(2,'y'),T(8),R(1),S()]),
 (0,'x'):(3,0,0,D(0,'x'),[D(0,'x'),T(1,'xxxx'),CB(10,'xxxx')]),
 (0,'y'):(4,0,0,D(0,'y'),[D(0,'y'),T(2,'yyyy'),CB(10,'yyyy')]),
 (0,'z'):(5,0,m.OP_MOV,D(0,'z'),[D(0,'z'),IMM(m.ONE_BITS)]),
}
def latest(before,reg,ch):
 q=writers.get((reg,ch))
 return q if q and q[0]<before else None
resources=[
 {'name':'normalMap00','inputType':Guard.INPUT_TEXTURE,'bindPoint':0},
 {'name':'normalMap01','inputType':Guard.INPUT_TEXTURE,'bindPoint':1},
]
cache={}
lx=m.variable_leaves(Coord,Weight,Guard,resources,[],[],latest,10,0,'x',cache)
ly=m.variable_leaves(Coord,Weight,Guard,resources,[],[],latest,10,0,'y',cache)
assert {z[1] for z in lx|ly if z[0]=='sample'}=={'normalMap00','normalMap01'}
assert {(z[1],z[2]) for z in lx|ly if z[0]=='cb'}=={(2,10)}
assert m.prove_exact_one_mov(Shared,Weight,[],latest,10,0,'z')['immediateBits']=='3f800000'

# yzw storage is lane-order-sensitive: logical Z is storage w, not z.
writers[(3,'y')]=(6,0,0,D(3,'y'),[D(3,'y'),T(1,'xxxx'),CB(6,'xxxx')])
writers[(3,'z')]=(7,0,0,D(3,'z'),[D(3,'z'),T(2,'yyyy'),CB(6,'yyyy')])
writers[(3,'w')]=(8,0,m.OP_MOV,D(3,'w'),[D(3,'w'),IMM(m.ONE_BITS)])
assert m.prove_exact_one_mov(Shared,Weight,[],latest,10,3,'w')['immediateBits']=='3f800000'
try:
 m.prove_exact_one_mov(Shared,Weight,[],latest,10,3,'z')
except ValueError:
 pass
else:
 raise AssertionError('logical-Z/storage-w lane guard failed')

writers[(4,'z')]=(9,0,m.OP_MOV,D(4,'z'),[D(4,'z'),IMM(0x3f000000)])
try:
 m.prove_exact_one_mov(Shared,Weight,[],latest,10,4,'z')
except ValueError:
 pass
else:
 raise AssertionError('non-1.0 raw Z accepted')

assert m.FAMILIES['TEXCOORD1']['count']==6
assert m.FAMILIES['TEXCOORD3']['count']==9
assert m.EXPECTED_STORAGE=={'xyz':14,'yzw':1}
print('TEMP component normal synthetic regression: OK')
