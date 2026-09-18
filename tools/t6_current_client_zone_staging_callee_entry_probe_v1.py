#!/usr/bin/env python3
"""Fast exact entry-window decode for current-client post-staging callees."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg
EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS={"post_staging_consumer":0x007FDDD0,"bounded_index_helper":0x005E91B0}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;docs=[]
 for name,va in TARGETS.items():
  off=cfg.va_to_offset(secs,va)
  if off is None:raise SystemExit(f"unmapped target {va:#x}")
  ins=list(md.disasm(raw[off:off+768],va));docs.append({"name":name,"address":f"0x{va:08x}","instructions":[cfg.insn_json(x) for x in ins[:160]]})
 out={"format":"t6-current-client-zone-staging-callee-entry-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},"targets":docs,"proofBoundary":"Direct bounded entry-window decode only. Descriptive labels are call-site roles, not source symbols. No historical-retail identity or Technique ownership is inferred."};payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({"proofSha256":hashlib.sha256(payload).hexdigest(),"instructionCounts":{x["name"]:len(x["instructions"]) for x in docs}},indent=2,sort_keys=True))
if __name__=="__main__":main()
