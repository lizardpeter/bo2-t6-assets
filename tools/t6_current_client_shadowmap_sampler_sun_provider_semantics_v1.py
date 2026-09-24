#!/usr/bin/env python3
"""Fail-closed current-client provider semantics for shadowmapSamplerSun (slot 6).

Joins five independently frozen proofs:
- retained enum/accessor denominator;
- generic code-image/sampler-state array geometry;
- exact slot-6 image writer mechanics;
- sole parent caller argument setup;
- complete slot-6 sampler-state writer denominator.

The resource is intentionally described by exact address/offset arithmetic rather
than guessed human names.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-shadowmap-sampler-sun-provider-semantics-v1"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
ARRAY_FMT="t6-current-client-code-pixel-sampler-array-semantics-v1"
IMAGE_FMT="t6-current-client-shadowmap-sun-image-writer-v1"
STACK_FMT="t6-current-client-shadowmap-sun-image-caller-stack-provenance-v1"
PARENT_FMT="t6-current-client-shadowmap-sun-parent-callers-v1"
STATE_FMT="t6-current-client-shadowmap-sampler-sun-all-writer-state-byte-semantics-v1"
ACC="shadowmapSamplerSun"
ENUM=6

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m):
    if not c: raise SystemExit(m)
def gate(rows,addr,mn,op):
    by={r["address"]:r for r in rows}
    r=by.get(addr);req(r is not None,f"missing instruction {addr}")
    req((r["mnemonic"],r["opStr"])==(mn,op),f"instruction drift {addr}: {r}")
    return r

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--array",type=Path,required=True)
    ap.add_argument("--image",type=Path,required=True)
    ap.add_argument("--stack",type=Path,required=True)
    ap.add_argument("--parent",type=Path,required=True)
    ap.add_argument("--state",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    den,arr,img,stk,par,state=map(load,[a.denominator,a.array,a.image,a.stack,a.parent,a.state])
    req(den.get("format")==DEN_FMT,"denominator format drift")
    req(arr.get("format")==ARRAY_FMT,"array format drift")
    req(img.get("format")==IMAGE_FMT,"image format drift")
    req(stk.get("format")==STACK_FMT,"stack format drift")
    req(par.get("format")==PARENT_FMT,"parent format drift")
    req(state.get("format")==STATE_FMT,"state format drift")

    rows=[x for x in den.get("rows",[]) if x.get("accessor")==ACC]
    req(len(rows)==1,"shadowmapSamplerSun denominator row drift")
    d=rows[0]
    req(int(d["enumValue"])==ENUM and int(d["totalOccurrences"])==16,"shadowmapSamplerSun identity/count drift")
    req(d["sourceClass"]=="sampler" and d["updateFrequency"]=="RARELY","shadowmapSamplerSun class/frequency drift")
    req(arr.get("summary",{}).get("arrayContractClosed") is True,"generic sampler array not closed")
    req(arr["summary"]["codeImagesBaseOffset"]==0x1530 and arr["summary"]["codeImageSamplerStatesBaseOffset"]==0x160c,"generic sampler array offsets drift")
    req(img.get("summary",{}).get("slot6ImageArgumentClosed") is True and img.get("summary",{}).get("sourceStateBaseClosed") is True,"slot6 image writer not closed")
    req(stk.get("summary",{}).get("writerCallClosed") is True,"slot6 caller stack proof not closed")
    req(par.get("summary",{}).get("directCallerCount")==1,"sun source-state builder caller denominator drift")
    req(state.get("summary",{}).get("writerDenominatorComplete") is True,"slot6 state writer denominator incomplete")
    req(state["summary"].get("currentClientSamplerStateByteClosed") is True and state["summary"].get("finalSamplerStateByteValue")==0,"slot6 state byte drift")

    # Inner source-state builder: with EBP already pushed, [esp+0x1578] is outer
    # arg4. After EBP+EBX+ESI+EDI+saved-EAX pushes, [esp+0x1584] is outer arg3.
    # The second argument to 0x009A7A30 is exactly arg3+arg4 and the proven writer
    # stores that unchanged to codeImages[6].
    ins=stk["instructions"]
    gate(ins,"0x009af9bd","mov","edx, dword ptr [esp + 0x1578]")
    gate(ins,"0x009af9c8","mov","eax, dword ptr [esp + 0x1584]")
    gate(ins,"0x009af9cf","lea","ecx, [eax + edx]")
    gate(ins,"0x009af9d2","push","ecx")
    gate(ins,"0x009af9d3","push","eax")
    gate(ins,"0x009af9d8","call","0x9a7a30")

    # Sole outer caller. Reverse cdecl pushes establish:
    # arg3 = address-derived resource base from 0x00BFE3E8 + loop offset;
    # arg4 = uint32 at 0x00C20040 + loop offset.
    caller=par["callers"][0]
    before=caller["contextBefore"]
    gate(before,"0x006d7e59","mov","ecx, dword ptr [esi + 0xbfe3e8]")
    gate(before,"0x006d7e5f","lea","ecx, [ecx + esi + 0xbfe3e8]")
    gate(before,"0x006d7e83","mov","eax, dword ptr [esi + 0xc20040]")
    gate(before,"0x006d7e89","push","eax")
    gate(before,"0x006d7e8a","push","ecx")
    gate(before,"0x006d7e8e","push","edi")
    gate(before,"0x006d7e8f","push","ecx")
    req(caller["call"]["address"]=="0x006d7e90" and caller["call"]["opStr"]=="0x9af970","parent call drift")

    runtime={
      "accessor":ACC,
      "enumSymbol":d["enumSymbol"],
      "enumValue":ENUM,
      "retainedSpecialOccurrences":int(d["totalOccurrences"]),
      "sourceClass":"sampler",
      "updateFrequency":d["updateFrequency"],
      "provider":{
        "codeImageSlot":{"formula":"source + 0x1530 + 6*4","offset":0x1548,"writerVa":"0x009a7a48"},
        "samplerStateSlot":{"formula":"source + 0x160C + 6","offset":0x1612,"exactByte":0},
        "sourceStateBuilder":{"functionStartVa":"0x009af970","soleDirectCallerVa":"0x006d7e90"},
        "imageSource":{
          "outerArg3":"uint32([loopOffset + 0x00BFE3E8]) + loopOffset + 0x00BFE3E8",
          "outerArg4":"uint32([loopOffset + 0x00C20040])",
          "imagePointer":"outerArg3 + outerArg4",
          "loopOffset":"ESI in sole caller; initialized 0 and advanced by 4 until 0x238",
        },
      },
    }
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client generic code-sampler contract + exact slot-6 writer/caller resource provenance + complete state-byte writer denominator",
      "client":img["client"],
      "runtimeInput":runtime,
      "sources":{
        "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator),"format":den["format"]},
        "array":{"path":str(a.array),"sha256":sha(a.array),"format":arr["format"]},
        "imageWriter":{"path":str(a.image),"sha256":sha(a.image),"format":img["format"]},
        "callerStack":{"path":str(a.stack),"sha256":sha(a.stack),"format":stk["format"]},
        "parentCaller":{"path":str(a.parent),"sha256":sha(a.parent),"format":par["format"]},
        "stateByte":{"path":str(a.state),"sha256":sha(a.state),"format":state["format"]},
      },
      "summary":{
        "currentClientProviderClosed":True,
        "enumValue":ENUM,
        "slot6ImageProviderClosed":True,
        "slot6SamplerStateByteClosed":True,
        "retainedSpecialOccurrenceCount":16,
        "historicalRetailEquivalent":False,
      },
      "proofBoundary":"Closes SHA-classified current-client shadowmapSamplerSun provider mechanics for retained-special replay: exact code-sampler enum/slot, generic array offsets, sole source-state builder caller, exact slot-6 image pointer arithmetic, and the complete decoded sampler-state writer denominator (byte 0) are proven. The human resource name behind the address-derived tables, byte-to-graphics-API sampler interpretation, historical-retail executable equivalence, universal frame resource lifetime, and framebuffer equivalence remain unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__":main()
