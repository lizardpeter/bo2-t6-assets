#!/usr/bin/env python3
"""Fail-closed current-client provider semantics for CONST_SRC_CODE_GENERIC_PARAM0 / scriptVector0."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-script-vector0-provider-semantics-v1"
FUNC_FMT="t6-current-client-render-target-size-provider-function-v1"
CLUSTER_FMT="t6-current-client-high-value-direct-provider-clusters-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m):
    if not c: raise SystemExit(m)

GATES={
 "0x0076ae9c":("8b7d08","mov","edi, dword ptr [ebp + 8]"),
 "0x0076ae9f":("8bb77c070000","mov","esi, dword ptr [edi + 0x77c]"),
 "0x0076aeae":("81c6e0010000","add","esi, 0x1e0"),
 "0x0076af37":("8d9e28020000","lea","ebx, [esi + 0x228]"),
 "0x0076b023":("b901000000","mov","ecx, 1"),
 "0x0076b10d":("f30f104bfc","movss","xmm1, dword ptr [ebx - 4]"),
 "0x0076b112":("f30f1013","movss","xmm2, dword ptr [ebx]"),
 "0x0076b116":("f30f105b04","movss","xmm3, dword ptr [ebx + 4]"),
 "0x0076b11b":("f30f1063f8","movss","xmm4, dword ptr [ebx - 8]"),
 "0x0076b120":("66010d3284a303","add","word ptr [0x3a38432], cx"),
 "0x0076b127":("f30f1125907da303","movss","dword ptr [0x3a37d90], xmm4"),
 "0x0076b12f":("f30f110d947da303","movss","dword ptr [0x3a37d94], xmm1"),
 "0x0076b137":("f30f1115987da303","movss","dword ptr [0x3a37d98], xmm2"),
 "0x0076b13f":("f30f111d9c7da303","movss","dword ptr [0x3a37d9c], xmm3"),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--function",type=Path,required=True)
    ap.add_argument("--clusters",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    fn=load(a.function);cl=load(a.clusters)
    req(fn.get("format")==FUNC_FMT,"function format drift")
    req(cl.get("format")==CLUSTER_FMT,"cluster format drift")
    req(fn.get("client",{}).get("sha256")==CLIENT_SHA,"client SHA drift")
    ins={x["address"]:x for x in fn["function"]["instructions"]}
    for addr,(b,mn,op) in GATES.items():
        r=ins.get(addr);req(r is not None,f"missing gate {addr}")
        req((r["bytes"],r["mnemonic"],r["opStr"])==(b,mn,op),f"gate drift {addr}: {r}")
    # ECX must remain the literal 1 for the version increment path.
    ecx_rows=[x for x in fn["function"]["instructions"]
              if 0x0076b023<=int(x["address"],16)<=0x0076b120 and ("ecx" in x["opStr"] or "cx" in x["opStr"])]
    req(ecx_rows[0]["address"]=="0x0076b023" and ecx_rows[0]["opStr"]=="ecx, 1","version scalar setup drift")
    req(all(x["mnemonic"]=="add" and x["opStr"].endswith(", cx") for x in ecx_rows[1:]),"ECX modified before scriptVector0 version increment")

    rows=[x for x in cl.get("rows",[]) if x.get("accessor")=="scriptVector0"]
    req(len(rows)==1,"scriptVector0 cluster row drift")
    cr=rows[0]
    req(int(cr["enumValue"])==169 and int(cr["totalOccurrences"])==160,"scriptVector0 denominator drift")
    req(cr["fieldXrefCounts"]=={"value[0]":1,"value[1]":1,"value[2]":1,"value[3]":1,"version":1},
        "scriptVector0 field xref closure drift")

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact function dataflow + exact enum-169 direct destination cluster",
      "client":fn["client"],
      "runtimeInput":{
        "accessor":"scriptVector0","enumSymbol":"CONST_SRC_CODE_GENERIC_PARAM0","enumValue":169,
        "retainedSpecialOccurrences":160,"sourceClass":"constant","updateFrequency":cr.get("updateFrequency"),
        "valueVas":["0x03a37d90","0x03a37d94","0x03a37d98","0x03a37d9c"],
        "versionVa":"0x03a38432",
      },
      "sourceContract":{
        "functionArgument0Register":"edi","argumentLoadVa":"0x0076ae9c",
        "pointerFieldOffset":0x77C,
        "derivedBase":"EBX = *(arg0+0x77C) + 0x1E0 + 0x228 = *(arg0+0x77C) + 0x408",
        "vectorBaseRelativeToPointerFieldTarget":0x400,
        "laneSourceOffsets":[0x400,0x404,0x408,0x40C],
        "humanSemanticNameOfSourceBlock":"unresolved",
      },
      "providerFormula":{
        "lane0":"float32(*(*(arg0+0x77C)+0x400))",
        "lane1":"float32(*(*(arg0+0x77C)+0x404))",
        "lane2":"float32(*(*(arg0+0x77C)+0x408))",
        "lane3":"float32(*(*(arg0+0x77C)+0x40C))",
        "version":"uint16 version slot at 0x03A38432 += 1 before lane stores",
      },
      "sources":{
        "providerFunction":{"path":str(a.function),"sha256":sha(a.function),"format":fn["format"]},
        "directProviderClusters":{"path":str(a.clusters),"sha256":sha(a.clusters),"format":cl["format"]},
      },
      "summary":{
        "enumValue":169,"sourcePointerChainClosed":True,"laneFormulaClosed":True,
        "versionUpdateClosed":True,"currentClientProviderClosed":True,
        "retainedSpecialOccurrenceCount":160,"historicalRetailEquivalent":False,
      },
      "proofBoundary":"Closes SHA-classified current-client scriptVector0 provider dataflow exactly: the function argument-0 object owns a pointer at +0x77C, and four consecutive float32 lanes at pointee offsets +0x400..+0x40C are copied lane-for-lane into enum-169 storage with an exact +1 version increment. The human semantic name of that pointee block and historical-retail executable equivalence remain unproven; no values are inferred or substituted."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
