#!/usr/bin/env python3
"""Audit and optionally stage retained Ghidra pseudocode for exact-hash T6 matches.

NOT a recompiler. Generated Ghidra C is unreviewed evidence, not native source.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import tarfile
from pathlib import Path

JOIN = Path("proof/current_client/pdb_exact_hash_join_v1_strict/join.json")
ACCEPTED = "accepted-exact-byte-identity-witness"
BUILD_SHA = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, dialect="excel-tab"))


def audit(root: Path) -> dict:
    source = json.loads((root / JOIN).read_text(encoding="utf-8"))
    accepted = {x["current_client_va"].lower(): x for x in source["matches"] if x["state"] == ACCEPTED}
    assert len(accepted) == 269
    hits: dict[str, dict] = {}
    archives = sorted(root.glob("proof/current_client/**/bundle.tar.zst"))
    for archive in archives:
        base = archive.parent
        selection = rows(base / "selection.tsv")
        results = {x["requested_va"].lower(): x for x in rows(base / "results.tsv")}
        for row in selection:
            address = row["requested_va"].lower()
            if address not in accepted:
                continue
            assert row["instruction_bytes_sha256"] == accepted[address]["current_client_hash"], (
                "archive selection hash mismatch", archive, address
            )
            assert address not in hits, ("duplicate exact-match archive ownership", address)
            result = results.get(address)
            assert result is not None and result["found_exact"].lower() == "true", (archive, address)
            hits[address] = {
                "current_client_va": address,
                "server_symbol_name": accepted[address]["server_symbol_name"],
                "server_object_name": accepted[address]["server_object_name"],
                "instruction_sha256": accepted[address]["current_client_hash"],
                "bundle": str(archive.relative_to(root)),
                "generated_file_name": address[2:] + ".c",
                "decompile_completed": result["decompile_completed"].lower() == "true",
                "source_status": "generated-unreviewed-ghidra-C",
                "native_admitted": False,
            }
    return {
        "schema": "t6-native-decompile-evidence-availability-v1",
        "source_build_sha256": BUILD_SHA,
        "cross_build_match_source": str(JOIN),
        "proof_boundary": "Presence in a retained archive selection index is not verification of tar member or reconstructed C++.",
        "total_unique_exact_hash_matches": len(accepted),
        "retained_archive_count": len(archives),
        "indexed_in_retained_archives": len(hits),
        "not_indexed_in_retained_archives": len(accepted) - len(hits),
        "indexed_decompiler_completed": sum(v["decompile_completed"] for v in hits.values()),
        "entries": sorted(hits.values(), key=lambda x: x["current_client_va"]),
    }


def stage(root: Path, report: dict, target: Path) -> dict:
    """Extract only indexed .c members from exact archives; never compile them."""
    requested: dict[str, dict[str, dict]] = {}
    for row in report["entries"]:
        if row["decompile_completed"]:
            requested.setdefault(row["bundle"], {})[row["generated_file_name"]] = row
    target.mkdir(parents=True, exist_ok=True)
    staged = []
    for rel, wanted in sorted(requested.items()):
        process = subprocess.Popen(["zstd", "-dc", str(root / rel)], stdout=subprocess.PIPE)
        assert process.stdout is not None
        try:
            with tarfile.open(fileobj=process.stdout, mode="r|") as bundle:
                for member in bundle:
                    archive_path = member.name.replace("\\", "/")
                    if not member.isfile() or not (
                        archive_path.startswith("unreviewed/") or "/unreviewed/" in archive_path
                    ):
                        continue
                    name = Path(archive_path).name
                    if name not in wanted:
                        continue
                    if member.size > 2_000_000:
                        raise ValueError(("oversized pseudocode", rel, name))
                    handle = bundle.extractfile(member)
                    assert handle is not None
                    payload = handle.read()
                    record = dict(wanted.pop(name))
                    destination = target / name
                    if destination.exists():
                        raise ValueError(("duplicate stage filename", name))
                    destination.write_bytes(payload)
                    record["source_bytes"] = len(payload)
                    staged.append(record)
            if process.wait() != 0:
                raise RuntimeError(("zstd failed", rel))
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
    missing = sorted(row["current_client_va"] for group in requested.values() for row in group.values())
    manifest = {
        "schema": "t6-generated-ghidra-staging-v1",
        "build_sha256": BUILD_SHA,
        "native_source_admission": False,
        "recompiled_functions": 0,
        "extracted_unreviewed_function_bodies": len(staged),
        "index_claims_missing_tar_member": missing,
        "files": staged,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stage-dir", type=Path)
    args = parser.parse_args()
    result = audit(args.repo_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "entries"}, sort_keys=True))
    if args.stage_dir:
        manifest = stage(args.repo_root, result, args.stage_dir)
        print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, sort_keys=True))


if __name__ == "__main__":
    main()
