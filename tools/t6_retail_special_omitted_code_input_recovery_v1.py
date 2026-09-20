#!/usr/bin/env python3
"""Recover exact matching-accessor T6 code inputs omitted by normal OAT dumps.

Authority:
- same-world pinned-OAT T6 TECHSET_DEBUG text,
- OAT's own exact comment grammar:
    // Omitted due to matching accessors: dst = constant.src;
    // Omitted due to matching accessors: dst = sampler.src;
- exact retained special TechniqueSet/map denominator,
- prior exact runtime-input/RDEF census.

Only OAT-authored omission comments are promoted. No RDEF name is independently
reclassified by similarity. The join proves that an otherwise-unassigned RDEF
destination has an exact hidden MaterialShaderArgument source class/accessor.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re
from pathlib import Path

FORMAT="t6-retail-special-omitted-code-input-recovery-v1"
FAMILY_FORMAT="t6-retail-special-material-family-census-v1"
RUNTIME_FORMAT="t6-retail-special-runtime-input-census-v1"

OMIT_RE=re.compile(r'^\s*// Omitted due to matching accessors: ([^=]+?) = (constant|sampler)\.([^;]+);\s*$')
SHADER_RE=re.compile(r'^\s*(vertexShader|pixelShader)\s+\S+\s+"([^"]+)"\s*$')
TECHSET_ITEM_RE=re.compile(r'^\s*[^:]+:\s*$|^\s*([^/\s][^;]*?)\s*;\s*$')

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)
def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def roots(values):
    out={}
    for x in values:
        if "=" not in x: raise E(f"bad root {x!r}")
        k,v=x.split("=",1); p=Path(v).resolve()
        req(k and k not in out and p.is_dir(),f"bad/duplicate root {x!r}")
        out[k]=p
    return out

def parse_techset_names(path:Path):
    names=[]
    for raw in path.read_text(encoding="utf-8",errors="strict").splitlines():
        s=raw.strip()
        if not s or s.startswith("//") or s.endswith(":"): continue
        m=re.fullmatch(r'([^;]+);',s)
        if m:
            n=m.group(1).strip()
            if n: names.append(n)
    return names

def parse_tech(path:Path,mapn:str,ts:str,tech:str):
    rows=[]
    stage=None; shader=None; waiting=None
    for line_no,raw in enumerate(path.read_text(encoding="utf-8",errors="strict").splitlines(),1):
        sm=SHADER_RE.match(raw)
        if sm:
            waiting=(sm.group(1),sm.group(2)); continue
        s=raw.strip()
        if waiting and s=="{":
            stage="vertex" if waiting[0]=="vertexShader" else "pixel"
            shader=waiting[1]; waiting=None; continue
        if stage and s=="}":
            stage=None; shader=None; continue
        m=OMIT_RE.match(raw)
        if not m: continue
        req(stage is not None and shader is not None,f"{path}:{line_no}: omission outside shader block")
        dest=m.group(1).strip(); klass=m.group(2); src=m.group(3).strip()
        req(dest==src,f"{path}:{line_no}: OAT matching-accessor comment not identity: {dest!r}!={src!r}")
        rows.append({
          "map":mapn,"techniqueSet":ts,"technique":tech,"stage":stage,"shaderAsset":shader,
          "destination":dest,"sourceClass":klass,"sourceAccessor":src,
          "line":line_no,
        })
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--family-census",type=Path,required=True)
    ap.add_argument("--runtime-census",type=Path,required=True)
    ap.add_argument("--root",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    fam=json.loads(a.family_census.read_text()); req(fam.get("format")==FAMILY_FORMAT,"family census format drift")
    runtime=json.loads(a.runtime_census.read_text()); req(runtime.get("format")==RUNTIME_FORMAT,"runtime census format drift")
    rr=roots(a.root)
    expected_maps={x["map"] for x in fam.get("maps",[])}
    req(set(rr)==expected_maps,f"root map set mismatch {sorted(rr)} vs {sorted(expected_maps)}")
    specials=fam.get("specialTechniqueSets",[]); req(len(specials)==31,f"special TS count {len(specials)} !=31")

    omissions=[]; missing_files=[]
    for tsrow in specials:
        ts=str(tsrow["techniqueSet"])
        for mapn in sorted(tsrow.get("maps",{})):
            root=rr[mapn]; tsp=root/"techsets"/f"{ts}.techset"
            if not tsp.is_file():
                missing_files.append({"map":mapn,"techniqueSet":ts,"kind":"techset"}); continue
            for tech in parse_techset_names(tsp):
                tp=root/"techniques"/f"{tech}.tech"
                if not tp.is_file():
                    missing_files.append({"map":mapn,"techniqueSet":ts,"technique":tech,"kind":"technique"}); continue
                omissions.extend(parse_tech(tp,mapn,ts,tech))
    req(not missing_files,f"missing debug dump files: {missing_files[:8]}")

    # Join only pixel-stage omissions to the prior pixel-stage RDEF unresolved census.
    unresolved=runtime.get("unassignedRdefInputs",[])
    key_to_indices=collections.defaultdict(list)
    for i,u in enumerate(unresolved):
        key=(str(u.get("map")),str(u.get("techniqueSet")),str(u.get("technique")),
             int(u.get("passIndex",-1)),str(u.get("name")))
        key_to_indices[key].append(i)

    # Pass index is not printed directly by text parsing; derive deterministic same-technique
    # shader occurrence order from runtime rows and match on exact map/TS/tech/shader/destination.
    runtime_rows=runtime.get("rows",[])
    candidate=collections.defaultdict(list)
    for r in runtime_rows:
        k=(str(r["map"]),str(r["techniqueSet"]),str(r["technique"]),
           str(r["pixelShader"]["asset"]))
        candidate[k].append(r)

    recovered=[]; ambiguous=[]; no_rdef=[]
    for o in omissions:
        if o["stage"]!="pixel": continue
        ck=(o["map"],o["techniqueSet"],o["technique"],o["shaderAsset"])
        passes=candidate.get(ck,[])
        hits=[]
        for r in passes:
            dest=o["destination"]
            for idx,u in enumerate(unresolved):
                if (u.get("map")==o["map"] and u.get("techniqueSet")==o["techniqueSet"] and
                    u.get("technique")==o["technique"] and u.get("passIndex")==r["passIndex"] and
                    u.get("name")==dest):
                    hits.append((r,idx,u))
        # Exact same dumped shader asset + exact RDEF destination should normally isolate a pass.
        uniq={(int(r["passIndex"]),idx) for r,idx,u in hits}
        if len(uniq)==1:
            r,idx,u=hits[0]
            recovered.append({**o,"passIndex":int(r["passIndex"]),"pixelShaderSha256":r["pixelShader"]["sha256"],
              "rdefKind":u["kind"],"runtimeUnassignedIndex":idx})
        elif len(uniq)>1:
            ambiguous.append({**o,"candidatePasses":sorted({int(r["passIndex"]) for r,idx,u in hits})})
        else:
            no_rdef.append(o)

    recovered_indices={x["runtimeUnassignedIndex"] for x in recovered}
    residual=[u for i,u in enumerate(unresolved) if i not in recovered_indices]
    counts=collections.Counter((x["stage"],x["sourceClass"],x["sourceAccessor"]) for x in omissions)
    summary={
      "specialTechniqueSetIdentityCount":len(specials),
      "debugOmissionOccurrenceCount":len(omissions),
      "debugPixelOmissionOccurrenceCount":sum(x["stage"]=="pixel" for x in omissions),
      "debugVertexOmissionOccurrenceCount":sum(x["stage"]=="vertex" for x in omissions),
      "debugCodeConstantOccurrenceCount":sum(x["sourceClass"]=="constant" for x in omissions),
      "debugCodeSamplerOccurrenceCount":sum(x["sourceClass"]=="sampler" for x in omissions),
      "uniqueOmittedCodeConstantAccessorCount":len({x["sourceAccessor"] for x in omissions if x["sourceClass"]=="constant"}),
      "uniqueOmittedCodeSamplerAccessorCount":len({x["sourceAccessor"] for x in omissions if x["sourceClass"]=="sampler"}),
      "priorUnassignedRdefInputCount":len(unresolved),
      "pixelOmittedIdentityRecoveredRdefCount":len(recovered_indices),
      "pixelOmittedIdentityAmbiguousCount":len(ambiguous),
      "pixelOmittedIdentityWithoutUnassignedRdefCount":len(no_rdef),
      "residualUnassignedRdefInputCount":len(residual),
      "missingDumpFileCount":len(missing_files),
    }
    doc={
      "format":FORMAT,
      "authority":"same-world SHA-pinned retail FastFiles + pinned OAT TECHSET_DEBUG omission comments + exact retained special denominator + exact prior pixel-stage RDEF census",
      "sources":{
        "familyCensus":{"path":str(a.family_census),"sha256":sha(a.family_census)},
        "runtimeCensus":{"path":str(a.runtime_census),"sha256":sha(a.runtime_census)},
        "debugRoots":{k:str(v) for k,v in sorted(rr.items())},
      },
      "summary":summary,
      "accessorOccurrences":[{"stage":k[0],"sourceClass":k[1],"accessor":k[2],"occurrenceCount":v} for k,v in sorted(counts.items())],
      "omissions":omissions,
      "pixelRecoveredRdefInputs":recovered,
      "pixelAmbiguous":ambiguous,
      "pixelOmissionsWithoutUnassignedRdef":no_rdef,
      "residualUnassignedRdefInputs":residual,
      "proofBoundary":"Only OAT-authored matching-accessor omission comments are promoted. A comment proves an actual native MaterialShaderArgument was CODE_CONST or CODE_SAMPLER and source accessor exactly equaled shader destination. Material assignments are never inferred from RDEF names. Residual RDEF declarations remain unresolved and may include unused declarations, ignored accessors, or other ABI entries; runtime values and upload mechanics remain outside this proof."
    }
    if ambiguous or no_rdef:
        raise SystemExit(f"fail-closed omitted pixel join: ambiguous={len(ambiguous)} noRdef={len(no_rdef)}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    print("CODE CONSTANT ACCESSORS",sorted({x["sourceAccessor"] for x in omissions if x["sourceClass"]=="constant"}))
    print("CODE SAMPLER ACCESSORS",sorted({x["sourceAccessor"] for x in omissions if x["sourceClass"]=="sampler"}))
if __name__=="__main__":main()
