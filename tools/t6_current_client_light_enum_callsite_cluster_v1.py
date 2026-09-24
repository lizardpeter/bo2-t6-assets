#!/usr/bin/env python3
"""Locate current-client light constant writer via enum-immediate callsite clustering.

For every direct call, inspect a bounded decoded window immediately before it for
push-immediate operands equal to retained light code-constant enum values.
Group exact callsites by target. A helper target used with many distinct light
enums is strong locator evidence for constant dirty/update helpers; no symbol or
provider semantics are assigned here.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-enum-callsite-cluster-v1"
ENUMS={
 0:"lightPosition",1:"lightDiffuse",2:"lightSpotDir",3:"lightSpotFactors",
 5:"lightFallOffA",6:"lightFallOffB",7:"lightSpotMatrix0",8:"lightSpotMatrix1",
 9:"lightSpotMatrix2",11:"lightSpotAABB",12:"lightConeControl1",
 14:"lightSpotCookieSlideControl",60:"spotShadowmapPixelAdjust"
}
LOOKBACK=18
LOOKAHEAD=6

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
    ib,secs=pe(raw);groups=defaultdict(list)
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
        target=int(i.operands[0].imm)&0xffffffff
        lo=max(0,n-LOOKBACK);hi=min(len(ins),n+LOOKAHEAD+1)
        pushes=[]
        for z in ins[lo:n]:
          if z.mnemonic=="push" and len(z.operands)==1 and z.operands[0].type==X86_OP_IMM:
            v=int(z.operands[0].imm)&0xffffffff
            if v in ENUMS:pushes.append({"enumValue":v,"accessor":ENUMS[v],"instruction":row(z)})
        if not pushes:continue
        groups[target].append({"section":s["name"],"call":row(i),"enumPushes":pushes,
          "contextBefore":[row(z) for z in ins[lo:n]],"contextAfter":[row(z) for z in ins[n+1:hi]]})
    targets=[]
    for t,calls in groups.items():
      enums=sorted({p["enumValue"] for c in calls for p in c["enumPushes"]})
      targets.append({"callTargetVa":f"0x{t:08x}","callCountWithLightEnumWindow":len(calls),
        "distinctLightEnumValues":enums,"distinctLightAccessors":[ENUMS[x] for x in enums],"callsites":calls})
    targets.sort(key=lambda x:(-len(x["distinctLightEnumValues"]),-x["callCountWithLightEnumWindow"],x["callTargetVa"]))
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct-call operands and immediate argument windows",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"callTargetCount":len(targets),"targetsWithAtLeast4DistinctLightEnums":sum(len(x["distinctLightEnumValues"])>=4 for x in targets),
        "maxDistinctLightEnumsPerTarget":max((len(x["distinctLightEnumValues"]) for x in targets),default=0)},
      "targets":targets,
      "proofBoundary":"Locator only. An enum-immediate in the preceding decoded window is not by itself proven to be a call argument; targets/functions are not assigned source symbols. Promotion requires a semantic projector proving stack argument positions/callee behavior and the caller's light source dataflow."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in targets[:20]:print(x["callTargetVa"],len(x["distinctLightEnumValues"]),x["callCountWithLightEnumWindow"],x["distinctLightAccessors"])
if __name__=="__main__":main()
