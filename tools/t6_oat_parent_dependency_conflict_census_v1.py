#!/usr/bin/env python3
"""Enumerate unresolved parent-owned T6 Technique dependency conflicts.

This is a diagnostic companion to t6_oat_material_shader_census_v4.py.  It uses
exactly the same parent-TechniqueSet provenance boundary but, instead of aborting
on the first divergent parent-owned child Technique, records every such conflict
in a machine-readable manifest.

It never chooses a winner.  A conflict is evidence that runtime duplicate-XAsset
selection remains required, not permission to infer patch/map precedence.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import t6_oat_material_shader_census_v3 as v3
import t6_oat_material_shader_census_v4 as v4

FORMAT = "t6-oat-parent-dependency-conflict-census-v1"


def _owner_child_record(owner: Path, technique: str) -> dict:
    relative = Path("techniques") / f"{technique}.tech"
    path = owner / relative
    if not path.is_file():
        return {
            "root": str(owner),
            "relativeFile": relative.as_posix(),
            "present": False,
        }
    passes, file_record = v3._parse_passes_from_owner(owner, technique)
    return {
        "root": str(owner),
        "relativeFile": relative.as_posix(),
        "present": True,
        "file": file_record,
        "parsedPassStageIdentitySha256": v3._jhash(passes),
        "passes": passes,
    }


def build(material_root: Path, shader_roots: list[Path]) -> dict:
    roots = [Path(p).resolve() for p in shader_roots]
    if not roots or any(not p.is_dir() for p in roots):
        raise v3.MaterialShaderCensusError("all shader roots must be existing directories")

    material_root = Path(material_root).resolve()
    materials, excluded_generated = v3._ordinary_materials(material_root)
    if not materials:
        raise v3.MaterialShaderCensusError("no ordinary native T6 Material rows remain after generated exclusion")

    techset_cache: dict[str, dict] = {}
    conflict_map: dict[str, dict] = {}
    missing_map: dict[str, dict] = {}
    checked_relations: set[tuple[str, str]] = set()
    duplicate_rows: list[dict] = []

    # Collect material users separately so one shared TechniqueSet conflict retains
    # every triggering Material instead of whichever material happened to be first.
    techset_materials: dict[str, set[str]] = collections.defaultdict(set)
    for material in materials:
        techset = str(material.get("techniqueSet") or "")
        name = str(material["material"])
        if not techset:
            raise v3.MaterialShaderCensusError(f"Material {name!r} has empty TechniqueSet")
        techset_materials[techset].add(name)

    for techset in sorted(techset_materials):
        if techset not in techset_cache:
            techset_cache[techset] = v4._techset_owners(roots, techset, duplicate_rows)
        ts = techset_cache[techset]
        parent_owners = list(ts["owners"])

        for binding in ts["bindings"]:
            technique = str(binding.get("technique") or "")
            types = sorted({str(v) for v in binding.get("types", []) if str(v)})
            if not technique or not types:
                raise v3.MaterialShaderCensusError(f"TechniqueSet {techset}: invalid binding {binding}")

            relation = (techset, technique)
            if relation in checked_relations:
                continue
            checked_relations.add(relation)

            owner_rows = [_owner_child_record(owner, technique) for owner in parent_owners]
            missing = [row for row in owner_rows if not row["present"]]
            if missing:
                key = v3._jhash({
                    "kind": "missing-parent-owned-child",
                    "techniqueSet": techset,
                    "technique": technique,
                    "owners": [row["root"] for row in owner_rows],
                })
                missing_map[key] = {
                    "conflictKey": key,
                    "kind": "missing-parent-owned-child",
                    "techniqueSet": techset,
                    "technique": technique,
                    "declaredTechniqueTypes": types,
                    "materials": sorted(techset_materials[techset]),
                    "parentOwners": [row["root"] for row in owner_rows],
                    "missingParentOwners": [row["root"] for row in missing],
                    "ownerChildren": owner_rows,
                    "resolution": "unresolved-no-winner-selected",
                }
                continue

            identities = {row["parsedPassStageIdentitySha256"] for row in owner_rows}
            if len(identities) > 1:
                key = v3._jhash({
                    "kind": "divergent-parent-owned-child",
                    "techniqueSet": techset,
                    "technique": technique,
                    "owners": [
                        (row["root"], row["parsedPassStageIdentitySha256"])
                        for row in owner_rows
                    ],
                })
                conflict_map[key] = {
                    "conflictKey": key,
                    "kind": "divergent-parent-owned-child",
                    "techniqueSet": techset,
                    "technique": technique,
                    "declaredTechniqueTypes": types,
                    "materials": sorted(techset_materials[techset]),
                    "parentOwners": [row["root"] for row in owner_rows],
                    "ownerChildren": owner_rows,
                    "distinctParsedPassStageIdentityCount": len(identities),
                    "resolution": "unresolved-no-winner-selected",
                }

    divergent = [conflict_map[k] for k in sorted(conflict_map)]
    missing = [missing_map[k] for k in sorted(missing_map)]
    unresolved = divergent + missing

    return {
        "format": FORMAT,
        "authoritativeWinnerSelection": False,
        "proofBoundary": (
            "Exact pinned-OAT Material -> physical parent TechniqueSet owner root(s) -> declared Technique binding -> same-root child Technique pass/stage identity. "
            "This diagnostic records divergent or missing parent-owned children without selecting a winner. It does not use load order, zone names, guessed patch precedence, OpenBO2 lineage priorities, or non-parent same-name Technique files. Runtime duplicate-XAsset selection remains a separate proof gate."
        ),
        "materialRoot": str(material_root),
        "shaderRoots": [str(p) for p in roots],
        "summary": {
            "ordinaryNativeMaterialCount": len(materials),
            "excludedGeneratedMaterialCount": len(excluded_generated),
            "uniqueTechniqueSetCount": len(techset_materials),
            "checkedParentTechniqueRelationCount": len(checked_relations),
            "divergentParentOwnedChildConflictCount": len(divergent),
            "missingParentOwnedChildConflictCount": len(missing),
            "unresolvedConflictCount": len(unresolved),
            "winnerSelectedCount": 0,
        },
        "conflicts": unresolved,
        "duplicateTechniqueSetsObserved": sorted(
            duplicate_rows,
            key=lambda row: (row["kind"], row["name"], row["relativeFile"]),
        ),
        "excludedGeneratedMaterialRelativeIdentities": excluded_generated,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--material-root", type=Path, required=True)
    p.add_argument("--shader-root", type=Path, action="append", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.material_root, a.shader_root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    for row in result["conflicts"]:
        print(
            f"CONFLICT kind={row['kind']} techset={row['techniqueSet']} "
            f"technique={row['technique']} materials={len(row['materials'])}"
        )
        for owner in row["ownerChildren"]:
            print(
                "  owner=" + owner["root"]
                + " present=" + str(owner["present"]).lower()
                + (" identity=" + owner.get("parsedPassStageIdentitySha256", "") if owner["present"] else "")
            )
    # Diagnostic succeeds when it faithfully records conflicts. Conflict presence
    # is data, not a tool failure; production census remains responsible for fail-closed authority.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
