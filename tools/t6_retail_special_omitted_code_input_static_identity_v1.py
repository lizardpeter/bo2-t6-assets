#!/usr/bin/env python3
"""Compact exact denominator for retained special omitted T6 code inputs.

Joins the authoritative omission recovery (what the exact retained TechniqueSets
actually omitted) to the pinned-OAT/current-client static code-input table proof.
This closes accessor identity/enum/update-frequency only; runtime values/resources
remain separate provider gates.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

FORMAT="t6-retail-special-omitted-code-input-static-identity-v1"
RECOVERY_FORMAT="t6-retail-special-omitted-code-input-recovery-v1"
CLIENT_FORMAT="t6-current-client-code-input-table-join-v1"

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def load(p:Path):return json.loads(p.read_text())
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--recovery",type=Path,required=True)
    ap.add_argument("--client-table",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    rec=load(a.recovery); cli=load(a.client_table)
    req(rec.get("format")==RECOVERY_FORMAT,f"recovery format drift {rec.get('format')!r}")
    req(cli.get("format")==CLIENT_FORMAT,f"client format drift {cli.get('format')!r}")

    static={}
    for cls,section in (("sampler",cli["samplers"]),("constant",cli["constants"])):
        for r in section["rows"]:
            key=(cls,r["accessor"])
            req(key not in static,f"duplicate static accessor {key}")
            static[key]=r

    occ=rec.get("accessorOccurrences")
    req(isinstance(occ,list) and occ,"missing accessorOccurrences")
    grouped={}
    for x in occ:
        cls=str(x["sourceClass"]);acc=str(x["accessor"]);stage=str(x["stage"])
        key=(cls,acc)
        g=grouped.setdefault(key,{"sourceClass":cls,"accessor":acc,"pixelOccurrences":0,"vertexOccurrences":0})
        n=int(x["occurrenceCount"])
        if stage=="pixel":g["pixelOccurrences"]+=n
        elif stage=="vertex":g["vertexOccurrences"]+=n
        else:raise E(f"unexpected stage {stage!r}")
    rows=[]
    for key,g in sorted(grouped.items()):
        r=static.get(key)
        req(r is not None,f"no pinned/current-client static row for {key}")
        matches=r.get("rowMatches",[])
        req(len(matches)==1,f"{key}: expected unique exact current-client row, got {len(matches)}")
        rows.append({
          **g,
          "totalOccurrences":g["pixelOccurrences"]+g["vertexOccurrences"],
          "enumSymbol":r["enumSymbol"],"enumValue":int(r["enumValue"]),
          "updateFrequency":r["updateFrequency"],
          "currentClientStaticRowVa":matches[0]["rowVa"],
          "currentClientStaticSection":matches[0]["section"],
          "currentClientStatus":r["status"],
        })

    constants=[x for x in rows if x["sourceClass"]=="constant"]
    samplers=[x for x in rows if x["sourceClass"]=="sampler"]
    req(len(constants)==32,f"expected 32 constants, got {len(constants)}")
    req(len(samplers)==5,f"expected 5 samplers, got {len(samplers)}")
    req(len(rows)==37,"expected 37 total accessors")
    summary={
      "specialTechniqueSetIdentityCount":int(rec["summary"]["specialTechniqueSetIdentityCount"]),
      "recoveredPixelOmissionOccurrenceCount":int(rec["summary"]["pixelOmittedIdentityRecoveredRdefCount"]),
      "runtimeInputAccessorCount":len(rows),
      "codeConstantAccessorCount":len(constants),
      "codeSamplerAccessorCount":len(samplers),
      "uniqueExactCurrentClientStaticRowCount":sum(1 for x in rows if x["currentClientStatus"]=="unique-exact-row"),
      "constantOccurrenceCount":sum(x["totalOccurrences"] for x in constants),
      "samplerOccurrenceCount":sum(x["totalOccurrences"] for x in samplers),
      "pixelOccurrenceCount":sum(x["pixelOccurrences"] for x in rows),
      "vertexOccurrenceCount":sum(x["vertexOccurrences"] for x in rows),
      "runtimeProviderSemanticsClosedCount":0,
      "runtimeProviderSemanticsRemainingCount":len(rows),
    }
    req(summary["uniqueExactCurrentClientStaticRowCount"]==37,"not all static rows unique")
    doc={
      "format":FORMAT,
      "authority":"exact retained special TechniqueSet omission recovery + pinned OAT source-table/current-client exact static-row join",
      "sources":{
        "recovery":{"path":str(a.recovery),"sha256":sha(a.recovery)},
        "clientTable":{"path":str(a.client_table),"sha256":sha(a.client_table)},
      },
      "summary":summary,"rows":rows,
      "proofBoundary":"This closes only the exact runtime-input accessor denominator, source class, enum identity/value, update-frequency classification, occurrence counts, and unique SHA-classified current-client static table representation for the 37 omitted inputs. It does not prove the runtime value/resource provider, setter formula, sampler state, upload mechanism, draw-time value, or historical-retail executable equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
