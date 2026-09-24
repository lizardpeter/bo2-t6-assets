#!/usr/bin/env python3
"""Locate RC_SET_CUSTOM_CONSTANT-shaped producers for unresolved indirect constants."""
from __future__ import annotations
import argparse,hashlib,json,struct,re
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-unresolved-custom-constant-producer-locator-v1"
TARGETS={
 37:"shadowmapSwitchPartition",38:"sunShadowmapPixelSize",
 60:"spotShadowmapPixelAdjust",61:"dlightSpotShadowmapPixelAdjust",
 111:"postFxControl4",112:"postFxControl5"
}
CTX=60

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
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def rn(md,r):return md.reg_name(r) if r else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);hits=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic!="mov" or len(i.operands)!=2:continue
        dst,src=i.operands
        if dst.type!=X86_OP_MEM or src.type!=X86_OP_IMM or int(dst.mem.disp)!=4:continue
        enum=int(src.imm)&0xffffffff
        if enum not in TARGETS:continue
        base=rn(md,dst.mem.base)
        if not base or dst.mem.index:continue
        lo=max(0,n-CTX);hi=min(len(ins),n+CTX+1)
        refs=[]
        for z in ins[lo:hi]:
          for oi,op in enumerate(z.operands):
            if op.type!=X86_OP_MEM or rn(md,op.mem.base)!=base or op.mem.index:continue
            disp=int(op.mem.disp)
            if disp in (0,2,4,8,12,16,20):
              refs.append({"instruction":rr(z),"offset":disp,"operandIndex":oi,
                "positionClass":"destination-or-rmw" if oi==0 and z.mnemonic not in ("cmp","test") else "source-or-other"})
        hits.append({"accessor":TARGETS[enum],"enumValue":enum,"section":s["name"],"enumStore":rr(i),
          "recordBaseRegister":base,"sameBaseReferences":refs,
          "contextBefore":[rr(x) for x in ins[lo:n]],"contextAfter":[rr(x) for x in ins[n+1:hi]]})
    rows=[]
    for h in hits:
      dest={}
      for x in h["sameBaseReferences"]:
        if x["positionClass"]=="destination-or-rmw":dest.setdefault(x["offset"],[]).append(x["instruction"])
      fields=set(dest);payload={8,12,16,20}
      rows.append({
        "accessor":h["accessor"],"enumValue":h["enumValue"],"enumStore":h["enumStore"],
        "recordBaseRegister":h["recordBaseRegister"],"destinationOffsets":sorted(fields),
        "hasOffset0Destination":0 in fields,"hasOffset2Destination":2 in fields,
        "fullFloat4PayloadDestinationCoverage":payload.issubset(fields),
        "commandShapeScore":sum(x in fields for x in (0,2,8,12,16,20)),
        "destinationInstructionsByOffset":{str(k):v for k,v in sorted(dest.items())},
        "contextBefore":h["contextBefore"],"contextAfter":h["contextAfter"],
      })
    summary={}
    for enum,acc in TARGETS.items():
      rs=[r for r in rows if r["enumValue"]==enum]
      summary[acc]={"enumValue":enum,"candidateCount":len(rs),
        "fullFloat4Count":sum(r["fullFloat4PayloadDestinationCoverage"] for r in rs),
        "headerAndFloat4Count":sum(r["hasOffset0Destination"] and r["fullFloat4PayloadDestinationCoverage"] for r in rs),
        "maxCommandShapeScore":max([r["commandShapeScore"] for r in rs],default=0)}
    doc={"format":FORMAT,"authority":"SHA-classified exact [base+4] enum stores reduced against proven RC_SET_CUSTOM_CONSTANT record field geometry",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "recordContract":{"byteCountOffset":0,"typeOffset":2,"enumOffset":4,"payloadOffsets":[8,12,16,20]},
      "summary":summary,"rows":rows,
      "proofBoundary":"Structural producer locator only. Full float4/header coverage strongly narrows command-shaped sites, but provider closure still requires allocator/type/header semantics, source-value provenance and reachability into the proven backend handler."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for r in rows:
      if r["fullFloat4PayloadDestinationCoverage"] or r["commandShapeScore"]>=3:
        print("CANDIDATE",r["accessor"],r["enumStore"]["address"],r["recordBaseRegister"],r["destinationOffsets"],r["commandShapeScore"])
if __name__=="__main__":main()
