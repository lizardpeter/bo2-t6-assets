#!/usr/bin/env python3
"""Rerunnable final reflection closure driver with repaired residual target census.

V4 is the canonical pending-corpus runner. Relative verifier dependencies are resolved
by executing every subprocess with the repository root as cwd. The 117 residual
TC2/TC1 + TC3/TC1 target identities are reconstructed/digest-pinned as an explicit
stage, and the exact/differential residual stages use their v2 wrappers that no
longer depend on the never-committed 75-SHA JSON.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

v3=load(HERE/'t6_retail_reflection_probe_final_closure_driver_v3.py','closure_driver_v3')
v1=v3.v1
TARGETS='t6_retail_reflection_probe_residual_target_census_v1.py'
EXACT='t6_retail_reflection_probe_residual_packed_ps_extension_v2.py'
DIFF='t6_retail_reflection_probe_residual_packed_ps_differential_v2.py'

def sha256_file(path:Path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

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
 rows=v3.build_commands(repo,root,out);fixed=[];py=sys.executable
 target_out=out/'T6_RETAIL_REFLECTION_PROBE_RESIDUAL_TARGET_CENSUS_V1.json'
 target_cmd=[py,str(repo/'tools'/TARGETS),'--root',str(root),'--out',str(target_out)]
 inserted=False
 for name,cmd,out_path in rows:
  if name=='residualExact' and not inserted:
   fixed.append(('residualTargets',target_cmd,target_out));inserted=True
  q=list(cmd);op=out_path
  if name=='residualExact':
   op=out/'T6_RETAIL_REFLECTION_PROBE_RESIDUAL_PACKED_PS_EXTENSION_V2.json';q[1]=str(repo/'tools'/EXACT);q=set_out(q,op)
  elif name=='residualDifferential':
   op=out/'T6_RETAIL_REFLECTION_PROBE_RESIDUAL_PACKED_PS_DIFFERENTIAL_V2.json';q[1]=str(repo/'tools'/DIFF);q=set_arg(q,'--structural-extension',repo/'tools'/EXACT);q=set_out(q,op)
  fixed.append((name,q,op))
 if not inserted:raise ValueError('residualExact stage absent; cannot insert target census')
 return fixed

def run_stage(name,cmd,out_path,repo):
 cp=subprocess.run(cmd,text=True,capture_output=True,cwd=str(repo))
 row={'name':name,'command':cmd,'cwd':str(repo),'returnCode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr,'output':str(out_path),'outputExists':out_path.exists()}
 data=None
 if cp.returncode==0:
  if not out_path.exists():row['returnCode']=97;row['stderr']+='\nverifier returned success but output file is absent'
  else:
   try:data=json.loads(out_path.read_text());row['outputSha256']=sha256_file(out_path)
   except Exception as e:row['returnCode']=98;row['stderr']+=f'\noutput parse failure: {e}';data=None
 return row,data

def validate_target_stage(data):
 s=data.get('summary',{})
 if s.get('tc2Texcoord1ShaderCount')!=75 or s.get('tc3Texcoord1ShaderCount')!=42 or s.get('combinedShaderCount')!=117:raise ValueError('residual target census count mismatch')
 if s.get('tc2Texcoord1ShaderSetSha256')!='be9e44e06742a56170b91ce5f94173fee63c3fbc8c91aaf690cf712b2f8cc0a0':raise ValueError('TC2 target-set digest mismatch')
 if s.get('tc2Texcoord1GlobalRowsSha256')!='0d088b939b586ee46c7d69f7728046e0c377e12627f2883eba2786d25de5e5f3':raise ValueError('TC2 global-row digest mismatch')
 if s.get('tc3Texcoord1GlobalRowsSha256')!='cf865119d342260faae59ebd964fadcfe6ad40cfb6280e28fe5a4f3c19cb59a4':raise ValueError('TC3 global-row digest mismatch')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True);ap.add_argument('--repo',type=Path,default=ROOT);ap.add_argument('--summary-out',type=Path);a=ap.parse_args();a.repo=a.repo.resolve();a.root=a.root.resolve();a.out_dir=a.out_dir.resolve();a.out_dir.mkdir(parents=True,exist_ok=True)
 summary_out=(a.summary_out.resolve() if a.summary_out else a.out_dir/'T6_RETAIL_REFLECTION_PROBE_FINAL_CLOSURE_RUN_V4.json')
 stages=[];data={};ok={}
 for name,cmd,out_path in build_commands(a.repo,a.root,a.out_dir):
  row,parsed=run_stage(name,cmd,out_path,a.repo);stages.append(row);ok[name]=row['returnCode']==0 and parsed is not None
  if parsed is not None:data[name]=parsed
 accounting_error=None
 try:
  if ok.get('residualTargets'):validate_target_stage(data['residualTargets'])
  else:raise ValueError('residual target census did not pass')
  closure=v1.account(data,ok)
 except Exception as e:closure=None;accounting_error=str(e)
 result={
  'format':'t6-retail-reflection-probe-final-closure-run-v4','producer':'tools/t6_retail_reflection_probe_final_closure_driver_v4.py','supersedes':'tools/t6_retail_reflection_probe_final_closure_driver_v3.py','closureLedger':'manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2.json',
  'execution':{'repoCwd':str(a.repo),'residualTargetCensus':'tools/'+TARGETS,'residualExact':'tools/'+EXACT,'residualDifferential':'tools/'+DIFF},
  'root':str(a.root),'stages':stages,'stageSuccess':ok,'closureAccounting':closure,'accountingError':accounting_error,
  'proofBoundary':'Orchestration/accounting only. V4 requires a successful 117-identity residual target census before closure accounting, executes all stages from the repository root so relative verifier dependencies are stable, and uses only repaired v2 residual stages. Failed or absent proof stages still contribute zero to closure.'}
 summary_out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'stageSuccess':ok,'closureAccounting':closure,'accountingError':accounting_error},indent=2,sort_keys=True))
 if accounting_error or not all(ok.values()):raise SystemExit(1)
if __name__=='__main__':main()
