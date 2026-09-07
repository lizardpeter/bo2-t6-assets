#!/usr/bin/env python3
"""T6 native Material shader census v2: ordinary-only + duplicate-owner proof.

Wraps v1 without changing its exact Material -> TechniqueSet -> lit Technique ->
ordered VS/PS identity grouping. v2 closes two coverage/ownership holes exposed
by the first full Nuketown run:

1. OAT writes generated compound Materials under ``materials/generated`` using
   disk-safe names. Those 120 rows belong to the separate exact generated
   120/34/34 recipe/DAG path and must not be counted as ordinary native rows.
2. The same TechniqueSet/Technique dependency may be emitted by more than one
   loaded zone. Multiple physical owners are accepted only when the candidate
   files are byte-identical. Divergent duplicate owners fail closed; no zone
   precedence is guessed.
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

    def byte_identical_owner(roots: list[Path], relative: Path, label: str):
        matches = [(root, root / relative) for root in roots if (root / relative).is_file()]
        if not matches:
            raise MaterialShaderCensusError(
                f"{label}: no dump owner for {relative.as_posix()}"
            )
        if len(matches) == 1:
            return matches[0]
        rows = [
            {
                "root": str(root),
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": _sha(path),
            }
            for root, path in matches
        ]
        identities = {(row["bytes"], row["sha256"]) for row in rows}
        if len(identities) != 1:
            raise MaterialShaderCensusError(
                f"{label}: divergent duplicate dump owners for {relative.as_posix()}: "
                f"{[(row['root'], row['bytes'], row['sha256']) for row in rows]}"
            )
        key = (label, relative.as_posix())
        duplicate_rows[key] = {
            "label": label,
            "relativeFile": relative.as_posix(),
            "bytes": rows[0]["bytes"],
            "sha256": rows[0]["sha256"],
            "owners": [row["root"] for row in rows],
            "ownerCount": len(rows),
            "resolution": "byte-identical-duplicate-zone-output",
        }
        # Root order is not semantic here because every candidate is byte-identical.
        return matches[0]

    v1._index_materials = index_ordinary
    v1._owner = byte_identical_owner
    try:
        result = v1.build(material_root, shader_roots)
    finally:
        v1._index_materials = original_index
        v1._owner = original_owner

    duplicates = [duplicate_rows[key] for key in sorted(duplicate_rows)]
    result["format"] = FORMAT
    result["baseFormat"] = v1.FORMAT
    result["summary"] = dict(result.get("summary", {}))
    result["summary"]["excludedGeneratedMaterialCount"] = len(excluded_generated)
    result["summary"]["byteIdenticalDuplicateDependencyCount"] = len(duplicates)
    result["summary"]["divergentDuplicateDependencyCount"] = 0
    result["excludedGeneratedMaterialRelativeIdentities"] = sorted(excluded_generated)
    result["byteIdenticalDuplicateDependencies"] = duplicates
    result["proofBoundary"] = (
        str(result.get("proofBoundary") or "")
        + " v2 excludes OAT materials/generated rows from the ordinary census and accepts multi-zone dependency ownership only after exact byte-count/SHA-256 identity agreement; divergent duplicates fail closed."
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
