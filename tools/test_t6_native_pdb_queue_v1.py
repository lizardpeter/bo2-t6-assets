#!/usr/bin/env python3
"""Regression: prove the native source queue never treats ambiguous names as source."""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

MODULE = Path(__file__).with_name("t6_native_pdb_queue_v1.py")

def main() -> None:
    spec = importlib.util.spec_from_file_location("t6_native_pdb_queue_v1", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = Path(__file__).resolve().parents[1]
    value = module.generate(root)
    assert value["accepted_exact_byte_correspondences"] == 269
    assert value["rejected_ambiguous_match_rows"] == 580
    assert value["unprefixed_object_candidates"] == 15
    assert value["library_or_other_objects"] == 254
    assert all(item["admission_state"] == "matched-symbol-only-not-reconstructed-source" for item in value["entries"])
    assert all(item["cross_build_basis"] == "unique-exact-instruction-byte-sha256" for item in value["entries"])
    assert value["entries"][0]["server_object_name"] == "actor.obj"
    assert value["entries"][0]["current_client_va"] == "0x00421740"
    assert value["entries"][0]["server_symbol_name"] == "?Actor_ClearMoveHistory@@YIXPAUactor_t@@@Z"
    with tempfile.TemporaryDirectory() as dirname:
        target = Path(dirname) / "queue.json"
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assert json.loads(target.read_text(encoding="utf-8")) == value
    print("PASS: 269 exact unique / 580 ambiguous excluded / 15 unprefixed candidate objects")

if __name__ == "__main__":
    main()
