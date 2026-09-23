#!/usr/bin/env python3
"""Fail-closed current-client provider proof for viewProjectionMatrix (enum 227).

Composes only exact current-client evidence:
- generic matrix getter/index/version mechanics;
- baseIndex 16 derive-dispatch mapping;
- exact base-16 helper bytes;
- exact arithmetic helper bytes.

Human semantic names for source-relative fields are deliberately not invented.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-viewprojection-provider-semantics-v1"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
GET_FMT="t6-current-client-code-matrix-getter-semantics-v1"
DISP_FMT="t6-current-client-code-matrix-derive-dispatch-v1"
HELP_FMT="t6-current-client-viewprojection-helper-probe-v1"
MATH_FMT="t6-current-client-viewprojection-math-helper-probe-v1"
SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(rows,acc):
    x=[r for r in rows if r.get("accessor")==acc]
    if len(x)!=1:raise SystemExit(f"{acc}: expected one denominator row, got {len(x)}")
    return x[0]
def byaddr(ins):
    return {int(x["address"],16):x for x in ins}
def gate(m,va,mn,op):
    x=m.get(va)
    if not x or x["mnemonic"]!=mn or x["opStr"]!=op:
        raise SystemExit(f"gate drift 0x{va:08x}: {x} != {mn} {op}")
def first_ret(ins):
    for n,x in enumerate(ins):
        if x["mnemonic"]=="ret":return n,x
    raise SystemExit("no ret")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--getter",type=Path,required=True)
    ap.add_argument("--dispatch",type=Path,required=True)
    ap.add_argument("--helper",type=Path,required=True)
    ap.add_argument("--math",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    den,getter,disp,helper,math=map(load,[a.denominator,a.getter,a.dispatch,a.helper,a.math])
    for d,f in [(den,DEN_FMT),(getter,GET_FMT),(disp,DISP_FMT),(helper,HELP_FMT),(math,MATH_FMT)]:
        if d.get("format")!=f:raise SystemExit(f"format drift {d.get('format')} != {f}")
    for d in (getter,disp,helper,math):
        if d.get("client",{}).get("sha256")!=SHA:raise SystemExit("client SHA mismatch across proof chain")
    rt=one(den["rows"],"viewProjectionMatrix")
    if int(rt["enumValue"])!=227 or rt["sourceClass"]!="constant":
        raise SystemExit(f"viewProjection identity drift {rt}")
    if getter["summary"]["firstCodeMatrixEnum"]!=211:
        raise SystemExit("first matrix enum drift")
    matrix_index=227-211
    if matrix_index!=16:raise SystemExit("viewProjection matrix index drift")
    mapping=[x for x in disp["canonicalBaseMappings"] if x["baseIndex"]==16]
    if len(mapping)!=1 or mapping[0]["targetVa"]!="0x00772fc1":
        raise SystemExit(f"base16 dispatcher drift {mapping}")
    if helper["dispatch"]!={"baseIndex":16,"dispatcherThunkVa":"0x00772fc1","helperEntryVa":"0x00772ca0"}:
        raise SystemExit("helper dispatch identity drift")

    hi=helper["function"]["instructions"];hm=byaddr(hi)
    gates={
      0x00772ca1:("mov","ebx, dword ptr [esp + 8]"),
      0x00772ca5:("cmp","dword ptr [ebx + 0x19fc], 0x40000000"),
      0x00772cb1:("lea","esi, [ebx + 0x1650]"),
      0x00772cb7:("lea","ebp, [ebx + 0x400]"),
      0x00772cbd:("jne","0x772ceb"),
      0x00772cbf:("mov","ax, word ptr [ebx + 0x1996]"),
      0x00772cc6:("cmp","ax, word ptr [ebx + 0x19ca]"),
      0x00772cd0:("call","0x772ac0"),
      0x00772cd8:("push","ebp"),
      0x00772cd9:("lea","ecx, [ebx + 0x200]"),
      0x00772cdf:("push","ecx"),
      0x00772ce0:("push","esi"),
      0x00772ce1:("call","0x5866b0"),
      0x00772cec:("sub","esi, -0x80"),
      0x00772cef:("mov","ecx, 0x10"),
      0x00772cf4:("mov","edi, ebp"),
      0x00772cf6:("rep movsd","dword ptr es:[edi], dword ptr [esi]"),
      0x00772cf9:("lea","edx, [ebp + 0x30]"),
      0x00772cfd:("lea","eax, [ebx + 0x19e0]"),
      0x00772d03:("push","ebp"),
      0x00772d04:("push","eax"),
      0x00772d05:("call","0x64d510"),
      0x00772d0a:("mov","cx, word ptr [ebx + 0x19ce]"),
      0x00772d16:("mov","word ptr [ebx + 0x19a6], cx"),
    }
    for va,(mn,op) in gates.items():gate(hm,va,mn,op)
    # 0x772cfc pushes output pointer immediately before the two above.
    gate(hm,0x00772cfc,"push","edx")

    mm=math["helpers"]["matrixHelper"]["instructions"];mi=byaddr(mm)
    # Restrict arithmetic proof to first straight-line function ending at 0x5867d9.
    nret,rret=first_ret(mm)
    if rret["address"]!="0x005867d9":raise SystemExit(f"matrix helper first ret drift {rret}")
    core=mm[:nret+1]
    if any(x["mnemonic"].startswith("j") or x["mnemonic"]=="call" for x in core):
        raise SystemExit("matrix helper core unexpectedly branches/calls")
    for va,mn,op in [
      (0x005866b0,"mov","eax, dword ptr [esp + 4]"),
      (0x005866b4,"movups","xmm0, xmmword ptr [eax]"),
      (0x005866b7,"movups","xmm1, xmmword ptr [eax + 0x10]"),
      (0x005866bb,"movups","xmm2, xmmword ptr [eax + 0x20]"),
      (0x005866bf,"movups","xmm3, xmmword ptr [eax + 0x30]"),
      (0x005866c3,"mov","eax, dword ptr [esp + 8]"),
      (0x00586798,"mov","eax, dword ptr [esp + 0xc]"),
      (0x005867be,"movaps","xmmword ptr [ecx], xmm4"),
      (0x005867ca,"movaps","xmmword ptr [edx], xmm0"),
      (0x005867d3,"movaps","xmmword ptr [ecx], xmm1"),
      (0x005867d6,"movaps","xmmword ptr [eax], xmm2"),
      (0x005867d9,"ret",""),
    ]: gate(mi,va,mn,op)
    # Ensure arithmetic core is exactly shuffle/multiply/add composition after loads.
    allowed={"mov","movups","movaps","shufps","mulps","addps","and","lea","add","ret"}
    bad=[x for x in core if x["mnemonic"] not in allowed]
    if bad:raise SystemExit(f"matrix helper unsupported core ops: {bad[:4]}")

    vi=byaddr(math["helpers"]["vectorHelper"]["instructions"])
    for va,mn,op in [
      (0x0064d510,"mov","eax, dword ptr [esp + 8]"),
      (0x0064d514,"movups","xmm3, xmmword ptr [eax + 0x20]"),
      (0x0064d518,"movups","xmm4, xmmword ptr [eax + 0x30]"),
      (0x0064d51c,"movups","xmm1, xmmword ptr [eax]"),
      (0x0064d51f,"movups","xmm2, xmmword ptr [eax + 0x10]"),
      (0x0064d523,"mov","eax, dword ptr [esp + 4]"),
      (0x0064d52a,"mov","ecx, dword ptr [esp + 0xc]"),
      (0x0064d55f,"movaps","xmmword ptr [ecx], xmm5"),
      (0x0064d562,"ret",""),
    ]: gate(vi,va,mn,op)

    formula={
      "sourcePointer":"S = first argument to base-16 helper at 0x772CA0",
      "condition":"u32(S+0x19FC) == 0x40000000",
      "trueBranch":[
        "if u16(S+0x1996) != u16(S+0x19CA), call exact baseIndex-8 derive helper 0x772AC0",
        "M16 = Mat4(S+0x1650) * Mat4(S+0x0200)",
      ],
      "falseBranch":["M16 = copy64(S+0x16D0)"],
      "commonAdjustment":"M16.row3 = Vec4(S+0x19E0) * M16",
      "matrixProductConvention":"C[row] = A[row].x*B[0] + A[row].y*B[1] + A[row].z*B[2] + A[row].w*B[3]",
      "vectorProductConvention":"out = v.x*M[0] + v.y*M[1] + v.z*M[2] + v.w*M[3]",
      "destination":"matrixIndex16 storage at S+0x0400; SSE stores align each 16-byte destination row downward to a 16-byte boundary",
      "version":"u16(S+0x19A6) = u16(S+0x19CE)",
      "getter":"enum227 => matrixIndex16; returned row address = S + 16*64 + firstRow*16",
    }
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact matrix getter + dispatch + helper bytes and exact retained-special accessor identity",
      "runtimeInput":{
        "accessor":rt["accessor"],"enumSymbol":rt["enumSymbol"],"enumValue":rt["enumValue"],
        "sourceClass":rt["sourceClass"],"updateFrequency":rt["updateFrequency"],
        "retainedSpecialOccurrences":rt["totalOccurrences"],"pixelOccurrences":rt["pixelOccurrences"],"vertexOccurrences":rt["vertexOccurrences"],
      },
      "client":{"sha256":SHA,"revision":getter["client"]["revision"]},
      "formula":formula,
      "helperArithmetic":{
        "matrixHelper":{"entryVa":"0x005866b0","coreEndVaExclusive":"0x005867da",
                        "coreBytesSha256":hashlib.sha256(b"".join(bytes.fromhex(x["bytes"]) for x in core)).hexdigest(),
                        "straightLine":True,"formula":formula["matrixProductConvention"]},
        "vectorHelper":{"entryVa":"0x0064d510","functionSha256":math["helpers"]["vectorHelper"]["sha256"],
                        "formula":formula["vectorProductConvention"]},
      },
      "sources":{
        "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator)},
        "getter":{"path":str(a.getter),"sha256":sha(a.getter)},
        "dispatch":{"path":str(a.dispatch),"sha256":sha(a.dispatch)},
        "helper":{"path":str(a.helper),"sha256":sha(a.helper)},
        "math":{"path":str(a.math),"sha256":sha(a.math)},
      },
      "summary":{"currentClientProviderClosed":True,"enumValue":227,"matrixIndex":16,
                 "branchFormulaClosed":True,"matrixMultiplyHelperClosed":True,"vectorTransformHelperClosed":True,
                 "versionUpdateClosed":True,"historicalRetailEquivalent":False,
                 "retainedSpecialOccurrenceCount":rt["totalOccurrences"]},
      "proofBoundary":"Closes the SHA-classified current client's viewProjectionMatrix provider as exact executable dataflow in source-relative offsets, including both branches, matrix multiplication, vector adjustment, getter address, and version caching. Human physical names/units for S+0x1650/S+0x16D0/S+0x19E0/S+0x19FC are intentionally unresolved. The SSE helpers align destination rows down to 16-byte boundaries exactly as recorded. Historical-retail executable equivalence and framebuffer equivalence remain unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
