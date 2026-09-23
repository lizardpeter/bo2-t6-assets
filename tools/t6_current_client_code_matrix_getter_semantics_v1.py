#!/usr/bin/env python3
"""Fail-closed current-client proof of the generic T6 code-matrix getter.

The proof is derived only from SHA-classified current-client bytes. Historical
lineage was used to locate the function, not as proof.

Closes:
- sourceIndex -> matrixIndex = sourceIndex - 0xD3
- matrix version group = matrixIndex >> 2
- constVersions[sourceIndex] at source + 0x17E0 + sourceIndex*2
- matrixVersions[group] at source + 0x19C6 + group*2
- baseIndex = matrixIndex & ~3
- transpose/inverse sibling selection via xor 2 / xor 1
- matrix storage base at source+0 with 64 bytes per matrix
- returned row address = source + matrixIndex*64 + firstRow*16
- current-client derive-dispatch call target 0x00772F90

It does not yet prove each base-matrix derivation formula.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-matrix-getter-semantics-v1"
START=0x00773030
SCAN_END=0x00773230

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro})
    return ib,secs
def get(raw,secs,a,b):
    for s in secs:
        if s["va"]<=a and b<=s["va"]+s["rawSize"]:
            o=s["rawOffset"]+a-s["va"];return s,raw[o:o+b-a]
    raise E(f"range 0x{a:x}..0x{b:x} not raw-backed")
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);sec,blob=get(raw,secs,START,SCAN_END)
    md=Cs(CS_ARCH_X86,CS_MODE_32);ins=list(md.disasm(blob,START))
    by={i.address:i for i in ins}
    gates={
      0x00773030:("push","ebp"),
      0x00773039:("mov","eax, dword ptr [ebp + 0xc]"),
      0x0077303e:("mov","esi, dword ptr [ebp + 8]"),
      0x00773041:("movzx","edx, word ptr [esi + eax*2 + 0x17e0]"),
      0x0077304a:("lea","edi, [eax - 0xd3]"),
      0x00773052:("shr","ecx, 2"),
      0x00773055:("movzx","ecx, word ptr [esi + ecx*2 + 0x19c6]"),
      0x00773061:("cmp","edx, ecx"),
      0x00773065:("mov","eax, dword ptr [ebp + 0x10]"),
      0x00773068:("lea","eax, [eax + edi*4]"),
      0x0077306b:("shl","eax, 4"),
      0x0077306e:("add","eax, esi"),
      0x00773079:("and","ebx, 0xfffffffc"),
      0x0077307c:("movzx","edx, word ptr [esi + ebx*2 + 0x1986]"),
      0x00773091:("call","0x772f90"),
      0x007730a4:("mov","word ptr [esi + eax*2 + 0x17e0], cx"),
      0x007730ae:("xor","eax, 2"),
    }
    for va,(m,o) in gates.items():
        i=by.get(va);req(i is not None,f"missing instruction 0x{va:x}")
        req(i.mnemonic==m and i.op_str==o,f"gate drift 0x{va:x}: {i.mnemonic} {i.op_str} != {m} {o}")
    xor1=[i for i in ins if i.mnemonic=="xor" and i.op_str.endswith(", 1")]
    req(xor1,"missing xor-1 sibling selection")
    xor2=[i for i in ins if i.mnemonic=="xor" and i.op_str.endswith(", 2")]
    req(xor2,"missing xor-2 sibling selection")
    # Bound to first long INT3 pad after function body.
    rawscan=blob
    pad=rawscan.find(b"\xcc"*8,1)
    req(pad>0,"function end INT3 pad not found")
    end=START+pad
    f_ins=[i for i in ins if i.address<end]
    returns=[i.address for i in f_ins if i.mnemonic=="ret"]
    req(len(returns)>=3,f"expected multiple getter returns, got {len(returns)}")
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact function bytes and decoded dataflow",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{end:08x}","bytes":end-START,
                  "sha256":hashlib.sha256(rawscan[:pad]).hexdigest(),"section":sec["name"],
                  "instructions":[row(i) for i in f_ins],"returnVas":[f"0x{x:08x}" for x in returns]},
      "storage":{
        "matricesBaseOffset":0,
        "matrixStrideBytes":64,
        "rowStrideBytes":16,
        "constVersionsBaseOffset":0x17e0,
        "matrixVersionsBaseOffset":0x19c6,
        "firstCodeMatrixEnum":0xd3,
      },
      "dataflow":{
        "matrixIndex":"sourceIndex - 0xD3",
        "matrixVersionGroup":"matrixIndex >> 2",
        "currentConstVersion":"uint16(source + 0x17E0 + sourceIndex*2)",
        "currentMatrixVersion":"uint16(source + 0x19C6 + (matrixIndex>>2)*2)",
        "baseIndex":"matrixIndex & 0xFFFFFFFC",
        "baseConstVersion":"uint16(source + 0x1986 + baseIndex*2) == uint16(source + 0x17E0 + (0xD3+baseIndex)*2)",
        "deriveDispatchTarget":"0x00772f90",
        "transposeSibling":"matrixIndex ^ 2",
        "inverseSibling":"matrixIndex ^ 1",
        "returnAddress":"source + matrixIndex*64 + firstRow*16",
      },
      "summary":{"genericMatrixGetterClosed":True,"firstCodeMatrixEnum":0xd3,
                 "matrixStrideBytes":64,"rowStrideBytes":16,"deriveDispatchTarget":"0x00772f90",
                 "xor1InstructionCount":len(xor1),"xor2InstructionCount":len(xor2)},
      "proofBoundary":"Closes current-client generic code-matrix indexing/version/cache/sibling/return mechanics only. It does not yet prove the physical formula of each base matrix derivation, semantic meaning of source-state fields beyond their exact offsets, draw-time values, or historical-retail executable equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
