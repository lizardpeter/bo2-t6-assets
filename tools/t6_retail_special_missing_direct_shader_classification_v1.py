#!/usr/bin/env python3
"""Classify the exact 19 direct special pixel shaders missing symbolic coverage."""
from __future__ import annotations
import argparse,collections,hashlib,importlib.util,json,struct
from pathlib import Path

FORMAT="t6-retail-special-missing-direct-shader-classification-v1"
EXPECTED_FAMILY_COUNTS={"default":1,"unlit":13,"water":5}

def loadmod(p:Path,n:str):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--coverage",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_DIRECT_SYMBOLIC_COVERAGE_V1.json"))
    ap.add_argument("--program-root",type=Path,required=True)
    ap.add_argument("--opcode-tool",type=Path,default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"))
    ap.add_argument("--operand-tool",type=Path,default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"))
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    cov=json.loads(a.coverage.read_text())
    missing=cov["missingDirectPixelShaders"]
    if len(missing)!=19:raise SystemExit(f"missing denominator {len(missing)} != 19")
    byfam=collections.Counter(x["family"] for x in missing)
    if dict(byfam)!=EXPECTED_FAMILY_COUNTS:raise SystemExit(f"missing family population drift {dict(byfam)}")

    opcode=loadmod(a.opcode_tool,"opcode")
    operand=loadmod(a.operand_tool,"operand")
    rows=[]
    aggregate_ops=collections.Counter()
    for rec in missing:
        h=rec["sha256"];fam=rec["family"]
        matches=list(a.program_root.rglob(f"ps_{h}.cso"))
        if len(matches)!=1:raise SystemExit(f"{h}: exact extracted DXBC path count {len(matches)}")
        p=matches[0];raw=p.read_bytes()
        got=hashlib.sha256(raw).hexdigest()
        if got!=h:raise SystemExit(f"{h}: payload SHA mismatch {got}")
        payload=opcode.shdr_payload(raw)
        walked=opcode.walk(payload)
        dwords=struct.unpack("<%dI"%(len(payload)//4),payload)
        i=2;ops=[];samples=[];unknown=[]
        while i<dwords[1]:
            ir=operand.parse_instruction(dwords,i,opcode.OPCODES)
            op=ir["opcode"];ops.append(op);aggregate_ops[op]+=1
            if op.startswith("sample"):
                O=ir["operands"]
                def idx(o):
                    if o.get("indexRepresentation")!=0 or not o.get("indices"):
                        return None
                    q=o["indices"][0]
                    return q.get("imm32") if q.get("kind")=="imm32" else None
                samples.append({"atDword":i,"opcode":op,
                    "resourceRegister":idx(O[2]) if len(O)>2 else None,
                    "samplerRegister":idx(O[3]) if len(O)>3 else None})
            i+=ir["lengthDwords"]
        counts=collections.Counter(ops)
        row={
          "sha256":h,"family":fam,"path":str(p.relative_to(a.program_root)),
          "bytes":len(raw),"instructionCount":len(walked),
          "opcodeCounts":dict(sorted(counts.items())),
          "hasIf":counts["if"]>0,"ifCount":counts["if"],"elseCount":counts["else"],"endifCount":counts["endif"],
          "hasDiscard":counts["discard"]>0,"discardCount":counts["discard"],
          "hasLoopOrSwitch":any(counts[x] for x in ("loop","endloop","switch","endswitch","case","default","break","breakc","continue","continuec")),
          "sampleCount":len(samples),"samples":samples,
          "saturateInstructionCount":sum(1 for op,ln,ext,sat in walked if sat),
          "extendedOpcodeTokenCount":sum(1 for op,ln,ext,sat in walked if ext),
        }
        rows.append(row)
    rows.sort(key=lambda x:(x["family"],x["sha256"]))
    shape_counts=collections.Counter(
      ("branch" if r["hasIf"] else "straight",
       "discard" if r["hasDiscard"] else "no-discard",
       "loop-switch" if r["hasLoopOrSwitch"] else "no-loop-switch") for r in rows)
    summary={
      "missingShaderCount":len(rows),
      "familyCounts":dict(sorted(byfam.items())),
      "straightShaderCount":sum(not r["hasIf"] for r in rows),
      "branchShaderCount":sum(r["hasIf"] for r in rows),
      "discardShaderCount":sum(r["hasDiscard"] for r in rows),
      "loopOrSwitchShaderCount":sum(r["hasLoopOrSwitch"] for r in rows),
      "shapeCounts":{"|".join(k):v for k,v in sorted(shape_counts.items())},
      "opcodeCounts":dict(sorted(aggregate_ops.items())),
    }
    doc={"format":FORMAT,
      "sourceCoverage":{"path":str(a.coverage),"sha256":sha(a.coverage)},
      "summary":summary,"rows":rows,
      "proofBoundary":"Exact classification only for the 19 SHA-identified direct pixel shaders absent from all prior symbolic proof sets. Each DXBC blob must be uniquely extracted from the exact five-world retained corpus and match its coverage SHA. Opcode/control-flow/sample properties are decoded from the retained SM4 token stream; no visual or family-based semantic assignment is made."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
