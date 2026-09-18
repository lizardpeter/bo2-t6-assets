#!/usr/bin/env python3
"""Exact current-client field-flow inventory for the recovered 12-byte-row sink.

Authority is limited to the SHA-classified Plutonium revision 5346 client.
0x004174b0 is selected only because exact constructed 12-byte rows flow to it.
This probe records, without assigning source-level field names, every decoded
memory operand at displacements 0/4/8 in the bounded sink CFG, grouped by base
register, plus calls and nearby context. It is intended to determine whether the
three row fields are independently consumed before any semantic promotion.
"""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
from capstone.x86_const import X86_OP_MEM
import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfgmod

EXPECTED_SHA256='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf'
SINK=0x004174B0
OFFSETS={0,4,8}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('exe',type=Path); ap.add_argument('--revision',required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
 raw=a.exe.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED_SHA256: raise SystemExit(f'unexpected current-client SHA-256 {sha}')
 base,secs=cfgmod.parse_pe(raw)
 if not cfgmod.is_executable_va(secs,SINK): raise SystemExit('sink is not executable')
 cfg,_=cfgmod.build_cfg(raw,secs,SINK)
 hits=[]; by_base=defaultdict(list)
 for block in cfg['blocks']:
  ins=block.get('instructions') or []
  for i,row in enumerate(ins):
   matched=[]
   for op_index,op in enumerate(row.get('operands') or []):
    if op.get('type')=='mem' and op.get('disp') in OFFSETS and op.get('base'):
     matched.append({'operandIndex':op_index,'base':op.get('base'),'index':op.get('index'),'scale':op.get('scale'),'disp':op.get('disp')})
   if not matched: continue
   rec={'blockStart':block['start'],'instruction':row,'matchedMemoryOperands':matched,'contextBefore':ins[max(0,i-5):i],'contextAfter':ins[i+1:min(len(ins),i+6)]}
   hits.append(rec)
   for m in matched: by_base[m['base']].append(rec)
 groups=[]
 for reg,rows in sorted(by_base.items(),key=lambda kv:(-len(kv[1]),kv[0])):
  offs=Counter()
  addrs=[]
  for r in rows:
   addrs.append(r['instruction']['address'])
   for m in r['matchedMemoryOperands']:
    if m['base']==reg: offs[m['disp']]+=1
  groups.append({'baseRegister':reg,'hitCount':len(rows),'offsetCounts':{str(k):offs[k] for k in sorted(offs)},'instructionAddresses':sorted(set(addrs))})
 out={'format':'t6-current-client-zone-sink-fieldflow-probe-v1','authority':'current Plutonium CDN object only; exact decoded comparative evidence, not historical-retail authority','client':{'revision':a.revision,'bytes':len(raw),'sha256':sha,'imageBaseHex':f'0x{base:08x}'},'sink':f'0x{SINK:08x}','cfgSummary':{'instructionCount':cfg['instructionCount'],'basicBlockCount':cfg['basicBlockCount'],'retCount':len(cfg['retSites']),'externalOrIndirectJumpCount':len(cfg['externalOrIndirectJumps']),'truncated':cfg['truncated']},'fieldOffsetHits':hits,'baseRegisterGroups':groups,'directCalls':cfg['directCalls'],'summary':{'fieldOffsetHitCount':len(hits),'baseRegisterGroupCount':len(groups),'groupsTouchingAllThreeOffsets':sum(1 for g in groups if set(g['offsetCounts'])=={'0','4','8'})},'status':'exact_current_client_fieldflow_inventory_only_no_field_names_or_winner_promoted','proofBoundary':'Memory operands, CFG edges, and direct calls are exact decoded evidence for the SHA-classified current client. Displacements 0/4/8 are selected because exact 12-byte input rows were independently recovered. A base register touching those offsets does not by itself prove row identity, XZoneInfo semantics, alloc/free flag names, priority behavior, historical-retail equivalence, or any Technique winner.'}
 payload=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode(); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_bytes(payload)
 print(json.dumps({'fieldOffsetHitCount':len(hits),'baseRegisterGroups':groups,'proofBytes':len(payload),'proofSha256':hashlib.sha256(payload).hexdigest()},indent=2,sort_keys=True))
if __name__=='__main__': main()
