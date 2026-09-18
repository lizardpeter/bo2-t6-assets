#!/usr/bin/env python3
"""Enumerate exact executable references to the proven 16-byte linked-record arena.

Comparative/current-client only. No XAssetEntry source name is promoted.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM
CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
BASE=0x014342E0

def pe(raw):
 p=struct.unpack_from('<I',raw,0x3c)[0]; coff=p+4; n=struct.unpack_from('<H',raw,coff+2)[0]; os=struct.unpack_from('<H',raw,coff+16)[0]; opt=coff+20; ib=struct.unpack_from('<I',raw,opt+28)[0]; so=opt+os; out=[]
 for i in range(n):
  q=so+i*40; name=raw[q:q+8].split(b'\0',1)[0].decode('ascii','replace'); vs,rva,rs,ro=struct.unpack_from('<IIII',raw,q+8); ch=struct.unpack_from('<I',raw,q+36)[0]
  if ch&0x20000000: out.append((name,ib+rva,ro,rs))
 return ib,out

def row(ins):
 return {'address':f'0x{ins.address:08x}','bytes':ins.bytes.hex(),'mnemonic':ins.mnemonic,'opStr':ins.op_str}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--revision',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args(); raw=a.exe.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
 if sha!=CLIENT: raise SystemExit(f'unexpected client {sha}')
 ib,secs=pe(raw); md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True; allins=[]
 for name,va,ro,rs in secs:
  for x in md.disasm(raw[ro:ro+rs],va):
   if x.id: allins.append(x)
 hits=[]
 for i,x in enumerate(allins):
  reasons=[]
  for op in x.operands:
   if op.type==X86_OP_IMM and int(op.imm)&0xffffffff==BASE: reasons.append('immediate_base')
   elif op.type==X86_OP_MEM:
    disp=int(op.mem.disp)&0xffffffff
    if disp==BASE: reasons.append('memory_disp_base')
  if reasons:
   hits.append({'instruction':row(x),'reasons':reasons,'contextBefore':[row(z) for z in allins[max(0,i-24):i]],'contextAfter':[row(z) for z in allins[i+1:i+25]]})
 out={'format':'t6-current-client-linked-record-global-xref-probe-v1','authority':'SHA-classified current Plutonium client only','client':{'revision':a.revision,'bytes':len(raw),'sha256':sha,'imageBaseHex':f'0x{ib:08x}'},'linkedRecordArena':{'base':'0x014342e0','provenStrideBytes':16,'provenZoneIndexByteOffset':8,'provenLinkWordOffset':12},'xrefCount':len(hits),'xrefs':hits,'proofBoundary':'Exact executable operand references to the already-proven linked-record arena only. Reference proximity and access shape do not source-name the structure or establish historical-retail duplicate ownership.'}
 payload=(json.dumps(out,indent=2,sort_keys=True)+'\n').encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload);print(json.dumps({'xrefCount':len(hits),'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()},indent=2))
if __name__=='__main__':main()
