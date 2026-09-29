#!/usr/bin/env python3
"""Find exact direct-control-flow reachability from VP8 decode callback 0x009B59F0 to 0x009BCD00.

This is a machine-code proof, not a symbol guess. It decodes .text once,
walks reachable basic blocks from each exact direct-call target, and builds
a bounded direct-call/tail-jump graph. Indirect calls remain explicit
frontiers rather than being guessed.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import deque
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ROOT=0x009B59F0
TARGET=0x009BCD00
MAX_DEPTH=12
MAX_FUNCS=2500
MAX_INS_PER_FUNC=20000

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def rec(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def imm_target(i):
    if len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
        return int(i.operands[0].imm)&0xffffffff
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw)
    textsec=next(s for s in secs if s["name"]==".text")
    data=raw[textsec["rawOffset"]:textsec["rawOffset"]+textsec["rawSize"]]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    ins=[i for i in md.disasm(data,textsec["va"]) if i.id]
    by={i.address:i for i in ins}
    addrs=[i.address for i in ins]
    next_addr={v:(addrs[k+1] if k+1<len(addrs) else None) for k,v in enumerate(addrs)}
    lo=textsec["va"];hi=lo+textsec["rawSize"]
    req(ROOT in by and TARGET in by,"root/target not decoded")

    cache={}
    def direct_callees(entry):
        if entry in cache:return cache[entry]
        q=deque([entry]);seen=set();calls=[];indirect=[];visited=0
        while q:
            va=q.popleft()
            if va in seen:continue
            seen.add(va);visited+=1
            if visited>MAX_INS_PER_FUNC:break
            i=by.get(va)
            if i is None:continue
            mn=i.mnemonic.lower();nxt=next_addr.get(va)
            if mn=="call":
                t=imm_target(i)
                if t is not None and lo<=t<hi:
                    calls.append({"call":rec(i),"target":t})
                else:
                    indirect.append(rec(i))
                if nxt is not None:q.append(nxt)
            elif mn=="jmp":
                t=imm_target(i)
                if t is not None and lo<=t<hi:q.append(t)
                else: indirect.append(rec(i))
            elif mn.startswith("j") or mn in ("loop","loope","loopne"):
                t=imm_target(i)
                if t is not None and lo<=t<hi:q.append(t)
                if nxt is not None:q.append(nxt)
            elif mn in ("ret","retn","iret","iretd"):
                continue
            elif mn in ("int3","ud2"):
                continue
            else:
                if nxt is not None:q.append(nxt)
        out={"entry":entry,"calls":calls,"indirect":indirect,"reachableInstructionCount":len(seen)}
        cache[entry]=out;return out

    parent={ROOT:None};parent_edge={};depth={ROOT:0};fq=deque([ROOT]);order=[]
    found=False
    while fq and len(parent)<=MAX_FUNCS:
        f=fq.popleft();order.append(f)
        if f==TARGET:found=True;break
        if depth[f]>=MAX_DEPTH:continue
        info=direct_callees(f)
        for e in info["calls"]:
            t=e["target"]
            if t not in parent:
                parent[t]=f;parent_edge[t]=e["call"];depth[t]=depth[f]+1;fq.append(t)
            if t==TARGET:
                found=True;fq.clear();break

    path=[]
    if TARGET in parent:
        cur=TARGET
        while cur is not None:
            path.append({"entry":f"0x{cur:08X}","viaCall":parent_edge.get(cur)})
            cur=parent[cur]
        path.reverse()

    rootinfo=direct_callees(ROOT)
    doc={
      "format":"t6-current-client-vp8-decode-to-9bcd00-direct-reachability-v1",
      "authority":"SHA-pinned current-client decoded direct-control-flow/call reachability",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "rootVa":f"0x{ROOT:08X}","targetVa":f"0x{TARGET:08X}",
      "settings":{"maxDepth":MAX_DEPTH,"maxFunctions":MAX_FUNCS},
      "summary":{"targetReached":TARGET in parent,"pathLengthEdges":(len(path)-1 if path else None),
                 "visitedFunctionEntryCount":len(parent),"rootDirectCallCount":len(rootinfo["calls"]),
                 "rootIndirectCallCount":len(rootinfo["indirect"])},
      "path":path,
      "rootDirectCalls":[{"call":x["call"],"targetVa":f"0x{x['target']:08X}"} for x in rootinfo["calls"]],
      "rootIndirectCalls":rootinfo["indirect"],
      "visitedEntries":[f"0x{x:08X}" for x in order],
      "proofBoundary":"Direct decoded control-flow/call reachability only. Indirect calls/jumps are retained as unresolved and are not guessed. Absence of a direct path is not proof of non-membership; presence of a path is exact machine-code reachability."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    if TARGET not in parent:
        raise SystemExit(2)
if __name__=="__main__":main()
