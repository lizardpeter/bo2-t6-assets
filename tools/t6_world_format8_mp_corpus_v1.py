#!/usr/bin/env python3
"""Aggregate exact per-XFile format-8 scans across the 31 retail MP targets."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

FORMAT = "t6-retail-mp-format8-corpus-census-v1"
SCAN_FORMAT = "t6-world-format8-expanded-scan-v1"
TARGET_FORMAT = "t6-retail-mp-world-format-targets-v1"


class CorpusError(RuntimeError):
    pass


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CorpusError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusError(f"{path}: top level is not object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(targets: dict, scan_root: Path) -> dict:
    if targets.get("format") != TARGET_FORMAT:
        raise CorpusError(f"unexpected target format {targets.get('format')!r}")
    maps = targets.get("maps")
    if not isinstance(maps, list) or len(maps) != 31:
        raise CorpusError(f"expected exactly 31 MP target rows, got {len(maps or [])}")

    expected = {}
    for row in maps:
        zone = str(row.get("zone") or "")
        if not zone or zone in expected:
            raise CorpusError(f"empty/duplicate target zone {zone!r}")
        expected[zone] = row

    scan_files = sorted(scan_root.glob("*.json"))
    scans = {}
    for path in scan_files:
        row = load(path)
        if row.get("format") != SCAN_FORMAT:
            raise CorpusError(f"{path}: unexpected scan format {row.get('format')!r}")
        zone = str(row.get("zone") or "")
        if not zone or zone in scans:
            raise CorpusError(f"empty/duplicate scan zone {zone!r}")
        scans[zone] = (row, path)

    if set(scans) != set(expected):
        missing = sorted(set(expected) - set(scans))
        extra = sorted(set(scans) - set(expected))
        raise CorpusError(f"scan universe mismatch missing={missing} extra={extra}")

    aggregate = collections.Counter()
    total_strong = 0
    format8_hits = []
    rows = []

    for zone in sorted(expected):
        target = expected[zone]
        scan, path = scans[zone]
        source = scan.get("sourceFastfile") or {}

        expected_bytes = int(target.get("bytes", -1))
        expected_sha = str(target.get("sha256") or "").lower()
        actual_bytes = int(source.get("bytes", -1))
        actual_sha = str(source.get("sha256") or "").lower()
        if actual_bytes != expected_bytes or actual_sha != expected_sha:
            raise CorpusError(
                f"{zone}: exact source mismatch bytes {actual_bytes}/{expected_bytes} "
                f"sha {actual_sha}/{expected_sha}"
            )

        hist = scan.get("formatDistribution")
        if not isinstance(hist, dict):
            raise CorpusError(f"{zone}: missing formatDistribution")
        for key, value in hist.items():
            fmt = int(key)
            count = int(value)
            if not 0 <= fmt <= 8 or count < 0:
                raise CorpusError(f"{zone}: invalid histogram row {key!r}:{value!r}")
            aggregate[fmt] += count

        hit_count = int(scan.get("format8StrongInlineHitCount", -1))
        hits = scan.get("format8StrongInlineHits")
        if not isinstance(hits, list) or hit_count != len(hits):
            raise CorpusError(f"{zone}: format-8 hit count mismatch")
        for hit in hits:
            format8_hits.append({"zone": zone, **hit})

        strong = int(scan.get("strongInlineTechniqueSetCount", -1))
        if strong < 0 or strong != sum(int(x) for x in hist.values()):
            raise CorpusError(f"{zone}: strong TechniqueSet count mismatch")

        total_strong += strong
        rows.append({
            "zone": zone,
            "sourceFastfile": {
                "path": str(target.get("path") or ""),
                "bytes": expected_bytes,
                "sha256": expected_sha,
            },
            "expanded": scan.get("expanded"),
            "assetCount": scan.get("assetCount"),
            "scanStartAfterXAssetTable": scan.get("scanStartAfterXAssetTable"),
            "strongInlineTechniqueSetCount": strong,
            "formatDistribution": {str(k): int(v) for k, v in sorted((int(k), v) for k, v in hist.items())},
            "format8StrongInlineHitCount": hit_count,
            "format8StrongInlineHits": hits,
            "scanManifestSha256": sha256(path),
        })

    no_hits = len(format8_hits) == 0
    return {
        "format": FORMAT,
        "targetFormat": 8,
        "expectedVd1Stride": 20,
        "targetMapCount": 31,
        "scannedMapCount": len(rows),
        "allTargetFastfileIdentitiesMatched": True,
        "strongInlineTechniqueSetCount": total_strong,
        "formatDistribution": {str(k): v for k, v in sorted(aggregate.items())},
        "format8StrongInlineHitCount": len(format8_hits),
        "format8StrongInlineHits": format8_hits,
        "strictInlineAbsenceAcrossAll31MpMaps": no_hits,
        "maps": rows,
        "proofBoundary": {
            "proven": (
                "All 31 SHA-pinned retail MP FastFiles from T6_RETAIL_MP_WORLD_FORMAT_TARGETS_V1 "
                "were independently identity-checked after download and their deterministic expanded "
                "XFiles were scanned after the XAsset table with the retained strict inline "
                "MaterialTechniqueSet classifier."
            ),
            "ifHit": (
                "Any worldVertFormat=8 TechniqueSet body is only a candidate fixture. Promotion still "
                "requires direct material-bound or standalone raw vd1 allocation evidence at the "
                "source-closed 20-byte stride with no contradiction."
            ),
            "ifNoHit": (
                "Zero strict inline hits is a bounded complete-MP-corpus absence result only. It does "
                "not establish absence from packed/non-inline TechniqueSet representations, Zombies/SP/DLC "
                "corpora, or universal T6, and cannot by itself mark format 8 export-enabled."
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--scan-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    doc = build(load(args.targets), args.scan_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "scannedMapCount": doc["scannedMapCount"],
        "strongInlineTechniqueSetCount": doc["strongInlineTechniqueSetCount"],
        "formatDistribution": doc["formatDistribution"],
        "format8StrongInlineHitCount": doc["format8StrongInlineHitCount"],
        "strictInlineAbsenceAcrossAll31MpMaps": doc["strictInlineAbsenceAcrossAll31MpMaps"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
