#!/usr/bin/env python3
"""Fail-closed current-client semantics for the generic RC_SET_CUSTOM_CONSTANT backend handler.

This closes the backend command-record -> generic code-constant storage contract.
It deliberately does not claim which individual code-constant enums are emitted
by front-end command producers; that usage join is a separate proof gate.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-rc-set-custom-constant-handler-semantics-v1"
TABLE_FMT="t6-current-client-render-command-table-locator-v1"
PROBE_FMT="t6-current-client-custom-constant-and-material-color-handlers-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m):
    if not c: raise SystemExit(m)

GATES={
 "0x00745b79":("8b7c240c","mov","edi, dword ptr [esp + 0xc]"),
 "0x00745b7d":("8b37","mov","esi, dword ptr [edi]"),
 "0x00745b86":("8b4e04","mov","ecx, dword ptr [esi + 4]"),
 "0x00745b89":("d94608","fld","dword ptr [esi + 8]"),
 "0x00745b8c":("8bc1","mov","eax, ecx"),
 "0x00745b8e":("c1e004","shl","eax, 4"),
 "0x00745b91":("050073a303","add","eax, 0x3a37300"),
 "0x00745b96":("d918","fstp","dword ptr [eax]"),
 "0x00745b98":("d9460c","fld","dword ptr [esi + 0xc]"),
 "0x00745b9b":("d95804","fstp","dword ptr [eax + 4]"),
 "0x00745b9e":("d94610","fld","dword ptr [esi + 0x10]"),
 "0x00745ba1":("d95808","fstp","dword ptr [eax + 8]"),
 "0x00745ba4":("d94614","fld","dword ptr [esi + 0x14]"),
 "0x00745ba7":("d9580c","fstp","dword ptr [eax + 0xc]"),
 "0x00745baa":("66ff044de082a303","inc","word ptr [ecx*2 + 0x3a382e0]"),
 "0x00745bb2":("8b07","mov","eax, dword ptr [edi]"),
 "0x00745bb4":("0fb708","movzx","ecx, word ptr [eax]"),
 "0x00745bb7":("03c8","add","ecx, eax"),
 "0x00745bb9":("890f","mov","dword ptr [edi], ecx"),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--command-table",type=Path,required=True)
    ap.add_argument("--handler-probe",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    table=load(a.command_table);probe=load(a.handler_probe)
    req(table.get("format")==TABLE_FMT,"command table format drift")
    req(probe.get("format")==PROBE_FMT,"handler probe format drift")
    for d,n in ((table,"table"),(probe,"probe")):
        req(d.get("client",{}).get("sha256")==CLIENT_SHA,f"{n}: client SHA drift")
    candidates=table.get("functionTableCandidates",[])
    req(len(candidates)==1,"function table candidate count drift")
    handlers=candidates[0].get("handlers",[])
    row=[x for x in handlers if int(x.get("index",-1))==1]
    req(len(row)==1,"command index 1 row drift")
    req(row[0].get("name")=="RC_SET_CUSTOM_CONSTANT","command name drift")
    req(row[0].get("va")=="0x00745b70","handler address drift")
    ranges={x["label"]:x for x in probe.get("ranges",[])}
    h=ranges.get("customConstant");req(h is not None,"customConstant probe range absent")
    req(h.get("startVa")=="0x00745b70" and h.get("endVaExclusive")=="0x00745bc0","handler range drift")
    ins={x["address"]:x for x in h["instructions"]}
    for addr,(b,mn,op) in GATES.items():
        r=ins.get(addr);req(r is not None,f"missing gate {addr}")
        req((r["bytes"],r["mnemonic"],r["opStr"])==(b,mn,op),f"gate drift {addr}: {r}")
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact render-command table + exact RC_SET_CUSTOM_CONSTANT handler dataflow",
      "client":probe["client"],
      "command":{
        "id":1,"name":"RC_SET_CUSTOM_CONSTANT","handlerVa":"0x00745b70",
        "recordLayout":{
          "byteCount":{"offset":0,"type":"uint16","meaning":"record byte size used to advance execState->cmd"},
          "enum":{"offset":4,"type":"uint32","meaning":"T6 code-constant enum index"},
          "value0":{"offset":8,"type":"float32"},
          "value1":{"offset":12,"type":"float32"},
          "value2":{"offset":16,"type":"float32"},
          "value3":{"offset":20,"type":"float32"},
        },
      },
      "storageContract":{
        "valueBaseVa":"0x03a37300","valueStridePerEnum":16,
        "versionBaseVa":"0x03a382e0","versionStridePerEnum":2,
        "formula":{
          "value[0]":"float32(record+8) -> *(0x03A37300 + enum*16 + 0)",
          "value[1]":"float32(record+12) -> *(0x03A37300 + enum*16 + 4)",
          "value[2]":"float32(record+16) -> *(0x03A37300 + enum*16 + 8)",
          "value[3]":"float32(record+20) -> *(0x03A37300 + enum*16 + 12)",
          "version":"uint16 *(0x03A382E0 + enum*2) += 1",
          "advance":"execState->cmd += uint16(record+0)",
        },
      },
      "sources":{
        "commandTable":{"path":str(a.command_table),"sha256":sha(a.command_table),"format":table["format"]},
        "handlerProbe":{"path":str(a.handler_probe),"sha256":sha(a.handler_probe),"format":probe["format"]},
      },
      "summary":{
        "commandId":1,"handlerAddressClosed":True,"recordLayoutClosed":True,
        "genericValueStorageClosed":True,"genericVersionStorageClosed":True,
        "commandAdvanceClosed":True,"currentClientBackendHandlerClosed":True,
        "individualEnumProducerUsageClosed":False,"historicalRetailEquivalent":False,
      },
      "proofBoundary":"Closes the SHA-classified current-client backend semantics of RC_SET_CUSTOM_CONSTANT exactly. It proves how any received command enum/value record updates generic code-constant storage and versioning. It does not prove that a particular retained-special accessor is actually emitted by a front-end command producer; individual enum usage must be joined independently before that accessor is promoted to provider-closed. Historical-retail executable equivalence is also unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
