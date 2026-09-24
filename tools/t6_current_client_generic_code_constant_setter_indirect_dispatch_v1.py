#!/usr/bin/env python3
"""Locate exact indirect-dispatch provenance for generic code-constant setter 0x00745B70.

Find every little-endian pointer to the setter in the SHA-locked executable,
freeze neighboring pointer-table bytes, then enumerate executable instructions
that reference the pointer VA or a small window containing it. Also retain
indirect CALL/JMP memory operands whose displacement lands in that table window.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-generic-code-constant-setter-indirect-dispatch-v1"
SETTER=0x00745B70
RADIUS=0x100
CTX=24
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
 p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
 c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];o=c+20;ib=struct.unpack_from("<I",raw,o+28)[0];sh=o+os;ss=[]
 for i in range(n):
  q=sh+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace");vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
  ss.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
 return ib,ss
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}");ib,ss=pe(raw)
 needle=struct.pack("<I",SETTER);ptrs=[]
 for s in ss:
  blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];pos=0
  while True:
   k=blob.find(needle,pos)
   if k<0:break
   va=s["va"]+k
   lo=max(0,k-64);hi=min(len(blob),k+68)
   words=[]
   wlo=max(0,k-32)&~3; whi=min(len(blob),k+36)&~3
   for off in range(wlo,whi,4):
    if off+4<=len(blob):words.append({"va":f"0x{s['va']+off:08x}","u32":f"0x{struct.unpack_from('<I',blob,off)[0]:08x}"})
   ptrs.append({"pointerVa":f"0x{va:08x}","section":s["name"],"rawOffset":s["rawOffset"]+k,
                "neighborHex":blob[lo:hi].hex(),"neighborWords":words})
   pos=k+1
 ptr_vas=[int(x["pointerVa"],16) for x in ptrs];refs=[]
 md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
 for s in ss:
  if not s["exec"]:continue
  ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
  for n,i in enumerate(ins):
   matched=[]
   for opi,op in enumerate(i.operands):
    if op.type==X86_OP_IMM:
     v=int(op.imm)&0xffffffff
     for pv in ptr_vas:
      if pv-RADIUS<=v<=pv+RADIUS:matched.append({"operandIndex":opi,"kind":"imm","value":f"0x{v:08x}","pointerVa":f"0x{pv:08x}","delta":v-pv})
    elif op.type==X86_OP_MEM:
     disp=int(op.mem.disp)&0xffffffff
     for pv in ptr_vas:
      if pv-RADIUS<=disp<=pv+RADIUS:matched.append({"operandIndex":opi,"kind":"memDisp","value":f"0x{disp:08x}","pointerVa":f"0x{pv:08x}","delta":disp-pv,
        "baseReg":md.reg_name(op.mem.base) if op.mem.base else None,"indexReg":md.reg_name(op.mem.index) if op.mem.index else None,"scale":op.mem.scale})
   if not matched:continue
   lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
   refs.append({"instruction":rr(i),"section":s["name"],"matches":matched,
                "isIndirectControlTransfer":i.mnemonic in {"call","jmp"} and any(o.type==X86_OP_MEM for o in i.operands),
                "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
 out={"format":FORMAT,"authority":"SHA-classified current-client exact setter-address literal and executable table-xref census",
  "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
  "setterVa":f"0x{SETTER:08x}","pointerOccurrences":ptrs,"references":refs,
  "summary":{"setterPointerOccurrenceCount":len(ptrs),"nearTableExecutableReferenceCount":len(refs),
             "indirectControlTransferReferenceCount":sum(r["isIndirectControlTransfer"] for r in refs)},
  "proofBoundary":"Locator/census only. A pointer-table occurrence and nearby executable xref are exact, but dispatcher record type, enum provenance, runtime reachability and per-accessor provider semantics require a subsequent dataflow join."}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");print(json.dumps(out["summary"],indent=2,sort_keys=True));print(json.dumps(ptrs,indent=2,sort_keys=True))
if __name__=="__main__":main()
