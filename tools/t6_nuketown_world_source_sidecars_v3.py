#!/usr/bin/env python3
"""Retail Nuketown GfxWorld source sidecars v3.

v3 is the production compatibility adapter after exact MaterialMemory ownership
closure. It does not scan for a physical MaterialMemory candidate and it does
not interpret GfxSurface Material aliases as top-level XAsset slots.

Required chain:

  exact expanded retail Nuketown
    -> authoritative MaterialMemory ownership proof v1
    -> direct GfxSurface byte parse
    -> strict serialized 327-Material child chain
    -> exact Material -> TechniqueSet -> worldVertFormat
    -> exact ownership-proof slot-by-slot agreement
    -> legacy-compatible sidecars for the audited world exporter

The emitted prefix document remains explicitly a compatibility projection: only
TechniqueSet rows needed by the existing vertex auditor are semantically filled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import t6_nuketown_world_source_sidecars_v1 as v1
import t6_retail_special_material_family_census_v1 as family
import t6_retail_world_formats_45_proof_v1 as worldproof

FORMAT = "t6-nuketown-world-source-sidecars-v3"
OWNERSHIP_FORMAT = "t6-nuketown-material-memory-ownership-v1"
OWNERSHIP_PHYSICAL_START = 84_463_050
OWNERSHIP_PHYSICAL_END = 84_465_666
OWNERSHIP_VIRTUAL_BLOCK = 5
OWNERSHIP_VIRTUAL_START = 71_642_512
OWNERSHIP_VIRTUAL_END = 71_645_128
MATERIAL_MEMORY_BYTES = 8


class SidecarV3Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _record(path: Path, payload: bytes) -> dict:
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(payload),
        "sha256": _sha(payload),
    }


def _load_ownership(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if doc.get("format") != OWNERSHIP_FORMAT:
        raise SidecarV3Error(f"ownership proof format {doc.get('format')!r} != {OWNERSHIP_FORMAT!r}")
    source = doc.get("source") or {}
    if int(source.get("bytes", -1)) != v1.EXPANDED_BYTES or source.get("sha256") != v1.EXPANDED_SHA256:
        raise SidecarV3Error("ownership proof is not bound to canonical expanded Nuketown")
    mm = doc.get("materialMemory") or {}
    expected = {
        "count": v1.MATERIAL_COUNT,
        "recordBytes": MATERIAL_MEMORY_BYTES,
        "physicalStart": OWNERSHIP_PHYSICAL_START,
        "physicalEndExclusive": OWNERSHIP_PHYSICAL_END,
        "virtualBlock": OWNERSHIP_VIRTUAL_BLOCK,
        "virtualStartOffset": OWNERSHIP_VIRTUAL_START,
        "virtualEndOffsetExclusive": OWNERSHIP_VIRTUAL_END,
        "surfaceAliasCount": v1.MATERIAL_COUNT,
        "surfaceAliasStride": MATERIAL_MEMORY_BYTES,
    }
    for key, value in expected.items():
        if int(mm.get(key, -1)) != value:
            raise SidecarV3Error(f"ownership proof {key} {mm.get(key)!r} != {value}")
    if mm.get("fixedArrayEndsAtFirstMaterialChild") is not True:
        raise SidecarV3Error("ownership proof does not close fixed-array/first-child boundary")
    if mm.get("allMaterialChildrenFollowOwned") is not True:
        raise SidecarV3Error("ownership proof does not close all 327 FOLLOW-owned Material children")
    validation = doc.get("validation") or {}
    if int(validation.get("strictMaterialCount", -1)) != v1.MATERIAL_COUNT:
        raise SidecarV3Error("ownership proof strict Material count mismatch")
    if int(validation.get("mixedFormatGroupCount", -1)) != 0:
        raise SidecarV3Error("ownership proof has mixed-format groups")
    if int(validation.get("unresolvedSurfaceMaterialCount", -1)) != 0:
        raise SidecarV3Error("ownership proof has unresolved surface Materials")
    slots = doc.get("slotBindings")
    if not isinstance(slots, list) or len(slots) != v1.MATERIAL_COUNT:
        raise SidecarV3Error("ownership proof slotBindings is not the exact 327-row population")
    return doc, raw


def build(expanded: Path, ownership_proof: Path, output_dir: Path) -> dict:
    data = expanded.read_bytes()
    if len(data) != v1.EXPANDED_BYTES or _sha(data) != v1.EXPANDED_SHA256:
        raise SidecarV3Error("expanded retail Nuketown source identity mismatch")
    ownership, ownership_raw = _load_ownership(ownership_proof)

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
            raise SidecarV3Error(f"GfxWorld {key} {world[key]} != {expected}")
    if int(world["materialMemoryPtr"]) != worldproof.FOLLOW:
        raise SidecarV3Error("GfxWorld MaterialMemory pointer is not FOLLOW-owned")

    vd0 = data[v1.VD0_START:v1.VD0_END]
    vd1 = data[v1.VD1_START:v1.VD1_END]
    indices = data[v1.INDEX_START:v1.INDEX_END]
    if _sha(vd0) != v1.VD0_SHA256:
        raise SidecarV3Error("canonical vd0 hash mismatch")
    if _sha(vd1) != v1.VD1_SHA256:
        raise SidecarV3Error("canonical vd1 hash mismatch")
    if _sha(indices) != v1.INDEX_SHA256 or len(indices) != v1.INDEX_COUNT * 2:
        raise SidecarV3Error("canonical index buffer mismatch")

    surfaces = v1._surface_rows(data, world)
    minimal, groups, _allocs = worldproof.surfaces_and_groups(
        data, v1.SURFACE_START, v1.SURFACE_COUNT, world
    )
    if len(minimal) != len(surfaces):
        raise SidecarV3Error("independent GfxSurface parser count mismatch")
    for rawrow, full in zip(minimal, surfaces):
        i, off0, off1, vc, mat = rawrow
        if (
            i != full["index"]
            or off0 != full["vertexDataOffset0"]
            or off1 != full["vertexDataOffset1"]
            or vc != full["vertexCount"]
            or mat != int(full["materialPointerRaw"], 16)
        ):
            raise SidecarV3Error(f"surface {i}: independent parser disagreement")

    identity = family.bind_map(v1.MAP, expanded)
    materials, technique_qs = v1._material_chain(data, blocks, identity)
    if len(materials) != v1.MATERIAL_COUNT:
        raise SidecarV3Error("strict serialized Material chain count mismatch")
    material_formats = Counter(int(row["worldVertFormat"]) for row in identity)
    if material_formats != Counter(v1.EXPECTED_MATERIAL_FORMATS):
        raise SidecarV3Error(f"Material worldVertFormat census changed: {dict(material_formats)}")
    if not all(v1.TECH_Q0 <= q <= v1.TECH_Q1 for q in technique_qs):
        raise SidecarV3Error("Material TechniqueSet XAsset escaped canonical range")

    tech_body = family.techs(data, blocks, v1.GFXWORLD_START)[-(v1.TECH_Q1 - v1.TECH_Q0 + 1):]
    if len(tech_body) != v1.TECH_Q1 - v1.TECH_Q0 + 1:
        raise SidecarV3Error("TechniqueSet body length changed")
    by_q = {v1.TECH_Q0 + i: row for i, row in enumerate(tech_body)}
    for material in materials:
        q = int(material["techniqueSet"]["assetIndex"])
        row = by_q[q]
        if row["name"] != material["techniqueSet"]["name"]:
            raise SidecarV3Error(f"{material['name']!r}: TechniqueSet name projection disagrees")
        if int(row["fmt"]) != int(material["worldVertFormat"]):
            raise SidecarV3Error(f"{material['name']!r}: TechniqueSet worldVertFormat projection disagrees")

    surface_ptrs = sorted({int(row["materialPointerRaw"], 16) for row in surfaces})
    if len(surface_ptrs) != v1.MATERIAL_COUNT or any(
        b - a != MATERIAL_MEMORY_BYTES for a, b in zip(surface_ptrs, surface_ptrs[1:])
    ):
        raise SidecarV3Error("surface Material aliases are not one contiguous 327-slot population")
    decoded = [worldproof.dec(raw) if False else worldproof.dec(raw, blocks) for raw in surface_ptrs]
    if any(kind != "packed" or block != OWNERSHIP_VIRTUAL_BLOCK for kind, block, _ in decoded):
        raise SidecarV3Error("surface Material aliases are not wholly packed VIRTUAL block 5")
    virtual_offsets = [offset for _, _, offset in decoded]
    if virtual_offsets[0] != OWNERSHIP_VIRTUAL_START:
        raise SidecarV3Error(f"surface Material VIRTUAL start {virtual_offsets[0]} != {OWNERSHIP_VIRTUAL_START}")
    if virtual_offsets[-1] + MATERIAL_MEMORY_BYTES != OWNERSHIP_VIRTUAL_END:
        raise SidecarV3Error("surface Material VIRTUAL end disagrees with ownership proof")
    if any(b - a != MATERIAL_MEMORY_BYTES for a, b in zip(virtual_offsets, virtual_offsets[1:])):
        raise SidecarV3Error("surface Material VIRTUAL aliases are not 8-byte stride")

    # Physical fixed array is source-derived by the ownership proof. Recheck its
    # exact bytes here, but never rescan for alternate candidates.
    physical = data[OWNERSHIP_PHYSICAL_START:OWNERSHIP_PHYSICAL_END]
    if len(physical) != v1.MATERIAL_COUNT * MATERIAL_MEMORY_BYTES:
        raise SidecarV3Error("ownership-derived MaterialMemory physical span is truncated")
    for index in range(v1.MATERIAL_COUNT):
        if int.from_bytes(physical[index * 8:index * 8 + 4], "little") != worldproof.FOLLOW:
            raise SidecarV3Error(f"MaterialMemory slot {index} is no longer FOLLOW-owned")

    ownership_slots = ownership["slotBindings"]
    catalog = []
    for index, (raw, virtual_offset, material, proof_row) in enumerate(
        zip(surface_ptrs, virtual_offsets, materials, ownership_slots)
    ):
        expected_raw = f"0x{raw:08x}"
        expected_physical = OWNERSHIP_PHYSICAL_START + index * MATERIAL_MEMORY_BYTES
        checks = {
            "slotIndex": index,
            "surfaceAliasRawHex": expected_raw,
            "virtualBlock": OWNERSHIP_VIRTUAL_BLOCK,
            "virtualOffset": virtual_offset,
            "physicalRecordStart": expected_physical,
            "material": material["name"],
            "techniqueSet": material["techniqueSet"]["name"],
            "worldVertFormat": int(material["worldVertFormat"]),
        }
        for key, expected in checks.items():
            actual = proof_row.get(key)
            if key in ("slotIndex", "virtualBlock", "virtualOffset", "physicalRecordStart", "worldVertFormat"):
                try:
                    actual = int(actual)
                except (TypeError, ValueError):
                    pass
            if actual != expected:
                raise SidecarV3Error(
                    f"ownership slot {index} {key} {actual!r} != independently parsed {expected!r}"
                )
        catalog.append(
            {
                "materialIndex": index,
                "materialMemorySlotIndex": index,
                "surfacePointerHex": expected_raw,
                "materialMemoryVirtualOffset": virtual_offset,
                "materialMemoryPhysicalRecordStart": expected_physical,
                "name": material["name"],
                "worldVertFormat": int(material["worldVertFormat"]),
                "techniqueSet": material["techniqueSet"]["name"],
            }
        )

    by_ptr = {int(row["surfacePointerHex"], 16): row for row in catalog}
    group_formats = Counter()
    for group in groups:
        formats = {int(by_ptr[p]["worldVertFormat"]) for p in group["mats"]}
        if len(formats) != 1:
            raise SidecarV3Error(f"vertex group {group['i']} has mixed formats {sorted(formats)}")
        group_formats[next(iter(formats))] += 1
    if len(groups) != v1.EXPECTED_GROUP_COUNT:
        raise SidecarV3Error(f"vertex group count {len(groups)} != {v1.EXPECTED_GROUP_COUNT}")
    if group_formats != Counter(v1.EXPECTED_GROUP_FORMATS):
        raise SidecarV3Error(f"vertex-group format census changed: {dict(sorted(group_formats.items()))}")

    lightmaps = Counter(row["lightmapIndex"] for row in surfaces)
    if lightmaps != Counter({0: 4779, 1: 750, 31: 85}):
        raise SidecarV3Error(f"surface lightmap census changed: {dict(sorted(lightmaps.items()))}")

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
        "format": "t6-gfxworld-surfaces-source-sidecar-v3",
        "name": v1.MAP,
        "surfaceCount": v1.SURFACE_COUNT,
        "vertexCount": v1.VERTEX_COUNT,
        "source": {
            "expandedSha256": v1.EXPANDED_SHA256,
            "arrayStart": v1.SURFACE_START,
            "recordBytes": v1.SURFACE_BYTES,
        },
        "surfaces": surfaces,
    }
    materials_doc = {
        "format": "t6-world-material-detail-compat-v3",
        "map": v1.MAP,
        "source": {
            "expandedSha256": v1.EXPANDED_SHA256,
            "firstMaterialStart": v1.MATERIAL_START,
            "lastMaterialEnd": v1.MATERIAL_LAST_END,
        },
        "materials": materials,
    }
    catalog_doc = {
        "format": "t6-world-surface-material-catalog-source-v3",
        "map": v1.MAP,
        "source": {
            "expandedSha256": v1.EXPANDED_SHA256,
            "method": "authoritative ownership proof -> GfxSurface packed VIRTUAL MaterialMemory.material slot -> FOLLOW-owned serialized Material child order",
            "ownershipProof": {
                "file": ownership_proof.name,
                "bytes": len(ownership_raw),
                "sha256": _sha(ownership_raw),
                "format": OWNERSHIP_FORMAT,
            },
            "materialMemoryPhysical": {
                "start": OWNERSHIP_PHYSICAL_START,
                "endExclusive": OWNERSHIP_PHYSICAL_END,
                "recordBytes": MATERIAL_MEMORY_BYTES,
                "count": v1.MATERIAL_COUNT,
            },
            "materialMemoryVirtual": {
                "block": OWNERSHIP_VIRTUAL_BLOCK,
                "startOffset": OWNERSHIP_VIRTUAL_START,
                "endOffsetExclusive": OWNERSHIP_VIRTUAL_END,
                "recordBytes": MATERIAL_MEMORY_BYTES,
                "count": v1.MATERIAL_COUNT,
            },
        },
        "materials": catalog,
    }
    prefix_doc = {
        "format": "t6-world-technique-prefix-compat-v3",
        "map": v1.MAP,
        "source": {
            "expandedSha256": v1.EXPANDED_SHA256,
            "assetPointerVirtualBase": v1.ASSET_POINTER_VIRTUAL_BASE,
            "proofBoundary": "Compatibility projection for t6_world_vertex_audit_v2; only exact TechniqueSet rows are semantically populated from direct retail proof.",
        },
        "walkedAssets": prefix,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "surfaces": (output_dir / f"{v1.MAP}.surfaces_source_v3.json", _json_bytes(surfaces_doc)),
        "materials": (output_dir / f"{v1.MAP}.materials_compat_v3.json", _json_bytes(materials_doc)),
        "catalog": (output_dir / f"{v1.MAP}.material_catalog_source_v3.json", _json_bytes(catalog_doc)),
        "prefix": (output_dir / f"{v1.MAP}.technique_prefix_compat_v3.json", _json_bytes(prefix_doc)),
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
        "materialMemoryPhysicalStart": OWNERSHIP_PHYSICAL_START,
        "materialMemoryPhysicalEndExclusive": OWNERSHIP_PHYSICAL_END,
        "materialMemoryVirtualBlock": OWNERSHIP_VIRTUAL_BLOCK,
        "materialMemoryVirtualStart": OWNERSHIP_VIRTUAL_START,
        "materialMemoryVirtualEndExclusive": OWNERSHIP_VIRTUAL_END,
        "ownershipSlotAgreementCount": len(catalog),
        "referencedTechniqueSetCount": len(set(technique_qs)),
        "assetPointerVirtualBase": v1.ASSET_POINTER_VIRTUAL_BASE,
        "vertexGroupCount": len(groups),
        "materialFormatCounts": {str(k): value for k, value in sorted(material_formats.items())},
        "groupFormatCounts": {str(k): value for k, value in sorted(group_formats.items())},
        "surfaceLightmapCounts": {str(k): value for k, value in sorted(lightmaps.items())},
        "mixedFormatGroupCount": 0,
        "unresolvedSurfaceMaterialCount": 0,
    }
    manifest = {
        "format": FORMAT,
        "map": v1.MAP,
        "source": {"file": expanded.name, "bytes": len(data), "sha256": _sha(data)},
        "ownershipProof": {
            "file": ownership_proof.name,
            "bytes": len(ownership_raw),
            "sha256": _sha(ownership_raw),
            "format": OWNERSHIP_FORMAT,
        },
        "supersedes": {
            "v1": "top-level MATERIAL XAsset-array interpretation rejected by live retail negative control",
            "v2": "nearby FOLLOW-signature candidate scan rejected after overlapping candidate ambiguity",
        },
        "canonicalRanges": {
            "gfxWorldFixedStart": v1.GFXWORLD_START,
            "surfaceArray": [v1.SURFACE_START, v1.SURFACE_START + v1.SURFACE_COUNT * v1.SURFACE_BYTES],
            "vd0": [v1.VD0_START, v1.VD0_END],
            "vd1": [v1.VD1_START, v1.VD1_END],
            "indices": [v1.INDEX_START, v1.INDEX_END],
            "materialMemory": [OWNERSHIP_PHYSICAL_START, OWNERSHIP_PHYSICAL_END],
            "materialChain": [v1.MATERIAL_START, v1.MATERIAL_LAST_END],
        },
        "outputs": outputs,
        "summary": summary,
        "proofBoundary": (
            "Exact canonical expanded Nuketown bytes and an authoritative loader-derived MaterialMemory ownership proof are both required. The adapter independently reparses all GfxSurface records and all 327 serialized Materials and requires slot-by-slot agreement with the ownership proof before emitting compatibility JSON. No local candidate scan, top-level Material XAsset assumption, material-name guess, old GLB assignment, or rendered appearance participates."
        ),
    }
    manifest_payload = _json_bytes(manifest)
    manifest_path = output_dir / "T6_NUKETOWN_WORLD_SOURCE_SIDECARS_V3.json"
    manifest_path.write_bytes(manifest_payload)
    manifest["manifest"] = _record(manifest_path, manifest_payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded", type=Path, required=True)
    parser.add_argument("--ownership-proof", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    doc = build(args.expanded, args.ownership_proof, args.out_dir)
    print(json.dumps({"manifest": doc["manifest"], **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
