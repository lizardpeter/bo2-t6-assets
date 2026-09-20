#!/usr/bin/env python3
"""Compact the same-zone OAT special-child proof into an exact unique-pointer census."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
FORMAT="t6-retail-special-oat-same-zone-child-census-v1"
SRC="t6-retail-special-oat-same-zone-child-resolution-v1"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--resolution",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.resolution.read_text())
    if d.get("format")!=SRC:raise SystemExit("resolution format drift")
    kinds={}
    for r in d["rows"]:
        k=r["kind"];p=(r["map"],int(r["block"]),int(r["offset"]),r["raw"])
        q=kinds.setdefault(k,{"occurrences":0,"pointers":{},"statuses":{}})
        q["occurrences"]+=1;q["statuses"][r["status"]]=q["statuses"].get(r["status"],0)+1
        x=q["pointers"].setdefault(p,{"statuses":set(),"shaderSha256":set(),"techniques":set(),"routingSha256":set()})
        x["statuses"].add(r["status"])
        if r.get("resolvedTechnique"):x["techniques"].add(r["resolvedTechnique"])
        sh=r.get("resolvedShader")
        if sh and sh.get("sha256"):x["shaderSha256"].add(sh["sha256"])
        if "resolvedVertexRouting" in r:
            x["routingSha256"].add(hashlib.sha256(json.dumps(r["resolvedVertexRouting"],sort_keys=True,separators=(",",":")).encode()).hexdigest())
    rows=[];conflicts=[]
    for k,v in sorted(kinds.items()):
        status_counts={};resolved=0
        for p,x in sorted(v["pointers"].items()):
            st=sorted(x["statuses"])
            for s in st:status_counts[s]=status_counts.get(s,0)+1
            if len(x["shaderSha256"])>1 or len(x["routingSha256"])>1:
                conflicts.append({"kind":k,"pointer":{"map":p[0],"block":p[1],"offset":p[2],"raw":p[3]},
                                  "shaderSha256":sorted(x["shaderSha256"]),"routingSha256":sorted(x["routingSha256"])})
            if st and all(s.startswith("resolved-") for s in st):resolved+=1
        rows.append({"kind":k,"occurrenceCount":v["occurrences"],"uniquePointerIdentityCount":len(v["pointers"]),
                     "resolvedUniquePointerIdentityCount":resolved,"statusByUniquePointer":status_counts})
    summary={"topologyOccurrenceCount":sum(x["occurrenceCount"] for x in rows),
             "uniquePointerIdentityCount":sum(x["uniquePointerIdentityCount"] for x in rows),
             "resolvedUniquePointerIdentityCount":sum(x["resolvedUniquePointerIdentityCount"] for x in rows),
             "conflictCount":len(conflicts)}
    out={"format":FORMAT,"source":{"path":str(a.resolution),"sha256":sha(a.resolution)},"summary":summary,"byKind":rows,"conflicts":conflicts,
         "proofBoundary":"Compacts exact same-zone OAT resolution by raw map/block/offset identity. Technique and shader pointers retain exact child identity; VertexDecl pointers are counted resolved only to emitted routing semantics, not to omitted declaration flags. No pointer arithmetic or cross-zone alias inference is introduced."}
    if summary["topologyOccurrenceCount"]!=1436 or conflicts:raise SystemExit(str(summary))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"summary":summary,"byKind":rows},indent=2,sort_keys=True))
if __name__=="__main__":main()
