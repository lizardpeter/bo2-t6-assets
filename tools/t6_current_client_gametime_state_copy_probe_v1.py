#!/usr/bin/env python3
"""Prove the indirect 20-byte copy that writes gameTime source-state T at +0x1A2C."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-gametime-state-copy-probe-v1"
START=0x0076f7e0
END=0x0076f856
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def read(raw,secs,va,n):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:
        o=s["rawOffset"]+va-s["va"];return s,raw[o:o+n]
    raise E(f"unbacked VA 0x{va:08x}+{n}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);sec,bb=read(raw,secs,START,END-START)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(bb,START));req(ins and ins[0].address==START,"decode start drift")
    expected={
      0x0076f7e0:"f30f7e00",
      0x0076f7e4:"660fd682281a0000",
      0x0076f7ec:"f30f7e4008",
      0x0076f7f1:"660fd682301a0000",
      0x0076f7f9:"8b4810",
      0x0076f7fc:"898a381a0000",
      0x0076f802:"8b4c2404",
      0x0076f806:"898af8190000",
      0x0076f80c:"d94008",
      0x0076f80f:"d99a101a0000",
      0x0076f815:"d9400c",
      0x0076f818:"d99a141a0000",
      0x0076f81e:"d94010",
      0x0076f821:"d99a181a0000",
      0x0076f827:"c782241a000000000000",
      0x0076f831:"e88afeffff",
    }
    by={i.address:i for i in ins}
    for va,h in expected.items():
      if va not in by or by[va].bytes.hex()!=h:raise SystemExit(f"gate drift 0x{va:08x}: {by.get(va)}")
    callers=[]
    for s in secs:
      if not s["exec"]:continue
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
      for p in range(max(0,len(blob)-5)):
        if blob[p]!=0xe8:continue
        disp=struct.unpack_from("<i",blob,p+1)[0];va=s["va"]+p;t=(va+5+disp)&0xffffffff
        if t==START:callers.append({"callVa":f"0x{va:08x}","bytes":blob[p:p+5].hex(),"section":s["name"]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact bytes/dataflow",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec["name"],"bytes":len(bb),"sha256":hashlib.sha256(bb).hexdigest(),"instructions":[row(i) for i in ins]},
      "copySemantics":{
        "inputBaseRegister":"eax","sourceStateBaseRegister":"edx",
        "copies":[
          {"inputOffset":0,"stateOffset":0x1a28,"bytes":8},
          {"inputOffset":8,"stateOffset":0x1a30,"bytes":8},
          {"inputOffset":16,"stateOffset":0x1a38,"bytes":4}
        ],
        "gameTimeScalarT":{"inputOffset":4,"stateOffset":0x1a2c,"reason":"second dword of exact 8-byte copy input+0 -> state+0x1A28"}
      },
      "postCopy":{"argumentFromStackOffset":4,"storedToStateOffset":0x19f8,"callsStateUpdate":"0x0076f6c0"},
      "directCallers":callers,
      "summary":{"directCallerCount":len(callers),"gameTimeFieldIndirectWriteClosed":True},
      "proofBoundary":"Proves current-client byte-level copying only: state+0x1A2C receives input+4 whenever this function executes. It does not yet identify the semantic type/units of input+4, prove every gameTime update passes through this function, or establish historical-retail equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"callers":callers,"copySemantics":doc["copySemantics"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
