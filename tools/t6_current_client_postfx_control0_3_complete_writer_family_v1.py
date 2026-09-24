#!/usr/bin/env python3
"""Freeze all five current-client postFxControl0..3 writer functions.

The destination-only census proved the exact writer-function denominator:
  control0/1: five functions
  control2: three functions
  control3: two functions
This proof retains all five complete INT3-bounded functions, callers, and exact
value/version writes. It is a denominator/provenance proof, not yet a simplified
provider formula.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-postfx-control0-3-complete-writer-family-v1"
ANCHORS=(0x00768980,0x007698B0,0x0076A970,0x0076BE00,0x0076C650)
VALUE_BASE=0x03A37300; VERSION_BASE=0x03A382E0
ENUMS={f"postFxControl{i}":107+i for i in range(4)}
SEARCH=0x7000;CTX=28

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
def secfor(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"VA 0x{va:x} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def body(raw,s,anchor):
    ro=s["rawOffset"]+anchor-s["va"];lo=max(s["rawOffset"],ro-SEARCH);hi=min(s["rawOffset"]+s["rawSize"],ro+SEARCH)
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(raw[lo:hi],s["va"]+lo-s["rawOffset"]) if i.id]
    n=next((k for k,i in enumerate(ins) if i.address==anchor),None);req(n is not None,f"anchor {anchor:x} not decoded")
    p=-1
    for k in range(n-1,-1,-1):
        if ins[k].mnemonic=="int3":
            while k+1<n and ins[k+1].mnemonic=="int3":k+=1
            p=k;break
    q=len(ins)
    for k in range(n+1,len(ins)):
        if ins[k].mnemonic=="int3":q=k;break
    out=ins[p+1:q];req(out,f"empty function {anchor:x}");return out
def classify(v):
    for acc,e in ENUMS.items():
        b=VALUE_BASE+e*16
        for lane in range(4):
            if v==b+lane*4:return acc,e,f"value[{lane}]"
        if v==VERSION_BASE+e*2:return acc,e,"version"
    return None
def writes(ins):
    out=[]
    for i in ins:
        if not i.operands:continue
        op=i.operands[0]
        if op.type!=X86_OP_MEM or op.mem.base!=0 or op.mem.index!=0:continue
        v=int(op.mem.disp)&0xffffffff;c=classify(v)
        if c:
            acc,e,field=c;out.append({"accessor":acc,"enumValue":e,"field":field,"targetVa":f"0x{v:08x}","instruction":rr(i)})
    return out
def callers(raw,secs,target):
    out=[];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    for s in secs:
        if not s["exec"]:continue
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=target:continue
            lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
            out.append({"call":rr(i),"section":s["name"],"contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for anchor in ANCHORS:
        s=secfor(secs,anchor);ins=body(raw,s,anchor);st=ins[0].address;en=ins[-1].address+ins[-1].size;ww=writes(ins);cc=callers(raw,secs,st)
        per={}
        for acc in ENUMS:
            rs=[x for x in ww if x["accessor"]==acc]
            per[acc]={"writeCount":len(rs),"fields":sorted({x["field"] for x in rs}),"writeAddresses":[x["instruction"]["address"] for x in rs]}
        rows.append({"anchorVa":f"0x{anchor:08x}","startVa":f"0x{st:08x}","endVaExclusive":f"0x{en:08x}","instructionCount":len(ins),
          "section":s["name"],"accessorWrites":per,"writes":ww,"directCallers":cc,"instructions":[rr(i) for i in ins]})
    denom={acc:sorted(f["startVa"] for f in rows if f["accessorWrites"][acc]["writeCount"]>0) for acc in ENUMS}
    expected={
      "postFxControl0":["0x00768980","0x007698b0","0x0076a970","0x0076be00","0x0076c650"],
      "postFxControl1":["0x00768980","0x007698b0","0x0076a970","0x0076be00","0x0076c650"],
      "postFxControl2":["0x007698b0","0x0076be00","0x0076c650"],
      "postFxControl3":["0x007698b0","0x0076c650"],
    }
    req(denom==expected,f"writer denominator drift {denom}")
    summary={"writerFunctionCount":len(rows),"writerFunctions":[f["startVa"] for f in rows],"accessorWriterDenominator":denom,
             "directCallerCounts":{f["startVa"]:len(f["directCallers"]) for f in rows}}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact complete destination-writer denominator + INT3-bounded function/caller bytes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"functions":rows,
      "proofBoundary":"Closes the exact current-client writer-function denominator for postFxControl0..3 and preserves every writer body/caller. It does not yet simplify all branch formulas or source-record semantics, and therefore does not alone promote provider closure, historical-retail equivalence or framebuffer parity."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
