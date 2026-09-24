#!/usr/bin/env python3
"""Promote exact current-client debugPerformance code-constant provider semantics."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-debug-performance-provider-semantics-v1"
HELPER_FMT="t6-current-client-gametime-upstream-helper-probe-v1"
MATRIX_FMT="t6-current-client-code-matrix-getter-semantics-v1"
ACC="debugPerformance"; ENUM=45

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def gate(m,a,mn,op):
    x=m.get(a)
    if x is None or x.get("mnemonic")!=mn or x.get("opStr")!=op:
        raise SystemExit(f"{a}: expected {mn} {op!r}, got {x}")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--helper",type=Path,required=True)
    ap.add_argument("--matrix",type=Path,required=True)
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    h=json.loads(a.helper.read_text()); mx=json.loads(a.matrix.read_text()); den=json.loads(a.denominator.read_text())
    if h.get("format")!=HELPER_FMT:raise SystemExit("helper format drift")
    if mx.get("format")!=MATRIX_FMT:raise SystemExit("matrix format drift")
    rr=[r for r in h["ranges"] if r.get("startVa")=="0x0076ef60"]
    if len(rr)!=1:raise SystemExit(f"helper range count {len(rr)}")
    m={x["address"]:x for x in rr[0]["instructions"]}
    # Exact source-state/cache construction and enum45 writer gates.
    gate(m,"0x0076ef61","mov","ebx, dword ptr [esp + 8]")
    gate(m,"0x0076ef6c","push","0x1a80")
    gate(m,"0x0076ef73","push","ebx")
    gate(m,"0x0076ef87","lea","edi, [ebx + 0x800]")
    gate(m,"0x0076ef98","lea","esi, [ebx + 0x17e0]")
    for addr,off in [("0x0076f04f","0xad0"),("0x0076f057","0xad4"),("0x0076f05f","0xad8"),("0x0076f067","0xadc")]:
        gate(m,addr,"movss",f"dword ptr [ebx + {off}], xmm0")
    gate(m,"0x0076f017","xorps","xmm0, xmm0")
    gate(m,"0x0076f06f","add","word ptr [ebx + 0x183a], di")
    # Independently established generic version-array addressing.
    if "source + 0x17E0 + sourceIndex*2" not in mx["dataflow"]["currentConstVersion"]:
        raise SystemExit("version-array contract drift")
    row=[r for r in den["rows"] if r.get("accessor")==ACC]
    if len(row)!=1 or int(row[0]["enumValue"])!=ENUM or row[0]["sourceClass"]!="constant":
        raise SystemExit("denominator debugPerformance identity drift")
    expected_value=0x800+ENUM*16; expected_ver=0x17e0+ENUM*2
    if expected_value!=0xad0 or expected_ver!=0x183a:raise SystemExit("enum45 offset arithmetic drift")
    runtime={"accessor":ACC,"enumSymbol":row[0]["enumSymbol"],"enumValue":ENUM,
      "sourceClass":"constant","updateFrequency":row[0]["updateFrequency"],
      "provider":{
        "sourceState":"EBX = first function argument at 0x0076EF61; same object is zero-initialized for 0x1A80 bytes and then treated as the code-constant cache",
        "constantValueSlot":{"formula":"source + 0x800 + 45*16","offset":expected_value,
          "lanes":[0.0,0.0,0.0,0.0],"writers":["0x0076F04F","0x0076F057","0x0076F05F","0x0076F067"]},
        "constantVersionSlot":{"formula":"source + 0x17E0 + 45*2","offset":expected_ver,
          "writerVa":"0x0076F06F","operation":"uint16 += DI"},
        "zeroRegisterProof":{"instructionVa":"0x0076F017","instruction":"xorps xmm0, xmm0"}
      },
      "retainedSpecialOccurrences":int(row[0]["totalOccurrences"])}
    doc={"format":FORMAT,
      "authority":"SHA-classified current-client exact source-state initializer bytes + independently proven code-constant version-array layout",
      "client":h["client"],"runtimeInput":runtime,
      "sources":{"helper":{"path":str(a.helper),"sha256":sha(a.helper),"format":h["format"]},
                 "matrix":{"path":str(a.matrix),"sha256":sha(a.matrix),"format":mx["format"]},
                 "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator),"format":den.get("format")}},
      "summary":{"currentClientProviderClosed":True,"enumValue":ENUM,"exactValue":[0.0,0.0,0.0,0.0],
                 "retainedSpecialOccurrenceCount":runtime["retainedSpecialOccurrences"]},
      "proofBoundary":"Closes SHA-classified current-client debugPerformance provider mechanics for this initializer path: exact source-state object, enum45 value slot, exact zero vector, and matching enum45 version update are proven. The semantic purpose of debugPerformance, the numerical meaning of the DI version increment, all possible later mutations, historical-retail executable equivalence, and framebuffer effects remain outside this proof."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
