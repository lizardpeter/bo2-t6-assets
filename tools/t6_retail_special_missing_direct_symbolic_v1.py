#!/usr/bin/env python3
"""Full-output symbolic DAG proof for the exact 19 retained special pixel shaders
missing from the prior lightmap/Nuketown symbolic proof union.

No family inference is used: the denominator and family are taken from the exact
SHA coverage proof, and each SHA must independently exist in the retained
five-world direct SHDR corpus. The generic straight-line evaluator is reused
without assigning HLSL names or renderer meaning to resources/constants.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json
from pathlib import Path

FORMAT="t6-retail-special-missing-direct-symbolic-v1"

def loadmod(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s); assert s.loader; s.loader.exec_module(m); return m
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(x)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--coverage",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_DIRECT_SYMBOLIC_COVERAGE_V1.json"))
    ap.add_argument("--classification",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_MISSING_DIRECT_SHADER_CLASSIFICATION_V1.json"))
    ap.add_argument("--family-manifest",type=Path,default=Path("manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json"))
    ap.add_argument("--opcode-tool",type=Path,default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"))
    ap.add_argument("--operand-tool",type=Path,default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"))
    ap.add_argument("--straight-tool",type=Path,default=Path("tools/t6_retail_special_shdr_symbolic_v1.py"))
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    cov=json.loads(a.coverage.read_text())
    cls=json.loads(a.classification.read_text())
    if cov.get("format")!="t6-retail-special-direct-symbolic-coverage-v1":raise SystemExit("coverage format drift")
    if cls.get("format")!="t6-retail-special-missing-direct-shader-classification-v1":raise SystemExit("classification format drift")
    missing=cov["missingDirectPixelShaders"]
    if len(missing)!=19:raise SystemExit(f"missing denominator {len(missing)} != 19")
    cls_by={x["sha256"]:x for x in cls["rows"]}
    if set(cls_by)!={x["sha256"] for x in missing}:raise SystemExit("classification SHA set != coverage missing set")

    opcode=loadmod(a.opcode_tool,"opcode")
    operand=loadmod(a.operand_tool,"operand")
    straight=loadmod(a.straight_tool,"straight")
    unique=opcode.collect(a.root,a.family_manifest,Path("tools/t6_retail_special_shader_payload_census_v1.py"),Path("tools/t6_retail_world_formats_45_proof_v1.py"))

    rows=[];fam=collections.Counter();total_nodes=total_outputs=total_samples=total_discards=0
    for rec in sorted(missing,key=lambda x:(x["family"],x["sha256"])):
        h=rec["sha256"];family=rec["family"];c=cls_by[h]
        sh=unique.get(h)
        if sh is None:raise SystemExit(f"{h}: absent from exact retained direct SHDR corpus")
        observed_families=sorted(sh["families"])
        if observed_families!=[family]:raise SystemExit(f"{h}: exact family ownership {observed_families} != {[family]}")
        q=straight.symbolic(sh,operand,opcode)
        if q["hasControlFlow"]:raise SystemExit(f"{h}: evaluator found control flow despite classification")
        if q["blockers"]:raise SystemExit(f"{h}: symbolic blockers {q['blockers'][:8]}")
        all_outputs=q.get("allOutputs")
        if not isinstance(all_outputs,list) or not all_outputs:raise SystemExit(f"{h}: no complete symbolic outputs")

        sample_nodes=[n for n in q["nodes"] if n["kind"] in ("textureSample","lightmapSample")]
        sample_dwords=sorted({int(n["instructionDword"]) for n in sample_nodes})
        if len(sample_dwords)!=int(c["sampleCount"]):
            raise SystemExit(f"{h}: symbolic sample instruction count {len(sample_dwords)} != classified {c['sampleCount']}")
        discard_count=sum(x.get("op")=="discard" for x in q["sideEffects"])
        if discard_count!=int(c["discardCount"]):
            raise SystemExit(f"{h}: symbolic discard count {discard_count} != classified {c['discardCount']}")
        sample_rows=[]
        for dw in sample_dwords:
            ns=[n for n in sample_nodes if int(n["instructionDword"])==dw]
            sample_rows.append({
              "instructionDword":dw,
              "kinds":sorted({n["kind"] for n in ns}),
              "resourceRegisters":sorted({int(n["textureRegister"] if n["kind"]=="lightmapSample" else n["resourceRegister"]) for n in ns}),
              "samplerRegisters":sorted({int(n["samplerRegister"]) for n in ns}),
              "channels":sorted({str(n["channel"]) for n in ns}),
            })
        compact={"nodes":q["nodes"],"allOutputs":all_outputs,"sideEffects":q["sideEffects"]}
        full_sha=digest(compact)
        row={
          "sha256":h,"family":family,
          "classification":{"instructionCount":c["instructionCount"],"sampleCount":c["sampleCount"],"discardCount":c["discardCount"],"saturateInstructionCount":c["saturateInstructionCount"]},
          "nodeCount":len(q["nodes"]),"outputCount":len(all_outputs),
          "sampleInstructionCount":len(sample_dwords),"samples":sample_rows,
          "sideEffects":q["sideEffects"],"outputs":all_outputs,
          "fullDagSha256":full_sha,
        }
        rows.append(row);fam[family]+=1;total_nodes+=len(q["nodes"]);total_outputs+=len(all_outputs);total_samples+=len(sample_dwords);total_discards+=discard_count

    set_sha=digest([(r["sha256"],r["family"],r["fullDagSha256"],r["nodeCount"],r["outputCount"],r["sampleInstructionCount"]) for r in rows])
    summary={
      "shaderCount":len(rows),"familyCounts":dict(sorted(fam.items())),
      "symbolicBlockerCount":0,"controlFlowShaderCount":0,
      "discardShaderCount":sum(bool(r["sideEffects"]) for r in rows),
      "discardInstructionCount":total_discards,
      "sampleInstructionCount":total_samples,"nodeCount":total_nodes,
      "outputLaneCount":total_outputs,"uniqueFullDagCount":len({r["fullDagSha256"] for r in rows}),
      "completeOutputDagCoverage":len(rows)==19,
    }
    if summary["familyCounts"]!={"default":1,"unlit":13,"water":5}:raise SystemExit(f"family population drift {summary['familyCounts']}")
    if summary["discardShaderCount"]!=1 or summary["discardInstructionCount"]!=1:raise SystemExit(f"discard population drift {summary}")
    doc={
      "format":FORMAT,
      "sources":{
        "coverage":{"path":str(a.coverage),"sha256":sha(a.coverage)},
        "classification":{"path":str(a.classification),"sha256":sha(a.classification)},
        "familyManifest":{"path":str(a.family_manifest),"sha256":sha(a.family_manifest)},
      },
      "summary":summary,"shaderSetSha256":set_sha,"rows":rows,
      "proofBoundary":"Exact SHA-256 identity and assembly-level straight-line dataflow only. Every row is one of the 19 direct retained pixel shaders previously absent from symbolic coverage, and its complete output register DAG is reconstructed from the retained SHDR token stream. Resource registers, constants, inputs and arithmetic operations remain symbolic unless independently mapped elsewhere. The single discard is retained as an exact side effect. This does not reconstruct HLSL, infer family semantics, resolve packed shader references, prove runtime resource values, or establish framebuffer equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True));print(set_sha)

if __name__=="__main__":main()
