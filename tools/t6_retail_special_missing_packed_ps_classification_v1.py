#!/usr/bin/env python3
"""Classify the exact packed special pixel shaders still missing symbolic coverage.

The denominator is read from the committed packed-PS coverage proof. Each target
SHA-256 must be recovered from one or more same-zone OAT-emitted ps_*.cso files.
Identical duplicate files are retained as provenance; no filename/family/slot
similarity participates in identity.

This stage classifies the native SM4 token stream only. It intentionally does
not claim output arithmetic until a later symbolic evaluator succeeds.
"""
from __future__ import annotations

import argparse, collections, hashlib, importlib.util, json, struct
from pathlib import Path

FORMAT="t6-retail-special-missing-packed-ps-classification-v1"
COVERAGE_FORMAT="t6-retail-special-packed-ps-symbolic-coverage-v1"

def loadmod(path:Path,name:str):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s); assert s.loader; s.loader.exec_module(m); return m
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def fsha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--coverage",type=Path,required=True)
    ap.add_argument("--program-root",type=Path,required=True)
    ap.add_argument("--opcode-tool",type=Path,default=Path("tools/t6_retail_special_shdr_opcode_census_v1.py"))
    ap.add_argument("--operand-tool",type=Path,default=Path("tools/t6_retail_special_shdr_operand_census_v1.py"))
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    cov=json.loads(a.coverage.read_text())
    if cov.get("format")!=COVERAGE_FORMAT:raise SystemExit(f"coverage format drift {cov.get('format')!r}")
    missing=cov.get("missingUniquePixelShaders",[])
    if len(missing)!=3:raise SystemExit(f"expected exactly 3 missing packed PS identities, got {len(missing)}")
    target={str(x["pixelShaderSha256"]):x for x in missing}
    if len(target)!=3 or any(len(h)!=64 for h in target):raise SystemExit("invalid target SHA set")

    files=collections.defaultdict(list)
    for p in sorted(a.program_root.rglob("ps_*.cso")):
        h=sha(p)
        if h in target:
            files[h].append(p)
    absent=sorted(set(target)-set(files))
    if absent:raise SystemExit(f"exact missing packed PS CSOs not recovered: {absent}")

    opcode=loadmod(a.opcode_tool,"packed_opcode")
    operand=loadmod(a.operand_tool,"packed_operand")
    rows=[]; aggregate=collections.Counter()
    for h in sorted(target):
        paths=files[h];raw=paths[0].read_bytes()
        if fsha(raw)!=h:raise SystemExit(f"{h}: primary payload SHA drift")
        sizes={p.stat().st_size for p in paths}
        if len(sizes)!=1:raise SystemExit(f"{h}: duplicate exact-SHA files disagree in size")
        payload=opcode.shdr_payload(raw);dw=struct.unpack("<%dI"%(len(payload)//4),payload)
        i=2;ops=[];samples=[];operand_failures=[]
        while i<dw[1]:
            try: ir=operand.parse_instruction(dw,i,opcode.OPCODES)
            except Exception as e:
                operand_failures.append({"atDword":i,"error":str(e)})
                # token boundary remains recoverable from opcode walker
                tok=dw[i];opid=tok&0x7ff
                if opid>=len(opcode.OPCODES):raise
                op=opcode.OPCODES[opid]
                ln=dw[i+1] if op=="customdata" else (tok>>24)&0x7f
                if ln<1:raise
                ops.append(op);aggregate[op]+=1;i+=ln;continue
            op=ir["opcode"];O=ir["operands"];ops.append(op);aggregate[op]+=1
            if op.startswith("sample"):
                def idx(o):
                    q=o.get("indices",[])
                    if not q:return None
                    z=q[0]
                    return z.get("immediate32") if z.get("representation")=="imm32" else None
                samples.append({
                    "atDword":i,"opcode":op,
                    "resourceRegister":idx(O[2]) if len(O)>2 else None,
                    "samplerRegister":idx(O[3]) if len(O)>3 else None,
                })
            i+=ir["lengthDwords"]
        counts=collections.Counter(ops)
        control={k:counts[k] for k in ("if","else","endif","loop","endloop","switch","endswitch","case","default","break","breakc","continue","continuec","discard") if counts[k]}
        source=target[h]
        rows.append({
            "sha256":h,
            "bytes":len(raw),
            "families":source.get("families",[]),
            "packedOccurrenceCount":int(source.get("occurrenceCount",0)),
            "recoveredFileCount":len(paths),
            "recoveredFiles":[str(p.relative_to(a.program_root)) for p in paths],
            "recoveredAssetNames":sorted({p.stem[3:] for p in paths}),
            "instructionCount":len(ops),
            "opcodeCounts":dict(sorted(counts.items())),
            "controlFlowCounts":control,
            "hasIf":bool(counts["if"]),
            "hasLoopOrSwitch":any(counts[x] for x in ("loop","endloop","switch","endswitch","case","default","break","breakc","continue","continuec")),
            "discardCount":counts["discard"],
            "sampleCount":len(samples),
            "samples":samples,
            "operandDecodeFailureCount":len(operand_failures),
            "operandDecodeFailures":operand_failures,
            "shdrPayloadBytes":len(payload),
            "shdrPayloadSha256":fsha(payload),
        })
    summary={
        "targetUniqueShaderCount":len(rows),
        "targetPackedOccurrenceCount":sum(r["packedOccurrenceCount"] for r in rows),
        "recoveredUniqueShaderCount":sum(bool(r["recoveredFileCount"]) for r in rows),
        "operandDecodeFailureCount":sum(r["operandDecodeFailureCount"] for r in rows),
        "controlFlowShaderCount":sum(bool(r["hasIf"] or r["hasLoopOrSwitch"]) for r in rows),
        "ifShaderCount":sum(r["hasIf"] for r in rows),
        "loopOrSwitchShaderCount":sum(r["hasLoopOrSwitch"] for r in rows),
        "discardShaderCount":sum(bool(r["discardCount"]) for r in rows),
        "sampleInstructionCount":sum(r["sampleCount"] for r in rows),
        "aggregateOpcodeCounts":dict(sorted(aggregate.items())),
    }
    if summary["targetPackedOccurrenceCount"]!=22:raise SystemExit(f"packed occurrence denominator drift {summary}")
    if summary["recoveredUniqueShaderCount"]!=3:raise SystemExit(f"recovery incomplete {summary}")
    doc={
      "format":FORMAT,
      "authority":"exact missing SHA-256 denominator from packed symbolic coverage + same-zone pinned-OAT emitted DXBC bytes",
      "sources":{"coverage":{"path":str(a.coverage),"sha256":sha(a.coverage)},"programRoot":str(a.program_root)},
      "summary":summary,"rows":rows,
      "proofBoundary":"Exact bytecode classification only. Every row is one of the three exact SHA-256 identities absent from packed symbolic coverage and is recovered from pinned OAT same-zone TechniqueSet dumps. Opcode/control-flow/sample facts come from native SM4 tokens. No family, asset filename, TechniqueSet, visual result, adjacency, or similarity assigns semantics. Output arithmetic remains unresolved until a separate symbolic proof succeeds."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for r in rows:print(r["sha256"],r["instructionCount"],r["controlFlowCounts"],r["sampleCount"],r["recoveredAssetNames"])
if __name__=="__main__":main()
