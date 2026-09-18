#!/usr/bin/env python3
"""Exact CFG/caller probe for callees reached after current-client zone staging."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import CsError,CS_GRP_CALL
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg
EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS={"post_staging_consumer":0x007FDDD0,"bounded_index_helper":0x005E91B0}

def inbound_calls(raw,secs,wanted):
 out={x:[] for x in wanted};md=cfg.make_md();md.skipdata=True
 for sec in secs:
  if not sec["executable"]:continue
  blob=raw[sec["rawOffset"]:sec["rawOffset"]+sec["rawSize"]]
  for ins in md.disasm(blob,sec["va"]):
   try:is_call=ins.group(CS_GRP_CALL)
   except CsError:continue
   if not is_call:continue
   t=cfg.direct_target(ins)
   if t in out:out[t].append(cfg.insn_json(ins))
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw);inbound=inbound_calls(raw,secs,set(TARGETS.values()));docs=[]
 for name,va in TARGETS.items():
  graph,blocks=cfg.build_cfg(raw,secs,va);masks=cfg.trace_masks(raw,secs,blocks)
  docs.append({"name":name,"address":f"0x{va:08x}","globalInboundDirectCalls":inbound[va],"cfg":graph,"maskDataflow":masks})
 out={"format":"t6-current-client-zone-staging-callee-cfg-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},"targets":docs,"summary":{x["name"]:{"inboundDirectCalls":len(x["globalInboundDirectCalls"]),"cfgInstructions":x["cfg"]["instructionCount"],"basicBlocks":x["cfg"]["basicBlockCount"],"directCalls":len(x["cfg"]["directCalls"]),"retSites":len(x["cfg"]["retSites"]),"externalOrIndirectJumps":len(x["cfg"]["externalOrIndirectJumps"]),"truncated":x["cfg"]["truncated"]} for x in docs},"proofBoundary":"Exact decoded current-client control-flow only. SKIPDATA pseudo-instructions are excluded from inbound-call classification. Descriptive target labels identify only proved call-site roles, not source symbols. No server symbol, historical-retail identity, priority rule, or Technique winner is imported."}
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({"proofSha256":hashlib.sha256(payload).hexdigest(),"summary":out["summary"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
