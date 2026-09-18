#!/usr/bin/env python3
"""Compact exact instruction-backed persistent-zone global xrefs from persisted proof."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();src=json.loads(a.input.read_text());targets={int(v,16):k for k,v in src['globals'].items()};hits=[]
 for w in src['executableImmediateXrefs']:
  for ins in w['instructions']:
   matched=[]
   for op in ins.get('operands',[]):
    vals=[]
    if op.get('type')=='imm':vals.append(op.get('value'))
    if op.get('type')=='mem':vals.append(op.get('disp'))
    for v in vals:
     if v in targets:matched.append({'global':targets[v],'globalVa':f'0x{v:08x}'})
   if matched:hits.append({'instruction':ins,'matches':matched,'sourceWindowGlobal':w['global'],'sourceImmediateFileOffset':w['immediateFileOffset']})
 # de-duplicate same decoded instruction/match arising from overlapping windows
 uniq={}
 for h in hits:
  key=(h['instruction']['address'],tuple(sorted((m['global'],m['globalVa']) for m in h['matches'])))
  uniq[key]=h
 out={'format':'t6-current-client-zone-persistent-xref-compact-v1','source':{'path':str(a.input),'sha256':hashlib.sha256(a.input.read_bytes()).hexdigest()},'client':src['client'],'exactInstructionXrefs':list(uniq.values()),'summary':{'exactInstructionXrefCount':len(uniq),'byGlobal':{name:sum(any(m['global']==name for m in h['matches']) for h in uniq.values()) for name in src['globals']}},'proofBoundary':'Projection only from persisted exact current-client decoded windows. An absolute operand proves that instruction references the address; descriptive global labels retain only already-proved staging roles. No source symbol, historical-retail identity, precedence, or Technique winner is inferred.'};payload=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({'proofSha256':hashlib.sha256(payload).hexdigest(),**out['summary']},indent=2,sort_keys=True))
if __name__=='__main__':main()
