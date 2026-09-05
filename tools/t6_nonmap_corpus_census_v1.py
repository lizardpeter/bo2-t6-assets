#!/usr/bin/env python3
"""Run a deterministic cross-zone T6 non-map XAsset corpus census v1.

This is the corpus-level driver for the parallel non-map extraction track. It
accepts expanded/decrypted T6 fastfiles, emits one hash-pinned raw inventory per
input using t6_raw_xasset_inventory.py's exact front parser, then runs the
coverage classifier over the retained inventories.

No asset-class presence is inferred from enum definitions or filenames. A type
is considered observed only when it is present in an input zone's XAsset array.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from t6_raw_xasset_inventory import parse_front

FORMAT = "t6-nonmap-corpus-census-v1"
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe(value: str) -> str:
    value = SAFE.sub("_", value).strip("._")
    return value or "zone"


def collect_inputs(values: list[Path], pattern: str, recursive: bool) -> list[Path]:
    found: list[Path] = []
    for raw in values:
        p = raw.expanduser().resolve()
        if p.is_file():
            found.append(p)
            continue
        if not p.is_dir():
            raise FileNotFoundError(p)
        iterator = p.rglob(pattern) if recursive else p.glob(pattern)
        found.extend(x.resolve() for x in iterator if x.is_file())

    unique: list[Path] = []
    seen: set[str] = set()
    for p in sorted(found, key=lambda x: os.fspath(x).lower()):
        key = os.path.normcase(os.fspath(p))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    if not unique:
        raise ValueError("no expanded fastfiles matched")
    return unique


def inventory_one(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    result = parse_front(data)
    result.pop("_blocks", None)
    result["corpus_source"] = {
        "path": str(path),
        "file_name": path.name,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }
    result["format_proof"] = {
        "pointer_bits": 32,
        "offset_block_bit_count": 3,
        "packed_pointer_block_shift": 29,
        "packed_pointer_offset_mask": "0x1FFFFFFF",
        "physical_stream_alignment_rule": "destination XBlock alignment consumes no source bytes",
        "producer": "tools/t6_nonmap_corpus_census_v1.py via t6_raw_xasset_inventory.parse_front",
    }
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return result, raw


def run_coverage(repo_root: Path, inventories: list[Path], out: Path) -> None:
    tool = repo_root / "tools" / "t6_nonmap_asset_coverage_v1.py"
    if not tool.is_file():
        raise FileNotFoundError(tool)
    cmd = [sys.executable, str(tool), *(str(p) for p in inventories), "--out", str(out)]
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
    if proc.returncode:
        if proc.stdout:
            sys.stderr.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise RuntimeError(f"coverage driver failed with code {proc.returncode}")
    if proc.stdout:
        sys.stdout.write(proc.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path,
                    help="expanded fastfile paths and/or directories")
    ap.add_argument("--glob", default="*.expanded",
                    help="directory match pattern (default: *.expanded)")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--repo-root", type=Path,
                    default=Path(__file__).resolve().parents[1])
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    out_dir = args.out_dir.expanduser().resolve()
    inv_dir = out_dir / "inventories"
    inv_dir.mkdir(parents=True, exist_ok=True)

    sources = collect_inputs(args.inputs, args.glob, not args.no_recursive)
    rows = []
    inventory_paths: list[Path] = []
    type_totals: dict[str, int] = {}

    for ordinal, source in enumerate(sources):
        doc, raw = inventory_one(source)
        source_sha = doc["corpus_source"]["sha256"]
        name = f"{ordinal:04d}_{safe(source.stem)}_{source_sha[:12]}.xassets.json"
        inv = inv_dir / name
        inv.write_bytes(raw)
        inv_sha = sha256_bytes(raw)
        inventory_paths.append(inv)

        for asset_type, count in doc.get("asset_type_counts", {}).items():
            type_totals[asset_type] = type_totals.get(asset_type, 0) + int(count)

        rows.append({
            "ordinal": ordinal,
            "source": doc["corpus_source"],
            "inventory": {
                "path": inv.relative_to(out_dir).as_posix(),
                "bytes": len(raw),
                "sha256": inv_sha,
            },
            "assetCount": int(doc["asset_count"]),
            "observedAssetTypes": sorted(k for k, v in doc["asset_type_counts"].items() if int(v)),
            "assetTypeCounts": doc["asset_type_counts"],
        })

    coverage_path = out_dir / "nonmap_coverage.json"
    run_coverage(repo, inventory_paths, coverage_path)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))

    census = {
        "format": FORMAT,
        "rules": {
            "presenceRequiresXAssetArrayObservation": True,
            "enumDefinitionAloneDoesNotCountAsObserved": True,
            "inputBytesHashPinned": True,
            "perZoneInventoryHashPinned": True,
            "coverageReportHashPinned": True,
            "noFilenameBasedAssetClassification": True,
        },
        "summary": {
            "sourceFiles": len(rows),
            "assetOccurrences": sum(r["assetCount"] for r in rows),
            "observedAssetTypes": sorted(k for k, v in type_totals.items() if v),
            "observedAssetTypeCount": sum(1 for v in type_totals.values() if v),
            "nonMapCoverage": coverage.get("summary", {}),
        },
        "sources": rows,
        "aggregateAssetTypeCounts": dict(sorted(type_totals.items())),
        "coverage": {
            "path": coverage_path.relative_to(out_dir).as_posix(),
            "bytes": coverage_path.stat().st_size,
            "sha256": sha256_path(coverage_path),
            "format": coverage.get("format"),
        },
    }
    census_path = out_dir / "corpus_census.json"
    census_path.write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "census": str(census_path),
        "censusSha256": sha256_path(census_path),
        "sourceFiles": census["summary"]["sourceFiles"],
        "assetOccurrences": census["summary"]["assetOccurrences"],
        "observedAssetTypeCount": census["summary"]["observedAssetTypeCount"],
        "priorityObservedNonMapTypes": coverage.get("summary", {}).get("priorityObservedNonMapTypes", []),
        "oatDumpableObservedTypesPendingRepoPromotion": coverage.get("summary", {}).get(
            "oatDumpableObservedTypesPendingRepoPromotion", []
        ),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
