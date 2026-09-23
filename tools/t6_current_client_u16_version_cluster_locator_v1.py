#!/usr/bin/env python3
"""Locate dense current-client uint16 version-counter write clusters.

Scans the SHA-classified client for exact absolute-memory writes consistent with
C/C++ ++/+=1 to uint16 counters. It does not assign any cluster to
GfxCmdBufSourceState::constVersions. The 243-entry/2-byte geometry is used only
to rank candidate bases for later semantic anchoring.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_AC_WRITE
from capstone.x86 import X86_OP_MEM,X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-u16-version-cluster-locator-v1"
COUNT=243
SPAN=COUNT*2

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
def is_plus_one(i):
    if i.mnemonic=="inc" and len(i.operands)==1:return True
    if i.mnemonic=="add" and len(i.operands)==2 and i.operands[1].type==X86_OP_IMM and int(i.operands[1].imm)==1:return True
    return False
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);writes=[];by_target=collections.defaultdict(list)
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        for i in md.disasm(blob,s["va"]):
            if not is_plus_one(i):continue
            for op in i.operands[:1]:
                if op.type!=X86_OP_MEM or op.size!=2:continue
                if op.mem.base!=0 or op.mem.index!=0:continue
                t=int(op.mem.disp)&0xffffffff
                rec={"targetVa":f"0x{t:08x}","section":s["name"],"instruction":row(i)}
                writes.append(rec);by_target[t].append(rec)
    targets=sorted(by_target)
    # Rank every even base that can be induced by one observed target at one
    # possible 0..242 index. Collapse identical occupancy sets/bases.
    scores={}
    targetset=set(targets)
    for t in targets:
        for idx in range(COUNT):
            base=t-2*idx
            if base<0 or base&1:continue
            occ=[i for i in range(COUNT) if base+2*i in targetset]
            if len(occ)<4:continue
            key=base
            prev=scores.get(key)
            if prev is None or len(occ)>len(prev):scores[key]=occ
    ranked=sorted(scores.items(),key=lambda kv:(-len(kv[1]),kv[0]))[:100]
    candidates=[]
    for base,occ in ranked:
        candidates.append({
          "baseVa":f"0x{base:08x}","entryBytes":2,"entryCount":COUNT,
          "observedIncrementedIndexCount":len(occ),"observedIncrementedIndices":occ,
          "observedTargetRange":[f"0x{base+2*min(occ):08x}",f"0x{base+2*max(occ):08x}"],
          "writeInstructionCount":sum(len(by_target[base+2*i]) for i in occ),
          "writes":[{"index":i,"targetVa":f"0x{base+2*i:08x}","instructions":by_target[base+2*i]} for i in occ],
        })
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client exact decoded writes only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"absoluteUint16PlusOneInstructionCount":len(writes),"uniqueAbsoluteTargetCount":len(targets),"ranked243EntryCandidateBaseCount":len(candidates),"bestCandidateObservedIndexCount":candidates[0]["observedIncrementedIndexCount"] if candidates else 0},
      "candidateGeometry":{"entryCount":COUNT,"entryBytes":2,"totalBytes":SPAN},
      "candidates":candidates,
      "proofBoundary":"Exact current-client absolute uint16 increment/add-one writes only. The 243-entry geometry is a ranking hypothesis derived from the independently known T6 code-constant count; no candidate base is promoted as constVersions and no index is assigned a code-constant semantic until an independent setter/function anchor closes the base."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in candidates[:10]:print(c["baseVa"],c["observedIncrementedIndexCount"],c["observedIncrementedIndices"][:20],"...",c["observedIncrementedIndices"][-5:])
if __name__=="__main__":main()
