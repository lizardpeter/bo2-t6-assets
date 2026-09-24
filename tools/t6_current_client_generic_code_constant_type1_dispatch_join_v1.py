#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
FMT="t6-current-client-generic-code-constant-type1-dispatch-join-v1"
def req(v,m):
    if not v: raise SystemExit(m)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dispatch",type=Path,required=True)
    ap.add_argument("--setter",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.dispatch.read_text());s=json.loads(a.setter.read_text())
    req(d["format"]=="t6-current-client-generic-code-constant-setter-indirect-dispatch-v1","dispatch format")
    req(s["format"]=="t6-current-client-generic-code-constant-setter-semantics-v1","setter format")
    req(d["setterVa"]=="0x00745b70","setter VA")
    req(len(d["pointerOccurrences"])==1,"setter pointer denominator")
    p=d["pointerOccurrences"][0]
    req(p["pointerVa"]=="0x00d27e74","setter table pointer VA")
    words={x["va"]:x["u32"] for x in p["neighborWords"]}
    req(words["0x00d27e70"]=="0x00000000","type0 table entry")
    req(words["0x00d27e74"]=="0x00745b70","type1 table entry")
    rr=[x for x in d["references"] if x["instruction"]["address"]=="0x00749f68"]
    req(len(rr)==1,"dispatcher table load")
    r=rr[0]
    before={x["address"]:x for x in r["contextBefore"]}
    after={x["address"]:x for x in r["contextAfter"]}
    gates={
      "0x00749f3b":("mov","dword ptr [esp + 8], edx"),
      "0x00749f3f":("cmp","byte ptr [edx + 2], 0"),
      "0x00749f43":("mov","ecx, edx"),
      "0x00749f64":("movzx","ecx, byte ptr [ecx + 2]"),
    }
    allm={**before,r["instruction"]["address"]:r["instruction"],**after}
    for va,(mn,op) in gates.items():
        x=allm.get(va);req(x and x["mnemonic"]==mn and x["opStr"]==op,f"gate drift {va}")
    req(r["instruction"]["mnemonic"]=="mov" and r["instruction"]["opStr"]=="eax, dword ptr [ecx*4 + 0xd27e70]","table load drift")
    for va,mn,op in [
      ("0x00749f6f","lea","edx, [esp + 8]"),
      ("0x00749f73","push","edx"),
      ("0x00749f74","call","eax"),
    ]:
        x=after.get(va);req(x and x["mnemonic"]==mn and x["opStr"]==op,f"call gate drift {va}")
    req(s["summary"]["currentClientGenericSetterClosed"] is True,"setter closure drift")
    doc={
      "format":FMT,
      "authority":"exact join of current-client indirect type dispatch and generic code-constant setter semantics",
      "dispatcher":{
        "recordCursorLocal":"[esp+8]",
        "typeByte":"uint8(runtimeRecord+0x02)",
        "handlerTableBase":"0x00D27E70",
        "handlerFormula":"uint32(0x00D27E70 + typeByte*4)",
        "type1Handler":"0x00745B70",
        "callSiteVa":"0x00749F74",
        "wrapperArgument":"address of local runtimeRecord cursor"
      },
      "type1Record":{
        "enumValue":"uint32(runtimeRecord+0x04)",
        "lanes":["float32(runtimeRecord+0x08)","float32(runtimeRecord+0x0C)","float32(runtimeRecord+0x10)","float32(runtimeRecord+0x14)"],
        "destination":"0x03A37300 + enumValue*16",
        "version":"uint16[0x03A382E0 + enumValue*2] += 1",
        "advance":"runtimeRecord += uint16(runtimeRecord+0x00)"
      },
      "sources":{"dispatchSha256":sha(a.dispatch),"setterSha256":sha(a.setter)},
      "summary":{"type1DispatchClosed":True,"genericCodeConstantRecordProviderClosed":True,"handlerTableIndex":1},
      "proofBoundary":"Closes the generic current-client type-1 runtime-record dispatch and setter contract. It does not prove that a particular code-constant enum is supplied by a type-1 record on a given render path; per-enum reachability/provider ownership remains a separate gate."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
