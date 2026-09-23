#!/usr/bin/env python3
"""Recover exact worldMatrix writer functions using decoded ret->INT3 boundaries.

V1 used long raw INT3 pads and could merge adjacent functions when the compiler
emitted only one/four INT3 bytes. V2 scans decoded executable instructions and
bounds each direct writer by the nearest preceding INT3 run and following RET
whose next decoded instruction is INT3.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-world-matrix-writer-functions-v2"
OFFS={0x1986:"worldConstVersion",0x19c6:"worldMatrixVersion"}
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
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}");ib,secs=pe(raw)
    functions=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        hits=[]
        for n,i in enumerate(ins):
            if i.mnemonic in ("cmp","test"):continue
            for oi,op in enumerate(i.operands):
                if oi!=0 or op.type!=X86_OP_MEM or op.mem.index!=0:continue
                disp=int(op.mem.disp)&0xffffffff
                if disp in OFFS:
                    hits.append((n,{"field":OFFS[disp],"instruction":row(i),"baseReg":i.reg_name(op.mem.base) if op.mem.base else None}))
        for n,h in hits:
            # start at first non-INT3 after nearest preceding INT3 run
            j=n-1
            while j>=0 and ins[j].mnemonic!="int3":j-=1
            start=j+1
            while start<n and ins[start].mnemonic=="int3":start+=1
            # end at first ret followed by one or more INT3 decoded instructions
            end=None
            for k in range(n,len(ins)-1):
                if ins[k].mnemonic in ("ret","retf") and ins[k+1].mnemonic=="int3":
                    end=k+1;break
            req(end is not None,f"no ret->int3 boundary after {i.address:x}")
            body=ins[start:end]
            req(body and body[0].mnemonic!="int3","empty writer body")
            st=body[0].address;en=body[-1].address+len(body[-1].bytes)
            key=(st,en)
            rec=next((x for x in functions if x["_key"]==key),None)
            if rec is None:
                b0=s["rawOffset"]+st-s["va"];blob=raw[b0:b0+(en-st)]
                rec={"_key":key,"startVa":f"0x{st:08x}","endVaExclusive":f"0x{en:08x}","bytes":len(blob),
                     "sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(body),"instructions":[row(x) for x in body],"writerHits":[]}
                functions.append(rec)
            rec["writerHits"].append(h)
    for r in functions:
        r.pop("_key",None)
        r["matrixVersionWriteCount"]=sum(x["field"]=="worldMatrixVersion" for x in r["writerHits"])
        r["constVersionWriteCount"]=sum(x["field"]=="worldConstVersion" for x in r["writerHits"])
    functions.sort(key=lambda x:int(x["startVa"],16))
    summary={"functionCount":len(functions),
      "functionsWritingBoth":sum(x["matrixVersionWriteCount"]>0 and x["constVersionWriteCount"]>0 for x in functions),
      "matrixVersionWriteInstructionCount":sum(x["matrixVersionWriteCount"] for x in functions),
      "constVersionWriteInstructionCount":sum(x["constVersionWriteCount"] for x in functions)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct version writes + decoded ret/INT3 function boundaries",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"functions":functions,
      "proofBoundary":"Exact function recovery only. A function is bounded from the first decoded instruction after the nearest preceding INT3 to a decoded RET immediately followed by INT3. No function role, base-register structure identity, placement formula, or historical-retail equivalence is promoted."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in functions:print(x["startVa"],x["endVaExclusive"],x["matrixVersionWriteCount"],x["constVersionWriteCount"],[h["instruction"]["address"] for h in x["writerHits"]])
if __name__=="__main__":main()
