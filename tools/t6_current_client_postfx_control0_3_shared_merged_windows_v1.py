#!/usr/bin/env python3
"""Small exact projection for the two postFx writers shared by controls 0..3."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
FORMAT="t6-current-client-postfx-control0-3-shared-merged-windows-v1"
SRC="t6-current-client-postfx-control0-3-merged-write-windows-v1"
TARGETS={"0x007698b0","0x0076c650"}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 d=json.loads(a.source.read_text());req(d.get("format")==SRC,"source format drift")
 funcs=[]
 for f in d["functions"]:
  if f["startVa"] not in TARGETS:continue
  callers=[{"call":c["call"],"contextBefore":c.get("contextBefore",[])[-36:],"contextAfter":c.get("contextAfter",[])[:12]} for c in f.get("directCallers",[])]
  funcs.append({"startVa":f["startVa"],"instructionCount":f["instructionCount"],"accessorWrites":f["accessorWrites"],
                "mergedWindowCount":f["mergedWindowCount"],"directCallers":callers,"windows":f["windows"]})
 req({f["startVa"] for f in funcs}==TARGETS,"shared writer set drift")
 out={"format":FORMAT,"authority":"exact selected projection from merged postFx writer windows",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":{"functionCount":len(funcs),"windowCounts":{f["startVa"]:f["mergedWindowCount"] for f in funcs}},
      "functions":funcs,
      "proofBoundary":"Projection only. Exact shared writer windows/callers are retained; source semantic identity and provider closure remain separate."}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
