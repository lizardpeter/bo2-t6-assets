#!/usr/bin/env python3
"""Census exact standalone OAT Material ownership for layered components.

This tool deliberately does not change the production Material union. The
production union remains restricted to source-derived catalog storage identities.
Here we answer a narrower secondary question: for component-only identities,
did any supplied native OAT dump root contain a standalone Material JSON?

Targets may be derived directly from a required catalog, or supplied explicitly
when they are already pinned outputs of an earlier fail-closed manifest. The
latter mode is useful for a small ownership probe without rerunning the entire
world-catalog pipeline.

For each target identity:

- no physical copy -> record missing evidence;
- one physical copy -> record its exact owner/hash;
- multiple byte-identical copies -> record every owner and one exact hash;
- multiple byte-different copies -> record a divergence and fail closed.

No owner precedence, filename similarity, component adjacency, or synthetic
Material is admitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_oat_material_root_union_v1 import (
    UnionError,
    index_root,
    required_from_catalog,
    sha256,
)

FORMAT = "t6-oat-component-material-owner-census-v1"


def _targets(
    *,
    catalog_path: Path | None,
    explicit_identities: list[str] | None,
    target_source: str | None,
) -> tuple[list[str], dict]:
    if catalog_path is not None:
        if explicit_identities:
            raise UnionError("cannot combine --required-catalog with explicit component identities")
        _required, source = required_from_catalog(catalog_path)
        component_only = source.get("componentOnlyMaterialIdentities")
        if not isinstance(component_only, list):
            raise UnionError("required catalog metadata lacks componentOnlyMaterialIdentities[]")
        identities = [str(x) for x in component_only]
        source_doc = {"kind": "required-catalog-derived", "catalog": source}
    else:
        identities = [str(x) for x in (explicit_identities or [])]
        if not identities:
            raise UnionError("no component identities supplied")
        if not target_source:
            raise UnionError("explicit component identities require --target-source")
        source_doc = {
            "kind": "explicit-pinned-identities",
            "description": target_source,
            "componentOnlyMaterialIdentities": sorted(identities),
        }

    if any(not identity for identity in identities):
        raise UnionError("empty component-only identity")
    if len(identities) != len(set(identities)):
        raise UnionError("duplicate component-only identity")
    return sorted(identities), source_doc


def build(
    roots: list[tuple[str, Path]],
    *,
    catalog_path: Path | None = None,
    explicit_identities: list[str] | None = None,
    target_source: str | None = None,
) -> dict:
    if not roots:
        raise UnionError("no Material roots supplied")

    component_only, source = _targets(
        catalog_path=catalog_path,
        explicit_identities=explicit_identities,
        target_source=target_source,
    )
    indexed = {label: index_root(label, root) for label, root in roots}
    rows: list[dict] = []
    missing: list[str] = []
    divergent: list[dict] = []

    for identity in component_only:
        copies = [indexed[label][identity] for label in sorted(indexed) if identity in indexed[label]]
        owners = [row["label"] for row in copies]
        if not copies:
            missing.append(identity)
            rows.append(
                {
                    "identity": identity,
                    "status": "missing-from-all-supplied-native-oat-roots",
                    "owners": [],
                    "ownerCount": 0,
                    "bytes": None,
                    "sha256": None,
                    "byteIdenticalAcrossOwners": None,
                }
            )
            continue

        hashes = {row["sha256"] for row in copies}
        if len(hashes) != 1:
            detail = {
                "identity": identity,
                "owners": owners,
                "copies": [
                    {
                        "owner": row["label"],
                        "relative": row["relative"],
                        "bytes": row["bytes"],
                        "sha256": row["sha256"],
                    }
                    for row in copies
                ],
            }
            divergent.append(detail)
            rows.append(
                {
                    "identity": identity,
                    "status": "byte-divergent-across-supplied-native-oat-roots",
                    "owners": owners,
                    "ownerCount": len(copies),
                    "bytes": None,
                    "sha256": None,
                    "byteIdenticalAcrossOwners": False,
                }
            )
            continue

        selected = copies[0]
        rows.append(
            {
                "identity": identity,
                "status": (
                    "exact-single-owner-standalone-material"
                    if len(copies) == 1
                    else "exact-byte-identical-multi-owner-standalone-material"
                ),
                "owners": owners,
                "ownerCount": len(copies),
                "relative": selected["relative"],
                "bytes": selected["bytes"],
                "sha256": selected["sha256"],
                "byteIdenticalAcrossOwners": True,
            }
        )

    present = [row for row in rows if row["ownerCount"] > 0 and row["byteIdenticalAcrossOwners"]]
    doc = {
        "format": FORMAT,
        "authoritativeForPresentStandaloneComponents": not divergent,
        "summary": {
            "rootCount": len(roots),
            "physicalMaterialJsonCount": sum(len(rows_) for rows_ in indexed.values()),
            "componentOnlyIdentityCount": len(component_only),
            "presentComponentOnlyIdentityCount": len(present),
            "missingComponentOnlyIdentityCount": len(missing),
            "divergentComponentOnlyIdentityCount": len(divergent),
            "singleOwnerComponentOnlyIdentityCount": sum(1 for row in present if row["ownerCount"] == 1),
            "byteIdenticalMultiOwnerComponentOnlyIdentityCount": sum(1 for row in present if row["ownerCount"] > 1),
        },
        "targetSource": source,
        "roots": [
            {"label": label, "path": str(root), "materialJsonCount": len(indexed[label])}
            for label, root in roots
        ],
        "components": rows,
        "missing": missing,
        "divergent": divergent,
        "proofBoundary": (
            "This census is secondary standalone-component evidence only. It does not alter production dependency authority or infer retail owner precedence. A present component is admitted only from an exact native OAT Material JSON; multiple physical copies must be byte-identical. Missing standalone evidence remains missing, and byte-divergent owners are a hard blocker."
        ),
    }
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", required=True, help="LABEL=PATH")
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--required-catalog", type=Path)
    target.add_argument("--component-identity", action="append")
    ap.add_argument("--target-source")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    roots: list[tuple[str, Path]] = []
    labels: set[str] = set()
    for spec in args.root:
        if "=" not in spec:
            raise UnionError(f"invalid --root {spec!r}; expected LABEL=PATH")
        label, raw_path = spec.split("=", 1)
        if not label or label in labels:
            raise UnionError(f"empty/duplicate root label {label!r}")
        labels.add(label)
        roots.append((label, Path(raw_path)))

    doc = build(
        roots,
        catalog_path=args.required_catalog,
        explicit_identities=args.component_identity,
        target_source=args.target_source,
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({"out": str(args.out), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    for row in doc["components"]:
        print("COMPONENT_OWNER", json.dumps(row, sort_keys=True))
    if doc["divergent"]:
        raise UnionError(
            f"component Material owner census found {len(doc['divergent'])} byte-divergent identities"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
