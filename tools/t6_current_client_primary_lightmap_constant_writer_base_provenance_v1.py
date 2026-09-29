#!/usr/bin/env python3
"""Trace base-object provenance for the remaining constant writes to object+0x1610.

Targets are the four exact constant-value writers retained after the two
transfer-window occurrences were excluded:
  0x009BCDE7 -> slot4 low byte 0
  0x009BD388 -> slot4 low byte 0
  0x009C1DBB -> slot4 low byte 1
  0x009C2A88 -> slot4 low byte 1

For each target this probe:
  * verifies an exact decoded destination memory operand at displacement 0x1610;
  * recovers a conservative local function group;
  * records the destination base register and nearest definition chain;
  * enumerates every decoded direct CALL/JMP into that group start;
  * joins the already-retained exact slot4 value proof.

No target is admitted as GfxCmdBufSourceState solely because of +0x1610.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM,X86_OP_IMM,X86_OP_REG

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS=(0x009BCDE7,0x009BD388,0x009C1DBB,0x009C2A88)
EXPECTED_VALUES={0x009BCDE7:0,0x009BD388:0,0x009C1DBB:1,0x009C2A88:1}
DISP=0x1610

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def row(i): return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def decode(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    b=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(b,s["va"]) if i.id]
def writes(md,i):
    try:
        _r,w=i.regs_access();return [md.reg_name(x) for x in w]
    except Exception:return []
def group(ins,idx):
    # Diagnostic INT3-bounded group; exact target instruction remains the authority.
    start=ins[0].address
    run=0
    for j in range(idx-1,-1,-1):
        if ins[j].mnemonic=="int3":
            run+=1
            if run>=6:
                k=j
                while k>0 and ins[k-1].mnemonic=="int3":k-=1
                t=j+run
                while t<len(ins) and ins[t].mnemonic=="int3":t+=1
                if t<len(ins):start=ins[t].address
                break
        else:run=0
    end=None;run=0;first=None
    for j in range(idx+1,len(ins)):
        if ins[j].mnemonic=="int3":
            if run==0:first=j
            run+=1
            if run>=6:
                end=ins[first].address;break
        else:run=0;first=None
    return start,end
def def_chain(md,local,idx,reg):
    chain=[];cur=reg;j=idx-1
    for _ in range(8):
        hit=None
        while j>=0:
            q=local[j]
            if q.mnemonic=="call":
                return {"resolved":False,"reason":"call-barrier","chain":chain,"barrier":row(q)}
            if cur in writes(md,q):
                hit=q;break
            j-=1
        if hit is None:return {"resolved":False,"reason":"no-local-definition","chain":chain}
        rr=row(hit);rr["definesRegister"]=cur;chain.append(rr)
        if hit.mnemonic=="mov" and len(hit.operands)==2 and hit.operands[0].type==X86_OP_REG and hit.operands[1].type==X86_OP_REG:
            cur=md.reg_name(hit.operands[1].reg);j-=1;continue
        return {"resolved":True,"reason":"terminal-local-definition","chain":chain}
    return {"resolved":False,"reason":"depth-limit","chain":chain}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True)
    ap.add_argument("--slot4-proof",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw)
    decoded=[]
    for s in secs:
        if s["executable"]:
            md,ins=decode(raw,s);decoded.append((s,md,ins))
    proof=json.loads(a.slot4_proof.read_text(encoding="utf-8"))
    exact={int(x["writerVa"],16):x for x in proof["writers"] if x.get("slot4ValueClosed")}
    for va,val in EXPECTED_VALUES.items():
        req(va in exact,f"writer {va:x} missing from exact value proof")
        req(exact[va]["slot4Value"]==val,f"slot4 value drift {va:x}")

    targets=[]
    starts=set()
    for va in TARGETS:
        found=None
        for s,md,ins in decoded:
            for idx,i in enumerate(ins):
                if i.address==va:
                    found=(s,md,ins,idx,i);break
            if found:break
        req(found is not None,f"writer {va:x} not decoded")
        s,md,ins,idx,i=found
        req(i.mnemonic.startswith("mov"),f"writer {va:x} not mov")
        req(len(i.operands)>=2 and i.operands[0].type==X86_OP_MEM,f"writer {va:x} destination not memory")
        mem=i.operands[0].mem
        req(mem.disp==DISP,f"writer {va:x} displacement {mem.disp:x}")
        base_reg=md.reg_name(mem.base) if mem.base else None
        req(base_reg is not None,f"writer {va:x} has no base register")
        gs,ge=group(ins,idx)
        local=[q for q in ins if q.address>=gs and (ge is None or q.address<ge)]
        li=next(k for k,q in enumerate(local) if q.address==va)
        dc=def_chain(md,local,li,base_reg)
        rec={
          "writerVa":f"0x{va:08X}","instruction":row(i),"slot4Value":EXPECTED_VALUES[va],
          "baseRegister":base_reg,"diagnosticGroupStartVa":f"0x{gs:08X}",
          "diagnosticGroupEndVa":f"0x{ge:08X}" if ge else None,
          "baseDefinition":dc,
          "localInstructions":[row(q) for q in local],
        }
        targets.append(rec);starts.add(gs)

    incoming={x:[] for x in starts}
    for s,md,ins in decoded:
        for idx,i in enumerate(ins):
            if i.mnemonic not in ("call","jmp") or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            t=int(i.operands[0].imm)&0xffffffff
            if t in starts:
                incoming[t].append({
                  "source":row(i),"section":s["name"],
                  "before":[row(q) for q in ins[max(0,idx-36):idx]],
                  "after":[row(q) for q in ins[idx+1:min(len(ins),idx+16)]],
                })
    for r in targets:
        gs=int(r["diagnosticGroupStartVa"],16)
        r["directIncomingEdges"]=incoming[gs]
        r["directIncomingEdgeCount"]=len(incoming[gs])

    doc={
      "format":"t6-current-client-primary-lightmap-constant-writer-base-provenance-v1",
      "authority":"SHA-pinned current-client exact +0x1610 writers joined to retained exact slot4 values, local base-register definitions, and direct incoming control-flow",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "writers":targets,
      "summary":{
        "writerCount":len(targets),
        "writerVAs":[x["writerVa"] for x in targets],
        "directIncomingEdgeCount":sum(x["directIncomingEdgeCount"] for x in targets),
        "baseDefinitionFrontiers":[{
          "writerVa":x["writerVa"],"baseRegister":x["baseRegister"],
          "terminal":(x["baseDefinition"]["chain"][-1]["opStr"] if x["baseDefinition"]["chain"] else None),
          "resolved":x["baseDefinition"]["resolved"],
          "directIncomingEdgeCount":x["directIncomingEdgeCount"],
        } for x in targets],
      },
      "proofBoundary":"Exact writer/value/local-base/caller evidence only. Diagnostic INT3 groups are containers, not semantic symbols. No writer is admitted as GfxCmdBufSourceState until the destination base object is independently proven to be the generic sampler source object.",
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
