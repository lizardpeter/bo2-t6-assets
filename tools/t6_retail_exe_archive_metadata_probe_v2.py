#!/usr/bin/env python3
"""Recover the exact pinned BO2 MP executable through archived updater metadata.

Unlike the v1 direct-object probe, this pass does not guess object origins. It
uses two historically source-backed Plutonium revision archive roots, enumerates
archived ``/<revision>/info.json`` manifests through Internet Archive CDX, and
accepts a revision only when its CdnInfo row identifies the exact t6mp SHA-1 and
byte size. The manifest's own ``baseUrl`` then determines the only object URL
that is queried for that revision.

Recovered executable bytes are authoritative only if byte length, SHA-1 and
full SHA-256 all equal the project's existing retail pin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

EXPECTED_BYTES = 12_850_328
EXPECTED_SHA1 = "44eba16d0d9c66f40637611137affbe6b0364f20"
EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
USER_AGENT = "bo2-t6-assets-retail-exe-archive-metadata-probe/2"
CDX = "https://web.archive.org/cdx/search/cdx"
ARCHIVE_ROOTS = (
    "https://plutonium-archive.getserve.rs",
    "https://updater-archive.plutools.pw",
)
INFO_RE = re.compile(r"/(\d+)/info\.json$", re.I)


class ProbeError(RuntimeError):
    pass


def fetch(url: str, *, timeout: int = 60, retries: int = 3, max_bytes: int | None = None) -> bytes:
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
                time.sleep(min(2 ** attempt, 6))
    raise ProbeError(f"failed to fetch {url}: {last}")


def cdx_query(original_pattern: str, *, collapse: str = "urlkey") -> tuple[str, list[dict[str, str]]]:
    query = urllib.parse.urlencode({
        "url": original_pattern,
        "output": "json",
        "fl": "timestamp,original,statuscode,digest,length",
        "filter": "statuscode:200",
        "collapse": collapse,
    })
    url = f"{CDX}?{query}"
    raw = fetch(url, timeout=120, retries=4, max_bytes=16 << 20)
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, list) or not obj:
        return url, []
    header = obj[0]
    if not isinstance(header, list):
        raise ProbeError(f"invalid CDX header for {original_pattern}")
    rows: list[dict[str, str]] = []
    for row in obj[1:]:
        if not isinstance(row, list) or len(row) != len(header):
            raise ProbeError(f"invalid CDX row for {original_pattern}: {row!r}")
        rows.append({str(k): str(v) for k, v in zip(header, row)})
    return url, rows


def replay_url(row: dict[str, str]) -> str:
    ts = row.get("timestamp", "")
    original = row.get("original", "")
    if len(ts) != 14 or not ts.isdigit() or not original:
        raise ProbeError(f"invalid replay row: {row!r}")
    return f"https://web.archive.org/web/{ts}id_/{original}"


def normalized_files(info: Any) -> list[dict[str, Any]]:
    if not isinstance(info, dict):
        return []
    rows = info.get("files")
    return rows if isinstance(rows, list) else []


def target_file_rows(info: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in normalized_files(info):
        if not isinstance(row, dict):
            continue
        sha1_value = str(row.get("hash") or "").lower()
        if sha1_value != EXPECTED_SHA1:
            continue
        try:
            size = int(row.get("size"))
        except Exception:
            size = -1
        name = str(row.get("name") or "")
        out.append({"name": name, "size": size, "hash": sha1_value})
    return out


def exact_identity(raw: bytes) -> dict[str, Any]:
    actual_sha1 = hashlib.sha1(raw).hexdigest()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    return {
        "actualBytes": len(raw),
        "actualSha1": actual_sha1,
        "actualSha256": actual_sha256,
        "exact": (
            len(raw) == EXPECTED_BYTES
            and actual_sha1 == EXPECTED_SHA1
            and actual_sha256 == EXPECTED_SHA256
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--exe-out", type=Path)
    args = ap.parse_args()

    manifest_universe: list[dict[str, Any]] = []
    target_manifests: list[dict[str, Any]] = []
    object_candidates: dict[str, dict[str, Any]] = {}
    root_errors: list[dict[str, str]] = []

    for root in ARCHIVE_ROOTS:
        pattern = f"{root}/*/info.json"
        try:
            cdx_url, rows = cdx_query(pattern, collapse="urlkey")
        except Exception as exc:
            root_errors.append({"root": root, "error": str(exc)})
            continue
        root_doc: dict[str, Any] = {
            "root": root,
            "pattern": pattern,
            "cdxUrl": cdx_url,
            "capturedInfoUrlCount": len(rows),
            "manifestsRead": 0,
            "manifestsFailed": 0,
        }
        for row in rows:
            original = row.get("original", "")
            match = INFO_RE.search(urllib.parse.urlsplit(original).path)
            if not match:
                continue
            revision_from_url = int(match.group(1))
            replay = replay_url(row)
            manifest_doc: dict[str, Any] = {
                "archiveRoot": root,
                "revisionFromUrl": revision_from_url,
                "cdx": row,
                "replayUrl": replay,
            }
            try:
                raw = fetch(replay, timeout=90, retries=3, max_bytes=4 << 20)
                info = json.loads(raw.decode("utf-8"))
                root_doc["manifestsRead"] += 1
                manifest_doc["manifestSha256"] = hashlib.sha256(raw).hexdigest()
                manifest_doc["product"] = info.get("product") if isinstance(info, dict) else None
                manifest_doc["revision"] = info.get("revision") if isinstance(info, dict) else None
                manifest_doc["baseUrl"] = info.get("baseUrl") if isinstance(info, dict) else None
                manifest_doc["fileCount"] = len(normalized_files(info))
                matches = target_file_rows(info)
                manifest_doc["targetSha1Rows"] = matches
                if matches:
                    if any(m["size"] != EXPECTED_BYTES for m in matches):
                        raise ProbeError(
                            f"revision {revision_from_url}: exact SHA-1 appears with unexpected size {matches!r}"
                        )
                    base_url = manifest_doc.get("baseUrl")
                    if not isinstance(base_url, str) or not base_url:
                        raise ProbeError(f"revision {revision_from_url}: target SHA-1 manifest has no baseUrl")
                    if not base_url.endswith("/"):
                        base_url += "/"
                    object_url = urllib.parse.urljoin(base_url, EXPECTED_SHA1)
                    target_doc = dict(manifest_doc)
                    target_doc["derivedObjectUrl"] = object_url
                    target_manifests.append(target_doc)
                    object_candidates.setdefault(object_url, {
                        "objectUrl": object_url,
                        "derivedFrom": [],
                    })["derivedFrom"].append({
                        "archiveRoot": root,
                        "revision": manifest_doc.get("revision"),
                        "revisionFromUrl": revision_from_url,
                        "manifestReplayUrl": replay,
                    })
            except Exception as exc:
                root_doc["manifestsFailed"] += 1
                manifest_doc["readError"] = str(exc)
            manifest_universe.append(manifest_doc)
        manifest_universe.append({"rootSummary": root_doc})

    object_results: list[dict[str, Any]] = []
    recovered: bytes | None = None
    exact_sources: list[dict[str, Any]] = []

    for object_url, candidate in sorted(object_candidates.items()):
        obj_doc = dict(candidate)
        obj_doc["archivedSnapshots"] = []
        try:
            cdx_url, rows = cdx_query(object_url, collapse="digest")
            obj_doc["cdxUrl"] = cdx_url
            obj_doc["snapshotCount"] = len(rows)
            for row in rows:
                replay = replay_url(row)
                snap: dict[str, Any] = {"cdx": row, "replayUrl": replay}
                try:
                    raw = fetch(replay, timeout=120, retries=3, max_bytes=EXPECTED_BYTES + (1 << 20))
                    ident = exact_identity(raw)
                    snap.update(ident)
                    if ident["exact"]:
                        exact_sources.append({
                            "objectUrl": object_url,
                            "replayUrl": replay,
                            **ident,
                        })
                        if recovered is None:
                            recovered = raw
                        elif raw != recovered:
                            raise ProbeError("exact-identity archived object snapshots differ by bytes")
                except Exception as exc:
                    snap["fetchError"] = str(exc)
                    snap["exact"] = False
                obj_doc["archivedSnapshots"].append(snap)
        except Exception as exc:
            obj_doc["cdxError"] = str(exc)
            obj_doc["snapshotCount"] = 0
        object_results.append(obj_doc)

    if recovered is not None and args.exe_out is not None:
        args.exe_out.parent.mkdir(parents=True, exist_ok=True)
        args.exe_out.write_bytes(recovered)

    out = {
        "format": "t6-retail-exe-archive-metadata-probe-v2",
        "expectedRetailIdentity": {
            "bytes": EXPECTED_BYTES,
            "sha1": EXPECTED_SHA1,
            "sha256": EXPECTED_SHA256,
        },
        "historicallySourceBackedArchiveRoots": list(ARCHIVE_ROOTS),
        "rootErrors": root_errors,
        "targetManifestCount": len(target_manifests),
        "targetManifests": target_manifests,
        "derivedObjectCandidateCount": len(object_candidates),
        "derivedObjectResults": object_results,
        "exactRecoveredSnapshotCount": len(exact_sources),
        "exactRecoveredSnapshots": exact_sources,
        "manifestUniverse": manifest_universe,
        "proofBoundary": (
            "Archive roots and /<revision>/info.json behavior are source-backed by historical releases of "
            "mxve/plutonium-updater.rs. A revision becomes relevant only when its archived CdnInfo contains "
            "the exact independent SHA-1 and exact expected byte size. Object URLs are derived only from that "
            "manifest's own baseUrl. Executable bytes are authoritative only after exact length, SHA-1, and "
            "full SHA-256 all agree. Missing captures are bounded archival negatives, not global absence claims."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "rootErrors": root_errors,
        "targetManifestCount": len(target_manifests),
        "derivedObjectCandidateCount": len(object_candidates),
        "exactRecoveredSnapshotCount": len(exact_sources),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
