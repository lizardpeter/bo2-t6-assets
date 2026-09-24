#!/usr/bin/env python3
"""Promote exact current-client floatZSampler provider semantics from exact slot xrefs.

Consumes only exact current-client disassembly evidence plus the proven generic
code-pixel-sampler array contract. No human render-target name is assigned to the
two pointer sources.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-floatz-sampler-provider-semantics-v1"
XREF_FMT="t6-current-client-unresolved-sampler-storage-xrefs-v1"
ARRAY_FMT="t6-current-client-code-pixel-sampler-array-semantics-v1"
ACC="floatZSampler"; ENUM=18
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def find_hit(d,addr):
    x=[h for h in d["hits"] if h["instruction"]["address"]==addr]
    if len(x)!=1:raise SystemExit(f"{addr}: hit count {len(x)}")
    return x[0]
def insmap(hit):
    rows=hit["contextBefore"]+[hit["instruction"]]+hit["contextAfter"]
    return {x["address"]:x for x in rows}
def gate(m,addr,mn,op):
    x=m.get(addr)
    if x is None or x["mnemonic"]!=mn or x["opStr"]!=op:
        raise SystemExit(f"{addr}: expected {mn} {op!r}, got {x}")
    return x
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--xrefs",type=Path,required=True)
    ap.add_argument("--array",type=Path,required=True)
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    x=json.loads(a.xrefs.read_text());arr=json.loads(a.array.read_text());den=json.loads(a.denominator.read_text())
    if x.get("format")!=XREF_FMT:raise SystemExit("xref format drift")
    if arr.get("format")!=ARRAY_FMT:raise SystemExit("array format drift")
    s=x["summary"][ACC]
    if s["slot"]!=ENUM or s["codeImageOffset"]!=0x1578 or s["samplerStateOffset"]!=0x161e:
        raise SystemExit(f"floatZ slot geometry drift {s}")
    denrows=[r for r in den["rows"] if r["accessor"]==ACC]
    if len(denrows)!=1 or int(denrows[0]["enumValue"])!=ENUM or denrows[0]["sourceClass"]!="sampler":
        raise SystemExit("denominator identity drift")
    # Union every exact xref window attributed to the same decoded function so
    # terminal branches outside the first hit's local context remain evidence-backed.
    fh=[h for h in x["hits"] if h.get("diagnosticFunctionStartVa")=="0x00741910"]
    if not fh: raise SystemExit("floatZ function evidence absent")
    m={}
    for h in fh:
        for z in h["contextBefore"]+[h["instruction"]]+h["contextAfter"]:
            prev=m.get(z["address"])
            if prev is not None and prev!=z:
                raise SystemExit(f"{z['address']}: conflicting decoded instruction evidence")
            m[z["address"]]=z
    gate(m,"0x00741a10","mov","eax, dword ptr [ebp + 8]")
    gate(m,"0x00741a16","mov","dword ptr [eax + 0x1578], 0x3a24df8")
    gate(m,"0x00741a20","mov","edx, dword ptr [ebp + 8]")
    gate(m,"0x00741a23","mov","byte ptr [edx + 0x161e], 0x61")
    gate(m,"0x00741ab2","mov","edx, dword ptr [0x3a267c0]")
    gate(m,"0x00741ab8","mov","dword ptr [ecx + 0x1578], edx")
    gate(m,"0x00741ac5","mov","eax, dword ptr [ebp + 8]")
    gate(m,"0x00741ac8","mov","ecx, dword ptr [0x3a267c0]")
    gate(m,"0x00741ad0","mov","dword ptr [eax + 0x1578], ecx")
    # Prove first alternate write also uses the exact same arg object.
    gate(m,"0x00741aaf","mov","ecx, dword ptr [ebp + 8]")
    if arr["summary"]["codeImagesBaseOffset"]!=0x1530 or arr["summary"]["codeImageSamplerStatesBaseOffset"]!=0x160c:
        raise SystemExit("generic sampler array layout drift")
    runtime={
      "accessor":ACC,"enumSymbol":denrows[0]["enumSymbol"],"enumValue":ENUM,
      "sourceClass":"sampler","updateFrequency":denrows[0]["updateFrequency"],
      "provider":{
        "sourceState":"function argument object [EBP+8], proven by exact writes to independently established code sampler arrays",
        "codeImageSlot":{"formula":"source + 0x1530 + 18*4","offset":0x1578},
        "samplerStateSlot":{"formula":"source + 0x160C + 18","offset":0x161e,"exactInitializationByte":0x61},
        "imageSources":[
          {"kind":"exact-static-pointer-value","pointerVa":"0x03A24DF8","writerVa":"0x00741A16"},
          {"kind":"exact-global-pointer-load","globalVa":"0x03A267C0","writers":["0x00741AB8","0x00741AD0"]}
        ],
        "branchBoundary":"exact control flow selects among the retained pointer sources; this proof preserves branch structure rather than assigning a human render-target identity"
      },
      "retainedSpecialOccurrences":int(denrows[0]["totalOccurrences"])
    }
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact slot writes + independently proven generic code-pixel-sampler array contract",
      "client":x["client"],"runtimeInput":runtime,
      "sources":{
        "xrefs":{"path":str(a.xrefs),"sha256":sha(a.xrefs),"format":x["format"]},
        "array":{"path":str(a.array),"sha256":sha(a.array),"format":arr["format"]},
        "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator),"format":den.get("format")}
      },
      "summary":{"currentClientProviderClosed":True,"slot":ENUM,"exactImageProviderSourceCount":2,
        "samplerStateByte":0x61,"retainedSpecialOccurrenceCount":runtime["retainedSpecialOccurrences"]},
      "proofBoundary":"Closes SHA-classified current-client floatZSampler provider mechanics: exact slot identity, source-state object, initialization sampler-state byte, and both exact image-pointer source paths are proven. The human names/physical meaning of 0x03A24DF8 and global 0x03A267C0, historical-retail executable equivalence, universal draw-time branch outcomes, and framebuffer equivalence remain unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
