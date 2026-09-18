#!/usr/bin/env python3
"""Comparative-only T6 current-client zone-xref/call-target discovery.

Starts from exact executable xrefs to selected zone-name strings and records nearby
control-flow evidence. It intentionally does not name DB functions or promote winners.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_INS_CALL, X86_OP_IMM
STRINGS=(b'common\0',b'patch\0',b'_mp\0',b'mp_nuketown_2020\0')
MASKS=(0x3fffffff,0x17ffffff)
class E(Exception): pass

def pe(raw):
 p=struct.unpack_from('<I',raw,0x3c)[0]
 if raw[:2]!=b'MZ' or raw[p:p+4]!=b'PE\0\0': raise E('not PE')
 coff=p+4; machine,nsec,_,_,_,optsz,_=struct.unpack_from('<HHIIIHH',raw,coff)
 if machine!=0x14c: raise E('not i386')
 opt=coff+20
 if struct.unpack_from('<H',raw,opt)[0]!=0x10b: raise E('not PE32')
 base=struct.unpack_from('<I',raw,opt+28)[0]; so=opt+optsz; secs=[]
 for i in range(nsec):
  o=so+i*40; name=raw[o:o+8].split(b'\0',1)[0].decode('ascii','replace'); vs,rva,rs,ro=struct.unpack_from('<IIII',raw,o+8); ch=struct.unpack_from('<I',raw,o+36)[0]
  secs.append(dict(name=name,va=base+rva,vsize=vs,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
 return base,secs

def occ(raw,n):
 out=[]; p=0
 while True:
  p=raw.find(n,p)
  if p<0:return out
  out.append(p);p+=1

def offva(secs,o):
 for s in secs:
  if s['rawOffset']<=o<s['rawOffset']+s['rawSize']: return s['va']+o-s['rawOffset']
def vaoff(secs,v):
 for s in secs:
  if s['va']<=v<s['va']+s['rawSize']: return s['rawOffset']+v-s['va']
def execsec(secs,o): return next((s for s in secs if s['executable'] and s['rawOffset']<=o<s['rawOffset']+s['rawSize']),None)

def dis(raw,secs,a,b):
 s=execsec(secs,a)
 if not s:return []
 a=max(a,s['rawOffset']);b=min(b,s['rawOffset']+s['rawSize']);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
 return list(md.disasm(raw[a:b],s['va']+a-s['rawOffset']))
def row(i): return dict(address=f'0x{i.address:08x}',bytes=i.bytes.hex(),mnemonic=i.mnemonic,opStr=i.op_str)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--revision',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();base,secs=pe(raw); anchors=[]
 for st in STRINGS:
  for so in occ(raw,st):
   sv=offva(secs,so)
   if sv is None:continue
   for xo in occ(raw,struct.pack('<I',sv)):
    if not execsec(secs,xo):continue
    xv=offva(secs,xo); nearby=dis(raw,secs,max(execsec(secs,xo)['rawOffset'],xo-160),xo+192); calls=[]
    for ins in nearby:
     if ins.id==X86_INS_CALL and ins.operands and ins.operands[0].type==X86_OP_IMM:
      tv=int(ins.operands[0].imm)&0xffffffff; to=vaoff(secs,tv); masks=[]; body=[]
      if to is not None and execsec(secs,to):
       body=dis(raw,secs,to,to+512)
       for bi in body:
        if any(f'0x{m:x}' in bi.op_str.lower() for m in MASKS): masks.append(row(bi))
      calls.append(dict(call=row(ins),targetVa=f'0x{tv:08x}',targetExecutable=bool(to is not None and execsec(secs,to)),targetFirst512=[row(x) for x in body[:96]],maskInstructions=masks))
    anchors.append(dict(string=st[:-1].decode(),stringVa=f'0x{sv:08x}',xrefVa=f'0x{xv:08x}',xrefFileOffset=xo,nearbyInstructions=[row(x) for x in nearby],nearbyDirectCalls=calls))
 out=dict(format='t6-current-client-zone-xref-dataflow-probe-v1',authority='current Plutonium CDN object only; comparative discovery, not historical retail authority',client=dict(revision=a.revision,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),imageBaseHex=f'0x{base:08x}'),anchors=anchors,status='comparative_discovery_only_no_function_or_winner_promoted',proofBoundary='Exact string xrefs and decoded direct-call targets are byte evidence for this current client only. Proximity, call adjacency, masks, names, ordering, and similarity do not establish DB function identity, zone precedence, or historical-retail ownership.')
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'anchors':len(anchors),'directCalls':sum(len(x['nearbyDirectCalls']) for x in anchors),'sha256':out['client']['sha256']},indent=2))
if __name__=='__main__':main()
