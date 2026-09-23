#!/usr/bin/env python3
"""Recover the exact SHA-classified current T6 client from Plutonium CDN metadata.

Binary identity is the executable SHA/size. CDN manifest revision is retained as
observed transport metadata and is deliberately not an authority gate: the CDN
revision can advance while the exact t6mp.exe blob remains byte-identical.
"""
from __future__ import annotations
import argparse,hashlib,json,urllib.request
from pathlib import Path

FORMAT="t6-current-client-exact-fetch-v1"
EXPECTED_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
EXPECTED_BYTES=13263640
ENDPOINTS=(
 "https://cdn.plutoniummod.com/updater/prod/info.json",
 "https://cdn.plutonium.pw/updater/prod/info.json",
)

def get(url:str)->bytes:
    req=urllib.request.Request(url,headers={"User-Agent":"bo2-t6-assets-exact-client-fetch/1"})
    with urllib.request.urlopen(req,timeout=180) as r:return r.read()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out-exe",type=Path,required=True)
    ap.add_argument("--out-identity",type=Path,required=True)
    a=ap.parse_args()
    info=None;endpoint=None;errors=[]
    for ep in ENDPOINTS:
        try:
            info=json.loads(get(ep));endpoint=ep;break
        except Exception as e:errors.append({"endpoint":ep,"error":repr(e)})
    if info is None:raise SystemExit(f"no CDN info: {errors}")
    rows=[x for x in info.get("files",[]) if str(x.get("name","")).replace("\\","/").lower()=="games/t6mp.exe"]
    if len(rows)!=1:raise SystemExit(f"expected exactly one games/t6mp.exe row, got {len(rows)}")
    rec=rows[0]
    base=info.get("baseUrl")
    if not isinstance(base,str) or not base:raise SystemExit("CDN baseUrl missing")
    blob_hash=rec.get("hash")
    if not isinstance(blob_hash,str) or not blob_hash:raise SystemExit("t6mp row hash missing")
    raw=get(base+blob_hash);sha=hashlib.sha256(raw).hexdigest()
    if len(raw)!=EXPECTED_BYTES or sha!=EXPECTED_SHA:
        raise SystemExit(f"exact client identity drift bytes={len(raw)} sha={sha}")
    a.out_exe.parent.mkdir(parents=True,exist_ok=True);a.out_exe.write_bytes(raw)
    doc={
      "format":FORMAT,
      "authority":"downloaded executable byte identity",
      "observedCdnRevision":str(info.get("revision")),
      "infoEndpoint":endpoint,
      "fileName":rec.get("name"),
      "cdnBlobHash":blob_hash,
      "bytes":len(raw),
      "sha256":sha,
      "proofBoundary":"The executable is authoritative by exact SHA-256 and byte length. CDN manifest revision is transport/update metadata only and is intentionally not required to remain fixed while the executable blob is byte-identical."
    }
    a.out_identity.parent.mkdir(parents=True,exist_ok=True)
    a.out_identity.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc,indent=2,sort_keys=True))
if __name__=="__main__":main()
