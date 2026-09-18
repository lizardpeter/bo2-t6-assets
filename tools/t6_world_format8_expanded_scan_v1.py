#!/usr/bin/env python3
"""Scan one exact expanded T6 XFile for strict inline TechniqueSet format-8 bodies.

This reuses the established strict post-XAsset-table classifier from
t6_retail_world_format_8_absence_census_v1. The scan is a fixture-discovery
instrument. A format-8 hit is not by itself a world-geometry ownership proof.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

import t6_retail_world_format_8_absence_census_v1 as retained

FORMAT = "t6-world-format8-expanded-scan-v1"


def digest(path: Path) -> tuple[int, str]:
    raw = path.read_bytes()
    return len(raw), hashlib.sha256(raw).hexdigest()


def build(zone: str, source: Path, expanded: Path) -> dict:
    source_bytes, source_sha = digest(source)
    raw = expanded.read_bytes()
    expanded_sha = hashlib.sha256(raw).hexdigest()

    blocks, assets, start = retained.front(raw)
    rows = retained.scan(raw, blocks, start)
    hist = collections.Counter(fmt for _, fmt, _ in rows)
    hits = [
        {"start": int(offset), "name": name}
        for offset, fmt, name in rows
        if int(fmt) == 8
    ]

    return {
        "format": FORMAT,
        "zone": zone,
        "sourceFastfile": {
            "path": str(source),
            "bytes": source_bytes,
            "sha256": source_sha,
        },
        "expanded": {
            "path": str(expanded),
            "bytes": len(raw),
            "sha256": expanded_sha,
        },
        "assetCount": len(assets),
        "scanStartAfterXAssetTable": start,
        "strongInlineTechniqueSetCount": len(rows),
        "formatDistribution": {str(k): v for k, v in sorted(hist.items())},
        "format8StrongInlineHitCount": len(hits),
        "format8StrongInlineHits": hits,
        "classifier": "strict post-XAsset-table inline MaterialTechniqueSet body",
        "proofBoundary": (
            "The source FastFile identity is recorded exactly and the expanded bytes are scanned "
            "with the retained strict inline TechniqueSet classifier. A format-8 hit is a candidate "
            "for direct material-bound/raw allocation proof, not automatic GfxWorld use. Zero hits "
            "prove only absence from this classifier in this one exact expanded XFile."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True)
    ap.add_argument("--source-fastfile", type=Path, required=True)
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    doc = build(args.zone, args.source_fastfile, args.expanded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "zone": doc["zone"],
        "sourceBytes": doc["sourceFastfile"]["bytes"],
        "sourceSha256": doc["sourceFastfile"]["sha256"],
        "expandedBytes": doc["expanded"]["bytes"],
        "expandedSha256": doc["expanded"]["sha256"],
        "strongInlineTechniqueSetCount": doc["strongInlineTechniqueSetCount"],
        "formatDistribution": doc["formatDistribution"],
        "format8StrongInlineHitCount": doc["format8StrongInlineHitCount"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
