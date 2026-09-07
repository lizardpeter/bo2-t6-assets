#!/usr/bin/env python3
"""Fail-closed remote ZIP source probe with explicit Range-refusal state.

This is a thin policy wrapper around t6_public_zip_ff_catalog_probe_v2. It keeps
all ZIP/ZIP64 structural validation strict, but treats one environmental case as
nonfatal source evidence: an archive-byte GET that ignores the explicit Range
request and returns a non-206 response. The response body is never read in that
case. The catalog is emitted as unavailable-from-this-source and completeness
must remain false rather than turning a CDN capability issue into a parser
failure.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import t6_public_zip_ff_catalog_probe_v2 as base

RANGE_REFUSAL_RE = re.compile(r"range request returned status ([0-9]+), expected 206\Z")
FORMAT = "t6-public-zip-ff-catalog-probe-v3"


def write_rows(path: Path, wanted: set[str], url: str, found: dict[str, dict] | None = None) -> None:
    found = found or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for name in sorted(wanted):
            row = found.get(name)
            if row is None:
                f.write(f"{name}\tunavailable\t-\t-\t-\t-\t-\t-\t{url}\n")
            else:
                f.write(
                    f"{name}\tpresent\t{row['uncompressedBytes']}\t{row['crc32']}\t"
                    f"{row['compressedBytes']}\t{row['method']}\t{row['flags']}\t"
                    f"{row['localHeaderOffset']}\t{url}\n"
                )


def write_meta(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, sort_keys=True))


def safety(loc: dict | None = None) -> dict:
    return {
        "sizeDiscoveryBodylessHead": True,
        "requires206BeforeBodyRead": True,
        "maxCentralReadBytes": base.MAX_CENTRAL_BYTES,
        "archivePayloadDownloaded": False,
        "rangeRefusalHandledAsUnavailableSource": True,
        "zip64MetadataReadFromValidatedTail": bool(loc and loc.get("metadataReadFromTail")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--paths", type=Path, required=True)
    ap.add_argument("--out-tsv", type=Path, required=True)
    ap.add_argument("--out-meta", type=Path, required=True)
    a = ap.parse_args()

    wanted = {line.strip() for line in a.paths.read_text(encoding="utf-8").splitlines() if line.strip()}
    if not wanted:
        raise SystemExit("empty wanted path set")

    ua = "bo2-t6-assets-safe-zip-range-probe/3"
    total = base.remote_size(a.url, ua)
    try:
        loc = base.parse_directory_location(a.url, total, ua)
        cd_size = int(loc["centralSize"])
        cd_off = int(loc["centralOffset"])
        if cd_size <= 0 or cd_size > base.MAX_CENTRAL_BYTES:
            raise RuntimeError(f"central directory size {cd_size} outside safe range")
        if cd_off < 0 or cd_off + cd_size > total:
            raise RuntimeError("central directory outside remote archive")
        central, _ = base.request(a.url, start=cd_off, end=cd_off + cd_size - 1, user_agent=ua)
        found, parsed = base.parse_central(central, int(loc["entries"]), wanted)
    except RuntimeError as exc:
        match = RANGE_REFUSAL_RE.fullmatch(str(exc))
        if match is None:
            raise
        status = int(match.group(1))
        write_rows(a.out_tsv, wanted, a.url)
        meta = {
            "format": FORMAT,
            "url": a.url,
            "remoteZipBytes": total,
            "catalogPaths": len(wanted),
            "sourceProbeAvailable": False,
            "sourceProbeReason": "rangeUnsupported",
            "rangeFailure": {"httpStatus": status, "message": str(exc)},
            "present": 0,
            "unavailable": len(wanted),
            "directory": None,
            "parsedEntries": None,
            "duplicateCanonicalZonePaths": {},
            "safety": safety(),
            "proofBoundary": [
                "The server refused the explicit byte-range capability required for a safe central-directory-only probe.",
                "No archive payload body was read after the non-206 response was observed.",
                "All catalog rows are unavailable-from-this-source, not proven absent from the archive.",
                "This source cannot contribute to corpus completeness until a safe range-capable endpoint or independently retained bytes are available.",
            ],
        }
        write_meta(a.out_meta, meta)
        return 0

    write_rows(a.out_tsv, wanted, a.url, found)
    meta = {
        "format": FORMAT,
        "url": a.url,
        "remoteZipBytes": total,
        "catalogPaths": len(wanted),
        "sourceProbeAvailable": True,
        "sourceProbeReason": None,
        "rangeFailure": None,
        "present": len(found),
        "unavailable": len(wanted - set(found)),
        "directory": loc,
        **parsed,
        "safety": safety(loc),
        "proofBoundary": [
            "Central-directory presence establishes archive-container availability only.",
            "It does not establish byte identity with a Steam depot manifest or promote XAsset population completeness.",
        ],
    }
    write_meta(a.out_meta, meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
