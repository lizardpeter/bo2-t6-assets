#!/usr/bin/env python3
"""Exact tail decode for current-client zone sink staging loop."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfgmod
EXPECTED_SHA256="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x004181B5
END=0x00418240

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED_SHA256:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfgmod.parse_pe(raw);so=cfgmod.va_to_offset(secs,START);eo=cfgmod.va_to_offset(secs,END-1)
 if so is None or eo is None:raise SystemExit("tail range unmapped")
 md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
 ins=[cfgmod.insn_json(x) for x in md.disasm(raw[so:eo+1],START)]
 out={"format":"t6-current-client-zone-sink-staging-tail-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},"range":{"start":f"0x{START:08x}","endExclusive":f"0x{END:08x}"},"instructions":ins,"summary":{"instructionCount":len(ins)},"proofBoundary":"Direct decode only. No source symbol, historical-retail identity, priority rule, or Technique winner is inferred."}
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest(),"instructionCount":len(ins)},indent=2,sort_keys=True))
if __name__=="__main__":main()
