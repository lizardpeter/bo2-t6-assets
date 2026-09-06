#!/usr/bin/env python3
"""Resolve the retained Nuketown packed-GfxImage alias bank against retail IPAKs.

Every input alias is already pointer-proven and carries the retail GfxImage name
hash, streamed dataHash and dimensions.  This census only promotes payloads when
retail IPAK identity is exact:

1. exact (nameHash,dataHash), or
2. dataHash-only fallback when all matching IPAK entries decompress to the exact
   same byte payload and agree with the retained IWI dimensions.

The latter is needed for retail cases where the IPAK's nameHash key differs from
the retained GfxImage name hash while the streamed-part dataHash is exact.  No
filename similarity, nearest hash, or same-name/wrong-data fallback is allowed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import zlib
from collections import Counter, defaultdict
from pathlib import Path

from t6_ipak_http_range_v1 import open_ipak


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_bank(path: Path) -> dict:
    raw_b64 = path.read_bytes().strip()
    raw = zlib.decompress(base64.b64decode(raw_b64))
    doc = json.loads(raw)
    if doc.get("format") != "t6-nuketown-cross-material-type-packed-image-alias-bank-v1":
        raise ValueError(f"unexpected alias bank format {doc.get('format')!r}")
    aliases = doc.get("aliases") or []
    if doc.get("aliasCount") != len(aliases):
        raise ValueError("aliasCount mismatch")
    if doc.get("conflictCount") != 0:
        raise ValueError("input alias bank contains conflicts")
    return {
        "doc": doc,
        "rawJsonBytes": len(raw),
        "rawJsonSha256": sha256(raw),
        "storedBytes": len(raw_b64),
        "storedSha256": sha256(raw_b64),
    }


def iwi_identity(raw: bytes) -> dict:
    if len(raw) < 12 or raw[:4] != b"IWi\x1b":
        raise ValueError("extracted payload is not IWI27")
    fmt = raw[4]
    flags = raw[5]
    w, h, d = struct.unpack_from("<3H", raw, 6)
    return {"format": fmt, "flags": flags, "width": w, "height": h, "depth": d}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alias-bank", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("urls", nargs="+")
    a = ap.parse_args()

    bank_info = load_bank(a.alias_bank)
    bank = bank_info["doc"]
    aliases = bank["aliases"]
    ipaks = [open_ipak(url) for url in a.urls]

    cache: dict[tuple[str, tuple[int, int, int, int]], tuple[bytes, dict]] = {}
    rows = []
    resolution_counts = Counter()
    container_use = Counter()
    unique_payloads: dict[str, dict] = {}
    failures = []

    for i, alias in enumerate(aliases):
        name_hash = int(alias["hash"]) & 0xFFFFFFFF
        data_hash = int(alias["dataHash"]) & 0x1FFFFFFF
        exact_matches = []
        data_matches = []
        for ipak in ipaks:
            e = ipak.entry_exact(name_hash, data_hash)
            if e is not None:
                exact_matches.append((ipak, e))
            for e2 in ipak.by_data.get(data_hash, []):
                data_matches.append((ipak, e2))

        candidates = exact_matches if exact_matches else data_matches
        mode = "exact-pair" if exact_matches else "dataHash"
        extracted = []
        for ipak, e in candidates:
            key = (ipak.url, e)
            if key not in cache:
                raw = ipak.extract_entry(e)
                ident = iwi_identity(raw)
                cache[key] = (raw, ident)
            raw, ident = cache[key]
            extracted.append({
                "container": ipak.url,
                "entry": {"dataHash": e[0], "nameHash": e[1], "offset": e[2], "rawSize": e[3]},
                "bytes": len(raw),
                "sha256": sha256(raw),
                "iwi": ident,
            })

        status = "resolved"
        reason = None
        selected_sha = None
        if not extracted:
            status = "missing"
            reason = "no supplied IPAK contains retained dataHash"
        else:
            shas = {x["sha256"] for x in extracted}
            dims = {(x["iwi"]["width"], x["iwi"]["height"], x["iwi"]["depth"]) for x in extracted}
            expected_dims = (int(alias["width"]), int(alias["height"]), int(alias["depth"]))
            if len(shas) != 1:
                status = "conflict"
                reason = "same retained identity resolves to byte-different payloads across supplied IPAKs"
            elif dims != {expected_dims}:
                status = "conflict"
                reason = f"IWI dimensions {sorted(dims)} != retained {expected_dims}"
            else:
                selected_sha = next(iter(shas))
                if exact_matches:
                    resolution_counts["exactPair"] += 1
                else:
                    resolution_counts["dataHashByteIdentical"] += 1
                for x in extracted:
                    container_use[x["container"]] += 1
                unique_payloads.setdefault(selected_sha, {
                    "sha256": selected_sha,
                    "bytes": extracted[0]["bytes"],
                    "iwi": extracted[0]["iwi"],
                    "aliases": [],
                    "containers": sorted({x["container"] for x in extracted}),
                })["aliases"].append(i)
        if status != "resolved":
            resolution_counts[status] += 1
            failures.append({"aliasIndex": i, "name": alias.get("name"), "reason": reason})

        rows.append({
            "aliasIndex": i,
            "block": int(alias["block"]),
            "virtualOffset": int(alias["virtualOffset"]),
            "name": alias["name"],
            "nameHash": name_hash,
            "dataHash": data_hash,
            "semantic": int(alias["semantic"]),
            "samplerState": int(alias["samplerState"]),
            "retainedDimensions": {"width": int(alias["width"]), "height": int(alias["height"]), "depth": int(alias["depth"])},
            "status": status,
            "resolution": mode if status == "resolved" else None,
            "payloadSha256": selected_sha,
            "matches": extracted,
            "evidence": alias.get("evidence") or [],
            "reason": reason,
        })

    resolved = sum(1 for r in rows if r["status"] == "resolved")
    missing = sum(1 for r in rows if r["status"] == "missing")
    conflict = sum(1 for r in rows if r["status"] == "conflict")
    report = {
        "format": "t6-nuketown-shared-ipak-packed-image-alias-census-v1",
        "map": "mp_nuketown_2020",
        "sourceAliasBank": {
            "path": str(a.alias_bank),
            "aliasCount": len(aliases),
            "conflictCount": bank["conflictCount"],
            "rawJsonBytes": bank_info["rawJsonBytes"],
            "rawJsonSha256": bank_info["rawJsonSha256"],
            "storedBytes": bank_info["storedBytes"],
            "storedSha256": bank_info["storedSha256"],
        },
        "summary": {
            "aliasCount": len(rows),
            "resolved": resolved,
            "missing": missing,
            "conflict": conflict,
            "exactPair": resolution_counts["exactPair"],
            "dataHashByteIdentical": resolution_counts["dataHashByteIdentical"],
            "uniquePayloadCount": len(unique_payloads),
        },
        "containerUse": dict(sorted(container_use.items())),
        "containers": [x.describe() for x in ipaks],
        "uniquePayloads": list(unique_payloads.values()),
        "aliases": rows,
        "failures": failures,
        "proofBoundary": "Input aliases are already retail-pointer-proven. Payload promotion requires exact pair or retained dataHash with byte-identical decompressed payload across every matching supplied IPAK, CRC29 validation inside the range reader, IWI27 parse, and exact retained dimensions. No filename/material similarity or same-name wrong-data fallback is admitted.",
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if conflict:
        raise SystemExit(f"fail-closed: {conflict} conflicting aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
