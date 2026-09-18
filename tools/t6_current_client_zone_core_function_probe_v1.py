#!/usr/bin/env python3
"""Exact current-client zone-core function probe.

Targets:
- 0x007fdf00: callback passed to the exact recursive 12-byte record helper.
- 0x007fdf40: runtime consumer reached from persistent 68-byte records.
- 0x006e09b0: helper reached only from persistent records whose +0x40 dword has bit 0x8000.
- 0x00596780: receives the counted number of such 0x8000-selected records.

Current-client evidence only; no historical-retail/source-symbol promotion.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg

EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS={
 "row_callback_007fdf00":0x007FDF00,
 "persistent_record_consumer_007fdf40":0x007FDF40,
 "bit8000_record_helper_006e09b0":0x006E09B0,
 "bit8000_count_consumer_00596780":0x00596780,
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED: raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw); inbound=cfg.global_inbound_calls(raw,secs,set(TARGETS.values())); docs=[]
 for name,va in TARGETS.items():
  graph,blocks=cfg.build_cfg(raw,secs,va)
  docs.append({
   "name":name,"address":f"0x{va:08x}",
   "globalInboundDirectCalls":inbound.get(va,[]),
   "cfg":graph,
   "maskDataflow":cfg.trace_masks(raw,secs,blocks),
  })
 out={
  "format":"t6-current-client-zone-core-function-probe-v1",
  "authority":"SHA-classified current Plutonium client only",
  "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
  "targets":docs,
  "summary":{d["name"]:{
    "inboundDirectCalls":len(d["globalInboundDirectCalls"]),
    "instructions":d["cfg"]["instructionCount"],
    "basicBlocks":d["cfg"]["basicBlockCount"],
    "directCalls":len(d["cfg"]["directCalls"]),
    "retSites":len(d["cfg"]["retSites"]),
    "externalOrIndirectJumps":len(d["cfg"]["externalOrIndirectJumps"]),
    "truncated":d["cfg"]["truncated"],
  } for d in docs},
  "proofBoundary":"Exact decoded current-client control-flow only. Descriptive target labels encode only already-proven caller roles. No source symbol, XZoneInfo field name, historical-retail identity, precedence rule, or Technique winner is inferred."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"proofSha256":hashlib.sha256(payload).hexdigest(),"summary":out["summary"]},indent=2,sort_keys=True))

if __name__=="__main__": main()
