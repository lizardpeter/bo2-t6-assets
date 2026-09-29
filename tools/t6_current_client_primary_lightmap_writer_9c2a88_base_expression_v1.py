#!/usr/bin/env python3
"""Close the current-client base expression for writer 0x009C2A88.

Exact machine-code gates prove:
  function 0x009C1EF0:
    entry ESP = S
    sub esp,0x24; push ebx -> [esp+0x2C] == [S+4] == arg1
    later push ebp/esi/edi -> steady ESP == S-0x34
    [esp+0x38] == [S+4] == arg1
    0x009C264E EAX=[esp+0x38]
    0x009C2658 EAX+=0xF00
    0x009C2673 [esp+0x10]=EAX
    no later decoded direct write to [esp+0x10] before 0x009C2A81
    0x009C2A81 EDX=[esp+0x10]
    0x009C2A88 [EDX+0x1610]=EBX
  sole decoded direct caller:
    0x009B80DA ESI=[EBP+8]
    0x009B80E2 push ESI
    0x009B80E9 call 0x009C1EF0

Therefore the observed writer destination base is callee arg1+0xF00, and the
sole decoded direct caller propagates its own first argument as that arg1.

This proves address provenance only; it does not assign the resulting object a
source-level type.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x009C1EF0
END=0x009C3109
WRITER=0x009C2A88

GATES={
0x009C1EF0:("sub","esp, 0x24"),
0x009C1EF3:("push","ebx"),
0x009C1EF4:("mov","ebx, dword ptr [esp + 0x2c]"),
0x009C1F04:("push","ebp"),
0x009C1F07:("push","esi"),
0x009C1F29:("push","edi"),
0x009C264E:("mov","eax, dword ptr [esp + 0x38]"),
0x009C2658:("add","eax, 0xf00"),
0x009C2673:("mov","dword ptr [esp + 0x10], eax"),
0x009C2A81:("mov","edx, dword ptr [esp + 0x10]"),
0x009C2A88:("mov","dword ptr [edx + 0x1610], ebx"),
0x009B80DA:("mov","esi, dword ptr [ebp + 8]"),
0x009B80E2:("push","esi"),
0x009B80E9:("call","0x9c1ef0"),
}

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        ss.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro))
    return base,ss
def sec(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]:return s
    raise E(f"unbacked {va:x}")
def off(s,va):return s["rawOffset"]+va-s["va"]
def row(i):return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True)
    ap.add_argument("--base-proof",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"sha drift {dg}")
    image,ss=pe(raw);s=sec(ss,START)
    md=Cs(CS_ARCH_X86,CS_MODE_32)
    # Decode one encompassing text range from caller through target end.
    lo=0x009B80DA;hi=END
    req(sec(ss,lo)["name"]==sec(ss,hi-1)["name"],"range section drift")
    ts=sec(ss,lo);blob=raw[off(ts,lo):off(ts,hi)]
    ins=list(md.disasm(blob,lo));by={i.address:i for i in ins}
    gated=[]
    for va,(mn,op) in GATES.items():
        i=by.get(va);req(i is not None,f"missing {va:x}")
        req(i.mnemonic==mn and i.op_str==op,f"gate drift {va:x}: {i.mnemonic} {i.op_str}")
        gated.append(row(i))

    # Direct [esp+0x10] writes between the defining store and writer load.
    between=[i for i in ins if 0x009C2673<i.address<0x009C2A81]
    slot_writes=[row(i) for i in between
      if i.mnemonic.startswith("mov") and i.op_str.startswith("dword ptr [esp + 0x10],")]
    req(not slot_writes,f"later direct writes to stack slot: {slot_writes}")

    bp=json.loads(a.base_proof.read_text(encoding="utf-8"))
    req(bp["client"]["sha256"]==SHA,"base proof SHA drift")
    ww=next(x for x in bp["writers"] if x["writerVa"].lower()=="0x009c2a88")
    req(ww["directIncomingEdgeCount"]==1,"direct caller denominator drift")
    req(ww["directIncomingEdges"][0]["source"]["address"].lower()=="0x009b80e9","direct caller drift")

    doc={
      "format":"t6-current-client-primary-lightmap-writer-9c2a88-base-expression-v1",
      "authority":"SHA-pinned current-client exact stack geometry, local dataflow, and sole decoded direct-caller argument propagation",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{image:08X}"},
      "writer":{"va":"0x009C2A88","slot4Value":1,"destination":"[EDX+0x1610]","baseRegister":"EDX"},
      "function":{
        "startVa":"0x009C1EF0","diagnosticEndVaExclusive":"0x009C3109",
        "entryStackSymbol":"S",
        "prologueStackArithmetic":[
          "0x009C1EF0 sub esp,0x24 => ESP=S-0x24",
          "0x009C1EF3 push ebx => ESP=S-0x28; [esp+0x2C]=[S+4]=arg1",
          "0x009C1F04/0x009C1F07/0x009C1F29 push ebp/esi/edi => steady ESP=S-0x34; [esp+0x38]=[S+4]=arg1"
        ],
        "baseDataflow":[
          "0x009C264E EAX=[ESP+0x38]=arg1",
          "0x009C2658 EAX=arg1+0xF00",
          "0x009C2673 [ESP+0x10]=arg1+0xF00",
          "no later decoded direct [ESP+0x10] write before 0x009C2A81",
          "0x009C2A81 EDX=[ESP+0x10]=arg1+0xF00",
          "0x009C2A88 [EDX+0x1610]=1 on the proven writer branch"
        ],
      },
      "soleDecodedDirectCaller":{
        "callVa":"0x009B80E9","targetVa":"0x009C1EF0",
        "argumentFlow":"0x009B80DA ESI=[EBP+8] (caller arg1); 0x009B80E2 push ESI; therefore callee arg1 = caller arg1"
      },
      "gatedInstructions":gated,
      "summary":{
        "destinationBaseExpression":"callee_arg1 + 0xF00",
        "soleDecodedDirectCallerPropagatesCallerArg1":True,
        "observedDirectCallDestinationBaseExpression":"caller_arg1 + 0xF00",
        "laterDirectStackSlotOverwriteBeforeWriter":False
      },
      "proofBoundary":"Closes the exact base-address expression for the decoded direct-call occurrence of writer 0x009C2A88. It does not identify caller arg1 or arg1+0xF00 as GfxCmdBufSourceState and does not exclude indirect entries/calls.",
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
