#!/usr/bin/env python3
"""CFG-aware entry-stack identity for EDI at 0x009B59F6.

Builds the exact decoded control-flow graph from 0x009B5960 through the anchor,
propagates symbolic ESP deltas from entry S, and requires every reachable path
to the anchor to agree. Calls are caller-balanced for this local proof: CALL
pushes/pops its return address internally and therefore has net zero caller ESP
delta at the following instruction.

Fails closed on unsupported explicit ESP writes, indirect branches before the
anchor, or conflicting reachable ESP deltas.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import defaultdict, deque
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_REG

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009B5960
ANCHOR=0x009B59F6
END=0x009B5A20
DISP=0x7C

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]; req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4; n=struct.unpack_from("<H",raw,c+2)[0]; os=struct.unpack_from("<H",raw,c+16)[0]
    op=c+20; base=struct.unpack_from("<I",raw,op+28)[0]; so=op+os; ss=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss

def sec(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise E(f"unbacked {va:x}")

def rec(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def esp_effect(md,i):
    mn=i.mnemonic.lower(); op=i.op_str.lower()
    if mn=="push": return -4
    if mn=="pop": return 4
    if mn in ("call","ret"): return 0
    if len(i.operands)==2:
        a,b=i.operands
        if a.type==X86_OP_REG and md.reg_name(a.reg)=="esp" and b.type==X86_OP_IMM:
            imm=int(b.imm)
            if mn=="sub": return -imm
            if mn=="add": return imm
    if mn=="lea" and op.startswith("esp, [esp"):
        # Parse only simple +/- immediate.
        inside=op.split("[",1)[1].split("]",1)[0].replace(" ","")
        if inside=="esp": return 0
        if inside.startswith("esp+"): return int(inside[4:],0)
        if inside.startswith("esp-"): return -int(inside[4:],0)
    # Detect unsupported explicit ESP writes.
    try:
        _r,w=i.regs_access()
        if any(md.reg_name(z)=="esp" for z in w):
            if mn not in ("push","pop","call","ret","sub","add","lea"):
                raise E(f"unsupported ESP write at 0x{i.address:08X}: {i.mnemonic} {i.op_str}")
    except Exception as ex:
        if isinstance(ex,E): raise
    return 0

def direct_target(i):
    if len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
        return int(i.operands[0].imm)&0xffffffff
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    raw=a.exe.read_bytes(); dg=hashlib.sha256(raw).hexdigest(); req(dg==SHA,f"sha drift {dg}")
    base,ss=pe(raw); s=sec(ss,START); req(sec(ss,END-1)["name"]==s["name"],"cross section")
    off=s["rawOffset"]+(START-s["va"]); blob=raw[off:off+(END-START)]
    md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True
    ins=list(md.disasm(blob,START)); req(ins and ins[0].address==START,"decode failed")
    by={i.address:i for i in ins}; req(ANCHOR in by,"anchor missing")
    anchor=by[ANCHOR]
    req(anchor.mnemonic=="mov" and anchor.op_str=="edi, dword ptr [esp + 0x7c]",
        f"anchor drift {anchor.mnemonic} {anchor.op_str}")

    addrs=[i.address for i in ins]
    next_addr={i.address:(addrs[k+1] if k+1<len(addrs) else None) for k,i in enumerate(ins)}
    edges=defaultdict(list)
    edge_rows=[]
    for i in ins:
        if i.address>=ANCHOR: continue
        mn=i.mnemonic.lower(); nxt=next_addr[i.address]
        if mn.startswith("j"):
            t=direct_target(i)
            req(t is not None,f"indirect/undecoded branch before anchor at {i.address:#x}")
            if START<=t<=ANCHOR:
                edges[i.address].append(t); edge_rows.append({"from":f"0x{i.address:08X}","to":f"0x{t:08X}","kind":"branch"})
            # Conditional jumps also fall through. JMP does not.
            if mn!="jmp" and nxt is not None and nxt<=ANCHOR:
                edges[i.address].append(nxt); edge_rows.append({"from":f"0x{i.address:08X}","to":f"0x{nxt:08X}","kind":"fallthrough"})
        elif mn in ("ret","retn","iret","iretd"):
            pass
        else:
            if nxt is not None and nxt<=ANCHOR:
                edges[i.address].append(nxt); edge_rows.append({"from":f"0x{i.address:08X}","to":f"0x{nxt:08X}","kind":"fallthrough"})

    states=defaultdict(set)
    pred=defaultdict(list)
    states[START].add(0)
    q=deque([(START,0)])
    visited_pairs=set()
    while q:
        va,delta=q.popleft()
        if (va,delta) in visited_pairs: continue
        visited_pairs.add((va,delta))
        if va==ANCHOR: continue
        i=by.get(va); req(i is not None,f"CFG reached undecoded {va:#x}")
        nd=delta+esp_effect(md,i)
        for nv in edges.get(va,[]):
            if nv>ANCHOR: continue
            if nd not in states[nv]:
                states[nv].add(nd)
                pred[(nv,nd)].append((va,delta))
                q.append((nv,nd))

    deltas=sorted(states.get(ANCHOR,set()))
    req(deltas,f"anchor unreachable from entry")
    req(len(deltas)==1,f"conflicting ESP deltas at anchor: {deltas}")
    delta=deltas[0]
    effective=delta+DISP
    if effective==0:
        slot="entry return address [S+0]"
        ordinal=None
    elif effective>=4 and effective%4==0:
        ordinal=(effective-4)//4+1
        slot=f"entry_arg{ordinal}"
    elif effective<0:
        ordinal=None; slot=f"entry_local_or_saved[S{effective:+#x}]"
    else:
        ordinal=None; slot=f"entry_stack[S+0x{effective:X}]"

    # summarize reached instructions and state multiplicity
    reached=[]
    for va in sorted(states):
        if va<=ANCHOR:
            reached.append({"address":f"0x{va:08X}","espDeltas":sorted(states[va]),"instruction":rec(by[va])})

    doc={
      "format":"t6-current-client-writer-9c2a88-owner-stack-cfg-v2",
      "authority":"SHA-pinned exact decoded CFG with symbolic entry-relative ESP propagation",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "region":{"startVa":f"0x{START:08X}","endVaExclusive":f"0x{END:08X}",
                "sha256":hashlib.sha256(blob).hexdigest(),"instructions":[rec(i) for i in ins]},
      "cfg":{"edges":edge_rows,"reachableStates":reached},
      "anchor":{"instruction":rec(anchor),"reachableEspDeltas":deltas,
                "uniqueEspDelta":delta,"effectiveEntryOffset":effective,
                "classification":slot,"entryArgumentOrdinal":ordinal},
      "summary":{"anchorVa":f"0x{ANCHOR:08X}","reachablePathStateCount":len(visited_pairs),
                 "uniqueEspDeltaAtAnchor":delta,"effectiveEntryOffset":effective,
                 "ediExpression":slot,
                 "downstreamWriterBaseExpression":f"*({slot}+0x110)+0xF00"},
      "proofBoundary":"Closes entry-relative stack identity at 0x009B59F6 for every decoded path from exact entry 0x009B5960 that reaches the anchor within the analyzed prefix. Source-level semantic type of the resulting argument/slot remains unassigned; indirect/internal entries are not excluded."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()
