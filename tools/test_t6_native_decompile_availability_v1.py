#!/usr/bin/env python3
"""Pinned T6 archive index census. Does not promote Ghidra bodies into native source."""
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
    assert report["indexed_in_retained_archives"] == 57
    assert report["not_indexed_in_retained_archives"] == 212
    assert report["retained_archive_count"] == 8
    assert all(not x["native_admitted"] for x in report["entries"])
    assert all(x["source_status"] == "generated-unreviewed-ghidra-C" for x in report["entries"])
    print("PASS: 57 indexed archive functions / 212 absent / 0 native bodies promoted")

if __name__ == "__main__":
    main()
