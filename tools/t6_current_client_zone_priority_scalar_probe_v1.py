#!/usr/bin/env python3
"""Exact current-client scalar priority-function probe at 0x00493440.

The address is byte-proven as the shared scalar target receiving masked runtime
zone classifiers. This probe captures its CFG and immediate/return structure
without assigning a source symbol.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone.x86_const import X86_OP_IMM
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg

EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x00493440

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw)
 graph,blocks=cfg.build_cfg(raw,secs,TARGET)
 flat=[i for b in graph["blocks"] for i in b.get("instructions",[])]
 immediate_rows=[]
 for i in flat:
  vals=[op for op in i.get("operands",[]) if op.get("type")=="imm"]
  if vals:immediate_rows.append({"instruction":i,"immediates":vals})
 out={
  "format":"t6-current-client-zone-priority-scalar-probe-v1",
  "authority":"SHA-classified current Plutonium client only",
  "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
  "target":f"0x{TARGET:08x}",
  "cfg":graph,
  "immediateInstructions":immediate_rows,
  "summary":{"instructions":graph["instructionCount"],"basicBlocks":graph["basicBlockCount"],"retSites":len(graph["retSites"]),"directCalls":len(graph["directCalls"]),"truncated":graph["truncated"]},
  "proofBoundary":"Exact decoded CFG for the shared current-client scalar function reached from masked runtime-zone classifiers. No source symbol, priority-table semantic, historical-retail equivalence, or Technique winner is inferred by this raw probe."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest(),"summary":out["summary"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
