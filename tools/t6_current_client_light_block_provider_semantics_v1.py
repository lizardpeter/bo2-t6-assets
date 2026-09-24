#!/usr/bin/env python3
"""Close the SHA-classified current-client provider for the 12-light constant block.

Composes exact independent evidence:
- retained-special denominator identity/occurrence counts;
- current-client constVersions base formula;
- exact light version-slot writer census;
- exact 0x00786210 writer bytes;
- exact single direct caller and live-in register setup.

The proof intentionally describes the selected 0x160-byte EDI source as a
runtime light record by machine role, retaining raw offsets instead of assigning
unproven higher-level field names.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-current-client-light-block-provider-semantics-v1"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
GETTER_FMT="t6-current-client-code-matrix-getter-semantics-v1"
XREF_FMT="t6-current-client-light-const-version-writer-xrefs-v1"
WRITER_FMT="t6-current-client-light-writer-786210-probe-v1"
CALLER_FMT="t6-current-client-light-writer-786210-callers-v1"

EXPECTED={
 "lightPosition":0,"lightDiffuse":1,"lightSpotDir":2,"lightSpotFactors":3,
 "lightFallOffA":5,"lightFallOffB":6,"lightSpotMatrix0":7,"lightSpotMatrix1":8,
 "lightSpotMatrix2":9,"lightSpotAABB":11,"lightConeControl1":12,
 "lightSpotCookieSlideControl":14,
}
WRITER_SHA="b8b815456fe80bdf35711972f02aff7b0151fb933c950be468f4fa0d4a3d2d0b"
VALUE_BASE=0x800
VERSION_BASE=0x17e0

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def load(p:Path):return json.loads(p.read_text())
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def imap(rows):return {int(x["address"],16):x for x in rows}
def gate(m,va,mn,op=None):
    x=m.get(va);req(x is not None,f"missing instruction 0x{va:08x}")
    req(x["mnemonic"]==mn,f"0x{va:08x}: {x['mnemonic']} != {mn}")
    if op is not None:req(x["opStr"]==op,f"0x{va:08x}: {x['opStr']} != {op}")
    return x
def store_offset(op:str):
    m=re.search(r"\[esi \+ 0x([0-9a-f]+)\]",op,re.I)
    return int(m.group(1),16) if m else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--getter",type=Path,required=True)
    ap.add_argument("--version-xrefs",type=Path,required=True)
    ap.add_argument("--writer",type=Path,required=True)
    ap.add_argument("--callers",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    den,getter,xrefs,writer,callers=map(load,(a.denominator,a.getter,a.version_xrefs,a.writer,a.callers))
    req(den.get("format")==DEN_FMT,"denominator format drift")
    req(getter.get("format")==GETTER_FMT,"getter format drift")
    req(xrefs.get("format")==XREF_FMT,"version-xref format drift")
    req(writer.get("format")==WRITER_FMT,"writer format drift")
    req(callers.get("format")==CALLER_FMT,"caller format drift")

    req(getter["storage"]["constVersionsBaseOffset"]==VERSION_BASE,"constVersions base drift")
    req(writer["function"]["startVa"]=="0x00786210","writer start drift")
    req(writer["function"]["endVaExclusive"]=="0x00786960","writer end drift")
    req(writer["function"]["sha256"]==WRITER_SHA,"writer SHA drift")
    ins=writer["function"]["instructions"];wm=imap(ins)

    # Exact writer/caller machine anchors.
    gate(wm,0x00786210,"push","ebp")
    gate(wm,0x00786211,"mov","ebp, esp")
    gate(wm,0x00786216,"mov","eax, dword ptr [eax + 4]")
    gate(wm,0x0078695f,"ret","")
    req(callers["summary"]["directCallerCount"]==1,"writer direct-caller count drift")
    c=callers["callers"][0]
    req(c["call"]["address"]=="0x00786a74" and c["call"]["opStr"]=="0x786210","caller target drift")
    cm=imap(c["contextBefore"]+[c["call"]]+c["contextAfter"])
    for va,mn,op in [
      (0x00786960,"sub","esp, 8"),
      (0x00786963,"push","ebx"),
      (0x00786964,"mov","ebx, dword ptr [esp + 0x10]"),
      (0x00786979,"mov","ecx, dword ptr [ebx + 0x1644]"),
      (0x0078697f,"mov","edx, eax"),
      (0x00786981,"imul","edx, edx, 0x160"),
      (0x0078698f,"lea","ebp, [edx + ecx + 0x4751d0]"),
      (0x00786987,"cmp","byte ptr [edx + ecx + 0x4751d0], 1"),
      (0x007869d4,"mov","edx, dword ptr [ebp + 0x150]"),
      (0x00786a65,"mov","eax, dword ptr [esp + 0x14]"),
      (0x00786a70,"mov","edi, ebp"),
      (0x00786a72,"mov","esi, ebx"),
      (0x00786a74,"call","0x786210"),
    ]:gate(cm,va,mn,op)

    # The independently-proven const layout plus caller ESI=EBX makes EBX/ESI
    # the exact source-state/cache base for this call.
    den_by={x["accessor"]:x for x in den["rows"]}
    req(set(EXPECTED)<=set(den_by),"denominator missing light accessors")

    # Exact version writer cluster.
    clusters=[x for x in xrefs["diagnosticClusters"] if x["diagnosticFunctionStartVa"]=="0x00786210"]
    req(len(clusters)==1,"0x786210 version cluster count drift")
    cl=clusters[0]
    req(set(cl["distinctAccessors"])==set(EXPECTED),"version cluster accessor set drift")
    xhits=[h for h in xrefs["hits"] if h["diagnosticFunctionStartVa"]=="0x00786210"]
    byacc={k:[] for k in EXPECTED}
    for h in xhits:
      for r in h["references"]:
        if r["accessor"] in byacc:byacc[r["accessor"]].append((h,r))

    runtime=[]
    writerRows=[]
    for acc,enumv in sorted(EXPECTED.items(),key=lambda kv:kv[1]):
      src=den_by[acc]
      req(int(src["enumValue"])==enumv,f"{acc}: denominator enum drift")
      req(src["sourceClass"]=="constant",f"{acc}: source class drift")
      laneOffsets=[VALUE_BASE+enumv*16+i*4 for i in range(4)]
      laneWrites={o:[] for o in laneOffsets}
      for x in ins:
        off=store_offset(x.get("opStr",""))
        if off in laneWrites and x["mnemonic"] in ("movss","fstp","movaps","movups","mov"):
          laneWrites[off].append(x)
      for o,rows in laneWrites.items():req(rows,f"{acc}: no writer for value lane offset 0x{o:x}")
      vh=byacc[acc];req(vh,f"{acc}: no version writer")
      expectedVersion=VERSION_BASE+enumv*2
      for h,r in vh:
        req(r["baseReg"]=="esi",f"{acc}: version base register drift")
        req(int(r["displacement"])==expectedVersion,f"{acc}: version offset drift")
        req(h["instruction"]["mnemonic"] in ("add","inc"),f"{acc}: version write mnemonic drift")
      runtime.append({
        "accessor":acc,"enumSymbol":src["enumSymbol"],"enumValue":enumv,
        "sourceClass":src["sourceClass"],"updateFrequency":src["updateFrequency"],
        "retainedSpecialOccurrences":src["totalOccurrences"],
        "currentClientStaticRowVa":src["currentClientStaticRowVa"],
      })
      writerRows.append({
        "accessor":acc,"enumValue":enumv,
        "valueStorage":{"baseRegister":"ESI","baseOffset":VALUE_BASE,
          "formula":"source + 0x800 + enum*16 + lane*4",
          "laneOffsets":[f"0x{x:04x}" for x in laneOffsets],
          "laneWriterAddresses":{f"0x{o:04x}":[x["address"] for x in rows] for o,rows in laneWrites.items()}},
        "versionStorage":{"baseRegister":"ESI","baseOffset":VERSION_BASE,
          "formula":"source + 0x17E0 + enum*2","offset":f"0x{expectedVersion:04x}",
          "writerAddresses":[h["instruction"]["address"] for h,_ in vh]},
      })

    total=sum(int(x["retainedSpecialOccurrences"]) for x in runtime)
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact source-cache layout + exact light writer bytes + exact version-slot writes + exact single direct caller register provenance",
      "runtimeInputs":runtime,
      "provider":{
        "writer":{"startVa":"0x00786210","endVaExclusive":"0x00786960","sha256":WRITER_SHA},
        "sourceStateBase":{
          "callerFirstStackArgumentToEBX":"0x00786964",
          "EBXToWriterESI":"0x00786a72",
          "independentValueLayout":"source + 0x800 + enum*16",
          "independentVersionLayout":"source + 0x17E0 + enum*2",
        },
        "selectedRuntimeRecord":{
          "indexScaleBytes":0x160,
          "indexScaleInstruction":"0x00786981",
          "baseExpressionInstruction":"0x0078698f",
          "activeByteCheckInstruction":"0x00786987",
          "recordToWriterEDI":"0x00786a70",
          "auxPointerSource":"record + 0x150 -> caller local -> writer EAX -> [EAX+4]",
        },
        "constants":writerRows,
      },
      "summary":{
        "currentClientProviderClosed":True,
        "runtimeInputCount":len(runtime),
        "retainedSpecialOccurrenceCount":total,
        "writerFunctionCount":1,
        "directCallerCount":1,
        "allValueLanesHaveExactWriter":True,
        "allVersionSlotsHaveExactWriter":True,
        "allProviderInputsShareExactSourceStateBase":True,
        "selectedRuntimeRecordStrideBytes":0x160,
      },
      "sources":{
        "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator)},
        "getter":{"path":str(a.getter),"sha256":sha(a.getter)},
        "versionXrefs":{"path":str(a.version_xrefs),"sha256":sha(a.version_xrefs)},
        "writer":{"path":str(a.writer),"sha256":sha(a.writer)},
        "callers":{"path":str(a.callers),"sha256":sha(a.callers)},
      },
      "proofBoundary":"Closes the SHA-classified current-client provider mechanics for the listed 12 light code constants: the single exact writer writes every float4 lane into the independently proven source-state constant cache at source+0x800+enum*16 and updates the matching constVersions slot at source+0x17E0+enum*2; its single direct caller passes that source-state base via EBX->ESI and selects the EDI input from an exact 0x160-byte indexed runtime-record table. Raw record offsets/formulas are authoritative; higher-level physical names for individual record fields, historical-retail executable equivalence, universal draw-time values, and framebuffer equivalence are not inferred."
    }
    req(len(runtime)==12,"runtime member count drift")
    req(total==1189,f"retained occurrence count drift {total}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
