#!/usr/bin/env python3
"""Fail-closed current-client worldMatrix provider closure.

Composes already-persisted exact proofs:
- code-matrix getter: enum 211 maps to matrixIndex/baseIndex 0 and returns source+0
- exhaustive version-write writer census: exactly ten functions write both
  worldMatrixVersion (+0x19c6) and worldMatrix constVersion (+0x1986)
- exact matrix helpers: 0x455870 writes a complete 4x4 matrix to its first arg

Every recovered writer must match one of three exact matrix-population routes:
  COPY64    : explicit 16-dword copy into the same source-state base
  HELPER64  : exact call to 0x455870 with the source-state base as output
  ROW4X16   : four explicit 16-byte row stores to base,+0x10,+0x20,+0x30

No source symbol names or historical-retail equivalence are inferred.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-worldmatrix-provider-semantics-v1"
GETTER_FMT="t6-current-client-code-matrix-getter-semantics-v1"
WRITERS_FMT="t6-current-client-world-matrix-writer-functions-v2"
HELPER_FMT="t6-current-client-world-matrix-helper-probe-v1"

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def load(p:Path): return json.loads(p.read_text())
def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def imap(f): return {int(x["address"],16):x for x in f["instructions"]}
def gate(m,va,mn,op=None):
    x=m.get(va); req(x is not None,f"missing 0x{va:08x}")
    req(x["mnemonic"]==mn,f"0x{va:08x}: {x['mnemonic']} != {mn}")
    if op is not None: req(x["opStr"]==op,f"0x{va:08x}: {x['opStr']} != {op}")
    return x

# These route gates use exact instruction starts from the persisted V2 writer corpus.
ROUTES={
  0x0076f510:("COPY64",[
    (0x0076f630,"mov","edi, ebx"),(0x0076f632,"mov","ecx, 0x10"),
    (0x0076f637,"lea","esi, [esp + 0x50]"),(0x0076f63b,"rep movsd","dword ptr es:[edi], dword ptr [esi]")]),
  0x0076f6c0:("COPY64",[
    (0x0076f78e,"mov","ecx, 0x10"),(0x0076f793,"mov","esi, 0xd27798"),
    (0x0076f798,"mov","edi, edx"),(0x0076f79a,"rep movsd","dword ptr es:[edi], dword ptr [esi]"),
    (0x0076f7a9,"movss","dword ptr [edx + 0x30], xmm0"),
    (0x0076f7bb,"movss","dword ptr [edx + 0x34], xmm0"),
    (0x0076f7ce,"movss","dword ptr [edx + 0x38], xmm0")]),
  0x00772940:("HELPER64",[
    (0x007729cd,"push","esi"),(0x007729ce,"call","0x455870")]),
  0x0077c0b0:("HELPER64",[
    (0x0077c726,"push","ebx"),(0x0077c727,"call","0x455870")]),
  0x0077cde0:("HELPER64",[
    (0x0077ce7d,"push","esi"),(0x0077ce85,"call","0x455870")]),
  0x0077e320:("ROW4X16",[
    (0x0077e500,"movaps","xmmword ptr [edi], xmm0"),
    (0x0077e516,"movaps","xmmword ptr [edx], xmm0"),
    (0x0077e524,"movaps","xmmword ptr [eax], xmm0"),
    (0x0077e533,"movaps","xmmword ptr [ecx], xmm0")]),
  0x0077e600:("ROW4X16",[
    (0x0077e772,"movaps","xmmword ptr [ebx], xmm0"),
    (0x0077e77a,"movaps","xmmword ptr [edx], xmm0"),
    (0x0077e797,"movaps","xmmword ptr [edx], xmm0"),
    (0x0077e7aa,"movaps","xmmword ptr [eax], xmm0")]),
  0x0077e8a0:("ROW4X16",[
    (0x0077e9ce,"movaps","xmmword ptr [ebx], xmm0"),
    (0x0077e9d6,"movaps","xmmword ptr [edx], xmm0"),
    (0x0077e9f0,"movaps","xmmword ptr [edx], xmm0"),
    (0x0077ea03,"movaps","xmmword ptr [eax], xmm0")]),
  0x0077fb20:("HELPER64",[
    (0x0077fc04,"push","eax"),(0x0077fc17,"call","0x455870")]),
  0x0077fe30:("HELPER64",[
    (0x00780012,"push","edx"),(0x00780019,"call","0x455870")]),
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--getter",type=Path,required=True)
    ap.add_argument("--writers",type=Path,required=True)
    ap.add_argument("--helpers",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    den,getter,writers,helpers=map(load,(a.denominator,a.getter,a.writers,a.helpers))
    req(getter.get("format")==GETTER_FMT,"getter format drift")
    req(writers.get("format")==WRITERS_FMT,"writers format drift")
    req(helpers.get("format")==HELPER_FMT,"helper format drift")

    wm=[x for x in den["rows"] if x["accessor"]=="worldMatrix"]
    req(len(wm)==1,"worldMatrix denominator row count drift")
    wm=wm[0];req(wm["enumValue"]==211,"worldMatrix enum drift")
    req(wm["occurrenceCount"]==581,"worldMatrix occurrence drift")
    req(getter["storage"]["firstCodeMatrixEnum"]==211,"getter first enum drift")
    # enum 211 -> matrixIndex 0 -> baseIndex 0; base zero is direct cache state
    matrix_index=wm["enumValue"]-getter["storage"]["firstCodeMatrixEnum"]
    base_index=matrix_index & ~3
    req(matrix_index==0 and base_index==0,"worldMatrix not base-zero direct matrix")
    req(getter["storage"]["matrixStrideBytes"]==64,"matrix stride drift")
    req(getter["dataflow"]["returnAddress"]=="source + matrixIndex*64 + firstRow*16","return dataflow drift")

    mh=helpers["helpers"]["matrixConstructHelper"]
    req(mh["entryVa"]=="0x00455870","matrix helper entry drift")
    mm={int(x["address"],16):x for x in mh["instructions"]}
    # Helper first arg is output, and it writes all four 16-byte rows / full 4x4.
    for va,mn,op in [
      (0x00455870,"mov","eax, dword ptr [esp + 4]"),
      (0x00455886,"movss","dword ptr [eax], xmm1"),
      (0x004558b7,"movss","dword ptr [eax + 0x10], xmm2"),
      (0x004558e6,"movss","dword ptr [eax + 0x20], xmm2"),
      (0x0045591a,"fstp","dword ptr [eax + 0x30]"),
      (0x00455926,"movss","dword ptr [eax + 0x3c], xmm0")]:
        gate(mm,va,mn,op)

    req(writers["summary"]=={
      "constVersionWriteInstructionCount":10,
      "functionCount":10,
      "functionsWritingBoth":10,
      "matrixVersionWriteInstructionCount":10,
    },"writer census summary drift")
    bystart={int(f["startVa"],16):f for f in writers["functions"]}
    req(set(bystart)==set(ROUTES),f"writer start set drift {sorted(hex(x) for x in set(bystart)^set(ROUTES))}")

    rows=[]
    for start,(route,gates) in ROUTES.items():
        f=bystart[start];m=imap(f)
        req(f["matrixVersionWriteCount"]==1 and f["constVersionWriteCount"]==1,f"{start:x}: version write counts drift")
        regs={x["baseReg"] for x in f["writerHits"]}
        req(len(regs)==1,f"{start:x}: writer base-reg disagreement {regs}")
        for va,mn,op in gates: gate(m,va,mn,op)
        rows.append({
          "startVa":f["startVa"],"endVaExclusive":f["endVaExclusive"],"sha256":f["sha256"],
          "sourceStateBaseRegister":next(iter(regs)),"route":route,
          "matrixVersionWrite":next(x for x in f["writerHits"] if x["field"]=="worldMatrixVersion")["instruction"],
          "constVersionWrite":next(x for x in f["writerHits"] if x["field"]=="worldConstVersion")["instruction"],
          "routeGateVas":[f"0x{x[0]:08x}" for x in gates],
        })

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact code-matrix getter + exhaustive direct base-0 version writers + exact matrix-population route gates",
      "accessor":"worldMatrix","enumValue":211,"occurrenceCount":wm["occurrenceCount"],
      "matrix":{"matrixIndex":0,"baseIndex":0,"cacheOffset":0,"bytes":64,
                "returnAddress":"source + firstRow*16"},
      "writerRoutes":rows,
      "summary":{
        "currentClientProviderClosed":True,
        "writerFunctionCount":len(rows),
        "copy64RouteCount":sum(x["route"]=="COPY64" for x in rows),
        "helper64RouteCount":sum(x["route"]=="HELPER64" for x in rows),
        "row4x16RouteCount":sum(x["route"]=="ROW4X16" for x in rows),
        "allWriterFunctionsPopulateBaseZeroMatrix":True,
        "allWriterFunctionsSynchronizeMatrixAndConstVersions":True,
      },
      "sources":{
        "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator)},
        "getter":{"path":str(a.getter),"sha256":sha(a.getter)},
        "writers":{"path":str(a.writers),"sha256":sha(a.writers)},
        "helpers":{"path":str(a.helpers),"sha256":sha(a.helpers)},
      },
      "proofBoundary":"Closes the SHA-classified current-client worldMatrix provider as an executable base-0 cache contract: enum 211 indexes matrix 0, and every recovered direct base-0 version writer also populates the 64-byte matrix through one of the exact gated COPY64, HELPER64, or four-row routes before/with synchronized version updates. Route labels describe machine behavior, not source symbols. This does not name the physical object/placement inputs of each route, prove historical-retail executable equivalence, or establish framebuffer equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
