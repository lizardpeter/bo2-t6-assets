#!/usr/bin/env python3
"""Locate current-client code-image/sampler-state paired writes for unresolved T6 samplers.

Pinned T6 lineage supplies only one structural locator:
  GfxCmdBufInput.codeImages[55] immediately precedes
  GfxCmdBufInput.codeImageSamplerStates[55].

For a 32-bit client, the same-index byte state therefore lies
  (55*4 + N) - (N*4) == 0xDC - 3*N
bytes after codeImages[N].

This tool does NOT assume an absolute GfxCmdBufInput base/offset. A candidate is
admitted only when decoded current-client instructions write a dword image slot
and a byte state slot with the exact same base register and exact per-index
relative displacement inside one bounded instruction window.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FMT="t6-current-client-code-sampler-slot-pair-locator-v1"
TARGETS={
  6:"shadowmapSamplerSun",
  7:"shadowmapSamplerSpot",
  15:"attenuationSampler",
  16:"dlightAttenuationSampler",
  18:"floatZSampler",
}
WINDOW=80

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def md():
    d=Cs(CS_ARCH_X86,CS_MODE_32);d.detail=True;d.skipdata=True;return d
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def mem_write(i,size):
    if i.mnemonic not in {"mov","movzx","movsx"} or len(i.operands)<2:return None
    d=i.operands[0]
    if d.type!=X86_OP_MEM or d.size!=size or d.mem.base==0 or d.mem.index!=0:return None
    return {"baseRegId":int(d.mem.base),"disp":int(d.mem.disp),"instruction":row(i)}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);rows=[]
    for sec in secs:
        if not sec["exec"]:continue
        ins=[i for i in md().disasm(raw[sec["rawOffset"]:sec["rawOffset"]+sec["rawSize"]],sec["va"]) if i.id!=0]
        dwords=[(n,mem_write(i,4)) for n,i in enumerate(ins)]
        dwords=[(n,x) for n,x in dwords if x]
        bytes_=[(n,mem_write(i,1)) for n,i in enumerate(ins)]
        bytes_=[(n,x) for n,x in bytes_ if x]
        by_base={}
        for n,x in bytes_:by_base.setdefault(x["baseRegId"],[]).append((n,x))
        for n,img in dwords:
            state_candidates=by_base.get(img["baseRegId"],[])
            for enum,accessor in TARGETS.items():
                delta=0xDC-3*enum
                wanted=img["disp"]+delta
                for sn,st in state_candidates:
                    if st["disp"]!=wanted or abs(sn-n)>WINDOW:continue
                    lo=max(0,min(n,sn)-16);hi=min(len(ins),max(n,sn)+17)
                    rows.append({
                      "accessor":accessor,"enumValue":enum,"slotDelta":delta,
                      "section":sec["name"],"imageWrite":img,"samplerStateWrite":st,
                      "instructionDistance":sn-n,
                      "context":[row(z) for z in ins[lo:hi]],
                    })
    # Dedup exact instruction pairs if a row matched through repeated traversal.
    uniq={}
    for r in rows:
        k=(r["enumValue"],r["imageWrite"]["instruction"]["address"],r["samplerStateWrite"]["instruction"]["address"])
        uniq[k]=r
    rows=[uniq[k] for k in sorted(uniq)]
    by={}
    for enum,acc in TARGETS.items():
        rr=[x for x in rows if x["enumValue"]==enum]
        by[acc]={"enumValue":enum,"slotDelta":0xDC-3*enum,"candidatePairCount":len(rr)}
    doc={"format":FMT,
      "authority":"SHA-classified current-client decoded instructions; pinned BO2 55-code-image/55-state-array layout is locator only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "lineageLocator":{"codeImageCount":55,"stateArrayImmediatelyAfterImageArray":True,
        "sameIndexDeltaFormula":"0xDC - 3*N","source":"pinned BO2 lineage; not provider authority"},
      "summary":{"targetAccessorCount":len(TARGETS),"candidatePairCount":len(rows),"accessors":by},
      "rows":rows,
      "proofBoundary":"Paired current-client write candidates only. The exact same-base/per-index displacement relationship is required, but this does not yet prove the base object is GfxCmdBufInput, identify the image producer/resource, establish sampler-state meaning, or historical-retail equivalence. Each candidate needs focused caller/dataflow closure before provider promotion."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
