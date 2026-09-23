#!/usr/bin/env python3
"""Catalog pinned OpenBO2 source-lineage occurrences for the exact 37 runtime inputs.

This is investigation acceleration only. OpenBO2 is not retail/current-client
authority. Exact enum values come from the authoritative static-identity proof;
the catalog finds numeric source uses such as input.consts[N],
constVersions[N], and codeImages[N], retaining source path/line/context.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-special-runtime-input-openbo2-locator-catalog-v1"
INPUT_FORMAT="t6-retail-special-omitted-code-input-static-identity-v1"
OPENBO2_COMMIT="a64812d21946baf710cec7fa26b98ad0d193903b"

PATTERNS={
 "constValue":lambda n:re.compile(rf"(?:\\.|->)consts\\s*\\[\\s*{n}\\s*\\]"),
 "constVersion":lambda n:re.compile(rf"(?:\\.|->)constVersions\\s*\\[\\s*{n}\\s*\\]"),
 "codeImage":lambda n:re.compile(rf"(?:\\.|->)codeImages\\s*\\[\\s*{n}\\s*\\]"),
}

def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def context(lines,i,r=3):
    lo=max(0,i-r);hi=min(len(lines),i+r+1)
    return {"startLine":lo+1,"endLine":hi,"text":"".join(lines[lo:hi])}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--openbo2",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    d=json.loads(a.denominator.read_text())
    if d.get("format")!=INPUT_FORMAT:raise SystemExit("denominator format drift")
    git=(a.openbo2/".git")
    if not git.exists():raise SystemExit("OpenBO2 checkout missing .git")
    import subprocess
    head=subprocess.check_output(["git","-C",str(a.openbo2),"rev-parse","HEAD"],text=True).strip()
    if head!=OPENBO2_COMMIT:raise SystemExit(f"OpenBO2 commit drift {head}")
    files=[]
    for ext in ("*.cpp","*.c","*.h","*.hpp"):
        files.extend((a.openbo2/"src").rglob(ext))
    rows=[]
    total=0
    for src in d["rows"]:
        n=int(src["enumValue"]);cls=src["sourceClass"];hits=[]
        enabled=("codeImage",) if cls=="sampler" else ("constValue","constVersion")
        for p in files:
            try:lines=p.read_text(encoding="utf-8",errors="replace").splitlines(keepends=True)
            except OSError:continue
            rel=str(p.relative_to(a.openbo2))
            for kind in enabled:
                rx=PATTERNS[kind](n)
                for i,line in enumerate(lines):
                    if rx.search(line):
                        hits.append({"kind":kind,"path":rel,"line":i+1,"context":context(lines,i)})
        total+=len(hits)
        bykind={k:sum(h["kind"]==k for h in hits) for k in enabled}
        rows.append({
          "sourceClass":cls,"accessor":src["accessor"],"enumSymbol":src["enumSymbol"],"enumValue":n,
          "updateFrequency":src["updateFrequency"],"occurrenceCount":src["totalOccurrences"],
          "locatorHitCount":len(hits),"locatorHitCountsByKind":bykind,"hits":hits,
          "lineageStatus":"concrete-numeric-use" if hits else "no-numeric-use-in-pinned-source",
        })
    doc={
      "format":FORMAT,
      "authority":"locator-only pinned OpenBO2 source lineage joined to exact 37-input enum denominator",
      "openbo2":{"commit":head},
      "denominator":{"path":str(a.denominator),"sha256":sha(a.denominator)},
      "summary":{
        "runtimeInputAccessorCount":len(rows),
        "accessorsWithConcreteNumericUse":sum(bool(x["locatorHitCount"]) for x in rows),
        "accessorsWithoutConcreteNumericUse":sum(not x["locatorHitCount"] for x in rows),
        "totalNumericLocatorHitCount":total,
        "constantAccessorsWithValueWriteLocator":sum(x["sourceClass"]=="constant" and x["locatorHitCountsByKind"].get("constValue",0)>0 for x in rows),
        "constantAccessorsWithVersionWriteLocator":sum(x["sourceClass"]=="constant" and x["locatorHitCountsByKind"].get("constVersion",0)>0 for x in rows),
        "samplerAccessorsWithCodeImageLocator":sum(x["sourceClass"]=="sampler" and x["locatorHitCountsByKind"].get("codeImage",0)>0 for x in rows),
      },
      "rows":rows,
      "proofBoundary":"OpenBO2 source is used only as pinned T6 lineage/locator evidence. Numeric source use does not establish that the SHA-classified client contains the same function/formula or that historical retail did. No runtime provider is closed by this catalog; each provider still requires current-client/retail evidence or independently authoritative retained data."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    for x in rows:
        if x["locatorHitCount"]:print(x["accessor"],x["enumValue"],x["locatorHitCountsByKind"])
if __name__=="__main__":main()
