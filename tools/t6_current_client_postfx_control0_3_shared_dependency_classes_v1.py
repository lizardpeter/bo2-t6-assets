#!/usr/bin/env python3
"""Project exact postFxControl0..3 backward-slice classes for the two shared writers.

The full slice-class proof is intentionally broad. This reducer keeps only
0x007698B0 and 0x0076C650, strips repeated control noise, and groups exact value
classes by accessor/field/memory-leaf signature so record offsets and common
formulas become reviewable without changing proof authority.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path

FORMAT="t6-current-client-postfx-control0-3-shared-dependency-classes-v1"
SRC="t6-current-client-postfx-control0-3-slice-classes-v1"
TARGETS={"0x007698b0","0x0076c650"}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text());req(d.get("format")==SRC,"source format drift")
    rows=[];grouped=defaultdict(lambda:{"count":0,"classIds":[],"writeAddresses":[],"instructionSignatures":[]})
    for c in d.get("classes",[]):
        if c.get("functionStartVa") not in TARGETS:continue
        field=c.get("field","")
        # Versions are cadence metadata, not lane formulas; retain separately but
        # do not mix them into value dependency groups.
        ins=[{"address":x.get("address"),"mnemonic":x.get("mnemonic"),"opStr":x.get("opStr")} for x in c.get("instructions",[])]
        row={"functionStartVa":c["functionStartVa"],"accessor":c["accessor"],"enumValue":c["enumValue"],
             "field":field,"classId":c["classId"],"count":c["count"],"writeAddresses":c["writeAddresses"],
             "write":c["write"],"memoryLeaves":c.get("memoryLeaves",[]),
             "neededAtBoundary":c.get("neededAtBoundary",[]),"instructions":ins}
        rows.append(row)
        key=json.dumps({"f":c["functionStartVa"],"a":c["accessor"],"field":field,"leaves":c.get("memoryLeaves",[])},sort_keys=True)
        g=grouped[key];g["count"]+=c["count"];g["classIds"].append(c["classId"]);g["writeAddresses"]+=c["writeAddresses"]
        sig=[f"{x.get('mnemonic')} {x.get('opStr')}" for x in c.get("instructions",[])]
        if sig not in g["instructionSignatures"]:g["instructionSignatures"].append(sig)
        g["functionStartVa"]=c["functionStartVa"];g["accessor"]=c["accessor"];g["field"]=field;g["memoryLeaves"]=c.get("memoryLeaves",[])
    groups=list(grouped.values())
    groups.sort(key=lambda x:(x["accessor"],x["field"],x["functionStartVa"],json.dumps(x["memoryLeaves"])))
    counts=defaultdict(lambda:{"classCount":0,"writeCount":0,"valueClassCount":0,"versionClassCount":0})
    for r in rows:
        z=counts[r["accessor"]];z["classCount"]+=1;z["writeCount"]+=r["count"]
        if r["field"]=="version":z["versionClassCount"]+=1
        else:z["valueClassCount"]+=1
    out={"format":FORMAT,"authority":"exact selected projection of SHA-frozen backward-slice classes",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{"selectedFunctionCount":len(TARGETS),"selectedClassCount":len(rows),
                 "dependencyGroupCount":len(groups),"byAccessor":dict(sorted(counts.items()))},
      "groups":groups,"classes":rows,
      "proofBoundary":"Projection/grouping only. Exact slice instructions and memory leaves are retained, but a memory leaf is not automatically a named runtime field and incomplete boundary registers remain unresolved until caller/branch dataflow closes them."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
