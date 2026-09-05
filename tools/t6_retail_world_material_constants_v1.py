#!/usr/bin/env python3
"""Exact retained-world T6 Material constant-table reader.

This is intentionally a narrow companion to
`t6_retail_world_material_state_census_v2.py`.  That parser already validates the
entire serialized world Material record but historically only counted constants.
Here we re-walk the already source-closed child layout to retain every exact
MaterialConstantDef:

    uint32 nameHash
    char   name[12]
    float4 literal

The parser reads generated `*` Materials directly from the expanded retail world;
it does not reconstruct their constants from component materials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import t6_retail_special_material_family_census_v1 as family
import t6_retail_world_material_state_census_v2 as state


FORMAT = "t6-retail-world-material-constants-v1"


class RetailMaterialConstantError(RuntimeError):
    pass


def _constant_table_start(data: bytes, start: int, blocks) -> tuple[int, int, str]:
    """Return (constant-table offset, count, name) after exact inline texture payloads."""
    if start + 104 > len(data):
        raise RetailMaterialConstantError("material fixed header exceeds source")
    fixed = data[start:start + 104]
    texture_count = fixed[76]
    constant_count = fixed[77]
    if not 0 < texture_count <= 64 or constant_count > 64:
        raise RetailMaterialConstantError(
            f"invalid material counts tex={texture_count} const={constant_count}"
        )

    name, cursor = state.cstr(data, start + 104)
    texture_kinds: list[str] = []
    table_end = cursor + 16 * texture_count
    if table_end > len(data):
        raise RetailMaterialConstantError(f"{name!r}: texture table exceeds source")
    for index in range(texture_count):
        image_pointer = struct.unpack_from("<I", data, cursor + 16 * index + 12)[0]
        texture_kinds.append(state.req(image_pointer, blocks))
    cursor = table_end

    for index, kind in enumerate(texture_kinds):
        if kind not in ("follow", "insert"):
            continue
        if cursor + 80 > len(data):
            raise RetailMaterialConstantError(f"{name!r}: inline image {index} exceeds source")
        load_pointer = struct.unpack_from("<I", data, cursor)[0]
        name_pointer = struct.unpack_from("<I", data, cursor + 72)[0]
        load_kind = state.req(load_pointer, blocks)
        name_kind = state.req(name_pointer, blocks, False)
        if name_kind != "follow":
            raise RetailMaterialConstantError(
                f"{name!r}: inline image {index} name is not follow-owned"
            )
        cursor += 80
        _, cursor = state.cstr(data, cursor)
        if load_kind in ("follow", "insert"):
            if cursor + 12 > len(data):
                raise RetailMaterialConstantError(f"{name!r}: image loadDef header exceeds source")
            resource_size = struct.unpack_from("<i", data, cursor + 8)[0]
            if resource_size < 0 or cursor + 12 + resource_size > len(data):
                raise RetailMaterialConstantError(
                    f"{name!r}: invalid image loadDef resource size {resource_size}"
                )
            cursor += 12 + resource_size
    return cursor, constant_count, name


def parse_constants(data: bytes, start: int, blocks) -> list[dict]:
    # First invoke the established whole-record parser. This keeps this archival
    # reader coupled to the same strict fixed/child/state invariants as the census.
    validated = state.material(data, start, blocks)
    table, count, name = _constant_table_start(data, start, blocks)
    if name != validated["name"] or count != validated["constantCount"]:
        raise RetailMaterialConstantError(f"{name!r}: constant-table traversal disagrees with state parser")

    out: list[dict] = []
    seen_hashes: set[int] = set()
    for index in range(count):
        offset = table + 32 * index
        if offset + 32 > len(data):
            raise RetailMaterialConstantError(f"{name!r}: constant {index} exceeds source")
        name_hash = struct.unpack_from("<I", data, offset)[0]
        fragment_raw = data[offset + 4:offset + 16]
        fragment = fragment_raw.split(b"\0", 1)[0]
        if not fragment or any(byte < 32 or byte > 126 for byte in fragment):
            raise RetailMaterialConstantError(f"{name!r}: invalid constant {index} name fragment")
        literal = list(struct.unpack_from("<4f", data, offset + 16))
        if any(not math.isfinite(value) for value in literal):
            raise RetailMaterialConstantError(f"{name!r}: non-finite constant {index} literal")
        if name_hash in seen_hashes:
            raise RetailMaterialConstantError(
                f"{name!r}: duplicate MaterialConstantDef hash 0x{name_hash:08x}"
            )
        seen_hashes.add(name_hash)
        out.append({
            "index": index,
            "fileOffset": offset,
            "nameHash": name_hash,
            "nameHashHex": f"0x{name_hash:08x}",
            "nameFragment": fragment.decode("ascii"),
            "nameFragmentHex": fragment_raw.hex(),
            "literal": literal,
            "serializedSha256": hashlib.sha256(data[offset:offset + 32]).hexdigest(),
        })
    return out


def bind_map(name: str, path: Path) -> list[dict]:
    if name not in state.MAPS:
        raise RetailMaterialConstantError(f"unsupported retained map {name!r}")
    cfg = state.MAPS[name]
    data = Path(path).read_bytes()
    if len(data) != cfg[2] or hashlib.sha256(data).hexdigest() != cfg[1]:
        raise RetailMaterialConstantError(f"{name}: expanded retail source mismatch")
    blocks, _assets = family.front(data)
    identity_rows = family.bind_map(name, Path(path))
    if len(identity_rows) != cfg[4]:
        raise RetailMaterialConstantError(
            f"{name}: binding row count {len(identity_rows)} != material count {cfg[4]}"
        )

    cursor = cfg[3]
    rows: list[dict] = []
    for index, identity in enumerate(identity_rows):
        parsed = state.material(data, cursor, blocks)
        if parsed["name"] != identity["material"]:
            raise RetailMaterialConstantError(
                f"{name}: material order mismatch at {index}: {parsed['name']!r} != {identity['material']!r}"
            )
        constants = parse_constants(data, cursor, blocks)
        rows.append({
            **identity,
            "materialIndex": index,
            "materialStart": cursor,
            "materialArchiveSha256": parsed["archiveSha256"],
            "constantCount": len(constants),
            "constants": constants,
        })
        cursor = parsed["end"] + 8
    if rows and state.material(data, rows[-1]["materialStart"], blocks)["end"] != cfg[5]:
        raise RetailMaterialConstantError(f"{name}: final material end mismatch")
    return rows


def build(name: str, path: Path, *, generated_only: bool = False) -> dict:
    rows = bind_map(name, path)
    if generated_only:
        rows = [row for row in rows if row["material"].startswith("*")]
    constant_count = sum(row["constantCount"] for row in rows)
    hashes = sorted({item["nameHash"] for row in rows for item in row["constants"]})
    return {
        "format": FORMAT,
        "map": name,
        "source": {
            "file": Path(path).name,
            "bytes": Path(path).stat().st_size,
            "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        },
        "generatedOnly": generated_only,
        "materials": rows,
        "stats": {
            "materialCount": len(rows),
            "constantCount": constant_count,
            "uniqueConstantHashCount": len(hashes),
        },
        "proofBoundary": (
            "Direct serialized MaterialConstantDef bytes from the retained expanded GfxWorld Material chain; "
            "no component-material merge reconstruction and no semantic-name guessing."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", dest="map_name", required=True)
    parser.add_argument("--expanded-world", type=Path, required=True)
    parser.add_argument("--generated-only", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    doc = build(args.map_name, args.expanded_world, generated_only=args.generated_only)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
