#!/usr/bin/env python3
"""T6 native Material shader census v3: all TechniqueSet types/stages.

v1/v2 intentionally targeted the ordinary `lit` path.  The full Nuketown run
exposed a valid ordinary Material whose TechniqueSet (`trivial_9z33feqw`) has no
`lit` binding.  Treating that as an extraction failure is too narrow for a
whole-game exporter.

v3 keeps the v2 fail-closed ownership rules but censuses every exact TechniqueSet
type binding emitted by pinned OpenAssetTools and every shader stage emitted by
its Technique passes.  Generated `materials/generated/*` rows remain excluded
because their 120/34/34 final-output DAG path is separately source-closed.

No technique type is reinterpreted as a rendering semantic here.  The output is
coverage/identity evidence only: exact Material -> TechniqueSet -> declared type
-> Technique -> pass -> emitted shader-binary SHA-256 identities.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

import t6_oat_material_shader_census_v1 as v1

FORMAT = "t6-oat-material-shader-census-v3"
MaterialShaderCensusError = v1.MaterialShaderCensusError


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _ordinary_materials(root: Path) -> tuple[list[dict], list[str]]:
    rows = v1._index_materials(root)
    ordinary = []
    excluded = []
    for row in rows:
        relative = str(row.get("relativeMaterial") or "")
        if relative == "generated" or relative.startswith("generated/"):
            excluded.append(relative)
        else:
            ordinary.append(row)
    return ordinary, sorted(excluded)


def _record_file(path: Path, root: Path) -> dict:
    return {
        "ownerRoot": str(root),
        "relativeFile": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _techset_owner(roots: list[Path], techset: str, duplicate_rows: list[dict]) -> tuple[Path, Path]:
    relative = Path("techsets") / f"{techset}.techset"
    matches = [(root, root / relative) for root in roots if (root / relative).is_file()]
    if not matches:
        raise MaterialShaderCensusError(f"TechniqueSet {techset}: no dump owner for {relative.as_posix()}")
    if len(matches) == 1:
        return matches[0]
    ids = {(path.stat().st_size, _sha(path)) for _, path in matches}
    if len(ids) != 1:
        raise MaterialShaderCensusError(
            f"TechniqueSet {techset}: divergent duplicate owners "
            f"{[(str(root), path.stat().st_size, _sha(path)) for root, path in matches]}"
        )
    duplicate_rows.append({
        "kind": "TechniqueSet",
        "name": techset,
        "relativeFile": relative.as_posix(),
        "owners": [str(root) for root, _ in matches],
        "ownerCount": len(matches),
        "bytes": matches[0][1].stat().st_size,
        "sha256": _sha(matches[0][1]),
        "resolution": "byte-identical-duplicate-zone-output",
    })
    return matches[0]


def _parse_passes_from_owner(owner: Path, technique: str) -> tuple[list[dict], dict]:
    relative = Path("techniques") / f"{technique}.tech"
    path = owner / relative
    if not path.is_file():
        raise MaterialShaderCensusError(f"Technique {technique}: missing {relative.as_posix()} in {owner}")
    raw_passes, errors = v1.oat.split_top_level_passes(path.read_text(encoding="utf-8", errors="strict"))
    if errors:
        raise MaterialShaderCensusError(f"Technique {technique}: split errors {errors[:4]}")
    result = []
    for index, lines in enumerate(raw_passes):
        parsed, perrors = v1.oat.parse_pass(lines, owner)
        if perrors:
            raise MaterialShaderCensusError(f"Technique {technique} pass {index}: {perrors[:4]}")
        stages = []
        seen = set()
        for shader in parsed.get("shaders", []):
            kind = str(shader.get("kind") or "")
            binary = shader.get("binary")
            if not kind or not isinstance(binary, dict):
                raise MaterialShaderCensusError(
                    f"Technique {technique} pass {index}: shader {shader.get('name')!r} lacks exact binary"
                )
            if kind in seen:
                raise MaterialShaderCensusError(f"Technique {technique} pass {index}: duplicate {kind}")
            seen.add(kind)
            stages.append({
                "kind": kind,
                "asset": str(shader.get("name") or ""),
                "shaderModel": str(shader.get("model") or ""),
                "relativeFile": str(binary.get("path") or ""),
                "bytes": int(binary.get("size", -1)),
                "sha256": str(binary.get("sha256") or "").lower(),
                "arguments": shader.get("arguments", []),
            })
        if not stages:
            raise MaterialShaderCensusError(f"Technique {technique} pass {index}: no shader stages")
        result.append({
            "index": index,
            "stateMap": parsed.get("stateMap"),
            "vertexRouting": parsed.get("vertexRouting", []),
            "stages": stages,
        })
    if not result:
        raise MaterialShaderCensusError(f"Technique {technique}: no passes")
    return result, _record_file(path, owner)


def _technique_passes(
    roots: list[Path], preferred_owner: Path, technique: str, duplicate_rows: list[dict]
) -> tuple[list[dict], dict]:
    relative = Path("techniques") / f"{technique}.tech"
    owners = [root for root in roots if (root / relative).is_file()]
    if not owners:
        raise MaterialShaderCensusError(f"Technique {technique}: no dump owner for {relative.as_posix()}")
    parsed = [(owner, *_parse_passes_from_owner(owner, technique)) for owner in owners]
    identity = _jhash(parsed[0][1])
    for owner, passes, _record in parsed[1:]:
        if _jhash(passes) != identity:
            raise MaterialShaderCensusError(
                f"Technique {technique}: duplicate owners have divergent parsed pass/stage identities: "
                f"{[str(root) for root in owners]}"
            )
    chosen = next((row for row in parsed if row[0] == preferred_owner), parsed[0])
    if len(parsed) > 1:
        files = [owner / relative for owner in owners]
        text_ids = {(p.stat().st_size, _sha(p)) for p in files}
        duplicate_rows.append({
            "kind": "Technique",
            "name": technique,
            "relativeFile": relative.as_posix(),
            "owners": [str(root) for root in owners],
            "ownerCount": len(owners),
            "parsedPassStageIdentitySha256": identity,
            "serializedTextIdentical": len(text_ids) == 1,
            "resolution": (
                "byte-identical-technique-and-identical-parsed-stages"
                if len(text_ids) == 1 else
                "text-different-but-identical-parsed-pass-stage-identities"
            ),
        })
    return chosen[1], chosen[2]


def build(material_root: Path, shader_roots: list[Path]) -> dict:
    roots = [Path(path).resolve() for path in shader_roots]
    if not roots or any(not path.is_dir() for path in roots):
        raise MaterialShaderCensusError("all shader roots must be existing directories")
    materials, excluded_generated = _ordinary_materials(Path(material_root).resolve())
    if not materials:
        raise MaterialShaderCensusError("no ordinary native T6 Material rows remain after generated exclusion")

    duplicate_rows: list[dict] = []
    techset_cache: dict[str, dict] = {}
    technique_cache: dict[tuple[str, str], dict] = {}
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
            owner, path = _techset_owner(roots, techset, duplicate_rows)
            bindings, errors = v1.oat.parse_techset(path.read_text(encoding="utf-8", errors="strict"))
            if errors:
                raise MaterialShaderCensusError(f"TechniqueSet {techset}: parse errors {errors[:4]}")
            if not bindings:
                raise MaterialShaderCensusError(f"TechniqueSet {techset}: no declared technique type bindings")
            techset_cache[techset] = {
                "owner": owner,
                "file": _record_file(path, owner),
                "bindings": bindings,
            }
        ts = techset_cache[techset]
        declared_types = []
        material_programs = []
        for binding in ts["bindings"]:
            technique = str(binding.get("technique") or "")
            types = [str(value) for value in binding.get("types", []) if str(value)]
            if not technique or not types:
                raise MaterialShaderCensusError(f"TechniqueSet {techset}: invalid binding {binding}")
            cache_key = (str(ts["owner"]), technique)
            if cache_key not in technique_cache:
                passes, file_record = _technique_passes(roots, ts["owner"], technique, duplicate_rows)
                technique_cache[cache_key] = {"passes": passes, "file": file_record}
            exact = technique_cache[cache_key]
            pass_identity = _jhash(exact["passes"])
            for type_name in types:
                type_use[type_name] += 1
                declared_types.append(type_name)
                for p in exact["passes"]:
                    for stage in p["stages"]:
                        stage_hashes[stage["kind"]].add(stage["sha256"])
                group_key = _jhash({"techniqueType": type_name, "passes": exact["passes"]})
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
                })
        unique_types = sorted(set(declared_types))
        has_lit = "lit" in unique_types
        lit_count += int(has_lit)
        material_rows.append({
            "material": name,
            "materialJsonSha256": material["jsonSha256"],
            "techniqueSet": techset,
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
    return {
        "format": FORMAT,
        "proofBoundary": (
            "Native pinned-OAT Material JSON -> exact TechniqueSet file -> every declared technique type -> exact Technique file/pass -> emitted shader binary SHA-256. "
            "Generated materials/generated rows are excluded for the separate exact 120/34/34 generated DAG path. Duplicate TechniqueSet owners require byte identity; duplicate Technique owners require identical parsed pass/stage shader identities. Technique-type labels are retained verbatim and are not treated as shader semantic proof."
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
            "duplicateDependencyIdentityCheckCount": len(duplicate_rows),
            "divergentDuplicateDependencyCount": 0,
            "unresolvedMaterialCount": 0,
        },
        "materials": sorted(material_rows, key=lambda row: row["material"]),
        "shaderGroups": groups,
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
