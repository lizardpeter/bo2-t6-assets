#!/usr/bin/env python3
"""Full-output symbolic proof for the exact three packed special PS identities
missing from the prior SHA-projected symbolic union.

The denominator and control-flow classification are imported from committed
proof. Each shader is independently recovered by exact SHA-256 from pinned OAT
same-zone dumps, decoded with the already-closed SM4 operand parser, and run
through the existing straight-line symbolic evaluator. A program that writes no
output lanes remains an exact no-output program; no synthetic output is added.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

FORMAT="t6-retail-special-missing-packed-ps-symbolic-v1"
CLASS_FORMAT="t6-retail-special-missing-packed-ps-classification-v1"

def loadmod(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s); assert s.loader; s.loader.exec_module(m); return m
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(x)->str:
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--classification",type=Path,required=True)
    ap.add_argument("--program-root",type=Path,required=True)
    ap.add_argument("--opcode-tool",type=Path,default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"))
    ap.add_argument("--operand-tool",type=Path,default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"))
    ap.add_argument("--straight-tool",type=Path,default=Path("tools/t6_retail_special_shdr_symbolic_v1.py"))
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    cls=json.loads(a.classification.read_text())
    if cls.get("format")!=CLASS_FORMAT:raise SystemExit(f"classification format drift {cls.get('format')!r}")
    rows0=cls.get("rows",[])
    if len(rows0)!=3:raise SystemExit(f"classification denominator {len(rows0)} != 3")
    if cls["summary"]["controlFlowShaderCount"] or cls["summary"]["operandDecodeFailureCount"]:
        raise SystemExit("classification is not straight-line/operand-closed")

    opcode=loadmod(a.opcode_tool,"packed_sym_opcode")
    operand=loadmod(a.operand_tool,"packed_sym_operand")
    straight=loadmod(a.straight_tool,"packed_sym_straight")
    rows=[]
    for src in sorted(rows0,key=lambda x:x["sha256"]):
        h=src["sha256"]
        matches=[]
        for p in a.program_root.rglob("ps_*.cso"):
            if sha(p)==h:matches.append(p)
        if not matches:raise SystemExit(f"{h}: exact OAT CSO absent")
        raw=matches[0].read_bytes()
        shader={"data":raw,"families":set(src.get("families",[])),"name":matches[0].stem[3:]}
        q=straight.symbolic(shader,operand,opcode)
        if q["hasControlFlow"]:raise SystemExit(f"{h}: evaluator unexpectedly found control flow")
        if q["blockers"]:raise SystemExit(f"{h}: symbolic blockers {q['blockers'][:8]}")
        sample_nodes=[n for n in q["nodes"] if n["kind"] in ("textureSample","lightmapSample")]
        sample_dwords=sorted({int(n["instructionDword"]) for n in sample_nodes})
        if len(sample_dwords)!=int(src["sampleCount"]):
            raise SystemExit(f"{h}: symbolic sample count {len(sample_dwords)} != classified {src['sampleCount']}")
        side=q.get("sideEffects",[])
        discard_count=sum(x.get("op")=="discard" for x in side)
        if discard_count!=int(src["discardCount"]):
            raise SystemExit(f"{h}: symbolic discard count {discard_count} != classified {src['discardCount']}")
        compact={"nodes":q["nodes"],"allOutputs":q["allOutputs"],"sideEffects":side}
        rows.append({
          "sha256":h,
          "families":src.get("families",[]),
          "packedOccurrenceCount":src["packedOccurrenceCount"],
          "recoveredAssetNames":src["recoveredAssetNames"],
          "classification":{"instructionCount":src["instructionCount"],"sampleCount":src["sampleCount"],
                            "controlFlowCounts":src["controlFlowCounts"],"discardCount":src["discardCount"]},
          "nodeCount":len(q["nodes"]),
          "outputLaneCount":len(q["allOutputs"]),
          "writesAnyOutput":bool(q["allOutputs"]),
          "sampleInstructionCount":len(sample_dwords),
          "sampleInstructionDwords":sample_dwords,
          "sideEffects":side,
          "outputs":q["allOutputs"],
          "nodes":q["nodes"],
          "fullDagSha256":digest(compact),
        })
    summary={
      "shaderCount":len(rows),
      "packedOccurrenceCount":sum(r["packedOccurrenceCount"] for r in rows),
      "symbolicBlockerCount":0,
      "controlFlowShaderCount":0,
      "sampleInstructionCount":sum(r["sampleInstructionCount"] for r in rows),
      "outputWritingShaderCount":sum(r["writesAnyOutput"] for r in rows),
      "exactNoOutputShaderCount":sum(not r["writesAnyOutput"] for r in rows),
      "nodeCount":sum(r["nodeCount"] for r in rows),
      "outputLaneCount":sum(r["outputLaneCount"] for r in rows),
      "uniqueFullDagCount":len({r["fullDagSha256"] for r in rows}),
      "completeMissingPackedPixelShaderSymbolicCoverage":len(rows)==3,
    }
    if summary["packedOccurrenceCount"]!=22:raise SystemExit(f"occurrence denominator drift {summary}")
    doc={
      "format":FORMAT,
      "authority":"exact three-SHA packed symbolic deficit + exact pinned-OAT same-zone CSO bytes + existing fail-closed SM4 straight-line evaluator",
      "sources":{"classification":{"path":str(a.classification),"sha256":sha(a.classification)},"programRoot":str(a.program_root)},
      "summary":summary,
      "shaderSetSha256":digest([(r["sha256"],r["fullDagSha256"],r["nodeCount"],r["outputLaneCount"]) for r in rows]),
      "rows":rows,
      "proofBoundary":"Exact assembly-level full-output DAGs for the three previously unmatched packed PS CSO hashes. A shader with no output write is retained as an exact no-output program rather than assigned a color. Resource registers/constants/input lanes remain symbolic unless independently mapped elsewhere. No family/name/slot similarity, visual behavior, HLSL reconstruction, or neighboring shader semantics participate."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for r in rows:print(r["sha256"],r["nodeCount"],r["outputLaneCount"],r["sampleInstructionCount"],r["fullDagSha256"])
if __name__=="__main__":main()
