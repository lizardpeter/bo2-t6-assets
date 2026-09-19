#!/usr/bin/env python3
"""Exact SHA join of retained special direct pixel shaders to symbolic proofs."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-retail-special-direct-symbolic-coverage-v1"
FAMILIES=[
 ("default","T6_RETAIL_SPECIAL_DEFAULT_DIRECT_DXBC_VALIDATED_V1.json"),
 ("emissive_or_burning","T6_RETAIL_SPECIAL_EMISSIVE_OR_BURNING_DIRECT_DXBC_VALIDATED_V1.json"),
 ("rawnormal_special","T6_RETAIL_SPECIAL_RAWNORMAL_SPECIAL_DIRECT_DXBC_VALIDATED_V1.json"),
 ("shadowcaster","T6_RETAIL_SPECIAL_SHADOWCASTER_DIRECT_DXBC_VALIDATED_V1.json"),
 ("tv_special","T6_RETAIL_SPECIAL_TV_SPECIAL_DIRECT_DXBC_VALIDATED_V1.json"),
 ("unlit","T6_RETAIL_SPECIAL_UNLIT_DIRECT_DXBC_VALIDATED_V1.json"),
 ("water","T6_RETAIL_SPECIAL_WATER_DIRECT_DXBC_VALIDATED_V1.json"),
]
def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--proof-dir",type=Path,default=Path("proof/render"))
 ap.add_argument("--full-rows",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_SYMBOLIC_FULL_ROWS_V2.json"))
 ap.add_argument("--nuketown-full",type=Path,default=Path("manifests/render/T6_NUKETOWN_SPECIAL_FULL_OUTPUT_SYMBOLIC_V1.json"))
 ap.add_argument("--out",type=Path,required=True)
 a=ap.parse_args()
 full=load(a.full_rows);nuk=load(a.nuketown_full)
 assert full["format"]=="t6-retail-special-symbolic-full-rows-v2"
 straight={x["sha256"]:x for x in full["straightShaderRows"]}
 branch={x["sha256"]:x for x in full["branchShaderRows"]}
 assert not (set(straight)&set(branch))
 nrows=nuk.get("shaderRows",[])
 nset={x["pixelShaderSha256"]:x for x in nrows}
 family_rows=[];direct_all={};family_hashes={}
 for family,name in FAMILIES:
  p=a.proof_dir/name;d=load(p)
  assert d["family"]==family
  hs=sorted({x["dxbcSha256"] for x in d["directPrograms"] if x["stage"]=="ps"})
  family_hashes[family]=hs
  for h in hs:
   prev=direct_all.get(h)
   if prev is not None and prev!=family: raise RuntimeError(f"direct pixel hash crosses families: {h} {prev} {family}")
   direct_all[h]=family
  rows=[]
  for h in hs:
   hits=[]
   if h in straight:hits.append("lightmapped-straight")
   if h in branch:hits.append("lightmapped-branch")
   if h in nset:hits.append("nuketown-full-output")
   rows.append({"sha256":h,"coverage":hits,"covered":bool(hits)})
  missing=[x["sha256"] for x in rows if not x["covered"]]
  family_rows.append({"family":family,"directPixelShaderCount":len(hs),
    "straightSymbolicCount":sum(h in straight for h in hs),
    "branchSymbolicCount":sum(h in branch for h in hs),
    "nuketownFullOutputCount":sum(h in nset for h in hs),
    "coveredUnionCount":sum(bool(x["coverage"]) for x in rows),
    "missingCount":len(missing),"missingSha256":missing,"rows":rows})
 direct_set=set(direct_all);symbolic_set=set(straight)|set(branch)|set(nset)
 covered=direct_set&symbolic_set;missing=direct_set-symbolic_set;outside=symbolic_set-direct_set
 summary={"familyCount":len(FAMILIES),"directPixelShaderCount":len(direct_set),
   "straightSymbolicShaderCount":len(straight),"branchSymbolicShaderCount":len(branch),
   "nuketownFullOutputShaderCount":len(nset),"symbolicUnionShaderCount":len(symbolic_set),
   "coveredDirectPixelShaderCount":len(covered),"missingDirectPixelShaderCount":len(missing),
   "symbolicHashesOutsideDirectDenominatorCount":len(outside),
   "coveragePercent":round(100.0*len(covered)/len(direct_set),6)}
 assert len(direct_set)==176
 assert len(straight)==76 and len(branch)==78
 assert summary["coveredDirectPixelShaderCount"]==157
 assert summary["missingDirectPixelShaderCount"]==19
 expected_missing={"default":1,"emissive_or_burning":0,"rawnormal_special":0,"shadowcaster":0,"tv_special":0,"unlit":13,"water":5}
 assert {x["family"]:x["missingCount"] for x in family_rows}==expected_missing
 doc={"format":FORMAT,"sources":{
    "fullRows":{"path":str(a.full_rows),"sha256":sha(a.full_rows)},
    "nuketownFullOutput":{"path":str(a.nuketown_full),"sha256":sha(a.nuketown_full)},
    "directFamilyProofs":[{"family":f,"path":str(a.proof_dir/n),"sha256":sha(a.proof_dir/n)} for f,n in FAMILIES]},
   "summary":summary,"families":family_rows,
   "missingDirectPixelShaders":[{"sha256":h,"family":direct_all[h]} for h in sorted(missing)],
   "symbolicHashesOutsideDirectDenominator":sorted(outside),
   "proofBoundary":"Exact SHA-256 identity join only. A direct retained pixel shader is covered only when its DXBC SHA appears in an independently retained symbolic proof. Family totals, names, visual similarity, technique adjacency, packed references, and translated SPIR-V are not used to assign symbolic coverage. The 19 missing direct hashes remain unsolved by this proof."}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()
