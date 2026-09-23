#!/usr/bin/env python3
"""Promote exact current-client render-target table geometry from RC_RESOLVE_COMPOSITE.

Authority:
- exact current-client render-command table names handler 0x00745d30 RC_RESOLVE_COMPOSITE;
- exact handler bytes derive a 20-byte indexed record table at 0x03A26720;
- handler reads uint16 +0x0C/+0x0E from the selected record and writes source-state
  width/height fields before invoking a command callback with the first dword of
  fixed record 25 at 0x03A26914.

Pinned T6 source lineage is vocabulary/semantic corroboration only. All promoted
addresses and arithmetic come from current-client bytes.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-render-target-table-semantics-v1"
PROBE_FMT="t6-current-client-render-target-handler-probe-v1"
TABLE_FMT="t6-current-client-render-command-table-locator-v1"
SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
BASE=0x03A26720
STRIDE=20
ENTRY25=BASE+25*STRIDE
ENTRY8=BASE+8*STRIDE

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--probe",type=Path,required=True)
    ap.add_argument("--command-table",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    p=load(a.probe);t=load(a.command_table)
    req(p.get("format")==PROBE_FMT,"probe format drift")
    req(t.get("format")==TABLE_FMT,"command table format drift")
    req(p["client"]["sha256"]==SHA and t["client"]["sha256"]==SHA,"client SHA drift")
    tabs=t.get("functionTableCandidates",[])
    matches=[]
    for tb in tabs:
      h={int(x["index"]):x for x in tb.get("handlers",[])}
      if h.get(9,{}).get("name")=="RC_RESOLVE_COMPOSITE" and h.get(9,{}).get("va")=="0x00745d30":
        matches.append(tb)
    req(len(matches)==1,f"resolve handler table matches={len(matches)}")
    r={x["label"]:x for x in p["ranges"]}["resolveComposite"]
    by={int(x["address"],16):x for x in r["instructions"]}
    gates={
      0x00745d46:("mov","cl, byte ptr [0x35e6024]"),
      0x00745d51:("movzx","eax, cl"),
      0x00745d54:("mov","dl, byte ptr [eax + 0xd276e8]"),
      0x00745d5a:("lea","eax, [eax + eax*4]"),
      0x00745d5d:("lea","eax, [eax*4 + 0x3a26720]"),
      0x00745d64:("mov","byte ptr [0x3a38564], dl"),
      0x00745d6a:("movzx","edx, word ptr [eax + 0xc]"),
      0x00745d6e:("movzx","eax, word ptr [eax + 0xe]"),
      0x00745d72:("mov","dword ptr [0x3a38568], edx"),
      0x00745d7e:("mov","dword ptr [0x3a3856c], eax"),
      0x00745d93:("mov","edx, dword ptr [0x3a26914]"),
      0x00745d99:("mov","eax, dword ptr [edi + 4]"),
      0x00745d9f:("push","edx"),
      0x00745da0:("call","eax"),
    }
    for va,(mn,op) in gates.items():
      x=by.get(va);req(x is not None and x["mnemonic"]==mn and x["opStr"]==op,f"gate drift 0x{va:x}: {x}")
    req(ENTRY25==0x03A26914,f"entry25 arithmetic drift 0x{ENTRY25:x}")
    req(ENTRY8==0x03A267C0,f"entry8 arithmetic drift 0x{ENTRY8:x}")
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client RC_RESOLVE_COMPOSITE exact handler dataflow",
      "client":p["client"],
      "renderCommand":{"index":9,"name":"RC_RESOLVE_COMPOSITE","handlerVa":"0x00745d30"},
      "recordTable":{
        "baseVa":f"0x{BASE:08x}","recordStrideBytes":STRIDE,"recordCountNotProvenHere":True,
        "selectedRecordIndexPipeline":"frameBuffer byte -> byte lookup table -> index * 20",
        "selectedRecordWidthOffset":12,"selectedRecordHeightOffset":14,
        "selectedRecordWidthType":"uint16","selectedRecordHeightType":"uint16",
        "selectedRecordAuxByteSource":"byte lookup result",
        "fixedRecord25FirstDwordVa":f"0x{ENTRY25:08x}",
        "derivedRecord8FirstDwordVa":f"0x{ENTRY8:08x}",
      },
      "sourceStateWrites":{
        "auxByteVa":"0x03A38564","widthDwordVa":"0x03A38568","heightDwordVa":"0x03A3856C"
      },
      "callback":{
        "commandCallbackPointerOffset":4,
        "argument":"first dword of fixed table record 25",
        "argumentVa":f"0x{ENTRY25:08x}"
      },
      "summary":{
        "recordStrideBytes":STRIDE,"tableBaseExact":True,"widthHeightOffsetsExact":True,
        "record25FirstDwordCallbackExact":True,"record8FirstDwordAddressDerivedExactly":True
      },
      "sources":{
        "handlerProbe":{"path":str(a.probe),"sha256":sha(a.probe)},
        "renderCommandTable":{"path":str(a.command_table),"sha256":sha(a.command_table)}
      },
      "proofBoundary":"Closes current-client table geometry used by the exact RC_RESOLVE_COMPOSITE handler: base, 20-byte stride, selected-record uint16 width/height offsets, source-state writes, and fixed record-25 first-dword callback argument. The first dword is structurally the callback resource field in this handler; calling it GfxRenderTarget.image uses T6 source-lineage vocabulary and is not historical-retail proof. Record-8 address is exact arithmetic from the current-client table, but its float-Z role remains unpromoted until an exact consumer closes that relation."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
