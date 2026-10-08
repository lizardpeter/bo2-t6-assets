#!/usr/bin/env python3
"""Fail-closed audit of explicitly admitted T6 native C++ source candidates."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXPECTED_SHA = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
VALID_STATES = {"candidate-structural-reconstruction", "reviewed-source", "retail-validated"}


def audit(root: Path) -> dict:
    manifest = json.loads((root / "reconstruction/native/manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "t6-native-source-admission-v1"
    assert manifest["target_build"] == "current-client"
    assert manifest["target_sha256"] == EXPECTED_SHA
    functions = manifest["functions"]
    seen_addresses, seen_symbols = set(), set()
    counts = {"admitted": 0, "compiled": 0, "retail_validated": 0, "unresolved_external_dependent": 0}
    cmake = (root / "reconstruction/native/CMakeLists.txt").read_text(encoding="utf-8")
    for f in functions:
        address, symbol = f["entry_va"], f["symbol"]
        assert re.fullmatch(r"0x[0-9A-F]{8}", address), address
        assert re.fullmatch(r"t6_sub_[0-9a-f]{8}", symbol), symbol
        assert symbol == "t6_sub_" + address[2:].lower()
        assert address not in seen_addresses and symbol not in seen_symbols
        seen_addresses.add(address)
        seen_symbols.add(symbol)
        assert f["admission"] in VALID_STATES
        source = (root / f["source"]).resolve()
        assert source.is_relative_to(root.resolve()), f["source"]
        assert source.is_file(), f["source"]
        content = source.read_text(encoding="utf-8")
        assert re.search(r'extern\s+"C"\s+[^;\n]+?\b' + re.escape(symbol) + r'\s*\(', content), symbol
        assert source.name in cmake, (symbol, "source not admitted to CMake target")
        unresolved = f.get("unresolved_external_functions", [])
        assert isinstance(unresolved, list), symbol
        if unresolved:
            assert f.get("origin_uregraph_representation"), symbol
            assert f.get("test_dependency_policy") == (
                "test-only-virtual-address-copy-adapter-not-a-retail-implementation"
            ), symbol
            for external in unresolved:
                assert re.fullmatch(r"0x[0-9A-F]{8}", external), symbol
                assert "t6_sub_" + external[2:].lower() in content, symbol
            counts["unresolved_external_dependent"] += 1
        if f["retail_differential_verified"]:
            assert f["admission"] == "retail-validated", symbol
            assert f.get("retail_evidence_id"), symbol
        if f["admission"] == "retail-validated":
            assert f["retail_differential_verified"], symbol
        counts["admitted"] += 1
        counts["compiled"] += bool(f["compiled"])
        counts["retail_validated"] += bool(f["retail_differential_verified"])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.repo_root)
    print(json.dumps({"scope": "native source admission, NOT whole-game coverage", **result}, sort_keys=True))


if __name__ == "__main__":
    main()
