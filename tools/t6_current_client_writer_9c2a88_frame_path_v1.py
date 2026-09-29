#!/usr/bin/env python3
"""Path-sensitive proof for the 0x009B8083 -> 0x009B80DA entry feeding writer 0x009C2A88.

Closes whether EBP still denotes the 0x009B7E80 stack frame on the actual
taken path to 0x009B80DA. This corrects the deliberately conservative prior
linear scan that observed epilogue pops on mutually exclusive return paths.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import deque
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009B7E80
BRANCH=0x009B8083
TARGET=0x009B80DA
ANCHOR=0x009B80E9
END=0x009B8257

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        x=so+i*40;name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss

def sec_for(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"unbacked {va:x}")

def rec(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def target_of(i):
    s=i.op_str.strip().lower()
    if not s.startswith("0x"): return None
    try:return int(s,16)
    except:return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,ss=parse_pe(raw);s=sec_for(ss,START);req(sec_for(ss,END-1)["name"]==s["name"],"cross section")
    o=s["rawOffset"]+(START-s["va"]); blob=raw[o:o+(END-START)]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=False
    ins=list(md.disasm(blob,START)); by={i.address:i for i in ins}
    for va in (START,BRANCH,TARGET,ANCHOR):req(va in by,f"missing {va:x}")
    req(by[START].mnemonic=="push" and by[START].op_str=="ebp","entry push drift")
    req(by[START+1].mnemonic=="mov" and by[START+1].op_str=="ebp, esp","frame setup drift")
    req(by[BRANCH].mnemonic.startswith("j") and target_of(by[BRANCH])==TARGET,"target branch drift")
    req(by[TARGET].mnemonic=="mov" and by[TARGET].op_str=="esi, dword ptr [ebp + 8]","target load drift")
    req(by[ANCHOR].mnemonic=="call" and target_of(by[ANCHOR])==0x009C1EF0,"anchor call drift")

    addresses=[i.address for i in ins]; next_addr={}
    for x,y in zip(ins,ins[1:]):next_addr[x.address]=y.address

    # CFG successors inside the bounded region. Calls fall through. Conditional
    # branches have taken + fallthrough; unconditional jmp only target; ret ends.
    def succ(i):
        m=i.mnemonic
        if m.startswith("ret"): return []
        if m=="jmp":
            t=target_of(i); return [t] if t in by else []
        if m.startswith("j") and m!="jmp":
            out=[];t=target_of(i)
            if t in by: out.append(t)
            n=next_addr.get(i.address)
            if n in by: out.append(n)
            return out
        n=next_addr.get(i.address)
        return [n] if n in by else []

    # State: EBP is active frame pointer. We model only exact writes visible in
    # this function. CALL is not treated as an EBP write; MSVC x86 EBP is
    # nonvolatile, and the caller continues to use its established frame after calls.
    # Any explicit EBP destination other than the canonical setup invalidates state.
    start_after=START+by[START].size
    q=deque([(start_after,False,[])])
    seen=set(); paths=[]
    while q:
        va,frame,path=q.popleft()
        key=(va,frame)
        if key in seen: continue
        seen.add(key)
        i=by[va]; p=path+[rec(i)]
        new=frame
        if i.address==START+1 and i.mnemonic=="mov" and i.op_str=="ebp, esp": new=True
        elif i.mnemonic=="pop" and i.op_str=="ebp": new=False
        elif i.op_str.startswith("ebp,") and not (i.mnemonic=="mov" and i.op_str=="ebp, esp"):
            new=False
        if i.address==TARGET:
            paths.append({"frameActiveAtTarget":new,"path":p})
            continue
        for n in succ(i): q.append((n,new,p))

    req(paths,"target unreachable")
    active=[p for p in paths if p["frameActiveAtTarget"]]
    inactive=[p for p in paths if not p["frameActiveAtTarget"]]
    # Require every CFG state reaching TARGET from entry to retain the frame.
    req(len(inactive)==0,f"found {len(inactive)} non-frame path(s) to target")

    # Pin the immediate taken predecessor and alternate epilogue distinction.
    preds=[]
    for i in ins:
        if TARGET in succ(i): preds.append(rec(i))
    req(any(x["address"]==f"0x{BRANCH:08X}" for x in preds),"missing branch predecessor")

    # Keep one shortest-ish representative path by instruction count.
    representative=min(active,key=lambda p:len(p["path"]))["path"]
    doc={
      "format":"t6-current-client-writer-9c2a88-frame-path-v1",
      "authority":"SHA-pinned exact local CFG and path-sensitive EBP-frame state",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "region":{"startVa":f"0x{START:08X}","endVaExclusive":f"0x{END:08X}","sha256":hashlib.sha256(blob).hexdigest(),"instructionCount":len(ins)},
      "frameSetup":[rec(by[START]),rec(by[START+1])],
      "target":{"branch":rec(by[BRANCH]),"entry":rec(by[TARGET]),"anchorCall":rec(by[ANCHOR]),"predecessors":preds},
      "pathAnalysis":{"reachableStateCountAtTarget":len(paths),"frameActiveStateCount":len(active),"frameInactiveStateCount":len(inactive),"representativePath":representative},
      "conclusion":{"ebpIsActiveFrameAtTarget":True,"sourceLoadMeaning":"[EBP+8] is this 0x009B7E80 function's first stack argument on every decoded CFG path from its entry to 0x009B80DA","writerDestinationBase":"function_arg1 + 0xF00"},
      "proofBoundary":"Exact local current-client CFG through the 0x009B80DA path. Calls are treated according to the established MSVC x86 nonvolatile EBP contract; explicit in-function EBP writes/pops are path-tracked. Does not yet identify the semantic type of function_arg1 or prove indirect entries directly into 0x009B80DA absent."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"frameActiveAtTarget":True,"states":len(paths),"writerDestinationBase":"function_arg1 + 0xF00"},indent=2))

if __name__=="__main__":main()
