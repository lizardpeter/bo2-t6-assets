#!/usr/bin/env python3
"""Exact current-client xrefs to persistent staged-zone globals and downstream edges."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg
EXPECTED="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
GLOBALS={"persistent_name_base":0x012EEE98,"persistent_field4_first":0x012EEED8,"processed_count_a":0x012C6F1C,"processed_count_b":0x014DEACC}
DOWNSTREAM={"post_loop_005c7d20":0x005C7D20,"post_loop_00458cc0":0x00458CC0,"post_loop_tail_005b8bf0":0x005B8BF0}

def occ(raw,n):
 out=[];p=0
 while True:
  p=raw.find(n,p)
  if p<0:return out
  out.append(p);p+=1

def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();raw=a.exe.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED:raise SystemExit(f"unexpected current-client SHA-256 {sha}")
 base,secs=cfg.parse_pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;xrefs=[]
 for label,va in GLOBALS.items():
  for off in occ(raw,struct.pack('<I',va)):
   sec=next((s for s in secs if s['executable'] and s['rawOffset']<=off<s['rawOffset']+s['rawSize']),None)
   if not sec:continue
   start=max(sec['rawOffset'],off-64);end=min(sec['rawOffset']+sec['rawSize'],off+96);startva=sec['va']+start-sec['rawOffset'];ins=list(md.disasm(raw[start:end],startva))
   xrefs.append({"global":label,"globalVa":f"0x{va:08x}","immediateFileOffset":off,"windowStartVa":f"0x{startva:08x}","instructions":[cfg.insn_json(x) for x in ins]})
 docs=[]
 for label,va in DOWNSTREAM.items():
  graph,_=cfg.build_cfg(raw,secs,va);docs.append({"name":label,"address":f"0x{va:08x}","cfg":graph})
 out={"format":"t6-current-client-zone-persistent-global-xref-probe-v1","authority":"SHA-classified current Plutonium client only","client":{"revision":a.revision,"bytes":len(raw),"sha256":sha,"imageBaseHex":f"0x{base:08x}"},"globals":{k:f"0x{v:08x}" for k,v in GLOBALS.items()},"executableImmediateXrefs":xrefs,"downstreamTargets":docs,"summary":{"xrefCounts":{k:sum(1 for x in xrefs if x['global']==k) for k in GLOBALS},"downstream":{x['name']:{"instructions":x['cfg']['instructionCount'],"blocks":x['cfg']['basicBlockCount'],"calls":len(x['cfg']['directCalls']),"rets":len(x['cfg']['retSites']),"externalOrIndirectJumps":len(x['cfg']['externalOrIndirectJumps']),"truncated":x['cfg']['truncated']} for x in docs}},"proofBoundary":"Exact current-client immediate xrefs and bounded CFG only. Immediate occurrence is not by itself a source-symbol identity; descriptive global labels encode only already-proved staging role. No historical-retail precedence or Technique winner is inferred."};payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({"proofSha256":hashlib.sha256(payload).hexdigest(),**out['summary']},indent=2,sort_keys=True))
if __name__=="__main__":main()
