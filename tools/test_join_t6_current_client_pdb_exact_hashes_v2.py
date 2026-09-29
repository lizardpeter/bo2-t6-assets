#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
from pathlib import Path

TOOL = Path(__file__).with_name("join_t6_current_client_pdb_exact_hashes_v2.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("join_v2", TOOL)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def write_tsv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, dialect="excel-tab", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    mod = load_tool()

    client = [
        {"entry_va": "00401000", "name": "FUN_00401000", "instruction_bytes_sha256": "a" * 64},
        {"entry_va": "00402000", "name": "FUN_00402000", "instruction_bytes_sha256": "b" * 64},
        {"entry_va": "00403000", "name": "FUN_00403000", "instruction_bytes_sha256": "c" * 64},
    ]
    server = [
        {
            "variant_id": "variant:unique",
            "family_id": "family:unique",
            "symbol_name": "UniqueSymbol",
            "object_name": "unique.obj",
            "exact_address_start": "0x1000",
            "exact_size_bytes": "10",
            "exact_bytes_sha256": "a" * 64,
        },
        {
            "variant_id": "variant:amb1",
            "family_id": "family:amb1",
            "symbol_name": "AmbiguousOne",
            "object_name": "amb.obj",
            "exact_address_start": "0x2000",
            "exact_size_bytes": "5",
            "exact_bytes_sha256": "b" * 64,
        },
        {
            "variant_id": "variant:amb2",
            "family_id": "family:amb2",
            "symbol_name": "AmbiguousTwo",
            "object_name": "amb.obj",
            "exact_address_start": "0x3000",
            "exact_size_bytes": "5",
            "exact_bytes_sha256": "b" * 64,
        },
    ]

    matches, stats = mod.build_matches(client, server)
    assert stats == {
        "match_rows": 3,
        "current_client_functions_with_match": 2,
        "ambiguous_current_client_hashes": 1,
        "accepted_unique_match_rows": 1,
    }, stats

    unique = [x for x in matches if x["current_client_va"] == "0x00401000"]
    assert len(unique) == 1
    assert unique[0]["state"] == "accepted-exact-byte-identity-witness"
    assert unique[0]["server_hash_multiplicity"] == 1

    ambiguous = [x for x in matches if x["current_client_va"] == "0x00402000"]
    assert len(ambiguous) == 2
    assert all(x["state"] == "candidate-ambiguous-exact-byte-hash" for x in ambiguous)
    assert all(x["server_hash_multiplicity"] == 2 for x in ambiguous)

    assert not any(x["current_client_va"] == "0x00403000" for x in matches)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        manifest = mod.write_graph_projection(td, matches, 2)
        assert manifest["rows"] == 3
        assert len(manifest["files"]) == 2

        text = "\n".join((td / p).read_text(encoding="utf-8") for p in manifest["files"])
        assert "CROSSBUILD_CORRESPONDS_TO" in text
        assert "accepted-exact-byte-identity-witness" in text
        assert "candidate-ambiguous-exact-byte-hash" in text
        assert "CASE WHEN row.state='accepted-exact-byte-identity-witness'" in text

        saved = json.loads((td / "manifest.json").read_text(encoding="utf-8"))
        assert saved["rows"] == 3
        assert saved["server_pdb_sha256"] == mod.SERVER_PDB_SHA256

    print("PASS: unique exact hashes accept; duplicate hashes remain candidate-only")


if __name__ == "__main__":
    main()
