#!/usr/bin/env python3
"""Extract the exact current-client function containing the renderTargetSize writes."""
from __future__ import annotations
import argparse,hashlib,json,string,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-target-size-provider-function-v1"
TARGET=0x0076b0b9

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
def section_for_va(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked VA 0x{va:08x}")
def raw_off(s,va):return s["rawOffset"]+va-s["va"]
def cstr(raw,secs,va,limit=240):
    try:s=section_for_va(secs,va)
    except E:return None
    o=raw_off(s,va);end=min(s["rawOffset"]+s["rawSize"],o+limit);z=raw.find(b"\0",o,end)
    if z<=o:return None
    bb=raw[o:z]
    try:t=bb.decode("ascii")
    except:return None
    if len(t)<4 or any(ch not in string.printable for ch in t):return None
    return {"va":f"0x{va:08x}","section":s["name"],"text":t,"bytes":bb.hex()}
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=section_for_va(secs,TARGET);to=raw_off(s,TARGET)
    # Find prior and following INT3 padding fences. Require at least 4 CC bytes.
    lo=to
    while lo>s["rawOffset"]+4:
        if raw[lo-4:lo]==b"\xcc"*4: break
        lo-=1
    req(raw[lo-4:lo]==b"\xcc"*4,"prior INT3 fence not found")
    start_off=lo
    hi=to
    endlim=s["rawOffset"]+s["rawSize"]-4
    while hi<endlim:
        if raw[hi:hi+4]==b"\xcc"*4: break
        hi+=1
    req(raw[hi:hi+4]==b"\xcc"*4,"following INT3 fence not found")
    start_va=s["va"]+(start_off-s["rawOffset"]);end_va=s["va"]+(hi-s["rawOffset"])
    blob=raw[start_off:hi]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(blob,start_va))
    req(ins and ins[0].address==start_va,"decode start drift")
    req(any(i.address==TARGET for i in ins),"target absent from decoded function")
    lits={}
    for i in ins:
        for op in i.operands:
            if op.type==X86_OP_IMM:
                v=int(op.imm)&0xffffffff;cs=cstr(raw,secs,v)
                if cs:lits[v]=cs
    callers=[]
    for ss in secs:
        if not ss["exec"]:continue
        b=raw[ss["rawOffset"]:ss["rawOffset"]+ss["rawSize"]]
        for p in range(max(0,len(b)-5)):
            if b[p]!=0xe8:continue
            disp=struct.unpack_from("<i",b,p+1)[0];va=ss["va"]+p
            if ((va+5+disp)&0xffffffff)==start_va:
                callers.append({"callVa":f"0x{va:08x}","bytes":b[p:p+5].hex(),"section":ss["name"]})
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact function extent from INT3 fences",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{start_va:08x}","endVaExclusive":f"0x{end_va:08x}","section":s["name"],"bytes":len(blob),
        "sha256":hashlib.sha256(blob).hexdigest(),"instructions":[row(i) for i in ins],
        "printableImmediateStrings":[lits[k] for k in sorted(lits)],"directCallers":callers},
      "targetWriteVa":f"0x{TARGET:08x}",
      "summary":{"instructionCount":len(ins),"printableStringCount":len(lits),"directCallerCount":len(callers),
        "functionStartVa":f"0x{start_va:08x}","functionEndVaExclusive":f"0x{end_va:08x}"},
      "proofBoundary":"Exact function bytes/disassembly and call/string locators only. Render-target input fields and mathematical lane semantics remain unpromoted until a separate dataflow projector closes them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":doc["summary"],"strings":doc["function"]["printableImmediateStrings"],"callers":callers},indent=2,sort_keys=True))
if __name__=="__main__":main()
