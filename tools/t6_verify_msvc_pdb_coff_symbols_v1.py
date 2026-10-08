#!/usr/bin/env python3
"""Fail if MSVC x86 ABI shim object no longer exposes exact PDB names."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

def find_dumpbin() -> Path:
    root = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    paths = sorted(root.glob("Microsoft Visual Studio/*/*/VC/Tools/MSVC/*/bin/Hostx64/x86/dumpbin.exe"))
    if not paths:
        paths = sorted(root.glob("Microsoft Visual Studio/*/*/VC/Tools/MSVC/*/bin/Hostx86/x86/dumpbin.exe"))
    if not paths:
        raise RuntimeError("No MSVC x86 dumpbin.exe installation found")
    return paths[-1]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("coff_library", type=Path)
    parser.add_argument("--spec", type=Path, default=Path(__file__).resolve().parents[1] /
                        "reconstruction/native/msvc_pdb_abi_symbols_v1.json")
    args = parser.parse_args()
    expected = json.loads(args.spec.read_text(encoding="utf-8"))["required_symbols"]
    tool = find_dumpbin()
    completed = subprocess.run([str(tool), "/linkermember:1", str(args.coff_library)],
                               capture_output=True, text=True, check=True, errors="replace")
    # Exact token matching prevents suffix-only substring false positives.
    tokens = set(re.findall(r"\S+", completed.stdout))
    missing = sorted(set(expected) - tokens)
    if missing:
        raise SystemExit("Missing PDB-decorated x86 symbols: " + repr(missing))
    print(f"PASS: {len(expected)} MSVC x86 COFF decorations match exact server PDB symbols")

if __name__ == "__main__":
    main()
