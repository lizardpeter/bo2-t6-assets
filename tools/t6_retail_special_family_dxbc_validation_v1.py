#!/usr/bin/env python3
"""Seal exact retained special-family DXBC extraction with translated SPIR-V validation.

The extractor is byte authority. This validator proves only that every exact direct
DXBC blob retained by that extractor deterministically translated and validated in
this run. Packed/reused program references remain unresolved exactly as upstream.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-retail-special-family-dxbc-validated-v1"
EXTRACT_FORMAT="t6-retail-special-family-dxbc-extract-v1"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--extract",type=Path,required=True)
    ap.add_argument("--spirv-dir",type=Path,required=True)
    ap.add_argument("--vkd3d-version",type=Path,required=True)
    ap.add_argument("--spirv-tools-version",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    src=json.loads(a.extract.read_text())
    if src.get("format")!=EXTRACT_FORMAT:raise SystemExit(f"extract format drift {src.get('format')!r}")
    rows=[]
    for p in src.get("programs",[]):
        stage=str(p["stage"]);digest=str(p["sha256"]);stem=f"{stage}_{digest}"
        spv=a.spirv_dir/f"{stem}.spv";asm=a.spirv_dir/f"{stem}.spvasm"
        if not spv.is_file() or not asm.is_file():raise SystemExit(f"missing translated outputs for {stem}")
        rows.append({
          "stage":stage,"dxbcSha256":digest,"dxbcBytes":int(p["bytes"]),
          "spirvBytes":spv.stat().st_size,"spirvSha256":sha(spv),
          "spirvDisassemblyBytes":asm.stat().st_size,"spirvDisassemblySha256":sha(asm),
          "retainedUseCount":len(p.get("uses",[])),"retainedNames":p.get("names",[]),
        })
    expected=len(src.get("programs",[]))
    if len(rows)!=expected:raise SystemExit("program validation population drift")
    direct_uses=sum(int(x["retainedUseCount"]) for x in rows)
    summary={
      "family":src["family"],
      "techniqueSetCount":src["summary"]["techniqueSetCount"],
      "occurrenceCount":src["summary"]["occurrenceCount"],
      "uniqueDirectVertexShaderCount":src["summary"]["uniqueDirectVertexShaderCount"],
      "uniqueDirectPixelShaderCount":src["summary"]["uniqueDirectPixelShaderCount"],
      "directProgramCount":expected,
      "directProgramUseCount":direct_uses,
      "packedReferenceCount":src["summary"]["packedReferenceCount"],
      "translatedAndValidatedProgramCount":len(rows),
      "translationCoverageComplete":len(rows)==expected,
      "structuralFailureCount":src["summary"]["structuralFailureCount"],
    }
    doc={
      "format":FORMAT,"family":src["family"],
      "sourceExtract":{"path":str(a.extract),"sha256":sha(a.extract),"format":src["format"]},
      "sourceSummary":src["summary"],"techniqueSets":src["techniqueSets"],
      "directPrograms":rows,"packedReferences":src.get("packedReferences",[]),
      "structuralValidation":src.get("structuralValidation",[]),
      "toolchain":{"vkd3dCompiler":a.vkd3d_version.read_text(errors="replace").strip(),
                   "spirvTools":a.spirv_tools_version.read_text(errors="replace").strip()},
      "summary":summary,
      "proofBoundary":"Exact direct retained DXBC bytes are inherited only from the SHA-pinned five-world extractor. This seal adds complete translation/spirv-val coverage and deterministic translated hashes for every direct program. Translation success is not shader-semantic equivalence. Packed technique/shader references remain unresolved and no shader is assigned by name, adjacency, family similarity, or translated appearance."
    }
    if not summary["translationCoverageComplete"] or summary["structuralFailureCount"]!=0:raise SystemExit(f"validation incomplete {summary}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
