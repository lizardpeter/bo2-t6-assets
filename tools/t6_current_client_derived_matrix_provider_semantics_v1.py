#!/usr/bin/env python3
"""Fail-closed current-client provider proofs for selected derived code matrices.

Supported:
- worldViewProjectionMatrix / enum231 / baseIndex20
- shadowLookupMatrix / enum235 / baseIndex24

All formulas are derived from exact SHA-classified current-client helper bytes.
Human names for source-relative physical fields are not invented.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
CORP_FMT="t6-current-client-code-matrix-base-helper-corpus-v1"
MATH_FMT="t6-current-client-viewprojection-math-helper-probe-v1"
VP_FMT="t6-current-client-viewprojection-provider-semantics-v1"

SPECS={
 "worldViewProjectionMatrix":{
   "enum":231,"base":20,"helper":"20","entry":"0x00772d20",
   "format":"t6-current-client-worldviewprojection-provider-semantics-v1",
 },
 "shadowLookupMatrix":{
   "enum":235,"base":24,"helper":"24","entry":"0x00772de0",
   "format":"t6-current-client-shadowlookup-provider-semantics-v1",
 },
}
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def byaddr(ins):return {int(x["address"],16):x for x in ins}
def gate(m,va,mn,op):
    x=m.get(va)
    if not x or x["mnemonic"]!=mn or x["opStr"]!=op:
        raise SystemExit(f"gate drift 0x{va:08x}: {x} != {mn} {op}")
def denrow(d,acc):
    r=[x for x in d["rows"] if x["accessor"]==acc]
    if len(r)!=1:raise SystemExit(f"{acc}: denominator rows={len(r)}")
    return r[0]
def prove_wvp(h,math,vp):
    m=byaddr(h["instructions"])
    gates=[
      (0x00772d2d,"cmp","dword ptr [ebx + 0x19fc], 0x40000000"),
      (0x00772d39,"mov","ecx, 0x10"),(0x00772d3e,"mov","esi, ebx"),
      (0x00772d40,"lea","edi, [esp + 0x10]"),(0x00772d44,"rep movsd","dword ptr es:[edi], dword ptr [esi]"),
      (0x00772d46,"lea","esi, [ebx + 0x500]"),(0x00772d4c,"jne","0x772d6f"),
      (0x00772d4e,"mov","ax, word ptr [ebx + 0x19a6]"),(0x00772d55,"cmp","ax, word ptr [ebx + 0x19ce]"),
      (0x00772d5f,"call","0x772ca0"),(0x00772d67,"lea","ecx, [ebx + 0x400]"),
      (0x00772d75,"addss","xmm0, dword ptr [ebx + 0x19e0]"),
      (0x00772d83,"movss","xmm0, dword ptr [ebx + 0x19e4]"),
      (0x00772d8b,"addss","xmm0, dword ptr [esp + 0x44]"),
      (0x00772d97,"movss","xmm0, dword ptr [ebx + 0x19e8]"),
      (0x00772d9f,"addss","xmm0, dword ptr [esp + 0x48]"),
      (0x00772dab,"lea","ecx, [ebx + 0x16d0]"),
      (0x00772db1,"push","esi"),(0x00772db2,"push","ecx"),
      (0x00772db3,"lea","edx, [esp + 0x18]"),(0x00772db7,"push","edx"),
      (0x00772db8,"call","0x5866b0"),(0x00772dbd,"mov","ax, word ptr [ebx + 0x19d0]"),
      (0x00772dc9,"mov","word ptr [ebx + 0x19ae], ax"),
    ]
    for a,b,c in gates:gate(m,a,b,c)
    if vp.get("summary",{}).get("currentClientProviderClosed") is not True:
        raise SystemExit("viewProjection prerequisite not closed")
    if math["helpers"]["matrixHelper"]["entryVa"]!="0x005866b0":raise SystemExit("matrix helper identity drift")
    return {
      "condition":"u32(S+0x19FC) == 0x40000000",
      "worldTemp":"copy64(S+0x0000) to local W",
      "trueBranch":[
        "if u16(S+0x19A6) != u16(S+0x19CE), derive exact baseIndex16 via 0x772CA0",
        "B = Mat4(S+0x0400)",
      ],
      "falseBranch":[
        "W.row3.xyz += Vec3(S+0x19E0)",
        "B = Mat4(S+0x16D0)",
      ],
      "result":"Mat4(S+0x0500) = W * B",
      "multiplyConvention":vp["formula"]["matrixProductConvention"],
      "version":"u16(S+0x19AE) = u16(S+0x19D0)",
      "getter":"enum231 => matrixIndex20 => S+0x0500 + firstRow*16",
    }
def prove_shadow(h,math):
    m=byaddr(h["instructions"])
    gates=[
      (0x00772de7,"lea","eax, [ebx + 0x600]"),(0x00772def,"lea","esi, [ebx + 0x17a0]"),
      (0x00772df5,"mov","ecx, 0x10"),(0x00772dfa,"rep movsd","dword ptr es:[edi], dword ptr [esi]"),
      (0x00772dfc,"lea","ecx, [eax + 0x30]"),(0x00772e00,"push","eax"),
      (0x00772e01,"lea","edx, [ebx + 0x19e0]"),(0x00772e07,"push","edx"),
      (0x00772e08,"call","0x64d510"),(0x00772e0d,"mov","ax, word ptr [ebx + 0x19d2]"),
      (0x00772e19,"mov","word ptr [ebx + 0x19b6], ax"),
    ]
    for a,b,c in gates:gate(m,a,b,c)
    if math["helpers"]["vectorHelper"]["entryVa"]!="0x0064d510":raise SystemExit("vector helper identity drift")
    return {
      "initial":"Mat4(S+0x0600) = copy64(S+0x17A0)",
      "adjustment":"row3(Mat4(S+0x0600)) = Vec4(S+0x19E0) * Mat4(S+0x0600)",
      "vectorConvention":"out = v.x*M[0] + v.y*M[1] + v.z*M[2] + v.w*M[3]",
      "version":"u16(S+0x19B6) = u16(S+0x19D2)",
      "getter":"enum235 => matrixIndex24 => S+0x0600 + firstRow*16",
    }
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--accessor",choices=sorted(SPECS),required=True)
    ap.add_argument("--denominator",type=Path,required=True);ap.add_argument("--corpus",type=Path,required=True)
    ap.add_argument("--math",type=Path,required=True);ap.add_argument("--viewprojection",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    den,cor,math,vp=map(load,[a.denominator,a.corpus,a.math,a.viewprojection])
    if den.get("format")!=DEN_FMT or cor.get("format")!=CORP_FMT or math.get("format")!=MATH_FMT or vp.get("format")!=VP_FMT:
        raise SystemExit("input format drift")
    for d in (cor,math,vp):
        if d.get("client",{}).get("sha256")!=SHA:raise SystemExit("client SHA mismatch")
    spec=SPECS[a.accessor];r=denrow(den,a.accessor)
    if int(r["enumValue"])!=spec["enum"]:raise SystemExit("enum drift")
    h=cor["helpers"][spec["helper"]]
    if h["entryVa"]!=spec["entry"]:raise SystemExit("helper entry drift")
    formula=prove_wvp(h,math,vp) if a.accessor=="worldViewProjectionMatrix" else prove_shadow(h,math)
    doc={
      "format":spec["format"],
      "authority":"SHA-classified current-client exact code-matrix helper dataflow + exact retained-special accessor identity",
      "runtimeInput":{"accessor":r["accessor"],"enumSymbol":r["enumSymbol"],"enumValue":r["enumValue"],
        "sourceClass":r["sourceClass"],"updateFrequency":r["updateFrequency"],
        "retainedSpecialOccurrences":r["totalOccurrences"],"pixelOccurrences":r["pixelOccurrences"],"vertexOccurrences":r["vertexOccurrences"]},
      "client":{"sha256":SHA,"revision":cor["client"]["revision"]},
      "baseIndex":spec["base"],"helperEntryVa":spec["entry"],"helperSha256":h["sha256"],"formula":formula,
      "sources":{"denominator":{"path":str(a.denominator),"sha256":sha(a.denominator)},
        "corpus":{"path":str(a.corpus),"sha256":sha(a.corpus)},"math":{"path":str(a.math),"sha256":sha(a.math)},
        "viewProjection":{"path":str(a.viewprojection),"sha256":sha(a.viewprojection)}},
      "summary":{"currentClientProviderClosed":True,"enumValue":spec["enum"],"baseIndex":spec["base"],
        "retainedSpecialOccurrenceCount":r["totalOccurrences"],"formulaClosed":True,"historicalRetailEquivalent":False},
      "proofBoundary":"Closes the SHA-classified current client's provider formula in exact source-relative offsets and exact matrix arithmetic. Human physical names/units for source-state fields are not inferred beyond the accessor identity and already-proven matrix storage/version layout. Historical-retail executable equivalence and framebuffer equivalence remain unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
