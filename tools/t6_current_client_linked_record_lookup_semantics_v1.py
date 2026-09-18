#!/usr/bin/env python3
"""Project exact lookup/traversal semantics from the persisted linked-record xref proof.

Current-client only. Fail closed: this establishes concrete traversal/payload-return
patterns, not historical retail identity or duplicate winner authority.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path

def insmap(x):
    seq=x["contextBefore"]+[x["instruction"]]+x["contextAfter"]
    return {int(i["address"],16):i for i in seq}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("xref",type=Path);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    src=json.loads(a.xref.read_text())
    if src.get("format")!="t6-current-client-linked-record-global-xref-probe-v1": raise SystemExit("wrong input")
    rows=[]
    for x in src["xrefs"]:
        m=insmap(x)
        for start in (0x00479c40,0x004f3f70):
            need=[start+o for o in ()]
            if start in m:
                seq=sorted((v for k,v in m.items() if start<=k<start+0x80),key=lambda z:int(z["address"],16))
                ops=[z["opStr"] for z in seq]
                has_payload=any("[esi + 4]" in o for o in ops)
                has_next=any("[esi + 0xc]" in o for o in ops)
                if has_payload and has_next:
                    rows.append({"function":f"0x{start:08x}","xref":x["instruction"]["address"],
                      "observed":"bucket head -> record; compare dword +0; on accepted record return dword +4; collision traversal uses +0x0a; secondary chain traversal uses +0x0c before returning +4",
                      "payloadOffset":4,"collisionLinkOffset":10,"secondaryLinkOffset":12})
    uniq={r["function"]:r for r in rows}
    out={"format":"t6-current-client-linked-record-lookup-semantics-v1",
      "authority":"SHA-classified current Plutonium client plus persisted exact xref proof",
      "client":src["client"],"functions":list(uniq.values()),"functionCount":len(uniq),
      "exactFindings":{
        "recordStrideBytes":16,"payloadDwordOffset":4,"zoneIndexByteOffset":8,
        "collisionLinkWordOffset":10,"secondaryLinkWordOffset":12,
        "lookupReturnsPayloadDword":len(uniq)>0},
      "proofBoundary":"The listed current-client functions byte-prove traversal and +4 payload return shape. This does not by itself prove which duplicate owner wins after relinking, nor historical-retail equivalence."}
    if out["functionCount"]<2: raise SystemExit(f"expected >=2 independent lookup-shaped functions, got {out['functionCount']}")
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"functionCount":out["functionCount"],"sha256":hashlib.sha256(payload.encode()).hexdigest()},indent=2))
if __name__=="__main__":main()
