#!/usr/bin/env python3
"""T6 native Material shader census v4: parent-owned Technique provenance.

v3 correctly failed whenever a same-named Technique had divergent physical
copies anywhere in the loaded root universe.  That is too broad for ownership:
a Technique emitted in one zone is not a candidate child of every same-named
TechniqueSet in every other zone.

Pinned OpenAssetTools makes the stronger relationship available directly.  Its
T6 TechsetDumper writes one MaterialTechniqueSet and then walks that exact
``techset.techniques[]`` pointer array to emit each child Technique and shader
binary into the same zone output root.  v4 therefore resolves a Technique only
through the physical root(s) that own its parent TechniqueSet:

* a unique parent TechniqueSet owner must contain the declared child Technique;
* byte-identical duplicate parent TechniqueSets must all contain the child and
  all parent-owned child copies must have identical parsed pass/stage identity;
* same-named Technique files in roots that do not own that parent are retained
  as alternate definitions, but never merged and never used as precedence;
* divergent parent-owned dependencies still fail closed.

This is provenance, not guessed base/patch priority.  Generated
``materials/generated`` rows remain excluded for the separately closed generated
material DAG path.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

import t6_oat_material_shader_census_v3 as v3

FORMAT = "t6-oat-material-shader-census-v4"
MaterialShaderCensusError = v3.MaterialShaderCensusError


def _techset_owners(roots: list[Path], techset: str, duplicate_rows: list[dict]) -> dict:
    relative = Path("techsets") / f"{techset}.techset"
    matches = [(root, root / relative) for root in roots if (root / relative).is_file()]
    if not matches:
        raise MaterialShaderCensusError(f"TechniqueSet {techset}: no dump owner for {relative.as_posix()}")

    identities = {(path.stat().st_size, v3._sha(path)) for _, path in matches}
    if len(identities) != 1:
        raise MaterialShaderCensusError(
            f"TechniqueSet {techset}: divergent duplicate owners "
            f"{[(str(root), path.stat().st_size, v3._sha(path)) for root, path in matches]}"
        )

    if len(matches) > 1:
        duplicate_rows.append({
            "kind": "TechniqueSet",
            "name": techset,
            "relativeFile": relative.as_posix(),
            "owners": [str(root) for root, _ in matches],
            "ownerCount": len(matches),
            "bytes": matches[0][1].stat().st_size,
            "sha256": v3._sha(matches[0][1]),
            "resolution": "byte-identical-duplicate-zone-output",
        })

    bindings, errors = v3.v1.oat.parse_techset(matches[0][1].read_text(encoding="utf-8", errors="strict"))
    if errors:
        raise MaterialShaderCensusError(f"TechniqueSet {techset}: parse errors {errors[:4]}")
    if not bindings:
        raise MaterialShaderCensusError(f"TechniqueSet {techset}: no declared technique type bindings")

    return {
        "owners": [root for root, _ in matches],
        "file": v3._record_file(matches[0][1], matches[0][0]),
        "bindings": bindings,
    }


def _parent_owned_technique_passes(
    roots: list[Path],
    parent_owners: list[Path],
    technique: str,
    duplicate_rows: list[dict],
    alternate_rows: list[dict],
) -> tuple[list[dict], dict, dict]:
    relative = Path("techniques") / f"{technique}.tech"

    missing = [str(root) for root in parent_owners if not (root / relative).is_file()]
    if missing:
        raise MaterialShaderCensusError(
            f"Technique {technique}: parent TechniqueSet owner(s) did not emit declared child "
            f"{relative.as_posix()}: {missing}"
        )

    parsed = []
    for owner in parent_owners:
        passes, file_record = v3._parse_passes_from_owner(owner, technique)
        parsed.append((owner, passes, file_record))

    identity = v3._jhash(parsed[0][1])
    for owner, passes, _record in parsed[1:]:
        candidate = v3._jhash(passes)
        if candidate != identity:
            raise MaterialShaderCensusError(
                f"Technique {technique}: duplicate parent TechniqueSet owners emit divergent child pass/stage identities: "
                f"{[(str(row[0]), v3._jhash(row[1])) for row in parsed]}"
            )

    if len(parsed) > 1:
        files = [owner / relative for owner in parent_owners]
        text_ids = {(path.stat().st_size, v3._sha(path)) for path in files}
        duplicate_rows.append({
            "kind": "Technique",
            "name": technique,
            "relativeFile": relative.as_posix(),
            "owners": [str(root) for root in parent_owners],
            "ownerCount": len(parent_owners),
            "parsedPassStageIdentitySha256": identity,
            "serializedTextIdentical": len(text_ids) == 1,
            "resolution": (
                "byte-identical-parent-owned-technique-and-identical-parsed-stages"
                if len(text_ids) == 1 else
                "text-different-parent-owned-technique-but-identical-parsed-pass-stage-identities"
            ),
        })

    parent_set = set(parent_owners)
    alternates = [root for root in roots if root not in parent_set and (root / relative).is_file()]
    divergent_alternate_count = 0
    for owner in alternates:
        alt_passes, alt_record = v3._parse_passes_from_owner(owner, technique)
        alt_identity = v3._jhash(alt_passes)
        same = alt_identity == identity
        divergent_alternate_count += int(not same)
        alternate_rows.append({
            "kind": "Technique",
            "name": technique,
            "relativeFile": relative.as_posix(),
            "parentOwners": [str(root) for root in parent_owners],
            "alternateOwner": str(owner),
            "parentParsedPassStageIdentitySha256": identity,
            "alternateParsedPassStageIdentitySha256": alt_identity,
            "sameParsedPassStageIdentity": same,
            "alternateFile": alt_record,
            "resolution": "non-parent-zone-alternate-definition-not-used-for-this-TechniqueSet",
        })

    provenance = {
        "technique": technique,
        "relativeFile": relative.as_posix(),
        "parentOwners": [str(root) for root in parent_owners],
        "chosenOwner": str(parsed[0][0]),
        "parsedPassStageIdentitySha256": identity,
        "nonParentAlternateOwnerCount": len(alternates),
        "divergentNonParentAlternateOwnerCount": divergent_alternate_count,
        "resolution": "same-root-parent-TechniqueSet-pointer-provenance",
    }
    return parsed[0][1], parsed[0][2], provenance


def build(material_root: Path, shader_roots: list[Path]) -> dict:
    roots = [Path(path).resolve() for path in shader_roots]
    if not roots or any(not path.is_dir() for path in roots):
        raise MaterialShaderCensusError("all shader roots must be existing directories")

    materials, excluded_generated = v3._ordinary_materials(Path(material_root).resolve())
    if not materials:
        raise MaterialShaderCensusError("no ordinary native T6 Material rows remain after generated exclusion")

    duplicate_rows: list[dict] = []
    alternate_rows: list[dict] = []
    technique_provenance: list[dict] = []
    techset_cache: dict[str, dict] = {}
    technique_cache: dict[tuple[tuple[str, ...], str], dict] = {}
    group_map: dict[str, dict] = {}
    material_rows = []
    type_use = collections.Counter()
    stage_hashes: dict[str, set[str]] = collections.defaultdict(set)
    lit_count = 0

    for material in materials:
        name = str(material["material"])
        techset = str(material.get("techniqueSet") or "")
        if not techset:
            raise MaterialShaderCensusError(f"Material {name!r} has empty TechniqueSet")

        if techset not in techset_cache:
            techset_cache[techset] = _techset_owners(roots, techset, duplicate_rows)
        ts = techset_cache[techset]
        parent_owners = list(ts["owners"])

        declared_types = []
        material_programs = []
        for binding in ts["bindings"]:
            technique = str(binding.get("technique") or "")
            types = [str(value) for value in binding.get("types", []) if str(value)]
            if not technique or not types:
                raise MaterialShaderCensusError(f"TechniqueSet {techset}: invalid binding {binding}")

            cache_key = (tuple(str(root) for root in parent_owners), technique)
            if cache_key not in technique_cache:
                passes, file_record, provenance = _parent_owned_technique_passes(
                    roots, parent_owners, technique, duplicate_rows, alternate_rows
                )
                technique_cache[cache_key] = {"passes": passes, "file": file_record, "provenance": provenance}
                technique_provenance.append({"techniqueSet": techset, **provenance})
            exact = technique_cache[cache_key]
            pass_identity = v3._jhash(exact["passes"])

            for type_name in types:
                type_use[type_name] += 1
                declared_types.append(type_name)
                for p in exact["passes"]:
                    for stage in p["stages"]:
                        stage_hashes[stage["kind"]].add(stage["sha256"])

                group_key = v3._jhash({"techniqueType": type_name, "passes": exact["passes"]})
                group = group_map.setdefault(group_key, {
                    "groupKey": group_key,
                    "techniqueType": type_name,
                    "passStageIdentitySha256": pass_identity,
                    "techniqueSets": set(),
                    "techniques": set(),
                    "materials": [],
                    "passes": exact["passes"],
                })
                group["techniqueSets"].add(techset)
                group["techniques"].add(technique)
                group["materials"].append(name)
                material_programs.append({
                    "techniqueType": type_name,
                    "technique": technique,
                    "groupKey": group_key,
                    "passStageIdentitySha256": pass_identity,
                    "passCount": len(exact["passes"]),
                    "parentTechniqueSetOwners": [str(root) for root in parent_owners],
                    "techniqueOwner": exact["provenance"]["chosenOwner"],
                })

        unique_types = sorted(set(declared_types))
        has_lit = "lit" in unique_types
        lit_count += int(has_lit)
        material_rows.append({
            "material": name,
            "materialJsonSha256": material["jsonSha256"],
            "techniqueSet": techset,
            "techniqueSetOwners": [str(root) for root in parent_owners],
            "declaredTechniqueTypes": unique_types,
            "hasLitBinding": has_lit,
            "programs": sorted(material_programs, key=lambda row: (row["techniqueType"], row["technique"])),
        })

    groups = []
    for key in sorted(group_map):
        g = group_map[key]
        groups.append({
            "groupKey": key,
            "techniqueType": g["techniqueType"],
            "passStageIdentitySha256": g["passStageIdentitySha256"],
            "materialCount": len(g["materials"]),
            "materials": sorted(g["materials"]),
            "techniqueSets": sorted(g["techniqueSets"]),
            "techniques": sorted(g["techniques"]),
            "passes": g["passes"],
        })

    duplicate_rows = sorted(duplicate_rows, key=lambda row: (row["kind"], row["name"], row["relativeFile"]))
    alternate_rows = sorted(
        alternate_rows,
        key=lambda row: (row["name"], row["alternateOwner"], tuple(row["parentOwners"])),
    )
    technique_provenance = sorted(
        technique_provenance,
        key=lambda row: (row["techniqueSet"], row["technique"], tuple(row["parentOwners"])),
    )

    return {
        "format": FORMAT,
        "baseFormat": v3.FORMAT,
        "proofBoundary": (
            "Native pinned-OAT Material JSON -> exact TechniqueSet file -> every declared technique type -> the child Technique emitted from the physical owner root(s) of that same parent TechniqueSet -> exact pass -> emitted shader binary SHA-256. Pinned OAT T6 TechsetDumper writes child Techniques by walking the MaterialTechniqueSet.techniques[] pointers of the asset being dumped, so same-root parent/child provenance is used instead of filename-wide zone merging. Unique parent owners require a same-root child. Byte-identical duplicate parent TechniqueSets require every parent owner to emit the child and all parent-owned child pass/stage identities to agree. Same-name Technique files in roots that do not own that parent are retained as alternate definitions and never select or override the parent-owned child. Generated materials/generated rows remain excluded for the separate exact generated DAG path. No guessed zone precedence participates."
        ),
        "shaderRoots": [str(path) for path in roots],
        "summary": {
            "ordinaryNativeMaterialCount": len(materials),
            "excludedGeneratedMaterialCount": len(excluded_generated),
            "uniqueTechniqueSetCount": len(techset_cache),
            "declaredTechniqueTypeCount": len(type_use),
            "declaredTechniqueTypeUseCounts": dict(sorted(type_use.items())),
            "exactTechniqueTypeShaderGroupCount": len(groups),
            "litBindingMaterialCount": lit_count,
            "nonLitOnlyMaterialCount": len(materials) - lit_count,
            "uniqueShaderStageCounts": {kind: len(values) for kind, values in sorted(stage_hashes.items())},
            "parentOwnedTechniqueDependencyCount": len(technique_provenance),
            "duplicateDependencyIdentityCheckCount": len(duplicate_rows),
            "nonParentAlternateTechniqueDefinitionCount": len(alternate_rows),
            "divergentNonParentAlternateTechniqueDefinitionCount": sum(
                1 for row in alternate_rows if not row["sameParsedPassStageIdentity"]
            ),
            "divergentParentOwnedDependencyCount": 0,
            "unresolvedMaterialCount": 0,
        },
        "materials": sorted(material_rows, key=lambda row: row["material"]),
        "shaderGroups": groups,
        "techniqueProvenance": technique_provenance,
        "nonParentAlternateTechniqueDefinitions": alternate_rows,
        "excludedGeneratedMaterialRelativeIdentities": excluded_generated,
        "duplicateDependencies": duplicate_rows,
        "unresolved": [],
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
    return 1 if result.get("unresolved") else 0


if __name__ == "__main__":
    raise SystemExit(main())
