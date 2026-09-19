#!/usr/bin/env python3
"""Repair the compact branch-symbolic proof after canonical register merge ordering.

Commit e9898d435233670cfc65a8e8477b82e53719730d deliberately made merge_state()
iterate sorted register keys.  That changed proof-significant node IDs/DAG hashes
without changing the branch summary/source set.  This tool derives the compact
fixture from the independently regenerated full-row proof and patches the exact
test constants; no shader semantics are recomputed here.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FULL_FORMAT="t6-retail-special-symbolic-full-rows-v2"
COMPACT_FORMAT="t6-retail-special-shdr-branch-symbolic-v1"
EXPECTED_CANONICAL_DAG="2445f6adefcd1da3c5ae0f3df8ca12724ca0b2c26ba5e4102272956a8b3a2b86"

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--full",type=Path,default=Path("proof/render/T6_RETAIL_SPECIAL_SYMBOLIC_FULL_ROWS_V2.json"))
    ap.add_argument("--compact",type=Path,default=Path("manifests/render/T6_RETAIL_SPECIAL_SHDR_BRANCH_SYMBOLIC_V1.json"))
    ap.add_argument("--test",type=Path,default=Path("tools/test_t6_retail_special_shdr_branch_symbolic_v1.py"))
    a=ap.parse_args()

    full=json.loads(a.full.read_text())
    old=json.loads(a.compact.read_text())
    if full.get("format")!=FULL_FORMAT:raise SystemExit("full proof format drift")
    if old.get("format")!=COMPACT_FORMAT:raise SystemExit("compact proof format drift")
    rows=full["branchShaderRows"]
    if len(rows)!=78:raise SystemExit(f"branch row count {len(rows)} != 78")
    dag=full["summary"]["branchDagSetSha256"]
    if dag!=EXPECTED_CANONICAL_DAG:raise SystemExit(f"canonical branch DAG drift {dag}")
    row_digest=digest(rows)
    examples=[rows[0],rows[len(rows)//2],rows[-1]]

    # Summary/source population must be exactly unchanged by canonical merge ordering.
    if old["summary"]["controlFlowLightmappedShaderCount"]!=78:raise SystemExit("compact summary population drift")
    if old["sourcePixelShaderSetSha256"]!="aa581f23bf696c334020e19ad97e7f26f7772aac999b8720e7da60fbc1a61bc7":
        raise SystemExit("source shader set drift")

    old["dagSetSha256"]=dag
    old["shaderRowSetSha256"]=row_digest
    old["shaderRowExamples"]=examples
    boundary=str(old.get("proofBoundary",""))
    note=" Canonical register-key merge ordering is proof-significant and reflected in the current DAG/row fixtures."
    if note.strip() not in boundary:
        old["proofBoundary"]=boundary+note
    a.compact.write_text(json.dumps(old,indent=2,sort_keys=True)+"\n")

    txt=a.test.read_text()
    txt,n1=re.subn(r"EXPECTED_DAG='[0-9a-f]{64}'",f"EXPECTED_DAG='{dag}'",txt,count=1)
    txt,n2=re.subn(r"EXPECTED_ROWS='[0-9a-f]{64}'",f"EXPECTED_ROWS='{row_digest}'",txt,count=1)
    if n1!=1 or n2!=1:raise SystemExit(f"test constant patch counts dag={n1} rows={n2}")
    a.test.write_text(txt)

    print(json.dumps({
      "branchShaderCount":len(rows),
      "canonicalDagSetSha256":dag,
      "canonicalShaderRowSetSha256":row_digest,
      "exampleSha256":[x["sha256"] for x in examples],
    },indent=2,sort_keys=True))
if __name__=="__main__":main()
