#!/usr/bin/env python3
"""Fail-closed current-client provider semantics for CONST_SRC_CODE_RENDER_TARGET_SIZE."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-render-target-size-provider-semantics-v1"
FUNC_FMT="t6-current-client-render-target-size-provider-function-v1"
TABLE_FMT="t6-current-client-render-target-table-semantics-v1"
CLUSTER_FMT="t6-current-client-high-value-direct-provider-clusters-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m):
    if not c: raise SystemExit(m)

GATES={
 "0x0076aff2":("0fb7055467a203","movzx","eax, word ptr [0x3a26754]"),
 "0x0076aff9":("0fb7155667a203","movzx","edx, word ptr [0x3a26756]"),
 "0x0076b010":("0f57c0","xorps","xmm0, xmm0"),
 "0x0076b07b":("66010d0283a303","add","word ptr [0x3a38302], cx"),
 "0x0076b0a2":("f30f11051874a303","movss","dword ptr [0x3a37418], xmm0"),
 "0x0076b0aa":("f30f11051c74a303","movss","dword ptr [0x3a3741c], xmm0"),
 "0x0076b0b5":("f30f2ac8","cvtsi2ss","xmm1, eax"),
 "0x0076b0b9":("f30f110d1074a303","movss","dword ptr [0x3a37410], xmm1"),
 "0x0076b0c4":("f30f2aca","cvtsi2ss","xmm1, edx"),
 "0x0076b0c8":("f30f110d1474a303","movss","dword ptr [0x3a37414], xmm1"),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--function",type=Path,required=True)
    ap.add_argument("--table",type=Path,required=True)
    ap.add_argument("--clusters",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    fn=load(a.function);tb=load(a.table);cl=load(a.clusters)
    req(fn.get("format")==FUNC_FMT,"function format drift")
    req(tb.get("format")==TABLE_FMT,"table format drift")
    req(cl.get("format")==CLUSTER_FMT,"cluster format drift")
    for d,n in ((fn,"function"),(tb,"table")):
        req(d.get("client",{}).get("sha256")==CLIENT_SHA,f"{n}: client SHA drift")

    rt=tb["recordTable"]
    base=int(rt["baseVa"],16);stride=int(rt["recordStrideBytes"])
    woff=int(rt["selectedRecordWidthOffset"]);hoff=int(rt["selectedRecordHeightOffset"])
    req(stride==20 and woff==12 and hoff==14,"render-target table geometry drift")
    record_index=2
    width_va=base+record_index*stride+woff
    height_va=base+record_index*stride+hoff
    req(width_va==0x03A26754 and height_va==0x03A26756,
        f"record2 addresses drift width=0x{width_va:x} height=0x{height_va:x}")

    ins={x["address"]:x for x in fn["function"]["instructions"]}
    for addr,(b,mn,op) in GATES.items():
        r=ins.get(addr);req(r is not None,f"missing gate {addr}")
        req((r["bytes"],r["mnemonic"],r["opStr"])==(b,mn,op),f"gate drift {addr}: {r}")

    rows=[x for x in cl.get("rows",[]) if x.get("accessor")=="renderTargetSize"]
    req(len(rows)==1,"renderTargetSize cluster row drift")
    cr=rows[0]
    req(int(cr.get("enumValue",-1))==17,"enum drift")
    req(int(cr.get("totalOccurrences",-1))==23,"retained occurrence drift")
    req(cr.get("fieldXrefCounts")=={"value[0]":1,"value[1]":1,"value[2]":1,"value[3]":1,"version":1},
        "direct field xref closure drift")

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact provider function + exact render-target table geometry + exact enum-17 direct destinations",
      "client":fn["client"],
      "runtimeInput":{
        "accessor":"renderTargetSize","enumSymbol":"CONST_SRC_CODE_RENDER_TARGET_SIZE","enumValue":17,
        "retainedSpecialOccurrences":23,"sourceClass":"constant","updateFrequency":cr.get("updateFrequency"),
        "valueVas":["0x03a37410","0x03a37414","0x03a37418","0x03a3741c"],
        "versionVa":"0x03a38302",
      },
      "source":{
        "renderTargetTableBaseVa":rt["baseVa"],"recordStrideBytes":stride,"recordIndex":record_index,
        "widthFieldOffset":woff,"heightFieldOffset":hoff,
        "widthSourceVa":f"0x{width_va:08x}","heightSourceVa":f"0x{height_va:08x}",
        "widthType":"uint16","heightType":"uint16",
      },
      "providerFormula":{
        "lane0":"float32(uint16(renderTargetTable[2].width))",
        "lane1":"float32(uint16(renderTargetTable[2].height))",
        "lane2":"0.0f","lane3":"0.0f",
        "version":"uint16 version slot at 0x03A38302 increments in the same exact writer cluster",
      },
      "sources":{
        "providerFunction":{"path":str(a.function),"sha256":sha(a.function),"format":fn["format"]},
        "renderTargetTable":{"path":str(a.table),"sha256":sha(a.table),"format":tb["format"]},
        "directProviderClusters":{"path":str(a.clusters),"sha256":sha(a.clusters),"format":cl["format"]},
      },
      "summary":{
        "enumValue":17,"renderTargetRecordIndex":2,"tableGeometryClosed":True,
        "sourceFieldsClosed":True,"laneFormulaClosed":True,"versionUpdateClosed":True,
        "currentClientProviderClosed":True,"retainedSpecialOccurrenceCount":23,
        "historicalRetailEquivalent":False,
      },
      "proofBoundary":"Closes SHA-classified current-client renderTargetSize provider semantics exactly: enum-17 lanes 0/1 are float conversions of uint16 width/height from fixed render-target table record 2, lanes 2/3 are exact zero, and the version slot increments in the same writer cluster. It does not claim historical-retail executable equivalence, framebuffer identity, or that record 2 has a human render-target name beyond its exact table index and field geometry."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
