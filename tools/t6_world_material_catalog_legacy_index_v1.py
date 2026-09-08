#!/usr/bin/env python3
"""Project source-derived Nuketown Material catalog v3 into legacy consumer schema.

The v3 retail catalog deliberately names its source slot ``materialIndex``.
Older OAT world material-manifest consumers require the same ordinal under the
field name ``index``.  This adapter adds that compatibility alias only after
requiring the exact 327-row contiguous source population and preserving every
existing field unchanged.

No material identity, pointer, TechniqueSet, format, or ordering is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORMAT_IN = "t6-world-surface-material-catalog-source-v3"
FORMAT_OUT = "t6-world-surface-material-catalog-source-v3-legacy-index-v1"
MAP = "mp_nuketown_2020"
COUNT = 327
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"


class CatalogAdapterError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(doc: dict) -> dict:
    if doc.get("format") != FORMAT_IN:
        raise CatalogAdapterError(f"input format {doc.get('format')!r} != {FORMAT_IN!r}")
    if doc.get("map") != MAP:
        raise CatalogAdapterError(f"input map {doc.get('map')!r} != {MAP!r}")
    source = doc.get("source") or {}
    if source.get("expandedSha256") != EXPANDED_SHA256:
        raise CatalogAdapterError("catalog is not bound to canonical expanded Nuketown")
    rows = doc.get("materials")
    if not isinstance(rows, list) or len(rows) != COUNT:
        raise CatalogAdapterError(f"catalog row count {len(rows) if isinstance(rows,list) else None} != {COUNT}")

    projected = []
    names = set()
    pointers = set()
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict):
            raise CatalogAdapterError(f"row {ordinal} is not an object")
        material_index = int(row.get("materialIndex", -1))
        slot_index = int(row.get("materialMemorySlotIndex", -1))
        if material_index != ordinal or slot_index != ordinal:
            raise CatalogAdapterError(
                f"row {ordinal}: materialIndex/slotIndex {material_index}/{slot_index} != ordinal"
            )
        if "index" in row and int(row["index"]) != ordinal:
            raise CatalogAdapterError(f"row {ordinal}: pre-existing legacy index disagrees")
        name = str(row.get("name") or "")
        pointer = str(row.get("surfacePointerHex") or "")
        if not name or name in names:
            raise CatalogAdapterError(f"row {ordinal}: empty/duplicate Material name {name!r}")
        if not pointer or pointer in pointers:
            raise CatalogAdapterError(f"row {ordinal}: empty/duplicate surface pointer {pointer!r}")
        names.add(name)
        pointers.add(pointer)
        out = dict(row)
        out["index"] = ordinal
        projected.append(out)

    out_doc = dict(doc)
    out_doc["format"] = FORMAT_OUT
    out_source = dict(source)
    out_source["compatibilityProjection"] = {
        "adapter": "t6_world_material_catalog_legacy_index_v1.py",
        "addedField": "index",
        "equation": "index == materialIndex == materialMemorySlotIndex == row ordinal",
        "sourceFieldMutationCount": 0,
        "semanticInferenceCount": 0,
    }
    out_doc["source"] = out_source
    out_doc["materials"] = projected
    out_doc["compatibility"] = {
        "legacyIndexAddedCount": COUNT,
        "sourceRowCount": COUNT,
        "sourceOrderPreserved": True,
        "sourceFieldsPreserved": True,
    }
    return out_doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    raw = args.input.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    out = build(doc)
    payload = (json.dumps(out, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(json.dumps({
        "out": str(args.output),
        "bytes": len(payload),
        "sha256": sha256(payload),
        "sourceBytes": len(raw),
        "sourceSha256": sha256(raw),
        "rowCount": len(out["materials"]),
        "legacyIndexAddedCount": out["compatibility"]["legacyIndexAddedCount"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
