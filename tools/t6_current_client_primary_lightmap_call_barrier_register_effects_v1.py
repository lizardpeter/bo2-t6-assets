#!/usr/bin/env python3
"""Resolve tracked-register effects across the three remaining T6 lightmap writer call barriers.

Targets:
  writer 0x009BCDE7: ESI across call 0x009D8F30
  writer 0x009BD388: ECX across call 0x009BAA50
  writer 0x009C1DBB: EBP across call 0x009D9120

The probe emits exact helper bodies, tracked-register writes, push/pop save/restore
sites, and all returns. It intentionally does not infer preservation when the
machine code does not make it explicit.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS=[
  {"writer":"0x009BCDE7","call":"0x009BCDC0","helper":0x009D8F30,"reg":"esi","pre":"ESI=[EBP-8]; [EBP-8]=arg1+0x19660"},
  {"writer":"0x009BD388","call":"0x009BD367","helper":0x009BAA50,"reg":"ecx","pre":"ECX=[EBP-8]; [EBP-8]=arg1+0x19660"},
  {"writer":"0x009C1DBB","call":"0x009C1D8D","helper":0x009D9120,"reg":"ebp","pre":"EBP=[current enclosing object expression]; exact upstream expression separately required"},
]

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        x=so+i*40;name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    return md,[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
def region(ins,idx):
    start=0;run=0;last=None
    for j in range(idx):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=8:last=j+1
        else:run=0
    if last is not None:
        start=last
        while start<len(ins) and ins[start].mnemonic=="int3":start+=1
    end=len(ins);run=0
    for j in range(idx+1,len(ins)):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=8:
                end=j-run+1;break
        else:run=0
    return start,end
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw);ts=next(s for s in secs if s["name"]==".text");md,ins=dis(raw,ts);ix={i.address:j for j,i in enumerate(ins)}
    rows=[]
    for t in TARGETS:
        h=t["helper"];req(h in ix,f"missing helper {h:x}")
        si,ei=region(ins,ix[h]);body=ins[si:ei]
        req(body and body[0].address==h,f"diagnostic region for {h:x} starts at {body[0].address:x}, not helper")
        writes=[];pushes=[];pops=[];rets=[]
        for i in body:
            _r,w=i.regs_access()
            if any(md.reg_name(x)==t["reg"] for x in w):writes.append(rec(i))
            if i.mnemonic=="push" and i.op_str==t["reg"]:pushes.append(rec(i))
            if i.mnemonic=="pop" and i.op_str==t["reg"]:pops.append(rec(i))
            if i.mnemonic.startswith("ret"):rets.append(rec(i))
        nonpop=[x for x in writes if x["mnemonic"]!="pop"]
        rows.append({
          **t,
          "helperRegion":{"startVa":f"0x{body[0].address:08X}","endVaExclusive":f"0x{body[-1].address+body[-1].size:08X}",
                          "instructionCount":len(body),"instructions":[rec(i) for i in body]},
          "trackedRegisterWrites":writes,"nonPopTrackedWrites":nonpop,
          "trackedPushes":pushes,"trackedPops":pops,"returns":rets,
          "summary":{"writeCount":len(writes),"nonPopWriteCount":len(nonpop),"pushCount":len(pushes),"popCount":len(pops),"returnCount":len(rets)}
        })
    doc={"format":"t6-current-client-primary-lightmap-call-barrier-register-effects-v1",
         "authority":"SHA-pinned exact current-client helper bodies and Capstone explicit register-access metadata",
         "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
         "barriers":rows,
         "proofBoundary":"Exact decoded helper register effects. A helper is not classified as preserving a tracked register merely from ABI convention; explicit body/save/restore evidence must support that conclusion.",
         "summary":[{"writer":x["writer"],"helper":f"0x{x['helper']:08X}","reg":x["reg"],**x["summary"]} for x in rows]}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
