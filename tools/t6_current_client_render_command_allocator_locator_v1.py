#!/usr/bin/env python3
"""Locate current-client R_GetCommandBuffer-equivalent from exact diagnostic strings.

This is locator evidence only. Exact retained strings are searched in raw-backed
sections, then decoded executable operands referencing those string VAs are
retained with bounded context and enclosing INT3 function ranges.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-render-command-allocator-locator-v1"
STRINGS=[
 "(renderCmd) = %i",
 "(bytes) = %i",
 "RENDERCOMMAND_CRITICAL_WARN_SIZE (%i bytes) reached\n",
 "RENDERCOMMAND_WARN_SIZE (%.0f KB) reached\n",
]
CTX=32
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
def locate_strings(raw,secs):
    out={}
    for text in STRINGS:
      needle=text.encode("ascii")+b"\0";hits=[]
      for s in secs:
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];pos=0
        while True:
          i=blob.find(needle,pos)
          if i<0:break
          hits.append({"text":text,"section":s["name"],"rawOffset":s["rawOffset"]+i,
            "va":s["va"]+i,"vaHex":f"0x{s['va']+i:08x}"})
          pos=i+1
      out[text]=hits
    return out
def function_bounds(raw,s,va):
    o=s["rawOffset"]+va-s["va"];lo=o
    while lo>s["rawOffset"]+4 and raw[lo-4:lo]!=b"\xcc"*4:lo-=1
    start=o
    if raw[lo-4:lo]==b"\xcc"*4:start=lo
    hi=o;lim=s["rawOffset"]+s["rawSize"]-4
    while hi<lim and raw[hi:hi+4]!=b"\xcc"*4:hi+=1
    end=hi if raw[hi:hi+4]==b"\xcc"*4 else min(lim,o+1024)
    return s["va"]+start-s["rawOffset"],s["va"]+end-s["rawOffset"]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);strings=locate_strings(raw,secs);targets={}
    for text,hits in strings.items():
      for h in hits:targets[h["va"]]=text
    refs=[]
    for s in secs:
      if not s["exec"]:continue
      md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
      ins=[i for i in md.disasm(raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]],s["va"]) if i.id]
      for n,i in enumerate(ins):
        hits=[]
        for op in i.operands:
          vals=[]
          if op.type==X86_OP_IMM:vals.append(int(op.imm)&0xffffffff)
          elif op.type==X86_OP_MEM and op.mem.base==0 and op.mem.index==0:vals.append(int(op.mem.disp)&0xffffffff)
          for v in vals:
            if v in targets:hits.append({"va":f"0x{v:08x}","text":targets[v]})
        if not hits:continue
        fs,fe=function_bounds(raw,s,i.address)
        refs.append({"section":s["name"],"instruction":row(i),"strings":hits,
          "functionStartVa":f"0x{fs:08x}","functionEndVaExclusive":f"0x{fe:08x}",
          "contextBefore":[row(x) for x in ins[max(0,n-CTX):n]],
          "contextAfter":[row(x) for x in ins[n+1:min(len(ins),n+CTX+1)]]})
    byfunc={}
    for r in refs:
      k=(r["functionStartVa"],r["functionEndVaExclusive"])
      x=byfunc.setdefault(k,{"functionStartVa":k[0],"functionEndVaExclusive":k[1],"references":[],"uniqueStrings":set()})
      x["references"].append(r);x["uniqueStrings"].update(z["text"] for z in r["strings"])
    funcs=[]
    for x in byfunc.values():
      x["uniqueStrings"]=sorted(x["uniqueStrings"]);x["referenceCount"]=len(x["references"]);funcs.append(x)
    funcs.sort(key=lambda x:(-len(x["uniqueStrings"]),x["functionStartVa"]))
    summary={"requestedStringCount":len(STRINGS),"foundStringCount":sum(bool(strings[x]) for x in STRINGS),
      "decodedReferenceCount":len(refs),"candidateFunctionCount":len(funcs),
      "maxUniqueStringsInOneFunction":max((len(x["uniqueStrings"]) for x in funcs),default=0)}
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact diagnostic strings + decoded operand xrefs",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "summary":summary,"stringOccurrences":strings,"candidateFunctions":funcs,
      "proofBoundary":"Locator only. Exact diagnostics and decoded xrefs identify candidate enclosing functions. No candidate is named R_GetCommandBuffer, and no command-allocation or producer semantics are promoted until a separate structural projector validates argument checks, size accounting and callsites."}
    req(summary["foundStringCount"]>=2,"insufficient allocator diagnostic strings found")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":summary,"candidates":[{"start":x["functionStartVa"],"end":x["functionEndVaExclusive"],"strings":x["uniqueStrings"],"refs":x["referenceCount"]} for x in funcs]},indent=2,sort_keys=True))
if __name__=="__main__":main()
