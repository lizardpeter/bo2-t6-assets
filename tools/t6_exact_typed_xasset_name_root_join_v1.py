#!/usr/bin/env python3
"""Join one exact qualified asset name against native ordinal/type/name root bindings."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FMT="t6-exact-typed-xasset-name-root-join-v1"
EXPECTED_BINDING="t6-oat-all-xasset-ordinal-name-binding-v1"

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--name",required=True)
    ap.add_argument("--expected-type",required=True)
    ap.add_argument("--binding",action="append",nargs=2,metavar=("ROOT","JSON"),required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    matches=[];same_name_other=[];roots=[]
    for label,path_s in a.binding:
        path=Path(path_s);d=json.loads(path.read_text())
        if d.get("format")!=EXPECTED_BINDING:raise SystemExit(f"{label}: binding format drift")
        roots.append({"root":label,"file":str(path),"sha256":sha(path),"expandedSha256":d.get("expandedSha256"),"xassetCount":d.get("xassetCount")})
        for row in d.get("rows",[]):
            if row.get("nativeResolvedName")!=a.name:continue
            rec={"root":label,"assetTypeName":row.get("assetTypeName"),"name":row.get("nativeResolvedName"),"xassetIndex":row.get("xassetIndex"),"rawXAssetPointer":row.get("rawXAssetPointer"),"tableSourceOffset":row.get("tableSourceOffset")}
            if row.get("assetTypeName")==a.expected_type:matches.append(rec)
            else:same_name_other.append(rec)
    doc={"format":FMT,"query":{"name":a.name,"expectedAssetType":a.expected_type},"bindingRoots":roots,"typedMatches":matches,"sameNameOtherAssetTypes":same_name_other,
      "summary":{"rootCount":len(roots),"typedMatchCount":len(matches),"sameNameOtherTypeMatchCount":len(same_name_other),"typedOwnerRoots":sorted({x["root"] for x in matches})},
      "proofBoundary":"Exact canonical native XAsset name/type join over supplied SHA-bound ordinal/type/name root bindings. No basename normalization, prefix stripping, substring search, zone-order winner selection, or alias inference occurs here."}
    if not matches:raise SystemExit("exact typed target absent from supplied bindings")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
