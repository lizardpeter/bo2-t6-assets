#!/usr/bin/env python3
"""Pin exact EAX/ECX setup at all four generic runtime-record dispatcher calls.

The dispatcher contract is already source-closed: ECX enters as the record
cursor, while incoming EAX is retained as an optional filter/version pointer.
This projector keeps the final in-function definitions and a compact dependency
window for both registers at every direct caller.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-current-client-generic-runtime-record-call-contracts-v1"
SOURCE_FORMAT="t6-current-client-generic-runtime-record-caller-functions-v1"
DISPATCH=0x00749ED0

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)

def writes_reg(ins,reg):
    m=ins.get("mnemonic",""); op=ins.get("opStr","")
    if m in {"mov","lea","xor","or","and","add","sub","pop","movzx","movsx"}:
        dst=op.split(",",1)[0].strip()
        return dst==reg
    return False

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--source",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    d=json.loads(a.source.read_text()); req(d.get("format")==SOURCE_FORMAT,"source format drift")
    rows=[]
    for f in d["functions"]:
        ins=f["instructions"]
        calls=[(i,x) for i,x in enumerate(ins) if x["mnemonic"]=="call" and x["opStr"]=="0x749ed0"]
        req(len(calls)==1,f"{f['startVa']}: dispatcher call count {len(calls)}")
        n,call=calls[0]
        defs={}
        for reg in ("eax","ecx"):
            k=next((k for k in range(n-1,-1,-1) if writes_reg(ins[k],reg)),None)
            req(k is not None,f"{call['address']}: no prior {reg} definition")
            defs[reg]={"definition":ins[k],"distanceInstructions":n-k,"window":ins[max(0,k-8):n]}
        rows.append({
          "functionStartVa":f["startVa"],"call":call,
          "incomingEax":defs["eax"],"incomingEcx":defs["ecx"],
          "tail":ins[max(0,n-18):n],
        })
    req(len(rows)==4,"caller denominator drift")
    out={
      "format":FORMAT,
      "authority":"exact four-caller denominator + nearest in-function EAX/ECX definitions for the source-closed dispatcher ABI",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "dispatcherContract":{
        "entryVa":"0x00749ed0",
        "recordCursorRegister":"ecx",
        "optionalFilterPointerRegister":"eax",
        "typeByte":"uint8(record+0x02)",
        "recordAdvance":"record += uint16(record+0x00)"
      },
      "summary":{"callerCount":len(rows),"callAddresses":[r["call"]["address"] for r in rows]},
      "callers":rows,
      "proofBoundary":"Closes nearest in-function register definitions at the complete direct-call denominator. A preceding call may still own an EAX return value; such return provenance remains explicit rather than guessed. Per-enum record reachability remains a separate gate."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
