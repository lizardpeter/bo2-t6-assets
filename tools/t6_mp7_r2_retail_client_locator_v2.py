#!/usr/bin/env python3
"""Locate the exact pinned retail T6 MP client without weakening identity.

Two source universes are probed independently:
1. the historical Plutonium archive endpoint used by the earlier census; and
2. the current production CDN manifest used by mxve/plutonium-updater.rs.

A same-name or same-size t6mp.exe is never promoted.  Exact retail equivalence
requires both 12,850,328 bytes and SHA-256
11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1.

Historical endpoint failure/404 is retained as endpoint status, not converted
into an archive-absence claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

FORMAT = "t6-mp7-r2-retail-client-locator-v2"
HISTORICAL_REVISIONS = "https://plutonium-archive.getserve.rs/revisions.json"
CURRENT_INFO = "https://cdn.plutoniummod.com/updater/prod/info.json"
EXPECTED_BYTES = 12_850_328
EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
TARGET = "games/t6mp.exe"
UA = "bo2-t6-assets-mp7-retail-client-locator/2"


class LocatorError(RuntimeError):
    pass


def _request(url: str, *, timeout: int = 60) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return int(response.status), response.read(), {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}


def _request_retry(url: str, *, attempts: int = 5, timeout: int = 60) -> tuple[int, bytes, dict[str, str]]:
    last: Exception | None = None
    for i in range(attempts):
        try:
            status, body, headers = _request(url, timeout=timeout)
            if status < 500 or i + 1 == attempts:
                return status, body, headers
        except Exception as exc:
            last = exc
        if i + 1 < attempts:
            time.sleep(min(2**i, 8))
    raise LocatorError(f"request failed for {url}: {last}")


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(raw: bytes, label: str) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise LocatorError(f"{label}: invalid JSON: {exc}") from exc


def probe_historical() -> dict:
    try:
        status, body, headers = _request_retry(HISTORICAL_REVISIONS)
        doc = {
            "url": HISTORICAL_REVISIONS,
            "httpStatus": status,
            "responseBytes": len(body),
            "contentType": headers.get("content-type"),
            "available": status == 200,
        }
        if status == 200:
            parsed = _json(body, "historical revisions")
            doc["jsonType"] = type(parsed).__name__
            doc["revisionCount"] = len(parsed) if isinstance(parsed, list) else None
        else:
            doc["classification"] = "endpoint_unavailable_or_retired; no archive absence claim"
        return doc
    except Exception as exc:
        return {
            "url": HISTORICAL_REVISIONS,
            "available": False,
            "requestError": repr(exc),
            "classification": "endpoint probe failure; no archive absence claim",
        }


def probe_current(out_dir: Path) -> dict:
    status, body, headers = _request_retry(CURRENT_INFO)
    if status != 200:
        return {
            "infoUrl": CURRENT_INFO,
            "httpStatus": status,
            "responseBytes": len(body),
            "available": False,
            "classification": "current CDN manifest unavailable; no client identity claim",
        }
    info = _json(body, "current production info")
    if not isinstance(info, dict):
        raise LocatorError("current production info is not an object")
    base = info.get("baseUrl")
    files = info.get("files")
    revision = info.get("revision")
    product = info.get("product")
    if not isinstance(base, str) or not base.startswith("https://"):
        raise LocatorError(f"invalid current baseUrl {base!r}")
    if not isinstance(files, list):
        raise LocatorError("current files is not an array")

    matches: list[dict] = []
    for raw in files:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not isinstance(name, str):
            continue
        normalized = name.replace("\\", "/").lower()
        if normalized != TARGET and not normalized.endswith("/t6mp.exe"):
            continue
        size = raw.get("size")
        sha1 = raw.get("hash")
        if not isinstance(size, int) or size < 0:
            raise LocatorError(f"invalid size for {name!r}: {size!r}")
        if not isinstance(sha1, str) or len(sha1) != 40:
            raise LocatorError(f"invalid SHA-1 for {name!r}: {sha1!r}")
        int(sha1, 16)
        matches.append({"name": name, "size": size, "sha1": sha1.lower(), "objectUrl": base + sha1})

    result = {
        "infoUrl": CURRENT_INFO,
        "httpStatus": status,
        "available": True,
        "product": product,
        "revision": revision,
        "fileCount": len(files),
        "baseUrl": base,
        "targetMatchCount": len(matches),
        "targetRecords": matches,
        "downloadedTargets": [],
    }
    for rec in matches:
        status2, raw, headers2 = _request_retry(rec["objectUrl"], attempts=5, timeout=120)
        row = {**rec, "httpStatus": status2, "responseBytes": len(raw), "contentType": headers2.get("content-type")}
        if status2 == 200:
            row["actualSha1"] = _sha1(raw)
            row["actualSha256"] = _sha256(raw)
            row["sha1Exact"] = row["actualSha1"] == rec["sha1"]
            row["sizeExactMetadata"] = len(raw) == rec["size"]
            row["mz"] = raw[:2] == b"MZ"
            row["exactExpectedRetail"] = len(raw) == EXPECTED_BYTES and row["actualSha256"] == EXPECTED_SHA256
            if row["sha1Exact"] and row["sizeExactMetadata"]:
                p = out_dir / (Path(rec["name"]).name + ".current")
                p.write_bytes(raw)
                row["retainedObject"] = p.name
        else:
            row["exactExpectedRetail"] = False
        result["downloadedTargets"].append(row)
    result["exactExpectedRetailMatchCount"] = sum(bool(x.get("exactExpectedRetail")) for x in result["downloadedTargets"])
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    historical = probe_historical()
    fatal = None
    try:
        current = probe_current(args.out.parent)
    except Exception as exc:
        current = {"infoUrl": CURRENT_INFO, "available": False, "fatalError": repr(exc)}
        fatal = repr(exc)

    exact_rows = [x for x in current.get("downloadedTargets", []) if x.get("exactExpectedRetail")]
    result = {
        "format": FORMAT,
        "expectedRetailIdentity": {"bytes": EXPECTED_BYTES, "sha256": EXPECTED_SHA256},
        "target": TARGET,
        "historicalArchiveEndpoint": historical,
        "currentProductionCdn": current,
        "exactRetailMatches": exact_rows,
        "exactRetailMatchCount": len(exact_rows),
        "authoritativeExactRetailLocated": len(exact_rows) == 1,
        "proofBoundary": (
            "A client is retail-authoritative only when downloaded bytes match both the exact pinned byte length and "
            "SHA-256. Same name, current CDN membership, CDN SHA-1, or same size alone are insufficient. Historical "
            "endpoint unavailability is only an endpoint-status result and is not an archive-absence or global-absence claim."
        ),
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.out.write_text(payload, encoding="utf-8")
    print(json.dumps({
        "historicalAvailable": historical.get("available"),
        "currentAvailable": current.get("available"),
        "currentRevision": current.get("revision"),
        "targetMatchCount": current.get("targetMatchCount"),
        "exactRetailMatchCount": len(exact_rows),
        "manifestSha256": _sha256(payload.encode()),
    }, sort_keys=True))
    if fatal:
        raise SystemExit(fatal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
