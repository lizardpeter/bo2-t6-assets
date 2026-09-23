#!/usr/bin/env python3
"""Locate register-relative uint16 read/modify/write +1 sequences.

Compilers often expand ++uint16 into load/movzx -> increment/add -> store instead
of a single memory inc. This locator records same-base/same-displacement word
read/write windows containing an intervening +1 arithmetic instruction, then
ranks displacement bases against the independently known 243-entry T6
constVersions geometry. It is deliberately non-semantic until independently
anchored.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-u16-rmw-version-cluster-locator-v1"
COUNT=243
WINDOW=10

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
def memkey(op):
    if op.type!=X86_OP_MEM or op.size!=2 or op.mem.base==0 or op.mem.index!=0:return None
    return (op.mem.base,int(op.mem.disp))
def is_read_word(i):
    # Conservative: memory operand appears as source (operand index >=1), or movzx/movsx source.
    for k,op in enumerate(i.operands):
        key=memkey(op)
        if key and (k>0 or i.mnemonic in ("movzx","movsx")):return key
    return None
def is_write_word(i,key):
    if not i.operands:return False
    return memkey(i.operands[0])==key and i.mnemonic in ("mov","xchg")
def plus_one(i):
    if i.mnemonic=="inc":return True
    if i.mnemonic=="add" and len(i.operands)>=2 and i.operands[1].type==X86_OP_IMM and int(i.operands[1].imm)==1:return True
    if i.mnemonic=="sub" and len(i.operands)>=2 and i.operands[1].type==X86_OP_IMM and int(i.operands[1].imm)==0xffffffff:return True
    return False
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);seq=[];by_disp=collections.defaultdict(list)
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            key=is_read_word(i)
            if not key:continue
            for m in range(n+1,min(len(ins),n+1+WINDOW)):
                z=ins[m]
                if not is_write_word(z,key):continue
                middle=ins[n+1:m]
                plus=[q for q in middle if plus_one(q)]
                if not plus:break
                base,disp=key
                rec={"baseRegisterId":base,"displacement":disp,"section":s["name"],
                     "read":row(i),"plusOneInstructions":[row(q) for q in plus],"write":row(z),
                     "window":[row(q) for q in ins[max(0,n-5):min(len(ins),m+6)]]}
                seq.append(rec);by_disp[disp].append(rec);break
    disps=sorted(by_disp);dset=set(disps);scores={}
    for d in disps:
        for idx in range(COUNT):
            base=d-2*idx
            occ=[i for i in range(COUNT) if base+2*i in dset]
            if len(occ)>=4:scores[base]=occ
    ranked=sorted(scores.items(),key=lambda kv:(-len(kv[1]),kv[0]))[:100]
    candidates=[]
    for base,occ in ranked:
        candidates.append({
          "baseDisplacement":base,"baseDisplacementHex":f"0x{base&0xffffffff:08x}",
          "entryBytes":2,"entryCount":COUNT,"observedRmwIndexCount":len(occ),
          "observedRmwIndices":occ,"sequenceCount":sum(len(by_disp[base+2*i]) for i in occ),
          "sequences":[{"index":i,"displacement":base+2*i,"windows":by_disp[base+2*i]} for i in occ],
        })
    doc={"format":FORMAT,"authority":"SHA-classified current client exact decoded same-address uint16 RMW windows",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"u16ReadModifyWritePlusOneSequenceCount":len(seq),"uniqueDisplacementCount":len(disps),"ranked243EntryCandidateBaseCount":len(candidates),"bestCandidateObservedIndexCount":candidates[0]["observedRmwIndexCount"] if candidates else 0},
      "candidateGeometry":{"entryCount":COUNT,"entryBytes":2},"candidates":candidates,"allSequences":seq,
      "proofBoundary":"Exact same-register/same-displacement uint16 read/modify/write windows with an intervening +1 arithmetic instruction only. The 243-entry geometry is a ranking hypothesis. No base is promoted as constVersions and no index is assigned code-constant semantics until independently anchored."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in candidates[:12]:print(c["baseDisplacementHex"],c["observedRmwIndexCount"],c["observedRmwIndices"])
if __name__=="__main__":main()
