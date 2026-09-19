#!/usr/bin/env python3
"""Promote retained direct special pixel-shader symbolic coverage from 157/176 to
176/176 by an exact SHA join against the dedicated 19-shader full-output proof.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-retail-special-direct-symbolic-coverage-v2"
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--v1",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_DIRECT_SYMBOLIC_COVERAGE_V1.json"))
    ap.add_argument("--missing-symbolic",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_MISSING_DIRECT_SYMBOLIC_V1.json"))
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    v1=load(a.v1);ms=load(a.missing_symbolic)
    if v1.get("format")!="t6-retail-special-direct-symbolic-coverage-v1":raise SystemExit("v1 format drift")
    if ms.get("format")!="t6-retail-special-missing-direct-symbolic-v1":raise SystemExit("missing symbolic format drift")
    old_missing={x["sha256"]:x["family"] for x in v1["missingDirectPixelShaders"]}
    new={x["sha256"]:x["family"] for x in ms["rows"]}
    if len(old_missing)!=19 or old_missing!=new:raise SystemExit("19-shader exact SHA/family join mismatch")
    if not ms["summary"]["completeOutputDagCoverage"] or ms["summary"]["symbolicBlockerCount"]!=0:raise SystemExit("missing symbolic proof not complete")
    family_rows=[]
    for f in v1["families"]:
        missing=set(f["missingSha256"])
        joined=missing & set(new)
        if joined!=missing:raise SystemExit(f"{f['family']}: residual missing {sorted(missing-joined)}")
        row={k:v for k,v in f.items() if k!="rows"}
        row["v1CoveredCount"]=int(f["coveredUnionCount"])
        row["newFullOutputSymbolicCount"]=len(joined)
        row["coveredDirectPixelShaderCount"]=int(f["directPixelShaderCount"])
        row["missingCount"]=0;row["missingSha256"]=[]
        family_rows.append(row)
    direct=int(v1["summary"]["directPixelShaderCount"])
    if direct!=176:raise SystemExit(f"direct denominator drift {direct}")
    summary={
      "familyCount":int(v1["summary"]["familyCount"]),
      "directPixelShaderCount":direct,
      "priorCoveredDirectPixelShaderCount":int(v1["summary"]["coveredDirectPixelShaderCount"]),
      "newFullOutputSymbolicShaderCount":len(new),
      "coveredDirectPixelShaderCount":direct,
      "missingDirectPixelShaderCount":0,
      "coveragePercent":100.0,
      "completeDirectPixelShaderSymbolicCoverage":True,
    }
    if summary["priorCoveredDirectPixelShaderCount"]!=157 or len(new)!=19:raise SystemExit(f"coverage arithmetic drift {summary}")
    doc={
      "format":FORMAT,
      "sources":{"v1":{"path":str(a.v1),"sha256":sha(a.v1)},"missingFullOutput":{"path":str(a.missing_symbolic),"sha256":sha(a.missing_symbolic)}},
      "summary":summary,"families":family_rows,"missingDirectPixelShaders":[],
      "newlyCoveredDirectPixelShaders":[{"sha256":h,"family":new[h]} for h in sorted(new)],
      "proofBoundary":"Exact SHA-256 set join only. 100% means every one of the 176 directly retained pixel-shader DXBC identities in the seven-family five-world denominator now has an assembly-level symbolic dataflow proof: prior lightmap/branch/Nuketown proofs for 157 identities plus complete straight-line output DAGs for the exact 19 former misses. This does not resolve the 956 packed technique/shader references, reconstruct HLSL, prove runtime constant/resource values, or establish framebuffer equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
