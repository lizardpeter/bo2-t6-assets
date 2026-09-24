#!/usr/bin/env python3
"""Trace EDI provenance feeding the packed sampler-state write at 0x009BCDE7."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-9bcde7-edi-provenance-v1"
LO=0x009BC000
STORE=0x009BCDE7
HI=0x009BCDED
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
 p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
 c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];o=c+20;ib=struct.unpack_from("<I",raw,o+28)[0];sh=o+os;ss=[]
 for i in range(n):
  q=sh+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace");vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
  ss.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
 return ib,ss
def loc(ss,va,n):
 for s in ss:
  if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
 raise E("not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}");ib,ss=pe(raw);s,o=loc(ss,LO,HI-LO)
 md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(raw[o:o+HI-LO],LO));by={i.address:i for i in ins}
 st=by.get(STORE);req(st and st.bytes.hex()=="89be10160000","store drift")
 edi_defs=[];control=[]
 for i in ins:
  if i.address>=STORE:break
  try:r,w=i.regs_access()
  except Exception:r,w=([],[])
  if any(md.reg_name(x) in {"edi","di"} for x in w):edi_defs.append(rr(i))
  if i.mnemonic in {"call","ret","retf","int3"} or i.mnemonic.startswith("j"):control.append(rr(i))
 # Local exact window around the store plus all EDI definitions in scan.
 idx=next(k for k,i in enumerate(ins) if i.address==STORE)
 doc={"format":FORMAT,"authority":"SHA-classified current-client exact EDI reaching-definition diagnostic",
  "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
  "scan":{"loVa":f"0x{LO:08x}","storeVa":f"0x{STORE:08x}","ediDefinitions":edi_defs,
          "controlTransfers":control,"localInstructions":[rr(x) for x in ins[max(0,idx-96):idx+1]]},
  "summary":{"ediDefinitionCount":len(edi_defs),"lastEdiDefinition":edi_defs[-1] if edi_defs else None},
  "proofBoundary":"Diagnostic provenance only. The last syntactic EDI definition is not automatically the reaching definition across all branches; exact branch/function dataflow must be joined before promoting a value bound."}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
