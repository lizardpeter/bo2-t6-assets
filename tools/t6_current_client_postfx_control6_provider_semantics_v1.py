#!/usr/bin/env python3
"""Fail-closed current-client provider semantics for CONST_SRC_CODE_POSTFX_CONTROL6."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-postfx-control6-provider-semantics-v1"
FUNC_FMT="t6-current-client-postfx-control6-provider-function-v1"
CLUSTER_FMT="t6-current-client-special-constant-direct-write-clusters-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m):
    if not c: raise SystemExit(m)

CALLEE_GATES={
 "0x007685b0":("f30f10442460","movss","xmm0, dword ptr [esp + 0x60]"),
 "0x007685b6":("f30f104c2470","movss","xmm1, dword ptr [esp + 0x70]"),
 "0x007685c2":("f30f59c8","mulss","xmm1, xmm0"),
 "0x007685c6":("0f28d0","movaps","xmm2, xmm0"),
 "0x007685c9":("f30f5cd1","subss","xmm2, xmm1"),
 "0x007685cd":("f30f108c2480000000","movss","xmm1, dword ptr [esp + 0x80]"),
 "0x007685d6":("f30f1115107aa303","movss","dword ptr [0x3a37a10], xmm2"),
 "0x007685de":("f30f10942490000000","movss","xmm2, dword ptr [esp + 0x90]"),
 "0x007685e7":("f30f59d1","mulss","xmm2, xmm1"),
 "0x007685eb":("0f28d9","movaps","xmm3, xmm1"),
 "0x007685ee":("f30f5cda","subss","xmm3, xmm2"),
 "0x007685f8":("b801000000","mov","eax, 1"),
 "0x007685fd":("660105c283a303","add","word ptr [0x3a383c2], ax"),
 "0x0076860a":("f30f1105187aa303","movss","dword ptr [0x3a37a18], xmm0"),
 "0x0076861a":("f30f111d147aa303","movss","dword ptr [0x3a37a14], xmm3"),
 "0x00768622":("f30f110d1c7aa303","movss","dword ptr [0x3a37a1c], xmm1"),
}
CALLER_GATES={
 "0x00769974":("81ec90000000","sub","esp, 0x90"),
 "0x0076997a":("b924000000","mov","ecx, 0x24"),
 "0x0076997f":("8bfc","mov","edi, esp"),
 "0x00769981":("f3a5","rep movsd","dword ptr es:[edi], dword ptr [esi]"),
 "0x00769983":("e828ecffff","call","0x7685b0"),
}

def gate(rows, expected, label):
    by={r["address"]:r for r in rows}
    for addr,(b,mn,op) in expected.items():
        r=by.get(addr);req(r is not None,f"{label}: missing {addr}")
        req((r["bytes"],r["mnemonic"],r["opStr"])==(b,mn,op),f"{label}: drift {addr}: {r}")

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
    req(fn.get("summary",{}).get("callerCount")==1,"postFxControl6 caller count drift")
    gate(fn["function"]["instructions"],CALLEE_GATES,"callee")
    caller=fn["callers"][0]
    gate(caller["contextBefore"]+[caller["call"]],CALLER_GATES,"caller")
    req(caller["call"]["address"]=="0x00769983","unique caller address drift")

    rows=[x for x in cl.get("rows",[]) if x.get("accessor")=="postFxControl6"]
    req(len(rows)==1,"postFxControl6 cluster row drift")
    cr=rows[0]
    req(int(cr["enumValue"])==113 and int(cr["totalOccurrences"])==22,"postFxControl6 denominator drift")
    req(cr["fieldXrefCounts"]=={"value[0]":1,"value[1]":1,"value[2]":1,"value[3]":1,"version":1},
        "postFxControl6 field xref drift")

    # Caller copies 0x24 dwords = 0x90 bytes source ESI -> caller ESP.
    # CALL pushes a 4-byte return address, so callee [ESP+N] maps to copied source[N-4].
    source_offsets={"A":0x60-4,"B":0x70-4,"C":0x80-4,"D":0x90-4}
    req(source_offsets=={"A":0x5C,"B":0x6C,"C":0x7C,"D":0x8C},"stack/source offset derivation drift")

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact unique caller copy contract + exact postFxControl6 arithmetic/write dataflow",
      "client":fn["client"],
      "runtimeInput":{
        "accessor":"postFxControl6","enumSymbol":"CONST_SRC_CODE_POSTFX_CONTROL6","enumValue":113,
        "retainedSpecialOccurrences":22,"sourceClass":"constant",
        "valueVas":["0x03a37a10","0x03a37a14","0x03a37a18","0x03a37a1c"],
        "versionVa":"0x03a383c2",
      },
      "sourceRecordContract":{
        "uniqueCallerVa":"0x00769983","sourceRegisterBeforeRepMovsd":"esi",
        "copyDwordCount":0x24,"copyBytes":0x90,
        "sourceOffsets":source_offsets,
        "physicalSemanticName":"unresolved",
      },
      "providerFormula":{
        "A":"float32(sourceRecord+0x5C)","B":"float32(sourceRecord+0x6C)",
        "C":"float32(sourceRecord+0x7C)","D":"float32(sourceRecord+0x8C)",
        "lane0":"A - A*B = A*(1-B)",
        "lane1":"C - C*D = C*(1-D)",
        "lane2":"A","lane3":"C",
        "version":"uint16 version slot at 0x03A383C2 += 1",
      },
      "sources":{
        "providerFunction":{"path":str(a.function),"sha256":sha(a.function),"format":fn["format"]},
        "directWriteClusters":{"path":str(a.clusters),"sha256":sha(a.clusters),"format":cl["format"]},
      },
      "summary":{
        "enumValue":113,"uniqueCallerClosed":True,"sourceCopyContractClosed":True,
        "laneFormulaClosed":True,"versionUpdateClosed":True,"currentClientProviderClosed":True,
        "retainedSpecialOccurrenceCount":22,"historicalRetailEquivalent":False,
      },
      "proofBoundary":"Closes SHA-classified current-client postFxControl6 provider dataflow exactly. The sole caller copies a 0x90-byte source record to the callee stack; exact source offsets +0x5C/+0x6C/+0x7C/+0x8C produce [A*(1-B), C*(1-D), A, C] with an exact +1 version update. The human semantic names/units of A/B/C/D and historical-retail executable equivalence remain unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
