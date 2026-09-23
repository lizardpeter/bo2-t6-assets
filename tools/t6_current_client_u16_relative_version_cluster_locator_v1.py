#!/usr/bin/env python3
"""Locate register-relative uint16 +1 displacement clusters in current T6 client.

Designed to recover candidate GfxCmdBufSourceState::constVersions geometry when
functions receive the source-state pointer in a register. Only exact decoded
uint16 inc/add-one writes are retained. 243x2 geometry ranks displacement bases;
no semantic assignment is made without an independent provider anchor.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-u16-relative-version-cluster-locator-v1"
COUNT=243

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
def plus_one(i):
    if i.mnemonic=="inc" and len(i.operands)==1:return True
    return i.mnemonic=="add" and len(i.operands)==2 and i.operands[1].type==X86_OP_IMM and int(i.operands[1].imm)==1
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);writes=[];by_disp=collections.defaultdict(list)
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            if not plus_one(i) or not i.operands:continue
            op=i.operands[0]
            if op.type!=X86_OP_MEM or op.size!=2:continue
            if op.mem.base==0 or op.mem.index!=0:continue
            disp=int(op.mem.disp)
            lo=max(0,n-12);hi=min(len(ins),n+13)
            rec={"displacement":disp,"baseRegisterId":op.mem.base,"section":s["name"],"instruction":row(i),
                 "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]}
            writes.append(rec);by_disp[disp].append(rec)
    disps=sorted(by_disp)
    scores={}
    dset=set(disps)
    for d in disps:
        for idx in range(COUNT):
            base=d-2*idx
            occ=[i for i in range(COUNT) if base+2*i in dset]
            if len(occ)<4:continue
            scores[base]=occ
    ranked=sorted(scores.items(),key=lambda kv:(-len(kv[1]),kv[0]))[:100]
    cand=[]
    for base,occ in ranked:
        cand.append({
          "baseDisplacement":base,"baseDisplacementHex":f"0x{base&0xffffffff:08x}",
          "entryCount":COUNT,"entryBytes":2,"observedIncrementedIndexCount":len(occ),
          "observedIncrementedIndices":occ,
          "writeInstructionCount":sum(len(by_disp[base+2*i]) for i in occ),
          "writes":[{"index":i,"displacement":base+2*i,"instructions":by_disp[base+2*i]} for i in occ],
        })
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client exact decoded register-relative uint16 +1 writes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"relativeUint16PlusOneInstructionCount":len(writes),"uniqueDisplacementCount":len(disps),"ranked243EntryCandidateBaseCount":len(cand),"bestCandidateObservedIndexCount":cand[0]["observedIncrementedIndexCount"] if cand else 0},
      "candidateGeometry":{"entryCount":COUNT,"entryBytes":2},"candidates":cand,
      "allWrites":writes,
      "proofBoundary":"Exact current-client register-relative uint16 increment/add-one writes only. The 243-entry geometry ranks displacement bases using independently known T6 code-constant count. No displacement base is promoted as constVersions and no observed index gains a code-constant meaning until an independent provider/setter anchor closes it."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in cand[:12]:print(c["baseDisplacementHex"],c["observedIncrementedIndexCount"],c["observedIncrementedIndices"])
if __name__=="__main__":main()
