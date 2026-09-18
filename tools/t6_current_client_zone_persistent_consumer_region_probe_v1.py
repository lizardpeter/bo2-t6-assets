#!/usr/bin/env python3
"""Exact decode of current-client region consuming persistent 68-byte zone records."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg
EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf";START=0x007FE300;END=0x007FE520

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--revision',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f'unexpected current-client SHA-256 {sha}')
 base,secs=cfg.parse_pe(raw);so=cfg.va_to_offset(secs,START);eo=cfg.va_to_offset(secs,END-1);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(raw[so:eo+1],START));selected=[]
 for i,x in enumerate(ins):
  keep=False;reasons=[]
  for op in x.operands:
   if op.type==X86_OP_MEM:
    b=x.reg_name(op.mem.base) if op.mem.base else None;d=int(op.mem.disp)
    if b in ('esi','edi','ebx','ebp','eax','ecx','edx') and d in (0,4,8,0x40,0x44):keep=True;reasons.append(f'mem:{b}{d:+#x}')
   elif op.type==X86_OP_IMM and (int(op.imm)&0xffffffff) in (0x44,0x40,0x012EEE98,0x012EEED8,0x012C6F1C,0x014DEACC):keep=True;reasons.append(f'imm:{int(op.imm)&0xffffffff:#x}')
  if keep:selected.append({'instruction':cfg.insn_json(x),'reasons':reasons,'before':[cfg.insn_json(z) for z in ins[max(0,i-6):i]],'after':[cfg.insn_json(z) for z in ins[i+1:min(len(ins),i+7)]]})
 out={'format':'t6-current-client-zone-persistent-consumer-region-probe-v1','authority':'SHA-classified current Plutonium client only','client':{'revision':a.revision,'bytes':len(raw),'sha256':sha,'imageBaseHex':f'0x{base:08x}'},'range':{'start':f'0x{START:08x}','endExclusive':f'0x{END:08x}'},'instructions':[cfg.insn_json(x) for x in ins],'selectedPersistentGeometryEvidence':selected,'summary':{'decodedInstructions':len(ins),'selectedInstructions':len(selected)},'proofBoundary':'Direct bounded decode only. The region is selected because exact prior xrefs load persistent record globals here; register-relative geometry is recorded but not source-named. No historical-retail identity, precedence rule, or Technique winner is inferred.'};payload=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({'proofSha256':hashlib.sha256(payload).hexdigest(),**out['summary']},indent=2,sort_keys=True))
if __name__=='__main__':main()
