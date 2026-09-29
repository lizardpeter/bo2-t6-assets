#!/usr/bin/env python3
"""Trace the owner feeding current-client generic sampler source base at +0x19660.

Anchor facts:
  0x009BC5FD: EDI = ESI + 0x19660
  0x009BC647: [EDI + 0x160C] = 1

This probe:
  * recovers the exact INT3-delimited diagnostic region containing both anchors;
  * computes CFG-aware reaching definitions for ESI at 0x009BC5FD;
  * enumerates decoded direct CALL/JMP edges to the recovered region entry;
  * preserves bounded caller contexts.

No source-level type is assigned merely from offset/layout coincidence.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict, deque
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORM=0x009BC5FD
STORE=0x009BC647
CTX=80

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def sec(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"unbacked {va:x}")
def rec(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def region(raw,s,anchor):
    off=s["rawOffset"]+(anchor-s["va"]); data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]; rel=off-s["rawOffset"]
    b=data.rfind(b"\xcc"*8,0,rel); req(b>=0,"no preceding pad")
    st=b+8
    while st<len(data) and data[st]==0xcc: st+=1
    a=data.find(b"\xcc"*8,rel); req(a>=0,"no following pad")
    while a>st and data[a-1]==0xcc:a-=1
    sva=s["va"]+st; eva=s["va"]+a
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(data[st:a],sva));req(ins and ins[0].address==sva,"decode")
    return md,ins,sva,eva,raw[s["rawOffset"]+st:s["rawOffset"]+a]
def target(i):
    if len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:return int(i.operands[0].imm)&0xffffffff
    return None
def quick(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(data,s["va"]) if i.id]
def writes_reg(md,i,name):
    try:
        _r,w=i.regs_access()
        return any(md.reg_name(x)==name for x in w)
    except:
        return False
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha {dg}")
    base,ss=pe(raw);s=sec(ss,FORM);md,ins,start,end,blob=region(raw,s,FORM);by={i.address:i for i in ins}
    req(FORM in by and STORE in by,"anchors missing")
    req(by[FORM].mnemonic=="lea" and by[FORM].op_str=="edi, [esi + 0x19660]","formation drift")
    req(by[STORE].mnemonic=="mov" and by[STORE].op_str=="dword ptr [edi + 0x160c], 1","store drift")

    # CFG up to FORM, exact direct branches inside region.
    addrs=[i.address for i in ins]; nxt={v:(addrs[k+1] if k+1<len(addrs) else None) for k,v in enumerate(addrs)}
    edges=defaultdict(list)
    for i in ins:
        if i.address>=FORM: continue
        mn=i.mnemonic.lower(); n=nxt[i.address]
        if mn.startswith("j"):
            t=target(i)
            if t is not None and start<=t<=FORM: edges[i.address].append(t)
            if mn!="jmp" and n is not None and n<=FORM: edges[i.address].append(n)
        elif mn not in ("ret","retn","iret","iretd"):
            if n is not None and n<=FORM: edges[i.address].append(n)

    # Reaching-definition sets for ESI. "entry-livein" means not yet locally defined.
    states=defaultdict(set); states[start].add("entry-livein"); q=deque([(start,"entry-livein")]); seen=set()
    esi_defs={}
    for i in ins:
        if i.address<FORM and writes_reg(md,i,"esi"):
            esi_defs[f"0x{i.address:08X}"]=rec(i)
    while q:
        va,d=q.popleft()
        if (va,d) in seen: continue
        seen.add((va,d))
        if va==FORM: continue
        i=by.get(va);req(i is not None,f"undecoded cfg {va:x}")
        nd=f"0x{i.address:08X}" if writes_reg(md,i,"esi") else d
        for nv in edges.get(va,[]):
            if nd not in states[nv]:
                states[nv].add(nd);q.append((nv,nd))
    reaching=sorted(states.get(FORM,set()))
    req(reaching,"formation unreachable")

    incoming=[]
    for es in ss:
        if not es["executable"]:continue
        emd,eins=quick(raw,es)
        for j,i in enumerate(eins):
            if i.mnemonic not in ("call","jmp"):continue
            if target(i)!=start:continue
            incoming.append({"section":es["name"],"edge":rec(i),
                             "contextBefore":[rec(x) for x in eins[max(0,j-CTX):j]],
                             "contextAfter":[rec(x) for x in eins[j+1:min(len(eins),j+24)]]})
    doc={
      "format":"t6-current-client-generic-19660-source-owner-provenance-v1",
      "authority":"SHA-pinned exact generic sampler-source formation with CFG-aware ESI reaching definitions and direct incoming-edge census",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "region":{"startVa":f"0x{start:08X}","endVaExclusive":f"0x{end:08X}","sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(ins)},
      "anchors":{"sourceFormation":rec(by[FORM]),"genericSamplerWrite":rec(by[STORE])},
      "esi":{"localDefinitions":esi_defs,"reachingDefinitionsAtFormation":reaching,
             "reachingDefinitionRecords":[esi_defs.get(x,{"kind":"entry-livein"}) for x in reaching]},
      "directIncomingEdges":incoming,
      "summary":{"regionStartVa":f"0x{start:08X}","regionEndVaExclusive":f"0x{end:08X}",
                 "esiReachingDefinitionCount":len(reaching),"esiReachingDefinitions":reaching,
                 "directIncomingEdgeCount":len(incoming),
                 "sourceBaseExpression":"ESI_at_formation + 0x19660"},
      "proofBoundary":"Exact current-client region/CFG/direct-edge proof. It proves the generic sampler source base expression at this occurrence but does not assign the ESI owner a source-level type or equate different owner occurrences without independent provenance."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
