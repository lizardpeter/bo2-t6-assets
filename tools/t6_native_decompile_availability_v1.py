#!/usr/bin/env python3
"""Audit/stage exact-hash T6 Ghidra C evidence from monolithic AND split archives.

An indexed function with completed Ghidra C is still NOT compilable T6 source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

JOIN = Path("proof/current_client/pdb_exact_hash_join_v1_strict/join.json")
ACCEPTED = "accepted-exact-byte-identity-witness"
BUILD_SHA = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, dialect="excel-tab"))


def archive_groups(root: Path) -> list[tuple[Path, list[Path]]]:
    direct = {p.parent: [p] for p in root.glob("proof/current_client/**/bundle.tar.zst")}
    for part in sorted(root.glob("proof/current_client/**/bundle.tar.zst.part-*")):
        direct.setdefault(part.parent, []).append(part)
    output = []
    for base, pieces in sorted(direct.items()):
        if pieces[0].name.startswith("bundle.tar.zst.part-"):
            pieces.sort()
            assert [p.name.rsplit("-", 1)[-1] for p in pieces] == [
                f"{i:03d}" for i in range(len(pieces))
            ], ("missing chunk", base)
        else:
            assert len(pieces) == 1, ("mixed monolithic and split archive", base)
        output.append((base, pieces))
    return output


def archive_sha256(pieces: list[Path]) -> str:
    digest = hashlib.sha256()
    for part in pieces:
        with part.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def audit(root: Path) -> dict:
    source = json.loads((root / JOIN).read_text(encoding="utf-8"))
    accepted = {
        x["current_client_va"].lower(): x
        for x in source["matches"] if x["state"] == ACCEPTED
    }
    assert len(accepted) == 269
    hits: dict[str, dict] = {}
    groups = archive_groups(root)
    checked = 0
    for base, pieces in groups:
        selection_file = base / "selection.tsv"
        if not selection_file.exists():
            selection_file = base / "low_hanging.tsv"  # v1 did not save results.tsv
        assert selection_file.is_file(), base
        selection = rows(selection_file)
        result_file = base / "results.tsv"
        result_rows = (
            {x["requested_va"].lower(): x for x in rows(result_file)}
            if result_file.is_file() else None
        )
        if result_rows is None:
            summary = json.loads((base / "summary.json").read_text(encoding="utf-8"))
            assert summary["selected_functions"] == len(selection)
            assert summary["decompile_completed"] == len(selection), base
            assert summary["decompile_failed_or_timed_out"] == 0, base
        digest_file = base / "bundle.sha256"
        if digest_file.is_file():
            expected = digest_file.read_text(encoding="utf-8").split()[0].lower()
            assert archive_sha256(pieces) == expected, ("compressed archive hash mismatch", base)
            checked += 1
        for row in selection:
            address = row["requested_va"].lower()
            if address not in accepted:
                continue
            assert row["instruction_bytes_sha256"] == accepted[address]["current_client_hash"], (
                "archive selection instruction hash mismatch", base, address
            )
            assert address not in hits, ("duplicate exact-match ownership", base, address)
            if result_rows is None:
                completed = True
            else:
                result = result_rows.get(address)
                assert result is not None and result["found_exact"].lower() == "true", (base, address)
                completed = result["decompile_completed"].lower() == "true"
            hits[address] = {
                "current_client_va": address,
                "server_symbol_name": accepted[address]["server_symbol_name"],
                "server_object_name": accepted[address]["server_object_name"],
                "instruction_sha256": accepted[address]["current_client_hash"],
                "archive_parts": [str(p.relative_to(root)) for p in pieces],
                "generated_file_name": address[2:] + ".c",
                "decompile_completed": completed,
                "source_status": "generated-unreviewed-ghidra-C",
                "native_admitted": False,
            }
    return {
        "schema": "t6-native-decompile-evidence-availability-v2",
        "source_build_sha256": BUILD_SHA,
        "cross_build_match_source": str(JOIN),
        "proof_boundary": "Selection-index and compressed-hash verification; tar members staged separately and NOT reconstructed source.",
        "total_unique_exact_hash_matches": len(accepted),
        "retained_archive_count": len(groups),
        "verified_compressed_archive_count": checked,
        "indexed_in_retained_archives": len(hits),
        "not_indexed_in_retained_archives": len(accepted) - len(hits),
        "indexed_decompiler_completed": sum(v["decompile_completed"] for v in hits.values()),
        "entries": sorted(hits.values(), key=lambda x: x["current_client_va"]),
    }


def stage(root: Path, report: dict, target: Path) -> dict:
    """Extract exact-hash-selected generated .c from zstd archives; no auto-compile."""
    requested: dict[tuple[str, ...], dict[str, dict]] = {}
    for row in report["entries"]:
        if row["decompile_completed"]:
            key = tuple(row["archive_parts"])
            requested.setdefault(key, {})[row["generated_file_name"]] = row
    target.mkdir(parents=True, exist_ok=True)
    staged = []
    with tempfile.TemporaryDirectory() as tempdir:
        for archive_parts, wanted in sorted(requested.items()):
            pieces = [root / p for p in archive_parts]
            if len(pieces) == 1:
                archive_file = pieces[0]
            else:
                archive_file = Path(tempdir) / "recombined.tar.zst"
                with archive_file.open("wb") as out:
                    for piece in pieces:
                        with piece.open("rb") as stream:
                            shutil.copyfileobj(stream, out)
            process = subprocess.Popen(["zstd", "-dc", str(archive_file)], stdout=subprocess.PIPE)
            assert process.stdout is not None
            try:
                with tarfile.open(fileobj=process.stdout, mode="r|") as bundle:
                    for member in bundle:
                        name_in_archive = member.name.replace("\\", "/")
                        if not member.isfile() or not (
                            name_in_archive.startswith("unreviewed/")
                            or "/unreviewed/" in name_in_archive
                        ):
                            continue
                        name = Path(name_in_archive).name
                        if name not in wanted:
                            continue
                        if member.size > 2_000_000:
                            raise ValueError(("oversized pseudocode", archive_parts, name))
                        handle = bundle.extractfile(member)
                        assert handle is not None
                        payload = handle.read()
                        record = dict(wanted.pop(name))
                        destination = target / name
                        if destination.exists():
                            raise ValueError(("duplicate file", name))
                        destination.write_bytes(payload)
                        record["source_bytes"] = len(payload)
                        record["source_sha256"] = hashlib.sha256(payload).hexdigest()
                        staged.append(record)
                assert process.wait() == 0, ("zstd failed", archive_parts)
            finally:
                process.stdout.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()
    missing = sorted(row["current_client_va"] for group in requested.values() for row in group.values())
    manifest = {
        "schema": "t6-generated-ghidra-staging-v2",
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
    report = audit(args.repo_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "entries"}, sort_keys=True))
    if args.stage_dir:
        manifest = stage(args.repo_root, report, args.stage_dir)
        print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, sort_keys=True))
        if manifest["index_claims_missing_tar_member"]:
            raise RuntimeError("Some indexed generated-C members were not found in retained tar archives")


if __name__ == "__main__":
    main()
