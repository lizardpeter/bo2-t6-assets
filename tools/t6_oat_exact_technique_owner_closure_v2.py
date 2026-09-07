#!/usr/bin/env python3
"""Close one exact T6 Technique owner from provenance-aware native census v4.

The source census already proves Material -> TechniqueSet -> declared type ->
parent-owned Technique through pinned OAT's same-zone pointer traversal.  This
adapter adds the target-specific closure gates:

* source census is green v4 with zero divergent parent-owned dependencies;
* every physical copy of the exact target Technique has the required byte count
  and SHA-256 (duplicates may exist only if byte-identical);
* at least one Material program association names the exact target;
* every associated parent TechniqueSet file explicitly binds the same declared
  type to that target Technique.

No q-index, serialized offset, byte scan, name similarity, adjacency, visual
appearance, or guessed zone precedence can produce an authoritative result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_oat_exact_technique_owner_closure_v1 as v1
import t6_oat_techset_binding_manifest_v1 as oat

FORMAT = "t6-oat-exact-technique-owner-closure-v2"
SOURCE_FORMAT = "t6-oat-material-shader-census-v4"
ClosureError = v1.ClosureError


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _records(roots: list[tuple[str, Path]], relative: Path, label: str) -> list[dict]:
    rows = []
    for zone, root in roots:
        path = root / relative
        if path.is_file():
            rows.append({
                "zone": zone,
                "root": str(root),
                "relativeFile": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha(path),
                "path": path,
            })
    if not rows:
        raise ClosureError(f"{label}: no OAT-emitted file {relative.as_posix()}")
    identities = {(r["bytes"], r["sha256"]) for r in rows}
    if len(identities) != 1:
        raise ClosureError(
            f"{label}: divergent physical outputs for {relative.as_posix()}: "
            f"{[(r['zone'], r['bytes'], r['sha256']) for r in rows]}"
        )
    return rows


def _public(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "path"} for row in rows]


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("shader root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    label = label.strip()
    path = Path(raw).resolve()
    if not label or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid shader root {value!r}")
    return label, path


def build(
    census_path: Path,
    roots: list[tuple[str, Path]],
    target_name: str,
    target_bytes: int,
    target_sha256: str,
) -> dict:
    census = json.loads(census_path.read_text(encoding="utf-8"))
    if census.get("format") != SOURCE_FORMAT:
        raise ClosureError(f"unexpected census format {census.get('format')!r}")
    if census.get("unresolved"):
        raise ClosureError("source census is not green: unresolved rows are present")
    summary = census.get("summary", {})
    if int(summary.get("unresolvedMaterialCount", -1)) != 0:
        raise ClosureError("source census does not certify zero unresolved Materials")
    if int(summary.get("divergentParentOwnedDependencyCount", -1)) != 0:
        raise ClosureError("source census does not certify zero divergent parent-owned dependencies")

    relative = Path("techniques") / f"{target_name}.tech"
    target_rows = _records(roots, relative, "target Technique")
    observed = {(row["bytes"], row["sha256"].lower()) for row in target_rows}
    expected = (int(target_bytes), target_sha256.lower())
    if observed != {expected}:
        raise ClosureError(
            f"target Technique identity mismatch: expected {expected}, observed {sorted(observed)}"
        )

    associations = []
    for material in census.get("materials", []):
        for program in material.get("programs", []):
            if program.get("technique") != target_name:
                continue
            parent_owners = [str(v) for v in program.get("parentTechniqueSetOwners", [])]
            technique_owner = str(program.get("techniqueOwner") or "")
            if not parent_owners or not technique_owner:
                raise ClosureError(
                    f"target association for Material {material.get('material')!r} lacks v4 parent/child provenance"
                )
            if technique_owner not in parent_owners:
                raise ClosureError(
                    f"target association for Material {material.get('material')!r} chooses Technique owner outside parent TechniqueSet owners"
                )
            associations.append({
                "material": material.get("material"),
                "materialJsonSha256": material.get("materialJsonSha256"),
                "techniqueSet": material.get("techniqueSet"),
                "techniqueType": program.get("techniqueType"),
                "groupKey": program.get("groupKey"),
                "passStageIdentitySha256": program.get("passStageIdentitySha256"),
                "passCount": program.get("passCount"),
                "parentTechniqueSetOwners": parent_owners,
                "techniqueOwner": technique_owner,
            })
    if not associations:
        raise ClosureError(
            "exact target Technique is emitted, but the green provenance-aware Material census has no Material -> TechniqueSet -> Technique association for it"
        )

    parent_rows = []
    for techset in sorted({str(row["techniqueSet"]) for row in associations}):
        rel = Path("techsets") / f"{techset}.techset"
        physical = _records(roots, rel, f"parent TechniqueSet {techset}")
        first = physical[0]["path"]
        bindings, errors = oat.parse_techset(first.read_text(encoding="utf-8", errors="strict"))
        if errors:
            raise ClosureError(f"parent TechniqueSet {techset}: parse errors {errors[:4]}")
        exact_bindings = [row for row in bindings if row.get("technique") == target_name]
        if not exact_bindings:
            raise ClosureError(f"parent TechniqueSet {techset}: text does not name target Technique")

        declared = sorted({
            str(a["techniqueType"])
            for a in associations
            if str(a["techniqueSet"]) == techset
        })
        parent_types = sorted({str(t) for row in exact_bindings for t in row.get("types", [])})
        missing = sorted(set(declared) - set(parent_types))
        if missing:
            raise ClosureError(
                f"parent TechniqueSet {techset}: census types {missing} are absent from exact target binding"
            )

        census_parent_owners = sorted({
            owner
            for association in associations
            if str(association["techniqueSet"]) == techset
            for owner in association["parentTechniqueSetOwners"]
        })
        physical_roots = sorted(str(row["path"].parent.parent.resolve()) for row in physical)
        if census_parent_owners != physical_roots:
            raise ClosureError(
                f"parent TechniqueSet {techset}: v4 provenance owners disagree with physical outputs: "
                f"census={census_parent_owners}, physical={physical_roots}"
            )

        parent_rows.append({
            "techniqueSet": techset,
            "physicalOutputs": _public(physical),
            "targetBindings": exact_bindings,
            "censusDeclaredTypes": declared,
            "censusParentOwners": census_parent_owners,
        })

    associations.sort(
        key=lambda row: (str(row["techniqueSet"]), str(row["techniqueType"]), str(row["material"]))
    )
    return {
        "format": FORMAT,
        "sourceCensus": {
            "path": census_path.name,
            "sha256": _sha(census_path),
            "format": census.get("format"),
            "proofBoundary": census.get("proofBoundary"),
        },
        "target": {
            "technique": target_name,
            "relativeFile": relative.as_posix(),
            "bytes": target_bytes,
            "sha256": target_sha256.lower(),
            "physicalOutputs": _public(target_rows),
        },
        "nativeAssociations": associations,
        "parentTechniqueSets": parent_rows,
        "summary": {
            "targetPhysicalOutputCount": len(target_rows),
            "nativeAssociationCount": len(associations),
            "parentTechniqueSetCount": len(parent_rows),
            "divergentPhysicalOutputCount": 0,
            "divergentParentOwnedDependencyCount": 0,
            "unresolvedCount": 0,
            "authoritative": True,
        },
        "proofBoundary": (
            "Authoritative only because a green pinned-OAT v4 Material census proves the exact Technique through same-root parent MaterialTechniqueSet pointer provenance, the parent OAT .techset text independently names the same Technique under every declared type, and every emitted target .tech file agrees with the required byte count/SHA-256. Same-name non-parent alternate Techniques cannot establish ownership. No q-index, source offset, scan hit, asset-name similarity, adjacency, appearance, or guessed zone precedence participates."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--census", type=Path, required=True)
    p.add_argument("--shader-root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--target-name", required=True)
    p.add_argument("--target-bytes", type=int, required=True)
    p.add_argument("--target-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if len(a.target_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in a.target_sha256):
        p.error("--target-sha256 must be 64 hex characters")
    result = build(a.census.resolve(), a.shader_root, a.target_name, a.target_bytes, a.target_sha256)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
