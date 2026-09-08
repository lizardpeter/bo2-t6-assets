#!/usr/bin/env python3
"""Run the T6 native Material shader census under exact PC dedicated-server precedence.

This adapter is deliberately a separate authority domain from the retail-client
census. It consumes the exact PC dedicated-server v2 proof, selects the active
physical parent TechniqueSet owner only when duplicate parents exist, then calls
the existing v4 same-root parent->child provenance machinery.

A green result is authoritative for the exact SHA-pinned PC dedicated-server
build only. It MUST NOT be used as a retail t6mp.exe client census.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import t6_oat_material_shader_census_v4 as v4
import t6_oat_material_shader_census_v3 as v3

FORMAT = "t6-oat-material-shader-census-pc-server-projection-v1"
SERVER_FORMAT = "t6-pc-server-xasset-override-proof-v2"


class ServerProjectedCensusError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ServerProjectedCensusError(f"expected JSON object in {path}")
    return obj


def _parse_root_zone(values: list[str], server: dict) -> dict[str, dict]:
    flags = server.get("mpFlags", {})
    result: dict[str, dict] = {}
    for raw in values:
        if "=" not in raw:
            raise ServerProjectedCensusError(f"--root-zone requires ROOT=SERVER_CLASS, got {raw!r}")
        root_raw, cls = raw.split("=", 1)
        root = str(Path(root_raw).resolve())
        row = flags.get(cls)
        if not isinstance(row, dict) or not isinstance(row.get("priority"), int):
            raise ServerProjectedCensusError(f"server proof lacks priority for class {cls!r}")
        result[root] = {
            "serverZoneClass": cls,
            "allocFlagsHex": row.get("allocFlagsHex"),
            "priority": row["priority"],
        }
    return result


def choose_owner(owners: list[Path], root_semantics: dict[str, dict]) -> tuple[Path, list[dict]]:
    if not owners:
        raise ServerProjectedCensusError("cannot select from an empty owner set")
    if len(owners) == 1:
        return owners[0], []

    candidates = []
    for owner in owners:
        key = str(owner.resolve())
        row = root_semantics.get(key)
        if row is None:
            raise ServerProjectedCensusError(
                f"duplicate parent includes root without exact PC-server zone semantics: {key}"
            )
        candidates.append({"root": key, **row})

    maximum = max(row["priority"] for row in candidates)
    maxima = [row for row in candidates if row["priority"] == maximum]
    if len(maxima) != 1:
        raise ServerProjectedCensusError(
            f"duplicate parent has server priority tie requiring load-order proof: {maxima}"
        )
    selected = Path(maxima[0]["root"])
    return selected, candidates


def build(material_root: Path, shader_roots: list[Path], server: dict, root_semantics: dict[str, dict]) -> dict:
    if server.get("format") != SERVER_FORMAT:
        raise ServerProjectedCensusError(f"unexpected server proof format {server.get('format')!r}")
    authority = server.get("authority", {})
    if authority.get("pcDedicatedServerBuild") is not True or authority.get("retailT6mpClient") is not False:
        raise ServerProjectedCensusError("server proof authority boundary is not exact-server-only")

    selections: list[dict] = []
    original = v4._techset_owners

    def server_techset_owners(roots: list[Path], techset: str, duplicate_rows: list[dict]) -> dict:
        relative = Path("techsets") / f"{techset}.techset"
        matches = [(root, root / relative) for root in roots if (root / relative).is_file()]
        if not matches:
            raise v4.MaterialShaderCensusError(
                f"TechniqueSet {techset}: no dump owner for {relative.as_posix()}"
            )

        physical_owners = [root for root, _ in matches]
        selected, candidates = choose_owner(physical_owners, root_semantics)
        selected_path = selected / relative

        if len(matches) > 1:
            identities = [
                {
                    "root": str(root),
                    "bytes": path.stat().st_size,
                    "sha256": v3._sha(path),
                }
                for root, path in matches
            ]
            row = {
                "kind": "TechniqueSetPcServerSelected",
                "name": techset,
                "relativeFile": relative.as_posix(),
                "physicalOwners": [str(root) for root in physical_owners],
                "serverCandidates": candidates,
                "selectedOwner": str(selected),
                "selectedPriority": root_semantics[str(selected.resolve())]["priority"],
                "serializedParentIdentities": identities,
                "serializedParentIdentical": len({(r['bytes'], r['sha256']) for r in identities}) == 1,
                "resolution": "exact-pc-dedicated-server-zone-priority-parent-selection",
                "authoritativeForPcDedicatedServerBuild": True,
                "authoritativeForRetailClient": False,
            }
            duplicate_rows.append(row)
            selections.append(row)

        bindings, errors = v3.v1.oat.parse_techset(selected_path.read_text(encoding="utf-8", errors="strict"))
        if errors:
            raise v4.MaterialShaderCensusError(f"TechniqueSet {techset}: parse errors {errors[:4]}")
        if not bindings:
            raise v4.MaterialShaderCensusError(f"TechniqueSet {techset}: no declared technique type bindings")
        return {
            "owners": [selected],
            "file": v3._record_file(selected_path, selected),
            "bindings": bindings,
        }

    v4._techset_owners = server_techset_owners
    try:
        result = v4.build(material_root, shader_roots)
    finally:
        v4._techset_owners = original

    result["format"] = FORMAT
    result["baseFormat"] = v4.FORMAT
    result["authoritativeForPcDedicatedServerBuild"] = True
    result["authoritativeForRetailClient"] = False
    result["serverExecutable"] = server.get("pcDedicatedServer")
    result["rootSemantics"] = root_semantics
    result["pcServerTechniqueSetSelections"] = sorted(
        selections, key=lambda row: (row["name"], row["selectedOwner"])
    )
    result["summary"]["pcServerSelectedDuplicateTechniqueSetCount"] = len(selections)
    result["summary"]["authoritativeRetailClientWinnerCount"] = 0
    result["proofBoundary"] = (
        "Material JSON, physical TechniqueSet/Technique/shader files, and same-root parent->child relationships come from the pinned OAT retail FastFile dumps. "
        "When a parent TechniqueSet has multiple physical owners, the active parent is selected only from the exact SHA-pinned PC dedicated-server v2 zone flag/priority proof, after which the existing v4 same-root child provenance is used. "
        "This result is authoritative for that exact PC dedicated-server build only. It is NOT a retail t6mp.exe client census and emits zero authoritative retail-client winners."
    )
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--material-root", type=Path, required=True)
    p.add_argument("--shader-root", type=Path, action="append", required=True)
    p.add_argument("--server-proof", type=Path, required=True)
    p.add_argument("--root-zone", action="append", default=[], help="ROOT=SERVER_CLASS")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    server = _load_json(a.server_proof.resolve())
    roots = _parse_root_zone(a.root_zone, server)
    result = build(a.material_root.resolve(), [x.resolve() for x in a.shader_root], server, roots)
    if result.get("authoritativeForRetailClient") is not False:
        raise ServerProjectedCensusError("retail-client authority boundary violated")
    if result.get("summary", {}).get("authoritativeRetailClientWinnerCount") != 0:
        raise ServerProjectedCensusError("server projection emitted retail-client winners")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 1 if result.get("unresolved") else 0


if __name__ == "__main__":
    raise SystemExit(main())
