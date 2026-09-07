#!/usr/bin/env python3
"""Validate an authorized local recovery of T6 Steam depot 202974.

The validator never downloads retail game content. It accepts a caller-supplied
root containing the Steam depot's `zone/all/*.ff` files, derives the exact
84-path inventory from the retained catalog, requires every path, records exact
sizes/SHA-256 hashes, and optionally compares the two already-retained control
FastFiles byte-for-byte against a separately supplied trusted control root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-depot-202974-authorized-ingest-v1"
DEPOT_ID = 202974
EXPECTED_MANIFEST_ID = "8534031140633404768"
CONTROLS = ["zone/all/code_post_gfx.ff", "zone/all/code_pre_gfx.ff"]


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def sha256_file(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    return size, h.hexdigest()


def find_depot(base: dict[str, Any]) -> dict[str, Any]:
    depots = base.get("depots")
    if not isinstance(depots, list):
        raise ValueError("base catalog missing depots list")
    matches = [d for d in depots if int(d.get("depotId", -1)) == DEPOT_ID]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one depot {DEPOT_ID}, found {len(matches)}")
    depot = matches[0]
    if str(depot.get("manifestId")) != EXPECTED_MANIFEST_ID:
        raise ValueError(
            f"depot {DEPOT_ID} manifest {depot.get('manifestId')!r} != retained {EXPECTED_MANIFEST_ID!r}"
        )
    ff = depot.get("ff")
    if not isinstance(ff, list) or len(ff) != int(depot.get("expectedFfCount", -1)):
        raise ValueError("retained depot FastFile inventory is invalid")
    if len(ff) != 84 or len(set(ff)) != 84:
        raise ValueError(f"expected 84 unique depot FastFiles, got {len(ff)} / {len(set(ff))} unique")
    return depot


def under(root: Path, catalog_path: str) -> Path:
    # Accept either the game root (contains zone/all) or an already-pointed
    # zone/all directory without introducing fuzzy path discovery.
    exact = root / catalog_path
    if exact.is_file():
        return exact
    if root.name == "all" and root.parent.name == "zone":
        alt = root / Path(catalog_path).name
        if alt.is_file():
            return alt
    return exact


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-catalog", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True,
                    help="authorized local depot/game root containing the recovered FastFiles")
    ap.add_argument("--trusted-control-root", type=Path,
                    help="independent retained source root used only for exact code_*_gfx control comparison")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-controls-match", action="store_true")
    ap.add_argument("--require-complete", action="store_true")
    a = ap.parse_args()

    base = load(a.base_catalog)
    if base.get("format") != "t6-steam-english-base-zone-catalog-v1":
        raise ValueError("unexpected base catalog format")
    depot = find_depot(base)
    expected_paths = list(depot["ff"])

    files = []
    missing = []
    for catalog_path in expected_paths:
        local = under(a.source_root, catalog_path)
        if not local.is_file():
            missing.append(catalog_path)
            continue
        size, digest = sha256_file(local)
        files.append({
            "path": catalog_path,
            "bytes": size,
            "sha256": digest,
        })

    control_rows = []
    for catalog_path in CONTROLS:
        src = under(a.source_root, catalog_path)
        row: dict[str, Any] = {"path": catalog_path, "sourcePresent": src.is_file()}
        if src.is_file():
            s_size, s_hash = sha256_file(src)
            row.update({"sourceBytes": s_size, "sourceSha256": s_hash})
        if a.trusted_control_root is not None:
            trusted = under(a.trusted_control_root, catalog_path)
            row["trustedPresent"] = trusted.is_file()
            if trusted.is_file():
                t_size, t_hash = sha256_file(trusted)
                row.update({"trustedBytes": t_size, "trustedSha256": t_hash})
                row["exactByteIdentity"] = (
                    src.is_file() and s_size == t_size and s_hash == t_hash
                )
            else:
                row["exactByteIdentity"] = False
        else:
            row["trustedPresent"] = False
            row["exactByteIdentity"] = None
        control_rows.append(row)

    complete = len(files) == 84 and not missing
    controls_supplied = a.trusted_control_root is not None
    controls_match = controls_supplied and all(r.get("exactByteIdentity") is True for r in control_rows)
    gates = {
        "retainedDepotCatalogIsExact84PathInventory": True,
        "all84AuthorizedSourceFastFilesPresent": complete,
        "trustedControlsSupplied": controls_supplied,
        "bothRetainedControlsExactByteIdentity": controls_match,
    }

    out = {
        "format": FORMAT,
        "depot": {
            "depotId": DEPOT_ID,
            "manifestId": EXPECTED_MANIFEST_ID,
            "label": depot.get("label"),
            "expectedFastFiles": 84,
        },
        "sourceRoot": str(a.source_root),
        "trustedControlRoot": str(a.trusted_control_root) if a.trusted_control_root is not None else None,
        "observedFastFiles": len(files),
        "missingFastFiles": missing,
        "files": files,
        "controls": control_rows,
        "gates": gates,
        "proofBoundary": [
            "The exact 84-path inventory comes only from the retained Steam English base FastFile catalog for depot 202974 / manifest 8534031140633404768.",
            "This tool performs no network retrieval and accepts only caller-supplied local source bytes.",
            "Presence plus SHA-256 enumeration establishes the supplied local corpus shape and byte identities; it does not by itself prove Steam provenance.",
            "When a separately supplied trusted control root is used, the two retained code_pre_gfx.ff/code_post_gfx.ff files must match in both size and SHA-256 before the control-identity gate closes.",
            "No recovered campaign FastFile is promoted into the authoritative retail corpus merely from filename, directory adjacency, or content similarity."
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "depot": out["depot"],
        "observedFastFiles": len(files),
        "missingFastFiles": len(missing),
        "gates": gates,
    }, indent=2, sort_keys=True))

    failures = []
    if a.require_complete and not complete:
        failures.append("authorized source does not contain all 84 exact depot FastFiles")
    if a.require_controls_match and not controls_match:
        failures.append("trusted retained control identity did not close")
    if failures:
        raise SystemExit("; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
