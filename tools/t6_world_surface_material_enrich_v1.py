#!/usr/bin/env python3
"""Resolve T6 GfxSurface material pointers to exact material names.

The world surface walker naturally exposes serialized material pointers, while
human-usable/exportable material names live in the separately recovered world
material catalog. This tool joins those two source-closed records without
heuristics.

Expected catalog contract:
  {"materials": [{"surfacePointerHex": "0x...", "name": "..."}, ...]}

By default every surface pointer must resolve. `--allow-unresolved` exists only
for diagnostic workflows; production map export should remain strict.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


class MaterialResolutionError(RuntimeError):
    pass


def _pointer(value: object) -> int:
    if isinstance(value, int):
        return value & 0xFFFFFFFF
    if isinstance(value, str):
        return int(value, 0) & 0xFFFFFFFF
    raise MaterialResolutionError(f"unsupported material pointer {value!r}")


def enrich(
    surfaces_doc: dict,
    catalog_doc: dict,
    *,
    allow_unresolved: bool = False,
) -> dict:
    surfaces = surfaces_doc.get("surfaces")
    catalog = catalog_doc.get("materials")
    if not isinstance(surfaces, list):
        raise MaterialResolutionError("surface document has no surfaces list")
    if not isinstance(catalog, list):
        raise MaterialResolutionError("material catalog has no materials list")

    by_pointer: dict[int, dict] = {}
    duplicate_same_name = 0
    for record in catalog:
        if "surfacePointerHex" not in record:
            raise MaterialResolutionError(
                f"catalog record missing surfacePointerHex: {record!r}"
            )
        pointer = _pointer(record["surfacePointerHex"])
        name = record.get("name")
        if not isinstance(name, str) or not name:
            raise MaterialResolutionError(
                f"catalog pointer 0x{pointer:08x} has invalid material name {name!r}"
            )
        previous = by_pointer.get(pointer)
        if previous is not None:
            if previous["name"] != name:
                raise MaterialResolutionError(
                    f"catalog pointer 0x{pointer:08x} maps to both "
                    f"{previous['name']!r} and {name!r}"
                )
            duplicate_same_name += 1
            continue
        by_pointer[pointer] = record

    out = copy.deepcopy(surfaces_doc)
    resolved = 0
    unresolved: list[dict] = []
    existing_name_matches = 0

    for list_index, surface in enumerate(out["surfaces"]):
        surface_index = int(surface.get("index", list_index))
        raw_value = surface.get("materialPointerRaw")
        if raw_value is None:
            unresolved.append(
                {
                    "surface": surface_index,
                    "reason": "missing materialPointerRaw",
                }
            )
            continue

        pointer = _pointer(raw_value)
        record = by_pointer.get(pointer)
        if record is None:
            unresolved.append(
                {
                    "surface": surface_index,
                    "reason": "pointer absent from catalog",
                    "materialPointerRaw": f"0x{pointer:08x}",
                }
            )
            continue

        name = record["name"]
        existing = surface.get("material")
        if existing is not None:
            if str(existing) != name:
                raise MaterialResolutionError(
                    f"surface {surface_index}: existing material {existing!r} "
                    f"disagrees with catalog {name!r} for 0x{pointer:08x}"
                )
            existing_name_matches += 1
        surface["material"] = name

        catalog_index = record.get("materialIndex", record.get("index"))
        if surface.get("materialIndex") is None and catalog_index is not None:
            surface["materialIndex"] = int(catalog_index)

        surface["materialResolution"] = {
            "method": "exact materialPointerRaw -> surfacePointerHex",
            "materialPointerRaw": f"0x{pointer:08x}",
            "catalogName": name,
        }
        resolved += 1

    if unresolved and not allow_unresolved:
        preview = unresolved[:8]
        raise MaterialResolutionError(
            f"{len(unresolved)} surfaces did not resolve through the exact material "
            f"pointer catalog; first={preview}"
        )

    out["materialResolution"] = {
        "format": "t6-world-surface-material-resolution-v1",
        "policy": "exact pointer join; no name guessing or substitution",
        "catalogRecords": len(catalog),
        "uniqueCatalogPointers": len(by_pointer),
        "duplicateSameNameCatalogPointers": duplicate_same_name,
        "surfaceCount": len(out["surfaces"]),
        "resolvedSurfaceCount": resolved,
        "unresolvedSurfaceCount": len(unresolved),
        "existingNameMatches": existing_name_matches,
        "allSurfacesResolved": not unresolved,
        "unresolved": unresolved,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("surfaces_json", type=Path)
    parser.add_argument("material_catalog_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--allow-unresolved", action="store_true")
    args = parser.parse_args()

    surfaces = json.loads(args.surfaces_json.read_text(encoding="utf-8"))
    catalog = json.loads(args.material_catalog_json.read_text(encoding="utf-8"))
    out = enrich(
        surfaces,
        catalog,
        allow_unresolved=args.allow_unresolved,
    )
    text = json.dumps(out, indent=2, sort_keys=True) + "\n"
    args.output_json.write_text(text, encoding="utf-8")
    print(json.dumps({"out": str(args.output_json), **out["materialResolution"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
