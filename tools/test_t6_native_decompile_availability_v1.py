#!/usr/bin/env python3
"""Pinned evidence-retention census including v1/v2 split tar.zst bundles."""
from __future__ import annotations
import importlib.util
from pathlib import Path

def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "t6_native_decompile_availability_v1",
        repo / "tools/t6_native_decompile_availability_v1.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    report = mod.audit(repo)
    assert report["total_unique_exact_hash_matches"] == 269
    assert report["indexed_in_retained_archives"] == 269
    assert report["not_indexed_in_retained_archives"] == 0
    assert report["retained_archive_count"] == 10
    assert report["verified_compressed_archive_count"] == 10
    assert report["indexed_decompiler_completed"] == 269
    assert all(not x["native_admitted"] for x in report["entries"])
    assert all(x["source_status"] == "generated-unreviewed-ghidra-C" for x in report["entries"])
    print("PASS: 269/269 uniquely matched functions indexed in 10 hash-verified archives; 0 automatically promoted")

if __name__ == "__main__":
    main()
