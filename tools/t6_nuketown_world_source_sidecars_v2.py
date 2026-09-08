#!/usr/bin/env python3
"""Retail Nuketown GfxWorld sidecars v2: exact MaterialMemory-slot ownership.

v1 deliberately tested whether GfxSurface::material packed pointers addressed the
top-level XAsset array.  Live retail execution rejected that model.  v2 keeps the
same exact byte parsers but proves the observed layout instead:

    GfxSurface.material packed pointer
      -> VIRTUAL block-5 contiguous 8-byte slot population
      -> GfxWorld MaterialMemory[count=327] (sizeof=8)
      -> FOLLOW-owned Material* children in slot order
      -> strict 327-record serialized Material chain
      -> exact Material::techniqueSet XAsset
      -> exact worldVertFormat

The legacy exporter compatibility files are generated only after those layers
agree. No material name, shader name, adjacency guess, or old GLB participates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import t6_nuketown_world_source_sidecars_v1 as v1
import t6_retail_special_material_family_census_v1 as family
import t6_retail_world_formats_45_proof_v1 as worldproof

FORMAT = "t6-nuketown-world-source-sidecars-v2"
MATERIAL_MEMORY_BYTES = 8
MAX_MATERIAL_MEMORY_TO_FIRST_MATERIAL_GAP = 256


class SidecarV2Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _record(path: Path, payload: bytes) -> dict:
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _material_memory_physical_candidate(data: bytes) -> dict:
    span = v1.MATERIAL_COUNT * MATERIAL_MEMORY_BYTES
    candidates = []
    for gap in range(MAX_MATERIAL_MEMORY_TO_FIRST_MATERIAL_GAP + 1):
        start = v1.MATERIAL_START - span - gap
        if start < 0:
            continue
        material_ptrs = [struct.unpack_from("<I", data, start + i * 8)[0] for i in range(v1.MATERIAL_COUNT)]
        if all(value == worldproof.FOLLOW for value in material_ptrs):
            memories = [struct.unpack_from("<i", data, start + i * 8 + 4)[0] for i in range(v1.MATERIAL_COUNT)]
            candidates.append(
                {
                    "start": start,
                    "end": start + span,
                    "gapToFirstMaterial": gap,
                    "memoryValuesSha256": _sha(struct.pack("<" + "i" * len(memories), *memories)),
                    "memoryMin": min(memories),
                    "memoryMax": max(memories),
                }
            )
    if len(candidates) != 1:
        raise SidecarV2Error(
            f"MaterialMemory physical allocation candidate count {len(candidates)} != 1: {candidates[:8]}"
        )
    return candidates[0]


def build(expanded: Path, output_dir: Path) -> dict:
    data = expanded.read_bytes()
    if len(data) != v1.EXPANDED_BYTES or _sha(data) != v1.EXPANDED_SHA256:
        raise SidecarV2Error("expanded retail Nuketown source identity mismatch")

    blocks, assets = worldproof.front(data)
    world = worldproof.world(data, v1.GFXWORLD_START, v1.SURFACE_COUNT, v1.MATERIAL_COUNT)
    checks = {
        "surfaceCount": v1.SURFACE_COUNT,
        "lightmapCount": 2,
        "vertexCount": v1.VERTEX_COUNT,
        "vd0Bytes": v1.VD0_END - v1.VD0_START,
        "vd1Bytes": v1.VD1_END - v1.VD1_START,
        "indexCount": v1.INDEX_COUNT,
        "materialMemoryCount": v1.MATERIAL_COUNT,
    }
    for key, expected in checks.items():
        if int(world[key]) != expected:
            raise SidecarV2Error(f"GfxWorld {key} {world[key]} != {expected}")
    if int(world["materialMemoryPtr"]) != worldproof.FOLLOW:
        raise SidecarV2Error("GfxWorld MaterialMemory pointer is not FOLLOW-owned")

    vd0 = data[v1.VD0_START:v1.VD0_END]
    vd1 = data[v1.VD1_START:v1.VD1_END]
    indices = data[v1.INDEX_START:v1.INDEX_END]
    if _sha(vd0) != v1.VD0_SHA256 or _sha(vd1) != v1.VD1_SHA256 or _sha(indices) != v1.INDEX_SHA256:
        raise SidecarV2Error("canonical draw-buffer hash mismatch")

    surfaces = v1._surface_rows(data, world)
    minimal, groups, _allocs = worldproof.surfaces_and_groups(
        data, v1.SURFACE_START, v1.SURFACE_COUNT, world
    )
    if len(minimal) != len(surfaces):
        raise SidecarV2Error("independent GfxSurface parser count mismatch")
    for rawrow, full in zip(minimal, surfaces):
        i, off0, off1, vc, mat = rawrow
        if (
            i != full["index"]
            or off0 != full["vertexDataOffset0"]
            or off1 != full["vertexDataOffset1"]
            or vc != full["vertexCount"]
            or mat != int(full["materialPointerRaw"], 16)
        ):
            raise SidecarV2Error(f"surface {i}: independent parser disagreement")

    identity = family.bind_map(v1.MAP, expanded)
    materials, technique_qs = v1._material_chain(data, blocks, identity)
    if len(materials) != v1.MATERIAL_COUNT:
        raise SidecarV2Error("strict Material chain count mismatch")
    if Counter(int(row["worldVertFormat"]) for row in identity) != Counter(v1.EXPECTED_MATERIAL_FORMATS):
        raise SidecarV2Error("Material worldVertFormat histogram changed")
    if not all(v1.TECH_Q0 <= q <= v1.TECH_Q1 for q in technique_qs):
        raise SidecarV2Error("Material TechniqueSet XAsset escaped canonical range")

    tech_body = family.techs(data, blocks, v1.GFXWORLD_START)[-(v1.TECH_Q1 - v1.TECH_Q0 + 1):]
    if len(tech_body) != v1.TECH_Q1 - v1.TECH_Q0 + 1:
        raise SidecarV2Error("TechniqueSet body length changed")
    by_q = {v1.TECH_Q0 + i: row for i, row in enumerate(tech_body)}
    for material in materials:
        q = int(material["techniqueSet"]["assetIndex"])
        row = by_q[q]
        if row["name"] != material["techniqueSet"]["name"] or int(row["fmt"]) != material["worldVertFormat"]:
            raise SidecarV2Error(f"{material['name']!r}: TechniqueSet projection disagreement")

    # The v1 live run established that these are not XAsset-array addresses.
    # Decode them as their actual packed VIRTUAL slot allocation instead.
    surface_ptrs = sorted({int(row["materialPointerRaw"], 16) for row in surfaces})
    if len(surface_ptrs) != v1.MATERIAL_COUNT or any(b - a != 8 for a, b in zip(surface_ptrs, surface_ptrs[1:])):
        raise SidecarV2Error("surface Material pointers are not one contiguous 327-slot population")
    decoded = [worldproof.dec(raw, blocks) for raw in surface_ptrs]
    if any(kind != "packed" or block != 5 for kind, block, _ in decoded):
        raise SidecarV2Error("surface Material pointer population is not wholly VIRTUAL block 5")
    virtual_offsets = [offset for _, _, offset in decoded]
    if any(b - a != MATERIAL_MEMORY_BYTES for a, b in zip(virtual_offsets, virtual_offsets[1:])):
        raise SidecarV2Error("surface Material VIRTUAL offsets do not use sizeof(MaterialMemory)=8 stride")

    memory_physical = _material_memory_physical_candidate(data)
    # Every serialized MaterialMemory::material member is FOLLOW. The loader
    # therefore consumes the strict Material children in element order; this is
    # the exact order already validated by the retained Material chain parser.
    if memory_physical["gapToFirstMaterial"] < 0:
        raise SidecarV2Error("invalid MaterialMemory-to-Material serialization gap")

    catalog = []
    for index, (raw, virtual_offset, material) in enumerate(zip(surface_ptrs, virtual_offsets, materials)):
        catalog.append(
            {
                "materialIndex": index,
                "materialMemorySlotIndex": index,
                "surfacePointerHex": f"0x{raw:08x}",
                "materialMemoryVirtualOffset": virtual_offset,
                "name": material["name"],
                "worldVertFormat": material["worldVertFormat"],
                "techniqueSet": material["techniqueSet"]["name"],
            }
        )

    by_ptr = {int(row["surfacePointerHex"], 16): row for row in catalog}
    group_formats = Counter()
    for group in groups:
        formats = {int(by_ptr[p]["worldVertFormat"]) for p in group["mats"]}
        if len(formats) != 1:
            raise SidecarV2Error(f"vertex group {group['i']} has mixed formats {sorted(formats)}")
        group_formats[next(iter(formats))] += 1
    if len(groups) != v1.EXPECTED_GROUP_COUNT or group_formats != Counter(v1.EXPECTED_GROUP_FORMATS):
        raise SidecarV2Error(
            f"vertex-group census changed: count={len(groups)} formats={dict(sorted(group_formats.items()))}"
        )

    lightmaps = Counter(row["lightmapIndex"] for row in surfaces)
    if lightmaps != Counter({0: 4779, 1: 750, 31: 85}):
        raise SidecarV2Error(f"surface lightmap census changed: {dict(sorted(lightmaps.items()))}")

    prefix = []
    for index, (asset_type, raw_header) in enumerate(assets):
        row = {
            "index": index,
            "type": "techniqueset" if asset_type == 7 else f"xasset_type_{asset_type}",
            "rawHeaderPointerHex": f"0x{raw_header:08x}",
            "name": None,
            "details": {},
        }
        if index in by_q:
            row["name"] = by_q[index]["name"]
            row["details"] = {"worldVertFormat": int(by_q[index]["fmt"])}
        prefix.append(row)

    surfaces_doc = {
        "format": "t6-gfxworld-surfaces-source-sidecar-v2",
        "name": v1.MAP,
        "surfaceCount": v1.SURFACE_COUNT,
        "vertexCount": v1.VERTEX_COUNT,
        "source": {"expandedSha256": v1.EXPANDED_SHA256, "arrayStart": v1.SURFACE_START, "recordBytes": v1.SURFACE_BYTES},
        "surfaces": surfaces,
    }
    materials_doc = {
        "format": "t6-world-material-detail-compat-v2",
        "map": v1.MAP,
        "source": {"expandedSha256": v1.EXPANDED_SHA256, "firstMaterialStart": v1.MATERIAL_START, "lastMaterialEnd": v1.MATERIAL_LAST_END},
        "materials": materials,
    }
    catalog_doc = {
        "format": "t6-world-surface-material-catalog-source-v2",
        "map": v1.MAP,
        "source": {
            "expandedSha256": v1.EXPANDED_SHA256,
            "method": "GfxSurface packed VIRTUAL pointer -> contiguous MaterialMemory slot -> FOLLOW-owned serialized Material child order",
            "materialMemoryPhysical": memory_physical,
            "materialMemoryVirtual": {
                "block": 5,
                "startOffset": virtual_offsets[0],
                "endOffsetExclusive": virtual_offsets[-1] + MATERIAL_MEMORY_BYTES,
                "recordBytes": MATERIAL_MEMORY_BYTES,
                "count": len(virtual_offsets),
            },
        },
        "materials": catalog,
    }
    prefix_doc = {
        "format": "t6-world-technique-prefix-compat-v2",
        "map": v1.MAP,
        "source": {
            "expandedSha256": v1.EXPANDED_SHA256,
            "assetPointerVirtualBase": v1.ASSET_POINTER_VIRTUAL_BASE,
            "proofBoundary": "Compatibility projection for t6_world_vertex_audit_v2; only exact TechniqueSet rows are semantically populated.",
        },
        "walkedAssets": prefix,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "surfaces": (output_dir / f"{v1.MAP}.surfaces_source_v2.json", _json_bytes(surfaces_doc)),
        "materials": (output_dir / f"{v1.MAP}.materials_compat_v2.json", _json_bytes(materials_doc)),
        "catalog": (output_dir / f"{v1.MAP}.material_catalog_source_v2.json", _json_bytes(catalog_doc)),
        "prefix": (output_dir / f"{v1.MAP}.technique_prefix_compat_v2.json", _json_bytes(prefix_doc)),
        "vd0": (output_dir / f"{v1.MAP}.vd0.bin", vd0),
        "vd1": (output_dir / f"{v1.MAP}.vd1.bin", vd1),
        "indices": (output_dir / f"{v1.MAP}.indices.bin", indices),
    }
    outputs = {}
    for key, (path, payload) in payloads.items():
        path.write_bytes(payload)
        outputs[key] = _record(path, payload)

    summary = {
        "surfaceCount": len(surfaces),
        "materialCount": len(materials),
        "materialMemoryPhysicalStart": memory_physical["start"],
        "materialMemoryPhysicalEnd": memory_physical["end"],
        "materialMemoryGapToFirstMaterial": memory_physical["gapToFirstMaterial"],
        "materialMemoryVirtualBlock": 5,
        "materialMemoryVirtualStart": virtual_offsets[0],
        "materialMemoryVirtualEndExclusive": virtual_offsets[-1] + MATERIAL_MEMORY_BYTES,
        "referencedTechniqueSetCount": len(set(technique_qs)),
        "assetPointerVirtualBase": v1.ASSET_POINTER_VIRTUAL_BASE,
        "vertexGroupCount": len(groups),
        "materialFormatCounts": {str(k): val for k, val in sorted(Counter(v1.EXPECTED_MATERIAL_FORMATS).items())},
        "groupFormatCounts": {str(k): val for k, val in sorted(group_formats.items())},
        "surfaceLightmapCounts": {str(k): val for k, val in sorted(lightmaps.items())},
        "mixedFormatGroupCount": 0,
        "unresolvedSurfaceMaterialCount": 0,
    }
    manifest = {
        "format": FORMAT,
        "map": v1.MAP,
        "source": {"file": expanded.name, "bytes": len(data), "sha256": _sha(data)},
        "supersedes": {
            "producer": "tools/t6_nuketown_world_source_sidecars_v1.py",
            "reason": "live retail v1 negative control proved GfxSurface Material pointers are not top-level XAsset-array addresses",
        },
        "canonicalRanges": {
            "gfxWorldFixedStart": v1.GFXWORLD_START,
            "surfaceArray": [v1.SURFACE_START, v1.SURFACE_START + v1.SURFACE_COUNT * v1.SURFACE_BYTES],
            "vd0": [v1.VD0_START, v1.VD0_END],
            "vd1": [v1.VD1_START, v1.VD1_END],
            "indices": [v1.INDEX_START, v1.INDEX_END],
            "materialChain": [v1.MATERIAL_START, v1.MATERIAL_LAST_END],
        },
        "outputs": outputs,
        "summary": summary,
        "proofBoundary": (
            "Exact canonical expanded Nuketown bytes -> GfxSurface/draw buffers -> contiguous VIRTUAL MaterialMemory slot population -> unique nearby 327-record serialized MaterialMemory array with FOLLOW Material children -> strict serialized Material chain -> exact TechniqueSet XAssets/worldVertFormat. Legacy prefix/catalog JSON is emitted only as a deterministic compatibility projection after these checks."
        ),
    }
    manifest_payload = _json_bytes(manifest)
    manifest_path = output_dir / "T6_NUKETOWN_WORLD_SOURCE_SIDECARS_V2.json"
    manifest_path.write_bytes(manifest_payload)
    manifest["manifest"] = _record(manifest_path, manifest_payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    doc = build(args.expanded, args.out_dir)
    print(json.dumps({"manifest": doc["manifest"], **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
