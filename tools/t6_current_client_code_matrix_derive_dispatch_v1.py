#!/usr/bin/env python3
"""Fail-closed current-client proof of the T6 code-matrix derive dispatcher."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-matrix-derive-dispatch-v1"
START=0x00772f90
END=0x00773030
JUMP_TABLE=0x00772ff0
SELECTOR_TABLE=0x00773010

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro})
    return ib,secs
def get(raw,secs,a,n):
    for s in secs:
        if s["va"]<=a and a+n<=s["va"]+s["rawSize"]:
            o=s["rawOffset"]+a-s["va"];return s,raw[o:o+n]
    raise E(f"unbacked 0x{a:x}+{n}")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);sec,blob=get(raw,secs,START,END-START)
    md=Cs(CS_ARCH_X86,CS_MODE_32);ins=list(md.disasm(blob,START));by={i.address:i for i in ins}
    gates={
      0x00772f90:("lea","ecx, [eax - 4]"),
      0x00772f93:("cmp","ecx, 0x18"),
      0x00772f96:("ja","0x772fed"),
      0x00772f98:("movzx","ecx, byte ptr [ecx + 0x773010]"),
      0x00772f9f:("jmp","dword ptr [ecx*4 + 0x772ff0]"),
      0x00772fdc:("shl","eax, 6"),
      0x00772fe5:("call","0x772e30"),
      0x00772fed:("ret",""),
    }
    for va,(m,o) in gates.items():
        i=by.get(va);req(i and i.mnemonic==m and i.op_str==o,f"gate drift {va:x}: {i.mnemonic if i else None} {i.op_str if i else None}")
    # selector indexed by (baseIndex - 4), valid 0..24
    _,selectors=get(raw,secs,SELECTOR_TABLE,25)
    maxsel=max(selectors)
    _,jt=get(raw,secs,JUMP_TABLE,(maxsel+1)*4)
    jumps=list(struct.unpack("<"+"I"*(maxsel+1),jt))
    mapping=[]
    for base in range(4,29):
        sel=selectors[base-4]
        mapping.append({"baseIndex":base,"selector":sel,"targetVa":f"0x{jumps[sel]:08x}"})
    # Only canonical base matrices are multiples of four.
    canonical=[x for x in mapping if x["baseIndex"]%4==0]
    req([x["baseIndex"] for x in canonical]==[4,8,12,16,20,24,28],"canonical base set drift")
    req(len({x["targetVa"] for x in canonical})==7,"canonical derive targets not unique")
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact dispatcher bytes + exact selector/jump tables",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "dispatcher":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","sha256":hashlib.sha256(blob).hexdigest(),
                    "instructions":[row(i) for i in ins]},
      "tables":{"selectorTableVa":f"0x{SELECTOR_TABLE:08x}","selectorBytes":selectors.hex(),
                "jumpTableVa":f"0x{JUMP_TABLE:08x}","jumpTargets":[f"0x{x:08x}" for x in jumps]},
      "mapping":mapping,"canonicalBaseMappings":canonical,
      "summary":{"canonicalBaseCount":len(canonical),"canonicalTargetsUnique":True,
                 "viewProjectionBase16Target":next(x["targetVa"] for x in canonical if x["baseIndex"]==16),
                 "worldViewProjectionBase20Target":next(x["targetVa"] for x in canonical if x["baseIndex"]==20),
                 "shadowLookupBase24Target":next(x["targetVa"] for x in canonical if x["baseIndex"]==24)},
      "proofBoundary":"Closes current-client baseIndex-to-helper dispatch only. Numeric baseIndex labels are exact; helper semantic names beyond the retained accessor/base relation are not promoted until each helper's dataflow is independently proven. Historical-retail equivalence is unproven."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    print(json.dumps(canonical,indent=2))
if __name__=="__main__":main()
