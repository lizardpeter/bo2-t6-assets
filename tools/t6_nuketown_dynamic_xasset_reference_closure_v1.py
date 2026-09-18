#!/usr/bin/env python3
"""Join Nuketown MapEnt dynamic references to exact typed XAsset name bindings.

No substring/name normalization is allowed. A reference is resolved only when an
exact canonical name occurs under the expected T6 XAsset type in one or more
SHA-pinned root bindings. Multi-root identical typed ownership is retained.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

EXPECTED_BINDING="t6-oat-all-xasset-ordinal-name-binding-v1"
EXPECTED_MAPENTS="t6-mapents-model-animation-census-v1"

def typed_index(bindings):
    idx=collections.defaultdict(list)
    roots=[]
    for label,path in bindings:
        d=json.loads(path.read_text())
        if d.get("format")!=EXPECTED_BINDING:
            raise ValueError(f"{label}: binding format drift")
        roots.append({"root":label,"file":str(path),"expandedSha256":d.get("expandedSha256"),"xassetCount":d.get("xassetCount")})
        for row in d.get("rows",[]):
            idx[(row["assetTypeName"],row["nativeResolvedName"])].append({
              "root":label,
              "xassetIndex":row["xassetIndex"],
              "rawXAssetPointer":row["rawXAssetPointer"],
              "tableSourceOffset":row["tableSourceOffset"],
            })
    return idx,roots

def unique_refs(census):
    refs={}
    def add(kind,atype,name,entity,source_key):
        if not name: return
        key=(kind,atype,name)
        r=refs.setdefault(key,{"kind":kind,"expectedAssetType":atype,"name":name,"entityIndices":[],"sourceKeys":[]})
        r["entityIndices"].append(entity["entityIndex"])
        r["sourceKeys"].append(source_key)
    for e in census.get("relevantEntities",[]):
        add("model","XMODEL",e.get("model"),e,"model")
        add("destructible","DESTRUCTIBLEDEF",e.get("destructibledef"),e,"destructibledef")
        # Preserve every fxanim_fx_N key directly from raw entity pairs.
        for k,v in e.get("pairs",[]):
            if k.startswith("fxanim_fx_") and not k.endswith("_tag"):
                add("fx","FX",v,e,k)
    return refs

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mapents",type=Path,required=True)
    ap.add_argument("--binding",action="append",nargs=2,metavar=("ROOT","JSON"),required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    census=json.loads(a.mapents.read_text())
    if census.get("format")!=EXPECTED_MAPENTS:
        raise SystemExit("MapEnt census format drift")
    bindings=[(label,Path(path)) for label,path in a.binding]
    idx,root_meta=typed_index(bindings)
    refs=unique_refs(census)
    rows=[]
    for (_kind,_atype,_name),r in sorted(refs.items()):
        matches=idx.get((r["expectedAssetType"],r["name"]),[])
        other_types=sorted({atype for (atype,name) in idx if name==r["name"] and atype!=r["expectedAssetType"]})
        status="resolved" if matches else "absent-from-supplied-roots"
        rows.append({
          **r,
          "entityIndices":sorted(set(r["entityIndices"])),
          "sourceKeys":sorted(set(r["sourceKeys"])),
          "status":status,
          "matches":matches,
          "sameNameOtherAssetTypes":other_types,
        })
    counts=collections.Counter(x["status"] for x in rows)
    kinds={}
    for k in sorted({x["kind"] for x in rows}):
        rs=[x for x in rows if x["kind"]==k]
        kinds[k]={"referenceIdentityCount":len(rs),"resolved":sum(x["status"]=="resolved" for x in rs),"absent":sum(x["status"]!="resolved" for x in rs)}
    out={
      "format":"t6-nuketown-dynamic-xasset-reference-closure-v1",
      "map":census.get("map"),
      "sourceMapEntCensus":{"file":str(a.mapents),"sha256":hashlib.sha256(a.mapents.read_bytes()).hexdigest()},
      "bindingRoots":root_meta,
      "summary":{
        "referenceIdentityCount":len(rows),
        "resolved":counts["resolved"],
        "absentFromSuppliedRoots":counts["absent-from-supplied-roots"],
        "byKind":kinds,
      },
      "rows":rows,
      "proofBoundary":"References are extracted from exact MapEnt key/value pairs and joined only to exact canonical names under their required T6 XAsset type in supplied ordinal/type/name bindings. Same-name assets under another type do not resolve the reference. Absence means absent only from the supplied SHA-pinned root XAsset tables; no global retail absence is inferred."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))

if __name__=="__main__":
    main()
