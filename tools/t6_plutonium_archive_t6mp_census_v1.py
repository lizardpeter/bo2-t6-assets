#!/usr/bin/env python3
"""Fail-closed census of historical Plutonium T6 MP client objects.

The archive protocol is source-derived from mxve/plutonium-updater.rs v0.4.3:
  https://plutonium-archive.getserve.rs/revisions.json
  https://plutonium-archive.getserve.rs/<revision>/info.json
Each info.json supplies baseUrl and SHA-1-addressed files.

This tool does not treat an archive client as retail-equivalent merely because
it is named games/t6mp.exe. Only exact byte length + SHA-256 can match the
project's pinned historical retail executable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

FORMAT = "t6-plutonium-archive-t6mp-census-v1"
ARCHIVE_ROOT = "https://plutonium-archive.getserve.rs"
REVISIONS_URL = f"{ARCHIVE_ROOT}/revisions.json"
EXPECTED_RETAIL_BYTES = 12_850_328
EXPECTED_RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
TARGET_NAME = "games/t6mp.exe"
USER_AGENT = "bo2-t6-assets-archive-client-census/1"


class ProofError(RuntimeError):
    pass


def require(cond: bool, message: str) -> None:
    if not cond:
        raise ProofError(message)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_bytes(url: str, retries: int = 5, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                require(response.status == 200, f"HTTP {response.status} for {url}")
                return response.read()
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 8))
    raise ProofError(f"failed to fetch {url}: {last}")


def fetch_json(url: str) -> object:
    raw = fetch_bytes(url)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ProofError(f"invalid JSON at {url}: {exc}") from exc


def normalize_file_record(record: object, revision: int, base_url: str) -> dict:
    require(isinstance(record, dict), f"revision {revision}: file record is not object")
    name = record.get("name")
    size = record.get("size")
    digest = record.get("hash")
    require(isinstance(name, str), f"revision {revision}: file name invalid")
    require(isinstance(size, int) and size >= 0, f"revision {revision}: file size invalid for {name}")
    require(isinstance(digest, str) and len(digest) == 40, f"revision {revision}: SHA-1 invalid for {name}")
    int(digest, 16)
    return {
        "revision": revision,
        "name": name,
        "size": size,
        "sha1": digest.lower(),
        "baseUrl": base_url,
        "objectUrl": f"{base_url}{digest}",
    }


def census(download_exact_size: bool = True) -> dict:
    revisions_obj = fetch_json(REVISIONS_URL)
    require(isinstance(revisions_obj, list) and revisions_obj, "archive revisions list empty/invalid")
    revisions: list[int] = []
    for value in revisions_obj:
        require(isinstance(value, int) and 0 < value <= 65535, f"invalid archive revision {value!r}")
        revisions.append(value)
    require(len(revisions) == len(set(revisions)), "duplicate archive revisions")
    revisions.sort()

    revision_records: list[dict] = []
    target_records: list[dict] = []
    for revision in revisions:
        info_url = f"{ARCHIVE_ROOT}/{revision}/info.json"
        info = fetch_json(info_url)
        require(isinstance(info, dict), f"revision {revision}: info is not object")
        info_revision = info.get("revision")
        base_url = info.get("baseUrl")
        files = info.get("files")
        require(info_revision == revision, f"revision {revision}: embedded revision mismatch {info_revision!r}")
        require(isinstance(base_url, str) and base_url.startswith("https://"), f"revision {revision}: invalid baseUrl")
        require(isinstance(files, list), f"revision {revision}: files is not list")
        matches = []
        for raw_record in files:
            rec = normalize_file_record(raw_record, revision, base_url)
            if rec["name"].replace("\\", "/").lower() == TARGET_NAME:
                matches.append(rec)
        require(len(matches) <= 1, f"revision {revision}: duplicate {TARGET_NAME} entries")
        target_records.extend(matches)
        revision_records.append({
            "revision": revision,
            "infoUrl": info_url,
            "product": info.get("product"),
            "fileCount": len(files),
            "t6mp": matches[0] if matches else None,
        })
        print(json.dumps({"revision": revision, "t6mp": matches[0] if matches else None}, sort_keys=True), flush=True)

    unique_map: dict[tuple[int, str, str], dict] = {}
    for rec in target_records:
        key = (rec["size"], rec["sha1"], rec["objectUrl"])
        if key not in unique_map:
            unique_map[key] = {
                "size": rec["size"], "sha1": rec["sha1"], "objectUrl": rec["objectUrl"], "revisions": []
            }
        unique_map[key]["revisions"].append(rec["revision"])
    unique_objects = sorted(unique_map.values(), key=lambda x: (x["size"], x["sha1"], x["objectUrl"]))
    exact_size_objects = [obj for obj in unique_objects if obj["size"] == EXPECTED_RETAIL_BYTES]
    downloaded = []
    if download_exact_size:
        for obj in exact_size_objects:
            raw = fetch_bytes(obj["objectUrl"], retries=5, timeout=120)
            require(len(raw) == obj["size"], f"object length mismatch {obj['sha1']}")
            actual_sha1 = sha1(raw)
            require(actual_sha1 == obj["sha1"], f"object SHA-1 mismatch {obj['sha1']} -> {actual_sha1}")
            actual_sha256 = sha256(raw)
            downloaded.append({**obj, "sha256": actual_sha256, "mz": raw[:2] == b"MZ", "exactExpectedRetail": actual_sha256 == EXPECTED_RETAIL_SHA256})

    exact_matches = [obj for obj in downloaded if obj["exactExpectedRetail"]]
    revisions_with_target = sorted({rec["revision"] for rec in target_records})
    revisions_without_target = [rev for rev in revisions if rev not in set(revisions_with_target)]
    return {
        "format": FORMAT,
        "authority": "complete current revision census of the source-derived Plutonium updater archive endpoint",
        "archive": {"root": ARCHIVE_ROOT, "revisionsUrl": REVISIONS_URL, "revisionCount": len(revisions), "firstRevision": revisions[0], "lastRevision": revisions[-1]},
        "expectedRetailIdentity": {"bytes": EXPECTED_RETAIL_BYTES, "sha256": EXPECTED_RETAIL_SHA256},
        "target": TARGET_NAME,
        "revisionRecords": revision_records,
        "revisionsWithTargetCount": len(revisions_with_target),
        "revisionsWithoutTarget": revisions_without_target,
        "targetOccurrenceCount": len(target_records),
        "uniqueTargetObjectCount": len(unique_objects),
        "uniqueTargetObjects": unique_objects,
        "exactExpectedSizeObjectCount": len(exact_size_objects),
        "downloadedExactSizeObjects": downloaded,
        "exactExpectedRetailMatches": exact_matches,
        "proofBoundary": "This proves only what is present in the revision set returned by the current source-derived Plutonium archive endpoint. A same-name client is not retail-equivalent unless exact byte length and SHA-256 match the pinned retail identity. Archive absence is not a global absence claim."
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    result = census(download_exact_size=not args.metadata_only)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "revisionCount": result["archive"]["revisionCount"],
        "revisionsWithTargetCount": result["revisionsWithTargetCount"],
        "uniqueTargetObjectCount": result["uniqueTargetObjectCount"],
        "exactExpectedSizeObjectCount": result["exactExpectedSizeObjectCount"],
        "exactExpectedRetailMatchCount": len(result["exactExpectedRetailMatches"]),
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
