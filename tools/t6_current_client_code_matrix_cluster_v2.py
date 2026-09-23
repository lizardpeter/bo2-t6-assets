#!/usr/bin/env python3
"""Locate current-client versioned code-matrix machinery by structural clusters.

This v2 locator intentionally does NOT require an immediate 0xD3. Optimizers may
fold CONST_SRC_FIRST_CODE_MATRIX into LEA/add/sub forms. Instead it searches exact
current-client function-like instruction regions for the characteristic T6 matrix
family operations documented by lineage only as a locator:
- XOR with 1 and XOR with 2 (inverse/transpose sibling selection);
- group-of-four mask/alignment (AND with ~3 / 0xfffffffc / 0xfc);
- divide-by-four / multiply-by-64 / multiply-by-16 style arithmetic;
- multiple 16-bit memory operations consistent with version arrays.

Nothing is promoted from lineage. Output is exact current-client disassembly only.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-matrix-cluster-v2"
WINDOW=140

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
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
def imms(i):
    out=[]
    if i.id==0:return out
    for op in i.operands:
        if op.type==X86_OP_IMM:out.append(int(op.imm)&0xffffffff)
    return out
def wordmem(i):
    if i.id==0:return False
    return "word ptr [" in i.op_str.lower()
def score_window(w):
    has_x1=any(i.mnemonic=="xor" and 1 in imms(i) for i in w)
    has_x2=any(i.mnemonic=="xor" and 2 in imms(i) for i in w)
    has_mask=any(i.mnemonic=="and" and any(v in (0xfffffffc,0xfc,0x3ffffffc) for v in imms(i)) for i in w)
    has_div4=any((i.mnemonic in ("shr","sar") and 2 in imms(i)) for i in w)
    has_mul64=any((i.mnemonic in ("shl","sal") and 6 in imms(i)) or (i.mnemonic=="imul" and 0x40 in imms(i)) for i in w)
    has_mul16=any((i.mnemonic in ("shl","sal") and 4 in imms(i)) or (i.mnemonic=="imul" and 0x10 in imms(i)) for i in w)
    has_d3_form=any(any(v in (0xd3,0xffffff2d,0xffffff2c,0x2d) for v in imms(i)) for i in w)
    word_ops=sum(wordmem(i) for i in w)
    mem_cmps=sum(i.mnemonic in ("cmp","test") and "ptr [" in i.op_str.lower() for i in w)
    returns=sum(i.mnemonic=="ret" for i in w)
    score=(3 if has_x1 else 0)+(3 if has_x2 else 0)+(3 if has_mask else 0)+(2 if has_div4 else 0)+(2 if has_mul64 else 0)+(1 if has_mul16 else 0)+(1 if has_d3_form else 0)+(2 if word_ops>=3 else 0)+(1 if mem_cmps>=3 else 0)
    return {"score":score,"hasXor1":has_x1,"hasXor2":has_x2,"hasGroupMask":has_mask,"hasDivideBy4":has_div4,
            "hasScale64":has_mul64,"hasScale16":has_mul16,"hasFirstMatrixImmediateForm":has_d3_form,
            "wordMemoryInstructionCount":word_ops,"memoryCompareCount":mem_cmps,"returnCount":returns}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);cands=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
        ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
        anchors=[n for n,i in enumerate(ins) if i.mnemonic=="xor" and any(v in (1,2) for v in imms(i))]
        for n in anchors:
            lo=max(0,n-WINDOW);hi=min(len(ins),n+WINDOW+1);w=ins[lo:hi];sc=score_window(w)
            if sc["score"]<10 or not (sc["hasXor1"] and sc["hasXor2"]):continue
            cands.append({"anchor":row(ins[n]),**sc,"context":[row(x) for x in w]})
    # dedup heavily overlapping candidates by context first address + signature
    uniq={}
    for c in cands:
        k=(c["context"][0]["address"],c["context"][-1]["address"])
        old=uniq.get(k)
        if old is None or c["score"]>old["score"]:uniq[k]=c
    rows=sorted(uniq.values(),key=lambda x:(-x["score"],int(x["anchor"]["address"],16)))
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact decoded instruction clusters",
         "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
         "summary":{"candidateCount":len(rows),"score15PlusCount":sum(x["score"]>=15 for x in rows),
                    "score18PlusCount":sum(x["score"]>=18 for x in rows)},
         "candidates":rows[:80],
         "proofBoundary":"Locator only. Candidate scoring is not semantic proof. Lineage-informed arithmetic shapes are used only to choose current-client regions for inspection; no function name, matrix enum, storage layout, provider formula, draw-time value, or historical-retail equivalence is promoted."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in rows[:20]:
        print(c["anchor"]["address"],c["score"],c["hasGroupMask"],c["hasDivideBy4"],c["hasScale64"],c["hasScale16"],c["wordMemoryInstructionCount"])
if __name__=="__main__":main()
