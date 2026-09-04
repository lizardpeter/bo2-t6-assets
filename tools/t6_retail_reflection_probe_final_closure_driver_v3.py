#!/usr/bin/env python3
"""Metadata-clean final reflection closure driver.

V3 inherits V2's corrected TC2/TEXCOORD0 sphere accounting and routes every stage
that consumes the reusable sphere ownership graph through the corrected v2 owner and
paired-VS wrappers. This prevents any generated endgame artifact from inheriting the
superseded shifted-TBN family label carried by the original owner metadata.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

v2=load(HERE/'t6_retail_reflection_probe_final_closure_driver_v2.py','closure_driver_v2')
v1=v2.v1
OWNER='t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v2.py'
PAIRED='t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v2.py'
SPHERE='t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py'

def set_arg(cmd,key,value):
 q=list(cmd)
 if key in q:
  i=q.index(key)
  if i+1>=len(q):raise ValueError(f'missing value after {key}')
  q[i+1]=str(value)
 else:q += [key,str(value)]
 return q

def set_out(cmd,path):return set_arg(cmd,'--out',path)

def build_commands(repo:Path,root:Path,out:Path):
 rows=v2.build_commands(repo,root,out);fixed=[]
 owner=repo/'tools'/OWNER;paired=repo/'tools'/PAIRED;sphere=repo/'tools'/SPHERE
 for name,cmd,out_path in rows:
  q=list(cmd);op=out_path
  if name=='sphereOwner':
   op=out/'T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PACKED_PS_V2.json';q[1]=str(owner);q=set_out(q,op)
  elif name=='spherePairedVs':
   op=out/'T6_RETAIL_REFLECTION_PROBE_SPHERE_ELEC_PAIRED_VS_V2.json';q[1]=str(paired);q=set_arg(q,'--owner-probe',owner);q=set_out(q,op)
  elif name=='spherePhysical':
   q[1]=str(sphere);q=set_arg(q,'--owner-probe',owner);q=set_arg(q,'--paired-probe',paired)
  elif name in ('residualExact','residualDifferential'):
   q=set_arg(q,'--owner-probe',owner);q=set_arg(q,'--paired-probe',paired)
  fixed.append((name,q,op))
 return fixed

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True)
 ap.add_argument('--repo',type=Path,default=ROOT);ap.add_argument('--summary-out',type=Path);a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
 summary_out=a.summary_out or (a.out_dir/'T6_RETAIL_REFLECTION_PROBE_FINAL_CLOSURE_RUN_V3.json')
 stages=[];data={};ok={}
 for name,cmd,out_path in build_commands(a.repo,a.root,a.out_dir):
  row,parsed=v1.run_stage(name,cmd,out_path);stages.append(row);ok[name]=row['returnCode']==0 and parsed is not None
  if parsed is not None:data[name]=parsed
 accounting_error=None
 try:closure=v1.account(data,ok)
 except Exception as e:closure=None;accounting_error=str(e)
 result={
  'format':'t6-retail-reflection-probe-final-closure-run-v3',
  'producer':'tools/t6_retail_reflection_probe_final_closure_driver_v3.py',
  'supersedes':'tools/t6_retail_reflection_probe_final_closure_driver_v2.py',
  'closureLedger':'manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2.json',
  'metadataRouting':{
   'sphereOwner':'tools/'+OWNER,
   'spherePairedVs':'tools/'+PAIRED,
   'spherePhysical':'tools/'+SPHERE,
   'residualPackedPsStagesUseCorrectedOwnerAndPairedWrappers':True},
  'root':str(a.root),'stages':stages,'stageSuccess':ok,'closureAccounting':closure,'accountingError':accounting_error,
  'proofBoundary':'Orchestration/accounting only. V3 changes no parser or closure arithmetic. It routes sphere and residual ownership consumers through metadata-correct v2 wrappers so the obsolete shifted-TBN sphere-family assertion cannot reappear in generated endgame manifests.'}
 summary_out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'stageSuccess':ok,'closureAccounting':closure,'accountingError':accounting_error},indent=2,sort_keys=True))
 if accounting_error or not all(ok.values()):raise SystemExit(1)
if __name__=='__main__':main()
