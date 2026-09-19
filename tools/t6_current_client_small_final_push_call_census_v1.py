#!/usr/bin/env python3
"""Locate generic current-client call targets receiving small immediate final push args.

The immediate push immediately before a direct call is only a locator. Generic
functions that receive many values in the T6 XAssetType range are surfaced for
focused follow-up. No target is named from this census.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-small-final-push-call-census-v1"
MAX_SMALL=60
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
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"executable":bool(ch&0x20000000)})
    return ib,secs
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    grouped=collections.defaultdict(list)
    for s in secs:
      if not s["executable"]:continue
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=list(md.disasm(blob,s["va"]))
      for n,i in enumerate(ins):
        if i.mnemonic!="call" or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM or n==0:continue
        prev=ins[n-1]
        if prev.mnemonic!="push" or len(prev.operands)!=1 or prev.operands[0].type!=X86_OP_IMM:continue
        v=int(prev.operands[0].imm)&0xffffffff
        if v>MAX_SMALL:continue
        t=int(i.operands[0].imm)&0xffffffff
        lo=max(0,n-10)
        grouped[t].append({"finalPushValue":v,"finalPush":row(prev),"call":row(i),"section":s["name"],
                           "contextBefore":[row(z) for z in ins[lo:n-1]]})
    targets=[]
    for t,sites in grouped.items():
      vals=sorted({x["finalPushValue"] for x in sites})
      if len(vals)<3:continue
      targets.append({"targetVa":f"0x{t:08x}","siteCount":len(sites),"distinctSmallFinalPushValues":vals,
                      "distinctSmallFinalPushValueCount":len(vals),
                      "type16SiteCount":sum(x["finalPushValue"]==16 for x in sites),
                      "type16Sites":[x for x in sites if x["finalPushValue"]==16],
                      "sites":sites if len(sites)<=80 else []})
    targets.sort(key=lambda x:(-x["distinctSmallFinalPushValueCount"],-x["siteCount"],x["targetVa"]))
    doc={"format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "summary":{"candidateTargetCount":len(targets),"candidateWithType16Count":sum(x["type16SiteCount"]>0 for x in targets),
                 "maxDistinctSmallFinalPushValues":max([x["distinctSmallFinalPushValueCount"] for x in targets],default=0)},
      "targets":targets,
      "proofBoundary":"Locator-only census of decoded direct calls whose immediately preceding instruction is a small immediate push. A push value is not assigned as XAssetType from numeric coincidence, and a call target is not named DB_FindXAssetHeader without independent argument/dataflow proof. Whole-section linear decode is not treated as exhaustive absence evidence."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
