#!/usr/bin/env python3
"""Rank all current-client register-relative uint16 stores as 243-entry array candidates.

Unlike the earlier ++-specific probes, this records every exact write whose
destination is word ptr [register + displacement], then ranks displacement bases
against the independently known 243-entry T6 constVersions geometry. It does
not assume how the increment value was computed.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-u16-relative-write-cluster-v1"
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
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);by_disp=collections.defaultdict(list);writes=[]
    for s in secs:
        if not s["exec"]:continue
        md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
        ins=list(md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]))
        for n,i in enumerate(ins):
            if not i.operands:continue
            d=i.operands[0]
            if d.type!=X86_OP_MEM or d.size!=2 or d.mem.base==0 or d.mem.index!=0:continue
            disp=int(d.mem.disp);lo=max(0,n-8);hi=min(len(ins),n+9)
            rec={"baseRegisterId":d.mem.base,"displacement":disp,"section":s["name"],"instruction":row(i),
                 "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]}
            by_disp[disp].append(rec);writes.append(rec)
    disps=sorted(by_disp);dset=set(disps);scores={}
    for d in disps:
        for idx in range(COUNT):
            base=d-2*idx
            occ=[i for i in range(COUNT) if base+2*i in dset]
            if len(occ)>=6:scores[base]=occ
    ranked=sorted(scores.items(),key=lambda kv:(-len(kv[1]),kv[0]))[:150]
    candidates=[]
    for base,occ in ranked:
        candidates.append({
          "baseDisplacement":base,"baseDisplacementHex":f"0x{base&0xffffffff:08x}","entryCount":COUNT,"entryBytes":2,
          "observedWrittenIndexCount":len(occ),"observedWrittenIndices":occ,
          "writeInstructionCount":sum(len(by_disp[base+2*i]) for i in occ),
          "writes":[{"index":i,"displacement":base+2*i,"instructions":by_disp[base+2*i]} for i in occ],
        })
    doc={"format":FORMAT,"authority":"SHA-classified current client exact decoded register-relative uint16 writes",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"relativeUint16WriteInstructionCount":len(writes),"uniqueDisplacementCount":len(disps),"ranked243EntryCandidateBaseCount":len(candidates),"bestCandidateObservedIndexCount":candidates[0]["observedWrittenIndexCount"] if candidates else 0},
      "candidateGeometry":{"entryCount":COUNT,"entryBytes":2},"candidates":candidates,
      "proofBoundary":"Exact current-client register-relative uint16 destination writes only. The 243x2 geometry ranks candidate displacement bases from independently known T6 source-state layout. No base is promoted as constVersions and no slot semantic is assigned until anchored by independent provider dataflow."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for c in candidates[:15]:print(c["baseDisplacementHex"],c["observedWrittenIndexCount"],c["observedWrittenIndices"])
if __name__=="__main__":main()
