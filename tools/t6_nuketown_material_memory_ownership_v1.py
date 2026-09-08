#!/usr/bin/env python3
"""Exact retail proof for Nuketown GfxSurface -> MaterialMemory -> Material ownership.

This closes the ambiguity exposed by the live source-sidecar regressions.  A
GfxSurface::material packed pointer is an alias to a MaterialMemory::material
slot in VIRTUAL block 5, not a top-level XAsset-array slot.

The physical MaterialMemory location is derived from loader serialization, not
scanned: GfxWorld owns materialMemory[count], the fixed 8-byte records are read
as one array, and their FOLLOW-owned Material children are then processed in
array order.  Therefore the fixed array ends exactly where the first serialized
Material child begins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from collections import Counter
from pathlib import Path

import t6_nuketown_world_source_sidecars_v1 as v1
import t6_retail_special_material_family_census_v1 as family
import t6_retail_world_formats_45_proof_v1 as worldproof

FORMAT = "t6-nuketown-material-memory-ownership-v1"
OAT_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
MATERIAL_MEMORY_BYTES = 8


class OwnershipError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_source(path: Path, snippets: list[str]) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        raise OwnershipError(f"{path}: missing pinned-source semantics {missing}")
    return {
        "path": str(path),
        "bytes": len(raw),
        "sha256": sha(raw),
        "checkedSnippets": snippets,
    }


def validate_loader(oat_root: Path) -> dict:
    commit = subprocess.check_output(
        ["git", "-C", str(oat_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != OAT_COMMIT:
        raise OwnershipError(f"OAT commit {commit} != {OAT_COMMIT}")

    assets = require_source(
        oat_root / "src/Common/Game/T6/T6_Assets.h",
        [
            "struct MaterialMemory",
            "Material* material;",
            "int memory;",
        ],
    )
    zone = require_source(
        oat_root / "src/ZoneCode/Game/T6/XAssets/GfxWorld.txt",
        [
            "set count materialMemory materialMemoryCount;",
            "set count surfaces GfxWorld::surfaceCount;",
        ],
    )
    template_path = oat_root / "src/ZoneCodeGeneratorLib/Generating/Templates/ZoneLoadTemplate.cpp"
    template = require_source(
        template_path,
        [
            "void PrintLoadArrayMethod",
            "const auto arrayFill = m_stream.LoadWithFill(",
            "for (size_t index = 0; index < count; index++)",
            "Load_{0}(false);",
        ],
    )
    text = template_path.read_text(encoding="utf-8")
    function_start = text.index("void PrintLoadArrayMethod")
    next_function = text.index("void PrintLoadMethod", function_start + 1)
    body = text[function_start:next_function]
    fixed = body.find("const auto arrayFill = m_stream.LoadWithFill(")
    loop = body.find("for (size_t index = 0; index < count; index++)")
    child = body.find("Load_{0}(false);")
    if not (0 <= fixed < loop < child):
        raise OwnershipError(
            "pinned array loader no longer proves fixed-array read before per-element child load"
        )
    return {
        "project": "Laupetin/OpenAssetTools",
        "commit": commit,
        "sourceChecks": {
            "t6Assets": assets,
            "gfxWorldZoneCode": zone,
            "loadTemplate": template,
        },
        "arraySerializationOrder": "fixed array bytes first, then Load_<element>(false) in index order",
    }


def build(expanded: Path, oat_root: Path) -> dict:
    data = expanded.read_bytes()
    if len(data) != v1.EXPANDED_BYTES or sha(data) != v1.EXPANDED_SHA256:
        raise OwnershipError("expanded retail Nuketown identity mismatch")

    loader = validate_loader(oat_root)
    blocks, _assets = worldproof.front(data)
    world = worldproof.world(data, v1.GFXWORLD_START, v1.SURFACE_COUNT, v1.MATERIAL_COUNT)
    if int(world["materialMemoryCount"]) != v1.MATERIAL_COUNT:
        raise OwnershipError("GfxWorld MaterialMemory count mismatch")
    if int(world["materialMemoryPtr"]) != worldproof.FOLLOW:
        raise OwnershipError("GfxWorld MaterialMemory pointer is not FOLLOW-owned")

    # Source physical boundary follows directly from the generated loader order:
    # one fixed MaterialMemory[327] array, immediately followed by the first
    # FOLLOW-owned Material child.  Physical XFile cursor alignment is not added.
    span = v1.MATERIAL_COUNT * MATERIAL_MEMORY_BYTES
    physical_end = v1.MATERIAL_START
    physical_start = physical_end - span
    records = data[physical_start:physical_end]
    if len(records) != span:
        raise OwnershipError("MaterialMemory fixed-array source span is truncated")
    raw_children = [struct.unpack_from("<I", records, i * 8)[0] for i in range(v1.MATERIAL_COUNT)]
    if any(value != worldproof.FOLLOW for value in raw_children):
        raise OwnershipError("one or more MaterialMemory::material children are not FOLLOW-owned")
    memories = [struct.unpack_from("<i", records, i * 8 + 4)[0] for i in range(v1.MATERIAL_COUNT)]

    surfaces = v1._surface_rows(data, world)
    surface_ptrs = sorted({int(row["materialPointerRaw"], 16) for row in surfaces})
    if len(surface_ptrs) != v1.MATERIAL_COUNT or any(
        b - a != MATERIAL_MEMORY_BYTES for a, b in zip(surface_ptrs, surface_ptrs[1:])
    ):
        raise OwnershipError("GfxSurface material aliases are not one contiguous 327-slot population")
    decoded = [worldproof.dec(raw, blocks) for raw in surface_ptrs]
    if any(kind != "packed" or block != 5 for kind, block, _ in decoded):
        raise OwnershipError("GfxSurface material aliases are not wholly packed VIRTUAL block 5")
    virtual_offsets = [offset for _, _, offset in decoded]
    if any(
        b - a != MATERIAL_MEMORY_BYTES for a, b in zip(virtual_offsets, virtual_offsets[1:])
    ):
        raise OwnershipError("GfxSurface material alias offsets do not match sizeof(MaterialMemory)=8")

    identity = family.bind_map(v1.MAP, expanded)
    materials, technique_qs = v1._material_chain(data, blocks, identity)
    if len(materials) != v1.MATERIAL_COUNT:
        raise OwnershipError("strict Material child chain count mismatch")

    catalog = []
    for index, (raw, virtual_offset, material) in enumerate(
        zip(surface_ptrs, virtual_offsets, materials)
    ):
        catalog.append(
            {
                "slotIndex": index,
                "surfaceAliasRawHex": f"0x{raw:08x}",
                "virtualBlock": 5,
                "virtualOffset": virtual_offset,
                "physicalRecordStart": physical_start + index * MATERIAL_MEMORY_BYTES,
                "material": material["name"],
                "techniqueSet": material["techniqueSet"]["name"],
                "worldVertFormat": material["worldVertFormat"],
            }
        )

    by_ptr = {int(row["surfaceAliasRawHex"], 16): row for row in catalog}
    _minimal, groups, _allocs = worldproof.surfaces_and_groups(
        data, v1.SURFACE_START, v1.SURFACE_COUNT, world
    )
    group_formats = Counter()
    for group in groups:
        formats = {int(by_ptr[p]["worldVertFormat"]) for p in group["mats"]}
        if len(formats) != 1:
            raise OwnershipError(f"vertex group {group['i']} has mixed formats {sorted(formats)}")
        group_formats[next(iter(formats))] += 1
    if len(groups) != v1.EXPECTED_GROUP_COUNT or group_formats != Counter(v1.EXPECTED_GROUP_FORMATS):
        raise OwnershipError("MaterialMemory slot join changes canonical vertex-format census")

    # Record why local signature scanning is invalid: shifting the fixed window
    # by one record can overlap 326 true entries and a preceding FOLLOW word.
    shifted_start = physical_start - MATERIAL_MEMORY_BYTES
    shifted_ptrs = [
        struct.unpack_from("<I", data, shifted_start + i * 8)[0]
        for i in range(v1.MATERIAL_COUNT)
    ]
    shifted_locally_matches = all(value == worldproof.FOLLOW for value in shifted_ptrs)

    return {
        "format": FORMAT,
        "map": v1.MAP,
        "source": {
            "file": expanded.name,
            "bytes": len(data),
            "sha256": sha(data),
        },
        "loader": loader,
        "gfxWorld": {
            "fixedStart": v1.GFXWORLD_START,
            "materialMemoryCount": v1.MATERIAL_COUNT,
            "materialMemoryPointerRawHex": f"0x{int(world['materialMemoryPtr']):08x}",
        },
        "materialMemory": {
            "recordBytes": MATERIAL_MEMORY_BYTES,
            "count": v1.MATERIAL_COUNT,
            "physicalStart": physical_start,
            "physicalEndExclusive": physical_end,
            "physicalBytes": span,
            "fixedArrayEndsAtFirstMaterialChild": physical_end == v1.MATERIAL_START,
            "allMaterialChildrenFollowOwned": True,
            "memoryValuesSha256": sha(struct.pack("<" + "i" * len(memories), *memories)),
            "memoryMin": min(memories),
            "memoryMax": max(memories),
            "virtualBlock": 5,
            "virtualStartOffset": virtual_offsets[0],
            "virtualEndOffsetExclusive": virtual_offsets[-1] + MATERIAL_MEMORY_BYTES,
            "surfaceAliasCount": len(surface_ptrs),
            "surfaceAliasStride": MATERIAL_MEMORY_BYTES,
        },
        "slotBindings": catalog,
        "validation": {
            "strictMaterialCount": len(materials),
            "referencedTechniqueSetCount": len(set(technique_qs)),
            "vertexGroupCount": len(groups),
            "groupFormatCounts": {str(k): v for k, v in sorted(group_formats.items())},
            "mixedFormatGroupCount": 0,
            "unresolvedSurfaceMaterialCount": 0,
            "shiftedMinusOneRecordWindowAlsoLocallyMatchesFollowSignature": shifted_locally_matches,
            "signatureScanRejectedAsOwnershipMethod": True,
        },
        "proofBoundary": (
            "The physical MaterialMemory span is derived from pinned generated-loader ordering and the independently strict first-Material child boundary, not selected from local byte candidates. "
            "GfxSurface aliases must independently form the exact packed VIRTUAL block-5 8-byte-stride population. Material identities then follow the 327 FOLLOW-owned children in slot order and retain exact Material -> TechniqueSet -> worldVertFormat binding."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--oat-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.expanded, args.oat_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw = args.out.read_bytes()
    print(
        json.dumps(
            {
                "out": str(args.out),
                "bytes": len(raw),
                "sha256": sha(raw),
                "physical": [
                    doc["materialMemory"]["physicalStart"],
                    doc["materialMemory"]["physicalEndExclusive"],
                ],
                "virtual": [
                    doc["materialMemory"]["virtualBlock"],
                    doc["materialMemory"]["virtualStartOffset"],
                    doc["materialMemory"]["virtualEndOffsetExclusive"],
                ],
                "slots": len(doc["slotBindings"]),
                "unresolved": doc["validation"]["unresolvedSurfaceMaterialCount"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
