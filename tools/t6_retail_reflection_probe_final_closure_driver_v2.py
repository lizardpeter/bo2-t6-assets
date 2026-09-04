#!/usr/bin/env python3
"""Corrected final reflection closure driver.

V2 reuses V1 orchestration/accounting but replaces the superseded sphere-electric
stage with the corrected TC2/TEXCOORD0 physical gate. The V1 driver must not be used
for closure accounting because its sphere stage targeted the distinct already-closed
24-fetch shifted-TBN population.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

v1=load(HERE/'t6_retail_reflection_probe_final_closure_driver_v1.py','closure_driver_v1')

def build_commands(repo:Path,root:Path,out:Path):
 rows=v1.build_commands(repo,root,out)
 fixed=[]
 for name,cmd,out_path in rows:
  if name=='spherePhysical':
   cmd=list(cmd)
   cmd[1]=str(repo/'tools'/'t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py')
   # V2 sphere gate has a smaller CLI and does not accept the V1 shifted-TBN dependency arguments.
   cmd=[cmd[0],cmd[1],'--root',str(root),'--out',str(out_path)]
  fixed.append((name,cmd,out_path))
 return fixed

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--root',type=Path,required=True)
 ap.add_argument('--out-dir',type=Path,required=True)
 ap.add_argument('--repo',type=Path,default=ROOT)
 ap.add_argument('--summary-out',type=Path)
 a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
 summary_out=a.summary_out or (a.out_dir/'T6_RETAIL_REFLECTION_PROBE_FINAL_CLOSURE_RUN_V2.json')
 stages=[];data={};ok={}
 for name,cmd,out_path in build_commands(a.repo,a.root,a.out_dir):
  row,parsed=v1.run_stage(name,cmd,out_path);stages.append(row);ok[name]=row['returnCode']==0 and parsed is not None
  if parsed is not None:data[name]=parsed
 accounting_error=None
 try:closure=v1.account(data,ok)
 except Exception as e:closure=None;accounting_error=str(e)
 result={
  'format':'t6-retail-reflection-probe-final-closure-run-v2',
  'producer':'tools/t6_retail_reflection_probe_final_closure_driver_v2.py',
  'correction':{
   'supersedes':'tools/t6_retail_reflection_probe_final_closure_driver_v1.py',
   'reason':'V1 invoked the superseded shifted-TBN sphere gate. V2 invokes the corrected named-sphere TC2/TEXCOORD0 gate.'},
  'closureLedger':'manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2.json',
  'root':str(a.root),'stages':stages,'stageSuccess':ok,'closureAccounting':closure,'accountingError':accounting_error,
  'proofBoundary':'Orchestration/accounting only. Closure arithmetic is inherited from the regression-tested V1 accounting helper, but the sphere contribution can be nonzero only when the corrected v2 gate proves the named 24 sphere-electric PS objects are the unresolved TC2/TEXCOORD0 family and all paired VS roles pass.'}
 summary_out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'stageSuccess':ok,'closureAccounting':closure,'accountingError':accounting_error},indent=2,sort_keys=True))
 if accounting_error or not all(ok.values()):raise SystemExit(1)

if __name__=='__main__':main()
