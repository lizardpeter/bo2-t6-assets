#!/usr/bin/env python3
"""Comparative semantic probe for current T6 client DB zone-priority code.

Searches decoded executable instructions for the *ordered compare ladders* independently
proved in the exact PC dedicated server, while ignoring branch displacement/register
allocation details.  Current-client matches remain comparative evidence only and never
select a historical-retail Technique winner.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OPT_DETAIL

EXPECTED='770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf'
SERVER='f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d'

def sections(raw):
 p=struct.unpack_from('<I',raw,0x3c)[0]; assert raw[p:p+4]==b'PE\0\0'
 n=struct.unpack_from('<H',raw,p+6)[0]; opt=p+24; base=struct.unpack_from('<I',raw,opt+28)[0]
 s=opt+struct.unpack_from('<H',raw,p+20)[0]; out=[]
 for i in range(n):
  o=s+i*40; name=raw[o:o+8].split(b'\0')[0].decode('ascii','replace'); vs,va,rs,rp=struct.unpack_from('<IIII',raw,o+8); ch=struct.unpack_from('<I',raw,o+36)[0]
  if ch&0x20000000: out.append((name,rp,min(rs,len(raw)-rp),base+va))
 return base,out

def classify(ins):
 # Keep only semantic tokens relevant to the proved priority ladders.
 m=ins.mnemonic.lower(); op=ins.op_str.lower().replace(' ','')
 if m=='cmp':
  for imm in ('0x80','0x100','0x200','0x8000','0x10000','0x20000'):
   if op.endswith(','+imm): return ('cmp',int(imm,16))
 if m.startswith('j'): return ('jcc',m)
 if m=='mov' and op.startswith('eax,'):
  try:return ('mov_eax',int(op.split(',')[1],0))
  except:pass
 if m=='ret': return ('ret',None)
 return None

def main():
 a=argparse.ArgumentParser(); a.add_argument('exe'); a.add_argument('--revision',default='unknown'); a.add_argument('--out',required=True); x=a.parse_args()
 raw=Path(x.exe).read_bytes(); sha=hashlib.sha256(raw).hexdigest()
 if sha!=EXPECTED: raise SystemExit(f'fail closed: sha256 {sha}')
 base,secs=sections(raw); md=Cs(CS_ARCH_X86,CS_MODE_32)
 ladders=[[0x80,0x100,0x200],[0x8000,0x10000,0x20000]]; hits=[]; returns={54:[],57:[]}
 for sn,rp,sz,va in secs:
  ins=list(md.disasm(raw[rp:rp+sz],va))
  for i,q in enumerate(ins):
   c=classify(q)
   if c and c[0]=='mov_eax' and c[1] in returns and i+1<len(ins) and ins[i+1].mnemonic.lower()=='ret':
    returns[c[1]].append({'section':sn,'vaHex':f'0x{q.address:08x}','bytesHex':q.bytes.hex()+ins[i+1].bytes.hex()})
  for want in ladders:
   for i in range(len(ins)):
    got=[]; end=i
    # bounded decoded window: require the three compares in order and a conditional branch after each;
    # permit at most 2 unrelated instructions between semantic tokens.
    j=i; ok=True
    for imm in want:
     found=None
     for k in range(j,min(len(ins),j+3)):
      if classify(ins[k])==('cmp',imm): found=k; break
     if found is None: ok=False; break
     br=None
     for k in range(found+1,min(len(ins),found+4)):
      cc=classify(ins[k])
      if cc and cc[0]=='jcc': br=k; break
     if br is None: ok=False; break
     got.extend([found,br]); j=br+1; end=br
    if ok:
     lo=max(0,i-8); hi=min(len(ins),end+12)
     hits.append({'ladder':[hex(v) for v in want],'section':sn,'startVaHex':f'0x{ins[i].address:08x}','matchedVaHex':[f'0x{ins[k].address:08x}' for k in got], 'window':[{'address':f'0x{z.address:08x}','bytes':z.bytes.hex(),'mnemonic':z.mnemonic,'opStr':z.op_str} for z in ins[lo:hi]]})
 out={'format':'t6-current-client-db-priority-semantic-probe-v1','status':'comparative_discovery_only_no_retail_winner_promoted','authority':'current Plutonium CDN client only; NOT historical retail authority','client':{'revision':str(x.revision),'bytes':len(raw),'sha256':sha,'imageBaseHex':f'0x{base:08x}'},'serverReference':{'sha256':SERVER,'authority':'exact PC dedicated-server proof only'},'orderedCompareLadderHits':hits,'movEaxRetHits':{str(k):v for k,v in returns.items()},'summary':{'ladderHits':len(hits),'return54Hits':len(returns[54]),'return57Hits':len(returns[57])},'proofBoundary':'Decoded semantic matches can identify comparative current-client candidates for deeper function-boundary recovery. They do not prove historical retail behavior, function identity, XAsset ownership, or any winner among the 58 retail Technique conflicts.'}
 Path(x.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out['summary'],indent=2))
if __name__=='__main__': main()
