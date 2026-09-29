#!/usr/bin/env python3
"""Recover exact local context.source/state construction for direct generic sampler calls.

The current-client generic consumers take their first stack argument as a pointer
to a two-dword context: [context+0] is the source object, [context+4] is state.
For every decoded direct call to 0x0077D710 / 0x0077DBE0 this probe:
  * identifies the immediately pushed arg1 when possible;
  * resolves local LEA [esp+N] context pointers;
  * normalizes earlier ESP-relative stores across push/pop/add/sub ESP;
  * recovers the latest exact stores to context+0 and context+4;
  * records a fail-closed nearest definition chain for the source-value register.

It does not assign a source-level symbol to the recovered source pointer unless
the machine-code dataflow proves that identity.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS={0x0077D710:"consumer-a",0x0077DBE0:"consumer-b"}
WINDOW=180

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        x=so+i*40;name=raw[x:x+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,x+8);ch=struct.unpack_from("<I",raw,x+36)[0]
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro,executable=bool(ch&0x20000000)))
    return base,ss
def row(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def dis(raw,s):
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    data=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
    return md,[i for i in md.disasm(data,s["va"]) if i.id]
def sp_forward_delta(i):
    # Net caller-visible ESP change for simple explicit instructions only.
    if i.mnemonic=="push":return -4
    if i.mnemonic=="pop":return 4
    if i.mnemonic=="sub" and i.op_str.startswith("esp, "):
        try:return -int(i.op_str.split(",",1)[1].strip(),0)
        except:return None
    if i.mnemonic=="add" and i.op_str.startswith("esp, "):
        try:return int(i.op_str.split(",",1)[1].strip(),0)
        except:return None
    if i.mnemonic in ("enter","leave","ret","retn","retf"):return None
    if i.mnemonic=="call":return None
    return 0
def written_regs(md,i):
    try:
        _r,w=i.regs_access()
        return [md.reg_name(x) for x in w]
    except:return []
def nearest_reg_def(md,ins,start_idx,reg,max_steps=40):
    chain=[];cur=reg;idx=start_idx-1
    for depth in range(4):
        found=None
        steps=0
        while idx>=0 and steps<max_steps:
            q=ins[idx];steps+=1
            if q.mnemonic=="call":
                return {"resolved":False,"reason":"call-barrier","chain":chain,"barrier":row(q)}
            if cur in written_regs(md,q):
                found=q;break
            idx-=1
        if found is None:return {"resolved":False,"reason":"no-near-definition","chain":chain}
        rec=row(found);rec["definesRegister"]=cur;chain.append(rec)
        # Follow only exact MOV register copies. LEA/memory/immediate are terminal evidence.
        if found.mnemonic=="mov" and len(found.operands)==2 and found.operands[0].type==X86_OP_REG and found.operands[1].type==X86_OP_REG:
            nxt=md.reg_name(found.operands[1].reg)
            cur=nxt;idx-=1;continue
        return {"resolved":True,"reason":"terminal-definition","chain":chain}
    return {"resolved":False,"reason":"depth-limit","chain":chain}
def recover_local_context(md,ins,call_idx):
    # Arg1 must be the immediately preceding push of a register.
    if call_idx<=0:return {"recovered":False,"reason":"no-predecessor"}
    push=ins[call_idx-1]
    if push.mnemonic!="push" or len(push.operands)!=1:
        return {"recovered":False,"reason":"arg1-not-immediate-preceding-push","arg1Instruction":row(push)}
    if push.operands[0].type!=X86_OP_REG:
        return {"recovered":False,"reason":"arg1-push-not-register","arg1Instruction":row(push)}
    argreg=md.reg_name(push.operands[0].reg)
    # Find nearest definition of pushed register, stop at a call or another write.
    lea_idx=None;defrow=None
    for j in range(call_idx-2,max(-1,call_idx-36),-1):
        q=ins[j]
        if q.mnemonic=="call":break
        if argreg in written_regs(md,q):
            defrow=row(q)
            if q.mnemonic=="lea" and len(q.operands)==2 and q.operands[0].type==X86_OP_REG and q.operands[1].type==X86_OP_MEM:
                m=q.operands[1].mem
                if md.reg_name(m.base)=="esp" and not m.index:
                    lea_idx=j
            break
    if lea_idx is None:
        return {"recovered":False,"reason":"arg1-not-local-stack-lea","arg1Instruction":row(push),"arg1Register":argreg,"arg1Definition":defrow}
    lea=ins[lea_idx];m=lea.operands[1].mem;context_coord=m.disp # SP_at_lea is coordinate zero.
    # Walk backwards and normalize each earlier ESP-memory operand into SP_at_lea coordinates.
    sp_after=0
    stores={0:None,4:None}
    barrier=None
    lower=max(0,lea_idx-WINDOW)
    for j in range(lea_idx-1,lower-1,-1):
        q=ins[j]
        delta=sp_forward_delta(q)
        if delta is None:
            barrier=row(q);break
        sp_before=sp_after-delta
        if q.mnemonic.startswith("mov") and len(q.operands)>=2 and q.operands[0].type==X86_OP_MEM:
            mm=q.operands[0].mem
            if md.reg_name(mm.base)=="esp" and not mm.index:
                coord=sp_before+mm.disp
                rel=coord-context_coord
                if rel in stores and stores[rel] is None:
                    val={"store":row(q),"normalizedContextOffset":rel,"normalizedStackCoordinate":coord}
                    src=q.operands[1]
                    if src.type==X86_OP_REG:
                        rg=md.reg_name(src.reg);val["sourceKind"]="register";val["sourceRegister"]=rg
                        val["sourceRegisterDefinition"]=nearest_reg_def(md,ins,j,rg)
                    elif src.type==X86_OP_IMM:
                        val["sourceKind"]="immediate";val["sourceImmediate"]=int(src.imm)&0xffffffff
                    elif src.type==X86_OP_MEM:
                        val["sourceKind"]="memory";val["sourceMemoryText"]=q.op_str.split(",",1)[1].strip()
                    stores[rel]=val
                    if stores[0] is not None and stores[4] is not None:break
        sp_after=sp_before
    return {"recovered":stores[0] is not None,
            "reason":"local-context-recovered" if stores[0] is not None else "context-source-store-not-found-before-barrier",
            "arg1Instruction":row(push),"arg1Register":argreg,"arg1Definition":row(lea),
            "contextLeaDisplacement":m.disp,"contextCoordinateAtLea":context_coord,
            "sourceStore":stores[0],"stateStore":stores[4],"scanBarrier":barrier}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    base,secs=pe(raw);rows=[]
    for s in secs:
        if not s["executable"]:continue
        md,ins=dis(raw,s)
        for idx,i in enumerate(ins):
            if i.mnemonic not in ("call","jmp") or len(i.operands)!=1 or i.operands[0].type!=X86_OP_IMM:continue
            t=int(i.operands[0].imm)&0xffffffff
            if t not in TARGETS:continue
            rec=recover_local_context(md,ins,idx)
            rows.append({"section":s["name"],"call":row(i),"targetVa":f"0x{t:08X}","targetRole":TARGETS[t],"contextRecovery":rec})
    recovered=[x for x in rows if x["contextRecovery"]["recovered"]]
    def terminal(r):
        ss=r["contextRecovery"].get("sourceStore")
        if not ss:return None
        d=ss.get("sourceRegisterDefinition")
        if not d:return None
        ch=d.get("chain") or []
        return ch[-1]["opStr"] if ch else None
    terms={}
    for x in recovered:
        k=terminal(x) or "<unresolved>"
        terms[k]=terms.get(k,0)+1
    doc={
      "format":"t6-current-client-generic-sampler-context-source-backtrace-v1",
      "authority":"SHA-pinned current-client exact direct consumer calls with fail-closed local stack-context recovery",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "consumerContract":{"arg1":"pointer to two-dword context","contextSourceOffset":0,"contextStateOffset":4,
                          "basis":"consumer bodies load [arg1] for source and [arg1+4] for state"},
      "summary":{"directConsumerCallCount":len(rows),"localContextSourceRecoveredCount":len(recovered),
                 "unrecoveredCount":len(rows)-len(recovered),"terminalSourceDefinitionHistogram":terms},
      "calls":rows,
      "proofBoundary":"Exact direct-call/local stack dataflow only. Register-definition chains stop at calls and do not cross unresolved control-flow joins. A recovered source pointer is not assigned a semantic global/type name unless its terminal definition proves that identity."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
