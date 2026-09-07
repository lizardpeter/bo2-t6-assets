#!/usr/bin/env python3
"""Import exact XModel Material-handle proof rows into a retail asset index.

This adapter intentionally creates references only.  `ownerMaterialRawStart`
belongs to the proof that a Material handle resolves to a name; it is never
promoted into an authoritative Material-definition start by this tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_retail_asset_index_v1 import (
    AssetIndexError,
    AssetReference,
    RetailAssetIndex,
    StaleIndexError,
    ZoneFingerprint,
)


def source_fingerprint(proof: dict, zone: str) -> ZoneFingerprint:
    src = proof.get("source") or {}
    try:
        size = int(src["expandedBytes"])
        sha256 = str(src["expandedSha256"]).lower()
    except (KeyError, TypeError, ValueError) as exc:
        raise AssetIndexError("handle proof lacks exact expandedBytes/expandedSha256") from exc
    if size <= 0 or len(sha256) != 64:
        raise AssetIndexError("invalid source fingerprint in handle proof")
    return ZoneFingerprint(zone=zone, sha256=sha256, size=size)


def attach_material_handle_proof(
    index: RetailAssetIndex,
    proof: dict,
    source_zone: str,
) -> list[AssetReference]:
    fp = source_fingerprint(proof, source_zone)
    old = index.zones.get(source_zone)
    if old is None:
        index.add_zone(fp)
    elif old != fp:
        raise StaleIndexError(
            f"{source_zone}: handle proof fingerprint does not match indexed zone"
        )

    summary = proof.get("summary") or {}
    if summary.get("targetAllHandlesExact") is not True:
        raise AssetIndexError("refusing non-exact Material-handle proof")

    rows = proof.get("uniqueHandleOwners")
    if not isinstance(rows, list) or not rows:
        raise AssetIndexError("handle proof has no uniqueHandleOwners")

    refs: list[AssetReference] = []
    exact_names: set[str] = set()
    for row in rows:
        name = row.get("materialName")
        evidence = row.get("evidence")
        owner_model = row.get("ownerModel")
        if not isinstance(name, str) or not name:
            raise AssetIndexError(f"bad Material name in handle row: {row!r}")
        if not isinstance(evidence, str) or not evidence:
            raise AssetIndexError(f"missing exact evidence for {name}")
        if not isinstance(owner_model, str) or not owner_model:
            raise AssetIndexError(f"missing owner model for {name}")
        raw_start = row.get("ownerMaterialRawStart")
        owner_start = None if raw_start is None else int(raw_start)
        ref = AssetReference(
            asset_type="material",
            name=name,
            source_zone=source_zone,
            source_asset=owner_model,
            owner_start=owner_start,
            proof={
                "evidence": evidence,
                "materialPointerRaw": row.get("materialPointerRaw"),
                "ownerSlotIndex": row.get("ownerSlotIndex"),
                "ownerFieldVirtualOffset": row.get("ownerFieldVirtualOffset"),
                "ownerMaterialRawStartIsDefinitionStart": False,
            },
        )
        index.add_reference(ref)
        refs.append(ref)
        exact_names.add(name)

    surfaces = proof.get("surfaceMaterialSequence") or []
    missing = sorted({x for x in surfaces if x not in exact_names})
    if missing:
        raise AssetIndexError(
            "surface sequence contains Material identities with no exact owner: "
            + ", ".join(missing)
        )
    return refs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("handle_proof", type=Path)
    ap.add_argument("--source-zone", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    index = RetailAssetIndex.load(a.index) if a.index.exists() else RetailAssetIndex()
    proof = json.loads(a.handle_proof.read_text(encoding="utf-8"))
    refs = attach_material_handle_proof(index, proof, a.source_zone)
    index.save(a.out)
    print(json.dumps({
        "sourceZone": a.source_zone,
        "referencesAdded": len(refs),
        "uniqueMaterialNames": len({x.name for x in refs}),
        "definitionStartsPromotedFromOwnerRows": 0,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
