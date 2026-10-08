#!/usr/bin/env python3
"""Generate a fail-closed T6 recompilation symbol queue from retained exact-byte joins.

This is a source-prioritization inventory, not a C++ reconstruction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

INPUT = Path("proof/current_client/pdb_exact_hash_join_v1_strict/join.json")
BUILD_SHA = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ACCEPTED = "accepted-exact-byte-identity-witness"


def generate(root: Path) -> dict:
    data = json.loads((root / INPUT).read_text(encoding="utf-8"))
    assert data["current_client_catalog_functions"] == 24617
    assert data["match_rows"] == len(data["matches"])
    accepted = []
    ambiguous = 0
    for item in data["matches"]:
        if item["state"] != ACCEPTED:
            assert item["state"] == "candidate-ambiguous-exact-byte-hash"
            ambiguous += 1
            continue
        assert item["client_hash_multiplicity"] == 1
        assert item["server_hash_multiplicity"] == 1
        assert len(item["current_client_hash"]) == 64
        obj = item["server_object_name"]
        # A non-library-prefixed object is not automatically an original
        # Treyarch translation unit (it can still be vendored source).
        grouping = "unprefixed-object-candidate" if ":" not in obj and not obj.endswith(".o") else "library-or-other-object"
        accepted.append({
            "priority_group": 0 if grouping == "unprefixed-object-candidate" else 1,
            "object_group": grouping,
            "current_client_va": item["current_client_va"],
            "instruction_sha256": item["current_client_hash"],
            "server_object_name": obj,
            "server_symbol_name": item["server_symbol_name"],
            "server_size_bytes": int(item["server_size_bytes"]),
            "server_variant_id": item["server_variant_id"],
            "admission_state": "matched-symbol-only-not-reconstructed-source",
            "cross_build_basis": "unique-exact-instruction-byte-sha256",
        })
    accepted.sort(key=lambda x: (x["priority_group"], -x["server_size_bytes"], x["current_client_va"]))
    assert len({x["current_client_va"] for x in accepted}) == len(accepted)
    assert len({x["instruction_sha256"] for x in accepted}) == len(accepted)
    assert len(accepted) == 269, "Pinned V1 proof changed: review before updating the admitted queue."
    assert ambiguous == 580, "Pinned V1 ambiguous evidence changed."
    return {
        "schema": "t6-recomp-pdb-source-queue-v1",
        "source_evidence": str(INPUT),
        "source_build_sha256": BUILD_SHA,
        "proof_boundary": "Only unique exact instruction-byte matches are admitted to symbol queue. None are claimed to be recompilable source.",
        "accepted_exact_byte_correspondences": len(accepted),
        "rejected_ambiguous_match_rows": ambiguous,
        "unprefixed_object_candidates": sum(x["priority_group"] == 0 for x in accepted),
        "library_or_other_objects": sum(x["priority_group"] == 1 for x in accepted),
        "entries": accepted,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = generate(args.repo_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "entries"}, sort_keys=True))


if __name__ == "__main__":
    main()
