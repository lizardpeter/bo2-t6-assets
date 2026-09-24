#!/usr/bin/env python3
"""Compact current-client light enum direct-call argument clustering.

Stronger than v1:
- argument window begins after the nearest preceding call/ret/jmp boundary,
  capped to 14 decoded instructions;
- the light enum must be an actual push-immediate inside that local argument
  sequence;
- retain only compact callsite metadata, never whole decoded contexts;
- classify 2-push dirty-like and >=2-push argument shapes diagnostically.

Still locator-only: argument positions/callee semantics require a projector.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-light-enum-callsite-cluster-v2"
ENUMS={0:"lightPosition",1:"lightDiffuse",2:"lightSpotDir",3:"lightSpotFactors",
5:"lightFallOffA",6:"lightFallOffB",7:"lightSpotMatrix0",8:"lightSpotMatrix1",
9:"lightSpotMatrix2",11:"lightSpotAABB",12:"lightConeControl1",
14:"lightSpotCookieSlideControl",60:"spotShadowmapPixelAdjust"}
MAX_BACK=14
BOUNDARY={"call","ret","retf","jmp"}

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
        lo=max(0,n-MAX_BACK)
        for k in range(n-1,lo-1,-1):
          if ins[k].mnemonic in BOUNDARY:
            lo=k+1;break
        argseq=ins[lo:n]
        pushes=[z for z in argseq if z.mnemonic=="push"]
        enums=[]
        for z in pushes:
          if len(z.operands)==1 and z.operands[0].type==X86_OP_IMM:
            v=int(z.operands[0].imm)&0xffffffff
            if v in ENUMS:enums.append((v,z))
        if not enums:continue
        groups[target].append({"section":s["name"],"call":rr(i),
          "argInstructionCount":len(argseq),"pushCount":len(pushes),
          "enumPushes":[{"enumValue":v,"accessor":ENUMS[v],"instruction":rr(z),
                         "pushOrdinal":pushes.index(z)} for v,z in enums],
          "argInstructions":[rr(z) for z in argseq]})
    targets=[]
    for t,calls in groups.items():
      vals=sorted({p["enumValue"] for c in calls for p in c["enumPushes"]})
      dirty=[c for c in calls if c["pushCount"]==2 and len(c["enumPushes"])==1]
      targets.append({"callTargetVa":f"0x{t:08x}","callCount":len(calls),
        "distinctLightEnumValues":vals,"distinctLightAccessors":[ENUMS[v] for v in vals],
        "twoPushSingleEnumCallCount":len(dirty),
        "twoPushSingleEnumDistinctValues":sorted({p["enumValue"] for c in dirty for p in c["enumPushes"]}),
        "twoPushSingleEnumDistinctAccessors":sorted({p["accessor"] for c in dirty for p in c["enumPushes"]}),
        "callsites":calls})
    targets.sort(key=lambda x:(-len(x["twoPushSingleEnumDistinctValues"]),-x["twoPushSingleEnumCallCount"],
                               -len(x["distinctLightEnumValues"]),x["callTargetVa"]))
    # Fail-safe proof-size bound: only retain targets that touch >=2 exact light enums
    # or have >=2 dirty-like calls. Singletons are summarized but not expanded.
    retained=[x for x in targets if len(x["distinctLightEnumValues"])>=2 or x["twoPushSingleEnumCallCount"]>=2]
    summaryOnly=[{k:x[k] for k in ("callTargetVa","callCount","distinctLightEnumValues","distinctLightAccessors",
                                    "twoPushSingleEnumCallCount","twoPushSingleEnumDistinctValues",
                                    "twoPushSingleEnumDistinctAccessors")} for x in targets]
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact direct calls and local argument-setup instructions",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"allCallTargetCount":len(targets),"retainedExpandedTargetCount":len(retained),
        "maxDirtyLikeDistinctLightEnums":max((len(x["twoPushSingleEnumDistinctValues"]) for x in targets),default=0),
        "targetsWithAtLeast4DirtyLikeLightEnums":sum(len(x["twoPushSingleEnumDistinctValues"])>=4 for x in targets)},
      "targetSummaries":summaryOnly,"retainedTargets":retained,
      "proofBoundary":"Locator only. Local push sequences are exact machine evidence, but cdecl argument identity is not promoted solely from push count/order. A semantic projector must prove the selected callee body and exact caller dataflow before provider closure."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in targets[:30]:
      print(x["callTargetVa"],"dirtyDistinct",len(x["twoPushSingleEnumDistinctValues"]),x["twoPushSingleEnumDistinctAccessors"],
            "dirtyCalls",x["twoPushSingleEnumCallCount"],"allDistinct",len(x["distinctLightEnumValues"]))
if __name__=="__main__":main()
