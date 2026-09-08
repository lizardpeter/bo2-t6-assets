#!/usr/bin/env python3
"""Fail-closed Wayback probe for the exact historical retail T6 MP executable.

The project already pins the authoritative executable by full byte length and
SHA-256.  An independent historical analysis report also exposes its SHA-1,
which is useful because Plutonium's updater CDN addresses file objects by SHA-1.
This probe searches only exact content-addressed object URLs in the Internet
Archive CDX index and accepts recovered bytes only if *all* pinned identities
agree.

A zero-match result is a bounded negative control over the queried Wayback URL
universe, never a global absence claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_BYTES = 12_850_328
EXPECTED_SHA1 = "44eba16d0d9c66f40637611137affbe6b0364f20"
EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
USER_AGENT = "bo2-t6-assets-retail-exe-wayback-probe/1"
CDX = "https://web.archive.org/cdx/search/cdx"
OBJECT_PATH = f"updater/prod/files/{EXPECTED_SHA1}"
CANDIDATE_URLS = [
    f"https://cdn.plutoniummod.com/{OBJECT_PATH}",
    f"http://cdn.plutoniummod.com/{OBJECT_PATH}",
    f"https://cdn.plutonium.pw/{OBJECT_PATH}",
    f"http://cdn.plutonium.pw/{OBJECT_PATH}",
]


class ProbeError(RuntimeError):
    pass


def fetch(url: str, *, timeout: int = 60, retries: int = 4, max_bytes: int | None = None) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise ProbeError(f"HTTP {response.status}")
                raw = response.read() if max_bytes is None else response.read(max_bytes + 1)
                if max_bytes is not None and len(raw) > max_bytes:
                    raise ProbeError(f"response exceeded {max_bytes} bytes")
                return raw
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 8))
    raise ProbeError(f"failed to fetch {url}: {last}")


def cdx_rows(original: str) -> tuple[str, list[dict[str, str]]]:
    query = urllib.parse.urlencode({
        "url": original,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest,length",
        "filter": "statuscode:200",
        "collapse": "digest",
    })
    url = f"{CDX}?{query}"
    try:
        obj = json.loads(fetch(url, timeout=60, max_bytes=4 << 20).decode("utf-8"))
    except Exception as exc:
        return url, [{"probeError": str(exc)}]
    if not isinstance(obj, list) or not obj:
        return url, []
    header = obj[0]
    if not isinstance(header, list):
        raise ProbeError(f"CDX header invalid for {original}")
    out: list[dict[str, str]] = []
    for raw in obj[1:]:
        if not isinstance(raw, list) or len(raw) != len(header):
            raise ProbeError(f"CDX row invalid for {original}: {raw!r}")
        out.append({str(k): str(v) for k, v in zip(header, raw)})
    return url, out


def sha1(raw: bytes) -> str:
    return hashlib.sha1(raw).hexdigest()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--exe-out", type=Path)
    args = ap.parse_args()

    candidate_docs: list[dict[str, Any]] = []
    exact: list[dict[str, Any]] = []
    exact_bytes: bytes | None = None

    for original in CANDIDATE_URLS:
        cdx_url, rows = cdx_rows(original)
        doc: dict[str, Any] = {
            "originalUrl": original,
            "cdxUrl": cdx_url,
            "snapshotCount": 0,
            "snapshots": [],
        }
        if rows and "probeError" in rows[0]:
            doc["cdxError"] = rows[0]["probeError"]
            candidate_docs.append(doc)
            continue
        doc["snapshotCount"] = len(rows)
        for row in rows:
            timestamp = row.get("timestamp")
            archived_original = row.get("original") or original
            if not timestamp or len(timestamp) != 14 or not timestamp.isdigit():
                raise ProbeError(f"invalid CDX timestamp: {row!r}")
            replay = f"https://web.archive.org/web/{timestamp}id_/{archived_original}"
            observed: dict[str, Any] = {"cdx": row, "replayUrl": replay}
            try:
                raw = fetch(replay, timeout=120, retries=3, max_bytes=EXPECTED_BYTES + (1 << 20))
                observed.update({
                    "actualBytes": len(raw),
                    "actualSha1": sha1(raw),
                    "actualSha256": sha256(raw),
                })
                observed["exactExpectedRetail"] = (
                    len(raw) == EXPECTED_BYTES
                    and observed["actualSha1"] == EXPECTED_SHA1
                    and observed["actualSha256"] == EXPECTED_SHA256
                )
                if observed["exactExpectedRetail"]:
                    exact.append({
                        "originalUrl": original,
                        "timestamp": timestamp,
                        "replayUrl": replay,
                        "actualBytes": len(raw),
                        "sha1": observed["actualSha1"],
                        "sha256": observed["actualSha256"],
                    })
                    if exact_bytes is None:
                        exact_bytes = raw
                    elif raw != exact_bytes:
                        raise ProbeError("multiple exact-identity snapshots have differing bytes")
            except Exception as exc:
                observed["fetchError"] = str(exc)
                observed["exactExpectedRetail"] = False
            doc["snapshots"].append(observed)
        candidate_docs.append(doc)

    if args.exe_out is not None and exact_bytes is not None:
        args.exe_out.parent.mkdir(parents=True, exist_ok=True)
        args.exe_out.write_bytes(exact_bytes)

    result = {
        "format": "t6-retail-exe-wayback-probe-v1",
        "expectedRetailIdentity": {
            "bytes": EXPECTED_BYTES,
            "sha1": EXPECTED_SHA1,
            "sha256": EXPECTED_SHA256,
        },
        "candidateObjectUrls": CANDIDATE_URLS,
        "candidates": candidate_docs,
        "exactMatchCount": len(exact),
        "exactMatches": exact,
        "proofBoundary": (
            "Only exact SHA-1-addressed Plutonium updater object URLs on the four retained HTTP/HTTPS "
            "origins are queried through the current Internet Archive CDX/replay service. Recovered bytes "
            "are authoritative only after exact byte length, SHA-1, and full SHA-256 all agree. Zero matches "
            "are a bounded Wayback negative control, not a global absence claim."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "exactMatchCount": len(exact),
        "snapshotCounts": {d["originalUrl"]: d["snapshotCount"] for d in candidate_docs},
        "errors": {d["originalUrl"]: d.get("cdxError") for d in candidate_docs if d.get("cdxError")},
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
