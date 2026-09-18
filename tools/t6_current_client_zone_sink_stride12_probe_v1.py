#!/usr/bin/env python3
"""Exact 12-byte-stride evidence probe for the SHA-classified current T6 client sink.

Reconstructs the bounded CFG rooted at 0x004174b0 and emits only instructions
that perform exact +12/imul-by-12 row arithmetic, with local decoded context.
This is a structural probe only; no row-field names or source symbols are assigned.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfgmod

EXPECTED_SHA256="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
SINK=0x004174B0

def is_stride(row):
    ops=row.get("operands") or []
    if row.get("mnemonic")=="add" and len(ops)>=2:
        return ops[0].get("type")=="reg" and ops[1].get("type")=="imm" and ops[1].get("value")==12
    if row.get("mnemonic")=="lea" and len(ops)>=2:
        mem=ops[1]
        return ops[0].get("type")=="reg" and mem.get("type")=="mem" and mem.get("disp")==12 and mem.get("index") is None
    if row.get("mnemonic")=="imul":
        return any(op.get("type")=="imm" and op.get("value")==12 for op in ops)
    return False

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED_SHA256: raise SystemExit(f"unexpected current-client SHA-256 {sha}")
    base,secs=cfgmod.parse_pe(raw);cfg,_=cfgmod.build_cfg(raw,secs,SINK)
    hits=[]
    for block in cfg.get("blocks") or []:
        ins=block.get("instructions") or []
        for i,row in enumerate(ins):
            if not is_stride(row): continue
            hits.append({
              "blockStart":block.get("start"),
              "instruction":row,
              "contextBefore":ins[max(0,i-10):i],
              "contextAfter":ins[i+1:min(len(ins),i+11)],
            })
    out={
      "format":"t6-current-client-zone-sink-stride12-probe-v1",
      "authority":"SHA-classified current Plutonium client only; exact decoded structural evidence, not historical-retail authority",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},
      "sink":f"0x{SINK:08x}",
      "cfgSummary":{"instructionCount":cfg["instructionCount"],"basicBlockCount":cfg["basicBlockCount"],"retCount":len(cfg["retSites"]),"externalOrIndirectJumpCount":len(cfg["externalOrIndirectJumps"]),"truncated":cfg["truncated"]},
      "stride12Sites":hits,
      "summary":{"stride12SiteCount":len(hits),"addresses":[h["instruction"]["address"] for h in hits]},
      "proofBoundary":"Only exact decoded add/lea/imul forms containing a literal 12 row stride are selected from the bounded sink CFG. A stride match does not prove the iterated object is XZoneInfo, identify any field, establish zone priority, prove historical-retail equivalence, or select a Technique winner."
    }
    payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
    print(json.dumps({"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest(),**out["summary"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
