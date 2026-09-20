#!/usr/bin/env python3
"""Recover the exact current-client function containing the fifth G_ParseEntityFields-like call.

The function extent is bounded only by contiguous INT3 padding in the SHA-classified
client .text bytes. We retain complete linear disassembly, raw-backed printable
immediates, and direct rel32 callers to the recovered entry. No function/source
name is promoted by this probe alone.
"""
from __future__ import annotations
import argparse,hashlib,json,string,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-fifth-entity-field-caller-function-v1"
TARGET_CALL=0x0067d131
FIELD_LOOP=0x005c2280

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def locate(secs,va,n=1):
    for s in secs:
        if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:
            return s,s["rawOffset"]+va-s["va"]
    raise E(f"VA 0x{va:x}+{n} unbacked")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def cstr(raw,secs,va,limit=400):
    try:s,o=locate(secs,va)
    except E:return None
    end=min(o+limit,s["rawOffset"]+s["rawSize"]);z=raw.find(b"\0",o,end)
    if z<=o:return None
    b=raw[o:z]
    try:t=b.decode("ascii")
    except:return None
    if len(t)<4 or any(ch not in string.printable for ch in t):return None
    return {"va":f"0x{va:08x}","section":s["name"],"text":t,"bytes":b.hex()}
def padding_bounds(raw,secs,target):
    s,o=locate(secs,target)
    sec0=s["rawOffset"];sec1=sec0+s["rawSize"]
    # last >=4-CC run ending before target
    p=o-1;left=None
    while p>=sec0+3:
        if raw[p-3:p+1]==b"\xcc"*4:
            a=p-3
            while a>sec0 and raw[a-1]==0xcc:a-=1
            b=p+1
            while b<o and raw[b]==0xcc:b+=1
            left=(a,b);break
        p-=1
    req(left is not None,"no preceding INT3 padding")
    start_off=left[1]
    # first >=4-CC run after target
    p=o+5;right=None
    while p+4<=sec1:
        if raw[p:p+4]==b"\xcc"*4:
            a=p
            while a>o and raw[a-1]==0xcc:a-=1
            b=p+4
            while b<sec1 and raw[b]==0xcc:b+=1
            right=(a,b);break
        p+=1
    req(right is not None,"no following INT3 padding")
    end_off=right[0]
    start_va=s["va"]+(start_off-sec0);end_va=s["va"]+(end_off-sec0)
    return s,start_off,end_off,start_va,end_va,left,right
def direct_callers(raw,secs,target):
    out=[]
    for s in secs:
        if not s["exec"]:continue
        b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for p in range(0,max(0,len(b)-4)):
            if b[p]!=0xe8:continue
            disp=struct.unpack_from("<i",b,p+1)[0];va=s["va"]+p
            if (va+5+disp)&0xffffffff==target:
                out.append({"callVa":f"0x{va:08x}","section":s["name"],"bytes":b[p:p+5].hex()})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dig=hashlib.sha256(raw).hexdigest();req(dig==CLIENT_SHA,f"SHA drift {dig}")
    ib,secs=pe(raw);s,so,eo,sv,ev,left,right=padding_bounds(raw,secs,TARGET_CALL)
    blob=raw[so:eo];md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;ins=list(md.disasm(blob,sv))
    req(ins and ins[0].address==sv,"decode start failure")
    target=[i for i in ins if i.address==TARGET_CALL]
    req(len(target)==1 and target[0].mnemonic=="call" and target[0].op_str=="0x5c2280","target call drift")
    lits={}
    for i in ins:
        for op in i.operands:
            if op.type==X86_OP_IMM:
                x=cstr(raw,secs,int(op.imm)&0xffffffff)
                if x:lits[x["va"]]=x
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dig,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{sv:08x}","endVaExclusive":f"0x{ev:08x}","section":s["name"],
        "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"instructions":[row(i) for i in ins]},
      "padding":{"precedingRawOffsetRange":list(left),"followingRawOffsetRange":list(right)},
      "targetFieldLoopCall":{"callVa":f"0x{TARGET_CALL:08x}","targetVa":f"0x{FIELD_LOOP:08x}"},
      "referencedPrintableStrings":[lits[k] for k in sorted(lits)],
      "directCallersToFunctionEntry":direct_callers(raw,secs,sv),
      "summary":{"functionStartVa":f"0x{sv:08x}","functionEndVaExclusive":f"0x{ev:08x}",
        "instructionCount":len(ins),"printableLiteralCount":len(lits),"directCallerCount":len(direct_callers(raw,secs,sv))},
      "proofBoundary":"Exact function extent from current-client INT3 padding, bytes/disassembly, raw-backed printable immediates, and rel32 callers only. This does not yet name the function, prove EBX is map-owned SpawnVar data, prove MapEnt/entityString ownership, ClipMap submodel semantics, or historical-retail equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
