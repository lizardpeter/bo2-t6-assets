#!/usr/bin/env python3
"""Normalize an exact retained family of T6 XAnimParts in one deterministic pass.

Primary use: Stage 18D `mp7_base_xanim_raw.json` -> 23 independent
`t6-xanim-normalized-v1` sidecars.

The family manifest preserves:
- source expanded-stream SHA-256;
- raw asset start and raw-walker serialized SHA where available;
- normalized asset serialized SHA;
- normalized JSON file SHA;
- frame/track/notetrack counts;
- exact source-name equality;
- flat-pool exhaustion through the underlying normalizer.

Any member failure aborts the whole family. There is no partial-success mode and
no fallback animation fabrication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from t6_xanim_normalize_v1 import normalize

FORMAT = "t6-xanim-family-normalized-v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return value or "xanim"


def load_raw_family(path: Path) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, list):
        raise ValueError("raw family JSON must be the Stage 18D list form")
    rows = []
    seen_names = set()
    seen_offsets = set()
    for index, row in enumerate(doc):
        if not isinstance(row, dict):
            raise ValueError(f"raw family row {index} is not an object")
        name = row.get("name")
        start = row.get("raw_struct_offset")
        if not isinstance(name, str) or not name:
            raise ValueError(f"raw family row {index} lacks exact name")
        if not isinstance(start, int) or start < 0:
            raise ValueError(f"{name}: invalid raw_struct_offset {start!r}")
        if name in seen_names:
            raise ValueError(f"duplicate XAnim name {name}")
        if start in seen_offsets:
            raise ValueError(f"duplicate XAnim raw offset {start}")
        seen_names.add(name)
        seen_offsets.add(start)
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--raw-family", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--expected-count", type=int)
    ap.add_argument("--expected-source-sha256")
    args = ap.parse_args()

    data = args.stream.read_bytes()
    source_sha = sha256_bytes(data)
    if args.expected_source_sha256 and source_sha.lower() != args.expected_source_sha256.lower():
        raise ValueError(
            f"expanded stream SHA mismatch: {source_sha} != {args.expected_source_sha256.lower()}"
        )

    rows = load_raw_family(args.raw_family)
    if args.prefix:
        wrong = [r["name"] for r in rows if not r["name"].startswith(args.prefix)]
        if wrong:
            raise ValueError(f"raw family contains names outside prefix {args.prefix!r}: {wrong}")
    if args.expected_count is not None and len(rows) != args.expected_count:
        raise ValueError(f"family count {len(rows)} != expected {args.expected_count}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    members = []
    output_names = set()
    for row in rows:
        name = row["name"]
        start = int(row["raw_struct_offset"])
        raw_walk = row.get("walk") if isinstance(row.get("walk"), dict) else {}
        raw_walk_status = raw_walk.get("status")
        if raw_walk_status is not None and raw_walk_status != "exact":
            raise ValueError(f"{name}: Stage 18D raw walk is not exact: {raw_walk_status}")

        normalized = normalize(data, start)
        if normalized.get("format") != "t6-xanim-normalized-v1":
            raise ValueError(f"{name}: unexpected normalized format {normalized.get('format')!r}")
        if normalized.get("name") != name:
            raise ValueError(f"{name}: normalized identity changed to {normalized.get('name')!r}")
        if int(normalized.get("assetFixedStart", -1)) != start:
            raise ValueError(f"{name}: normalized fixed start changed")
        if normalized.get("allFlatPoolsExhausted") is not True:
            raise ValueError(f"{name}: normalized flat pools are not exhausted")

        raw_serialized_sha = raw_walk.get("exact_serialized_sha256")
        normalized_serialized_sha = normalized.get("assetSerializedSha256")
        if raw_serialized_sha and normalized_serialized_sha != raw_serialized_sha:
            raise ValueError(
                f"{name}: raw/normalized serialized SHA mismatch "
                f"{raw_serialized_sha} != {normalized_serialized_sha}"
            )

        filename = safe_name(name) + ".json"
        if filename in output_names:
            raise ValueError(f"normalized output filename collision: {filename}")
        output_names.add(filename)
        out_path = args.outdir / filename
        text = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
        out_path.write_text(text, encoding="utf-8")

        header = normalized.get("header", {})
        tracks = normalized.get("boneTracks", [])
        notifies = normalized.get("notifies", [])
        members.append({
            "name": name,
            "rawStructOffset": start,
            "rawWalkStatus": raw_walk_status,
            "rawSerializedSha256": raw_serialized_sha,
            "normalizedSerializedSha256": normalized_serialized_sha,
            "serializedHashMatchesRawWalk": (
                raw_serialized_sha is None or normalized_serialized_sha == raw_serialized_sha
            ),
            "outputPath": str(out_path),
            "outputBytes": len(text.encode("utf-8")),
            "outputSha256": sha256_file(out_path),
            "numFrames": header.get("numframes"),
            "frameRate": header.get("framerate"),
            "boneTrackCount": len(tracks),
            "notifyCount": len(notifies),
            "hasDelta": normalized.get("delta") is not None,
            "allFlatPoolsExhausted": True,
        })

    manifest = {
        "format": FORMAT,
        "source": {
            "expandedPath": str(args.stream),
            "expandedBytes": len(data),
            "expandedSha256": source_sha,
            "rawFamilyPath": str(args.raw_family),
            "rawFamilySha256": sha256_file(args.raw_family),
        },
        "rules": {
            "allMembersRequired": True,
            "exactNamePreserved": True,
            "assetFixedStartPreserved": True,
            "rawSerializedHashComparedWhenAvailable": True,
            "allFlatPoolsMustBeExhausted": True,
            "noFallbackAnimation": True,
        },
        "summary": {
            "prefix": args.prefix,
            "memberCount": len(members),
            "expectedCount": args.expected_count,
            "allMembersNormalized": len(members) == len(rows),
            "allRawSerializedHashesMatched": all(
                m["serializedHashMatchesRawWalk"] for m in members
            ),
            "allFlatPoolsExhausted": all(m["allFlatPoolsExhausted"] for m in members),
        },
        "members": members,
    }
    manifest_path = args.outdir / "family_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        **manifest["summary"],
        "manifest": str(manifest_path),
        "manifestSha256": sha256_file(manifest_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
