#!/usr/bin/env python3
"""Join exact per-root native T6 GfxImage packed identity traces.

Input lines are emitted by the pinned OAT diagnostic patch immediately before
its existing T6 IPAK lookup. The join is identity-exact and root-aware.
"""
from __future__ import annotations
import argparse,json,re
from collections import defaultdict
from pathlib import Path

RX=re.compile(r'^T6_GFXIMAGE_PACKED name=(.*?) nameHash=(\d+) dataHash=(\d+) streamedParts=(\d+) width=(\d+) height=(\d+) depth=(\d+)$')

def parse_file(root: str, path: Path):
    rows=[]
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        m=RX.match(line)
        if not m:
            raise ValueError(f"{root}: trace parse drift: {line}")
        name,nh,dh,sp,w,h,d=m.groups()
        rows.append({
            "root":root,"name":name,"nameHash":int(nh),"dataHash":int(dh),
            "streamedPartCount":int(sp),"width":int(w),"height":int(h),"depth":int(d),
        })
    return rows

def tup(x):
    return (x["nameHash"],x["dataHash"],x["streamedPartCount"],x["width"],x["height"],x["depth"])

def variant_dict(t, occ):
    nh,dh,sp,w,h,d=t
    return {
      "nameHash":nh,"dataHash":dh,"streamedPartCount":sp,
      "width":w,"height":h,"depth":d,
      "roots":sorted({x["root"] for x in occ}),
      "occurrenceCount":len(occ),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--input-dir",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    manifest=json.loads(a.manifest.read_text())
    roots=manifest.get("roots")
    if not isinstance(roots,list) or not roots:
        raise SystemExit("manifest roots missing")
    labels=[x["label"] for x in roots]
    if len(set(labels))!=len(labels):
        raise SystemExit("duplicate root labels")

    all_rows=[]
    root_counts={}
    for r in roots:
        label=r["label"]
        rows=parse_file(label,a.input_dir/f"{label}_packed.txt")
        all_rows.extend(rows)
        root_counts[label]=len(rows)

    by=defaultdict(list)
    for row in all_rows:
        by[row["name"]].append(row)

    stable=[]
    conflicts=[]
    for name,occ in sorted(by.items()):
        variants=defaultdict(list)
        for row in occ:
            variants[tup(row)].append(row)
        if len(variants)==1:
            t,rows=next(iter(variants.items()))
            row=variant_dict(t,rows)
            row["name"]=name
            stable.append(row)
        else:
            conflicts.append({
              "name":name,
              "variants":[variant_dict(t,rows) for t,rows in sorted(variants.items())],
              "proofBoundary":"same exact GfxImage name produced multiple native packed tuples across authoritative roots; no tuple is promoted here",
            })

    doc={
      "format":"t6-nuketown-gfximage-packed-identity-trace-v2",
      "authority":"SHA-pinned five-root FastFiles + exactly pinned OAT 9dca965 diagnostic trace",
      "sources":roots,
      "rows":stable,
      "conflicts":conflicts,
      "summary":{
        "rootTraceCounts":root_counts,
        "occurrenceCount":len(all_rows),
        "uniqueNameCount":len(by),
        "stableTupleNameCount":len(stable),
        "conflictingTupleNameCount":len(conflicts),
      },
      "proofBoundary":"Rows retain only exact native tuples identical across every observed authoritative root occurrence of that exact name. Cross-root tuple conflicts are preserved separately and remain unresolved. No filename transformation, inferred hash, nearest match, ordering heuristic, or visual substitution is used.",
    }
    if not all_rows:
        raise SystemExit("no packed trace rows")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__":
    main()
