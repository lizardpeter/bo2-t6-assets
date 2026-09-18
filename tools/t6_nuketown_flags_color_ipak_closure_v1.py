#!/usr/bin/env python3
"""Resolve the last v12 parked/static-XModel flags color payload across retail IPAKs."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from t6_ipak_http_range_v2 import open_ipak

EXPECTED={
 "material":"mc/mtl_nt_2020_flags_01",
 "image":"~-gnt_2020_flags_01_c",
 "nameHash":584722835,
 "dataHash":147283182,
}

def iwi27(raw:bytes):
    if len(raw)<12 or raw[:4]!=b"IWi\x1b":
        raise ValueError("payload is not IWI v27")
    w,h,d=struct.unpack_from("<3H",raw,6)
    return {"format":raw[4],"flags":raw[5],"width":w,"height":h,"depth":d}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--v12",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("urls",nargs="+")
    a=ap.parse_args()
    src=json.loads(a.v12.read_text())
    if src.get("format")!="t6-nuketown-three-missing-material-texture-closure-v1":
        raise SystemExit("v12 proof format drift")
    rem=src.get("remaining")
    if rem != {**EXPECTED,"reason":rem.get("reason")}:
        # Compare authority fields exactly while allowing the historical reason text.
        for k,v in EXPECTED.items():
            if not isinstance(rem,dict) or rem.get(k)!=v:
                raise SystemExit(f"v12 remaining {k} drift: {None if not isinstance(rem,dict) else rem.get(k)!r} != {v!r}")
    ipaks=[open_ipak(u) for u in a.urls]
    matches=[]
    for p in ipaks:
        e=p.entry_exact(EXPECTED["nameHash"],EXPECTED["dataHash"])
        if e is None:
            continue
        raw=p.extract_entry(e)
        matches.append({
          "container":p.url,
          "entry":{"dataHash":e[0],"nameHash":e[1],"offset":e[2],"rawSize":e[3]},
          "bytes":len(raw),
          "sha256":hashlib.sha256(raw).hexdigest(),
          "iwi":iwi27(raw),
        })
    status="missing"; payload=None; reason="exact pair absent from supplied retail IPAKs"
    if matches:
        shas={x["sha256"] for x in matches}
        if len(shas)!=1:
            status="conflict"; reason="same exact pair resolves to byte-different payloads across supplied IPAKs"
        else:
            status="resolved"; payload=next(iter(shas)); reason=None
    doc={
      "format":"t6-nuketown-flags-color-ipak-closure-v1",
      "sourceV12":{"path":str(a.v12),"sha256":hashlib.sha256(a.v12.read_bytes()).hexdigest()},
      "target":EXPECTED,
      "status":status,
      "payloadSha256":payload,
      "matches":matches,
      "containers":[p.describe() for p in ipaks],
      "reason":reason,
      "proofBoundary":"Only the exact source-proven v12 (nameHash,dataHash) pair is accepted. Each hit is CRC29-validated by the range reader; dataHash-only fallback, same-name fallback, nearest-entry selection, and visual substitution are forbidden.",
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":status,"matchCount":len(matches),"payloadSha256":payload},indent=2,sort_keys=True))

if __name__=="__main__":
    main()
