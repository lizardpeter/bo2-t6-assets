#!/usr/bin/env python3
"""Current-client +0xDC memory-access census for brush-index consumer discovery."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_AC_READ,CS_AC_WRITE
from capstone.x86 import X86_OP_MEM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-disp-dc-access-census-v1"
DISP=0xdc
CTX=20
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
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"executable":bool(ch&0x20000000)})
    return ib,secs
def row(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def acc(a):
    parts=[]
    if a&CS_AC_READ:parts.append("read")
    if a&CS_AC_WRITE:parts.append("write")
    return "+".join(parts) or "unspecified"
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;hits=[]
    for s in secs:
        if not s["executable"]:continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=list(md.disasm(blob,s["va"]))
        for n,i in enumerate(ins):
            ops=[]
            for oi,o in enumerate(i.operands):
                if o.type==X86_OP_MEM and int(o.mem.disp)==DISP and o.mem.base!=0:
                    ops.append({"operandIndex":oi,"sizeBytes":int(o.size),"access":acc(int(o.access)),
                                "baseReg":i.reg_name(o.mem.base),"indexReg":i.reg_name(o.mem.index) if o.mem.index else None,
                                "scale":int(o.mem.scale),"disp":DISP})
            if not ops:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            hits.append({"instruction":row(i),"section":s["name"],"matchingOperands":ops,
                         "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    size_counts={}
    access_counts={}
    for h in hits:
        for o in h["matchingOperands"]:
            size_counts[str(o["sizeBytes"])]=size_counts.get(str(o["sizeBytes"]),0)+1
            access_counts[o["access"]]=access_counts.get(o["access"],0)+1
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
         "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
         "summary":{"instructionHitCount":len(hits),"operandHitCount":sum(len(x["matchingOperands"]) for x in hits),
                    "sizeByteCounts":size_counts,"accessCounts":access_counts},
         "hits":hits,
         "proofBoundary":"Exact decoded current-client memory operands with displacement +0xDC and nonzero base register only. A +0xDC access is not assigned to gentity_s or brushmodel by displacement coincidence; structure identity and consumer semantics require independent dataflow anchors."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
