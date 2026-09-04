#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1] if Path(__file__).resolve().parent.name=='tests' else Path.cwd()

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def main():
 owner=load(ROOT/'tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py','owner')
 paired=load(ROOT/'tools/t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v1.py','paired')
 assert owner.EXPECTED_TARGET_OBJECTS==24
 assert owner.EXPECTED_STRUCTURAL_PS_ANCHORS==76
 assert owner.EXPECTED_TOMB_DIRECT_CONTROLS==10
 controls=[
  {'block':5,'offset':100,'fixedStart':1100,'delta':1000,'sha256':'a'},
  {'block':5,'offset':200,'fixedStart':1200,'delta':1000,'sha256':'b'},
 ]
 targets=[{'fixedStart':2000+i*100,'sha256':str(i)} for i in range(4)]
 ptrs=[('ptr','zm_tomb',5,o) for o in (1000,1100,1200,1300,5000,5100)]
 banks,cal=owner.target_candidate_banks(targets,ptrs,controls)
 assert len(banks)==1
 assert banks[0]['block']==5
 assert banks[0]['offsets']==[1000,1100,1200,1300]
 assert banks[0]['maxResidualBytes']==0
 assert cal[5]['maxPairwiseDifferentialDriftBytes']==0
 ptrs2=ptrs+[('ptr','zm_tomb',5,o) for o in (7000,7100,7200,7300)]
 banks2,_=owner.target_candidate_banks(targets,ptrs2,controls)
 assert len(banks2)==2
 p=('ptr','zm_tomb',5,1234)
 h='a'*64
 got,sources=paired.resolve_vs_node(p,{p:h},{p:h})
 assert got==h and sources==['crossMapPassKey','committedPackedVsAlias']
 try:
  paired.resolve_vs_node(p,{p:'a'*64},{p:'b'*64})
 except ValueError:
  pass
 else:
  raise AssertionError('paired VS disagreement did not fail closed')
 direct=('sha','c'*64)
 got,sources=paired.resolve_vs_node(direct,{},{});assert got=='c'*64 and sources==['direct']
 print('sphere-electric owner pipeline synthetic regression: OK')

if __name__=='__main__':main()
