#!/usr/bin/env python3
"""T6 native Material shader census v2: ordinary-only + duplicate-owner proof.

Wraps v1 without changing its exact Material -> TechniqueSet -> lit Technique ->
ordered VS/PS identity grouping. v2 closes two coverage/ownership holes exposed
by the first full Nuketown run:

1. OAT writes generated compound Materials under ``materials/generated`` using
   disk-safe names. Those rows belong to the separate exact generated 120/34/34
   recipe/DAG path and must not be counted as ordinary native rows.
2. The same TechniqueSet/Technique dependency may be emitted by more than one
   loaded zone. Multiple physical owners are accepted only after exact identity
   agreement. TechniqueSet files require byte identity. Duplicate Technique
   owners additionally require identical parsed pass structure and exact emitted
   VS/PS hashes, so no zone precedence is guessed through shader dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_material_shader_census_v1 as v1

FORMAT = "t6-oat-material-shader-census-v2"
MaterialShaderCensusError = v1.MaterialShaderCensusError


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(material_root: Path, shader_roots: list[Path]) -> dict:
    original_index = v1._index_materials
    original_owner = v1._owner
    original_technique_passes = v1._technique_passes
    duplicate_rows: dict[tuple[str, str], dict] = {}
    excluded_generated: list[str] = []

    def index_ordinary(root: Path):
        rows = original_index(root)
        out = []
        for row in rows:
            relative = str(row.get("relativeMaterial") or "")
            if relative == "generated" or relative.startswith("generated/"):
                excluded_generated.append(relative)
                continue
            out.append(row)
        return out

    def record_duplicate(*, label: str, relative: Path, owners: list[Path], bytes_: int | None, sha256: str | None, resolution: str, pass_identity: str | None = None):
        key = (label, relative.as_posix())
        row = {
            "label": label,
            "relativeFile": relative.as_posix(),
            "owners": [str(root) for root in owners],
            "ownerCount": len(owners),
            "resolution": resolution,
        }
        if bytes_ is not None:
            row["bytes"] = bytes_
        if sha256 is not None:
            row["sha256"] = sha256
        if pass_identity is not None:
            row["parsedPassIdentitySha256"] = pass_identity
        duplicate_rows[key] = row

    def byte_identical_owner(roots: list[Path], relative: Path, label: str):
        matches = [(root, root / relative) for root in roots if (root / relative).is_file()]
        if not matches:
            raise MaterialShaderCensusError(f"{label}: no dump owner for {relative.as_posix()}")
        if len(matches) == 1:
            return matches[0]
        rows = [
            {"root": root, "path": path, "bytes": path.stat().st_size, "sha256": _sha(path)}
            for root, path in matches
        ]
        identities = {(row["bytes"], row["sha256"]) for row in rows}
        if len(identities) != 1:
            raise MaterialShaderCensusError(
                f"{label}: divergent duplicate dump owners for {relative.as_posix()}: "
                f"{[(str(row['root']), row['bytes'], row['sha256']) for row in rows]}"
            )
        record_duplicate(
            label=label,
            relative=relative,
            owners=[row["root"] for row in rows],
            bytes_=rows[0]["bytes"],
            sha256=rows[0]["sha256"],
            resolution="byte-identical-duplicate-zone-output",
        )
        return matches[0]

    def exact_duplicate_technique_passes(root_paths: list[Path], preferred_owner: Path, technique: str):
        relative = Path("techniques") / f"{technique}.tech"
        owners = [root for root in root_paths if (root / relative).is_file()]
        if not owners:
            raise MaterialShaderCensusError(f"Technique {technique}: no dump owner for {relative.as_posix()}")
        parsed = []
        for owner in owners:
            passes, file_record = original_technique_passes([owner], owner, technique)
            parsed.append((owner, passes, file_record))
        canonical = json.dumps(parsed[0][1], sort_keys=True, separators=(",", ":"), allow_nan=False)
        canonical_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        for owner, passes, _file in parsed[1:]:
            candidate = json.dumps(passes, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if candidate != canonical:
                raise MaterialShaderCensusError(
                    f"Technique {technique}: duplicate zone owners resolve to divergent pass/VS/PS identities: "
                    f"{[str(root) for root in owners]}"
                )
        chosen = next((row for row in parsed if row[0] == preferred_owner), parsed[0])
        if len(parsed) > 1:
            tech_files = [owner / relative for owner in owners]
            text_ids = {(p.stat().st_size, _sha(p)) for p in tech_files}
            # Parsed pass identity is authoritative for shader closure. Also retain
            # whether serialized .tech text itself was identical across zones.
            record_duplicate(
                label=f"Technique {technique}",
                relative=relative,
                owners=owners,
                bytes_=tech_files[0].stat().st_size if len(text_ids) == 1 else None,
                sha256=_sha(tech_files[0]) if len(text_ids) == 1 else None,
                resolution=(
                    "byte-identical-technique-and-identical-parsed-vs-ps"
                    if len(text_ids) == 1 else
                    "text-different-but-identical-parsed-pass-vs-ps"
                ),
                pass_identity=canonical_sha,
            )
        return chosen[1], chosen[2]

    v1._index_materials = index_ordinary
    v1._owner = byte_identical_owner
    v1._technique_passes = exact_duplicate_technique_passes
    try:
        result = v1.build(material_root, shader_roots)
    finally:
        v1._index_materials = original_index
        v1._owner = original_owner
        v1._technique_passes = original_technique_passes

    duplicates = [duplicate_rows[key] for key in sorted(duplicate_rows)]
    result["format"] = FORMAT
    result["baseFormat"] = v1.FORMAT
    result["summary"] = dict(result.get("summary", {}))
    result["summary"]["excludedGeneratedMaterialCount"] = len(excluded_generated)
    result["summary"]["duplicateDependencyIdentityCheckCount"] = len(duplicates)
    result["summary"]["divergentDuplicateDependencyCount"] = 0
    result["excludedGeneratedMaterialRelativeIdentities"] = sorted(excluded_generated)
    result["duplicateDependencies"] = duplicates
    result["proofBoundary"] = (
        str(result.get("proofBoundary") or "")
        + " v2 excludes OAT materials/generated rows from the ordinary census; multi-zone TechniqueSet owners require exact file identity; duplicate Technique owners require identical parsed pass structure and exact emitted VS/PS hashes. Divergence fails closed and no zone precedence is guessed."
    )
    return result


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
