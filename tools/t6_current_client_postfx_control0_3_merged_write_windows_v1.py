#!/usr/bin/env python3
"""Merge overlapping exact write windows for the five postFxControl0..3 writers."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
FORMAT="t6-current-client-postfx-control0-3-merged-write-windows-v1"
SRC="t6-current-client-postfx-control0-3-complete-writer-family-v1"
PRE=8;POST=2
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 d=json.loads(a.source.read_text());req(d.get("format")==SRC,"source format drift")
 funcs=[];total=0
 for f in d["functions"]:
  ins=f["instructions"];by={x["address"]:i for i,x in enumerate(ins)}
  ranges=[]
  for w in f["writes"]:
   n=by[w["instruction"]["address"]];ranges.append((max(0,n-PRE),min(len(ins),n+POST+1)))
  ranges.sort();merged=[]
  for lo,hi in ranges:
   if merged and lo<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],hi))
   else:merged.append((lo,hi))
  windows=[]
  for lo,hi in merged:
   addrs={x["address"] for x in ins[lo:hi]}
   writes=[w for w in f["writes"] if w["instruction"]["address"] in addrs]
   windows.append({"startAddress":ins[lo]["address"],"endAddressExclusive":ins[hi-1]["address"],
                   "instructions":ins[lo:hi],"writes":writes})
  total+=len(windows)
  funcs.append({"startVa":f["startVa"],"instructionCount":f["instructionCount"],
                "accessorWrites":f["accessorWrites"],"directCallers":f["directCallers"],
                "mergedWindowCount":len(windows),"windows":windows})
 out={"format":FORMAT,"authority":"lossless merged local projection around every frozen exact postFxControl0..3 destination write",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{"functionCount":len(funcs),"mergedWindowCount":total,
                 "accessorWriterDenominator":d["summary"]["accessorWriterDenominator"]},
      "functions":funcs,
      "proofBoundary":"Projection only. Window merging removes repeated neighboring context but preserves exact write instructions. It does not itself prove source formulas, reachability, historical-retail equivalence or provider closure."}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
