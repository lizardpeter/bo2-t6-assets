#!/usr/bin/env python3
"""Exact current-client SpawnVar->entity spawn-dispatcher proof.

The function at 0x005c41f0 is promoted only as a SpawnVar/entity dispatcher shape:
- exact INT3 boundary at entry and end;
- original arg1 loaded into EBP;
- multiple entity-allocation branches;
- exact calls into the already-proven three-argument entity-field loop with EBP
  as arg1 and the newly allocated entity as arg2;
- entity pointer returned on successful branches.

The pinned OpenBO2 declaration gentity_t *G_CallSpawn(SpawnVar*) is locator/type
vocabulary only. Direct callers are retained with bounded context for the next
outer-loop proof.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-spawnvar-dispatcher-semantics-v1"
START=0x005c41f0;END=0x005c452a
SOURCE={"repo":"builtbyxeno/OpenBO2","commit":"a64812d21946baf710cec7fa26b98ad0d193903b",
"path":"src/code/src_noserver/game_mp/g_spawn_mp.cpp",
"declaration":"gentity_t *G_CallSpawn(SpawnVar *spawnVar)",
"authority":"locator/type vocabulary only; client bytes are semantic authority"}

GATES={
0x005c41ea:"cc",0x005c41ef:"cc",0x005c41f0:"83ec08",0x005c41f5:"380528733602",
0x005c41fb:"55",0x005c41fc:"8b6c2410",
0x005c4281:"e89aa61200",0x005c4286:"8bf0",0x005c4288:"57",0x005c4289:"56",0x005c428a:"55",0x005c428b:"e8f0dfffff",
0x005c42bb:"e860a61200",0x005c42c0:"8bf0",0x005c42c2:"6a01",0x005c42c4:"56",0x005c42c5:"55",0x005c42c6:"e8b5dfffff",
0x005c437e:"e89da51200",0x005c4383:"8bf0",0x005c4385:"57",0x005c4386:"56",0x005c4387:"55",0x005c4389:"e8f2deffff",
0x005c44f8:"e823a41200",0x005c44fd:"8bf0",0x005c4500:"8b542414",0x005c4504:"56",0x005c4505:"55",0x005c4506:"e875ddffff",
0x005c4520:"5b",0x005c4521:"8bc6",0x005c4523:"5e",0x005c4524:"5f",0x005c4525:"5d",0x005c4526:"83c408",0x005c4529:"c3",0x005c452a:"cc"
}
ALLOC=0x006ee920;FIELD_LOOP=0x005c2280
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
def locate(secs,va,n=1):
    for s in secs:
        if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s,s["rawOffset"]+va-s["va"]
    raise E(f"unbacked 0x{va:x}+{n}")
def read(raw,secs,va,n):
    s,o=locate(secs,va,n);return s,raw[o:o+n]
def gate(raw,secs,va,h):
    b=bytes.fromhex(h);_,g=read(raw,secs,va,len(b));req(g==b,f"gate 0x{va:08x} {g.hex()} != {h}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def callers(raw,secs,target):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;out=[]
    for s in secs:
        if not s["exec"]:continue
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=list(md.disasm(blob,s["va"]))
        for n,i in enumerate(ins):
            if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            if (int(i.operands[0].imm)&0xffffffff)!=target:continue
            lo=max(0,n-30);hi=min(len(ins),n+31)
            out.append({"call":row(i),"section":s["name"],"before":[row(x) for x in ins[lo:n]],"after":[row(x) for x in ins[n+1:hi]]})
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw)
    for va,h in GATES.items():gate(raw,secs,va,h)
    s,b=read(raw,secs,START,END-START);md=Cs(CS_ARCH_X86,CS_MODE_32);ins=[row(i) for i in md.disasm(b,START)]
    cs=callers(raw,secs,START)
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client semantics; pinned OpenBO2 declaration is locator/type vocabulary only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},"sourceLocator":SOURCE,
      "dispatcher":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"instructions":ins,
        "spawnVarArg":{"argumentIndex":1,"loadVa":"0x005c41fc","register":"ebp"},
        "entityAllocatorCallTarget":f"0x{ALLOC:08x}","entityFieldLoopTarget":f"0x{FIELD_LOOP:08x}",
        "fieldLoopCallSites":["0x005c428b","0x005c42c6","0x005c4389","0x005c4506"],
        "successReturn":{"entityRegister":"esi","moveToReturnRegisterVa":"0x005c4521","retVa":"0x005c4529"}},
      "directCallers":cs,
      "summary":{"directCallerCount":len(cs),"fieldLoopCallSiteCount":4,"allocatorCallSiteCount":4,
        "spawnVarArg1PreservedIntoFieldLoop":True,"allocatedEntityArg2PassedIntoFieldLoop":True,"allocatedEntityReturnedOnSuccess":True},
      "proofBoundary":"Current-client dispatcher dataflow only. The public G_CallSpawn declaration is used solely to name a matching byte-proven signature. This proof does not yet establish which caller obtains SpawnVars from the retail MapEnt entityString, the runtime meaning of allocator/callback callees beyond their proven dataflow role here, ClipMap submodel consumption, or historical-retail executable equivalence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
