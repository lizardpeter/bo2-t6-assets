#!/usr/bin/env python3
"""Project exact symbolic pixel-shader coverage onto same-zone resolved packed PS refs.

A packed special pixel shader inherits symbolic coverage ONLY when the exact
resolved CSO SHA-256 appears in one or more independently retained symbolic
pixel-shader proofs. Family, TechniqueSet name, slot, pass, adjacency, and
translated appearance are never used for semantic inheritance.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

FORMAT="t6-retail-special-packed-ps-symbolic-coverage-v1"
RES="t6-retail-special-oat-same-zone-child-resolution-v1"
FULL="t6-retail-special-symbolic-full-rows-v2"
MISS="t6-retail-special-missing-direct-symbolic-v1"
NUKE="t6-nuketown-special-full-output-symbolic-seal-v1"
DIRECT="t6-retail-special-direct-symbolic-coverage-v2"

def load(p:Path):return json.loads(p.read_text())
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--resolution",type=Path,required=True)
    ap.add_argument("--full-rows",type=Path,required=True)
    ap.add_argument("--missing",type=Path,required=True)
    ap.add_argument("--nuketown",type=Path,required=True)
    ap.add_argument("--direct-coverage",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    res=load(a.resolution);full=load(a.full_rows);miss=load(a.missing);nuke=load(a.nuketown);direct=load(a.direct_coverage)
    if res.get("format")!=RES:raise SystemExit("resolution format drift")
    if full.get("format")!=FULL:raise SystemExit("full rows format drift")
    if miss.get("format")!=MISS:raise SystemExit("missing symbolic format drift")
    if nuke.get("format")!=NUKE:raise SystemExit("nuketown symbolic format drift")
    if direct.get("format")!=DIRECT:raise SystemExit("direct coverage format drift")
    if not direct["summary"].get("completeDirectPixelShaderSymbolicCoverage") or direct["summary"]["coveredDirectPixelShaderCount"]!=176:
        raise SystemExit("direct symbolic denominator not complete")

    symbolic=collections.defaultdict(list)
    def add(h,source,meta):
        if not isinstance(h,str) or len(h)!=64:raise SystemExit(f"bad symbolic SHA {h!r}")
        symbolic[h].append({"source":source,**meta})
    for x in full.get("straightShaderRows",[]):add(x["sha256"],"five-world-straight",{"dagSha256":x.get("dagSha256"),"family":x.get("family")})
    for x in full.get("branchShaderRows",[]):add(x["sha256"],"five-world-branch",{"dagSha256":x.get("dagSha256"),"family":x.get("family")})
    for x in nuke.get("shaderRows",[]):add(x["pixelShaderSha256"],"nuketown-full-output",{"dagSha256":x.get("dagSha256"),"asset":x.get("asset")})
    for x in miss.get("rows",[]):add(x["sha256"],"missing-direct-full-output",{"dagSha256":x.get("fullDagSha256"),"family":x.get("family")})

    psrows=[r for r in res.get("rows",[]) if r.get("kind") in ("packedPSObjectRef","packedInlinePSNameRef")]
    if len(psrows)!=281:raise SystemExit(f"packed PS occurrence drift {len(psrows)}")
    projected=[];bad=[];byhash=collections.defaultdict(list)
    for r in psrows:
        if r.get("status")!="resolved-oat-same-zone-shader":
            bad.append({"row":r,"reason":"same-zone shader unresolved"});continue
        sh=r.get("resolvedShader") or {};h=sh.get("sha256")
        if not isinstance(h,str) or len(h)!=64:
            bad.append({"row":r,"reason":"resolved shader SHA absent"});continue
        sources=symbolic.get(h,[])
        row={k:r.get(k) for k in ("map","family","kind","techniqueSet","techniqueSlot","technique","passIndex","raw","block","offset")}
        row.update({"pixelShaderSha256":h,"resolvedShaderAsset":sh.get("asset"),
                    "symbolicCovered":bool(sources),"symbolicProofs":sources})
        projected.append(row);byhash[h].append(row)

    unique=[]
    for h,uses in sorted(byhash.items()):
        fam=sorted({x.get("family") for x in uses if x.get("family") is not None})
        unique.append({"pixelShaderSha256":h,"occurrenceCount":len(uses),"families":fam,
                       "symbolicCovered":h in symbolic,"symbolicProofs":symbolic.get(h,[])})

    covered_occ=sum(x["symbolicCovered"] for x in projected)
    covered_hash=sum(x["symbolicCovered"] for x in unique)
    missing_hash=[x for x in unique if not x["symbolicCovered"]]
    missing_occ=[x for x in projected if not x["symbolicCovered"]]
    summary={
      "packedPixelShaderOccurrenceCount":len(psrows),
      "projectedOccurrenceCount":len(projected),
      "uniqueResolvedPixelShaderSha256Count":len(unique),
      "symbolicCoveredOccurrenceCount":covered_occ,
      "symbolicCoveredUniqueShaderCount":covered_hash,
      "symbolicMissingOccurrenceCount":len(missing_occ),
      "symbolicMissingUniqueShaderCount":len(missing_hash),
      "symbolicCoveragePercentByOccurrence":round(100.0*covered_occ/len(projected),6) if projected else 0.0,
      "symbolicCoveragePercentByUniqueShader":round(100.0*covered_hash/len(unique),6) if unique else 0.0,
      "invalidSameZoneResolutionRowCount":len(bad),
      "symbolicProofUnionShaCount":len(symbolic),
    }
    doc={"format":FORMAT,
      "authority":"exact same-zone OAT-resolved packed PS CSO SHA-256 joined only to independently retained exact symbolic PS SHA-256 proofs",
      "sources":{
        "sameZoneResolution":{"path":str(a.resolution),"sha256":sha(a.resolution)},
        "fullRows":{"path":str(a.full_rows),"sha256":sha(a.full_rows)},
        "missingDirect":{"path":str(a.missing),"sha256":sha(a.missing)},
        "nuketownFullOutput":{"path":str(a.nuketown),"sha256":sha(a.nuketown)},
        "directCoverage":{"path":str(a.direct_coverage),"sha256":sha(a.direct_coverage)}},
      "summary":summary,"uniquePixelShaders":unique,"occurrences":projected,
      "missingUniquePixelShaders":missing_hash,"invalidRows":bad,
      "proofBoundary":"Symbolic semantics transfer only across exact pixel-shader CSO SHA-256 identity. No family label, TechniqueSet/Technique name, slot/pass adjacency, pointer alias component, SPIR-V similarity, or visual behavior is used. An unmatched exact hash remains a genuine symbolic-decompilation blocker."}
    if bad:raise SystemExit(f"same-zone input invalid: {len(bad)} rows")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    if missing_hash:
        print("MISSING UNIQUE PACKED PS HASHES")
        for x in missing_hash:print(x["pixelShaderSha256"],x["occurrenceCount"],x["families"])
if __name__=="__main__":main()
