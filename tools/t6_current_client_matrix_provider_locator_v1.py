#!/usr/bin/env python3
"""Locate current-client T6 matrix-provider code without source-symbol assumptions.

Evidence retained:
- exact printable strings containing renderer/matrix/source-file locator terms;
- decoded executable xrefs to those exact strings;
- decoded immediate uses of the three retained-special matrix enum values
  world=0xD3, viewProjection=0xE3, worldViewProjection=0xE7;
- bounded instruction context around every hit.

This is a locator only. Enum immediates and assertion strings are not promoted as
provider semantics until a dedicated projector proves dataflow/version behavior.
"""
from __future__ import annotations
import argparse,hashlib,json,re,struct,string
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-matrix-provider-locator-v1"
KEYWORDS=("matrix","r_state","unhandled case","viewprojection","worldview","projection","transpose","inverse")
ENUMS={
 "worldMatrix":0xD3,
 "viewProjectionMatrix":0xE3,
 "worldViewProjectionMatrix":0xE7,
}
CTX=36

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs

def off_to_va(secs,o):
    for s in secs:
        if s["rawOffset"]<=o<s["rawOffset"]+s["rawSize"]:
            return s["va"]+o-s["rawOffset"],s
    return None,None

def row(i):
    return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def strings(raw,secs):
    out=[]
    for m in re.finditer(rb'[\x20-\x7e]{4,}\x00',raw):
        b=m.group()[:-1]
        try:t=b.decode("ascii")
        except:continue
        lo=t.lower()
        if not any(k in lo for k in KEYWORDS):continue
        va,s=off_to_va(secs,m.start())
        if va is None:continue
        out.append({"text":t,"va":va,"vaHex":f"0x{va:08x}","section":s["name"],"rawOffset":m.start()})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==CLIENT_SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);ss=strings(raw,secs);str_targets={x["va"]:x["text"] for x in ss}
    string_hits=[];enum_hits=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            strs=[]; enums=[]
            for oi,op in enumerate(i.operands):
                vals=[]
                if op.type==X86_OP_IMM:
                    vals.append((int(op.imm)&0xffffffff,"imm",oi))
                elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:
                    vals.append((int(op.mem.disp)&0xffffffff,"mem",oi))
                for v,kind,oi2 in vals:
                    if v in str_targets:
                        strs.append({"targetVa":f"0x{v:08x}","text":str_targets[v],"kind":kind,"operandIndex":oi2})
                    for name,ev in ENUMS.items():
                        if v==ev:
                            enums.append({"accessor":name,"enumValue":ev,"kind":kind,"operandIndex":oi2})
            if strs or enums:
                lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
                rec={"section":s["name"],"instruction":row(i),
                     "contextBefore":[row(x) for x in ins[lo:n]],"contextAfter":[row(x) for x in ins[n+1:hi]]}
                if strs:
                    rec["stringReferences"]=strs;string_hits.append(rec)
                if enums:
                    rec2=dict(rec);rec2["enumReferences"]=enums;enum_hits.append(rec2)
    summary={
      "relevantStringCount":len(ss),
      "decodedStringXrefInstructionCount":len(string_hits),
      "decodedMatrixEnumImmediateInstructionCount":len(enum_hits),
      "matrixEnumImmediateCounts":{name:sum(any(r["accessor"]==name for r in h["enumReferences"]) for h in enum_hits) for name in ENUMS},
    }
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client exact bytes/decoded operands",
         "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
         "matrixEnums":ENUMS,"summary":summary,"strings":ss,"decodedStringXrefs":string_hits,
         "decodedMatrixEnumImmediateXrefs":enum_hits,
         "proofBoundary":"Locator only. Exact strings and decoded immediate operands are retained. No function/source-symbol identity, matrix storage layout, version semantics, provider formula, draw-time value, or historical-retail equivalence is promoted by this file alone."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
