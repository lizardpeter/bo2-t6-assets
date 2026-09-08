#!/usr/bin/env python3
"""Regenerate the production Nuketown GfxWorld compatibility sidecars from retail bytes.

The historical world exporter consumes surface/material/prefix sidecars that were
created during the first raw GfxWorld reconstruction but whose producer was not
retained.  This adapter does not reproduce that missing walker.  It rebuilds
only the fields consumed by the current audited exporter from newer direct
retail proofs that are already source-closed:

* the exact 80-byte T6 ``GfxSurface`` layout;
* the exact retained Nuketown GfxWorld buffer ranges;
* the strict 327-record retail Material parser;
* GfxSurface Material pointers -> contiguous top-level MATERIAL XAsset entries;
* each Material -> exact TechniqueSet XAsset -> ``worldVertFormat``.

The generated ``prefix`` document is explicitly a compatibility projection, not
a claim that the historical prefix walker was recreated.  Every TechniqueSet
row used by ``t6_world_vertex_audit_v2.py`` is derived directly from the current
retail XAsset/TechniqueSet proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

import t6_retail_special_material_family_census_v1 as family
import t6_retail_world_formats_45_proof_v1 as worldproof
import t6_retail_world_material_state_census_v2 as matstate

MAP = "mp_nuketown_2020"
EXPANDED_BYTES = 154_653_476
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
GFXWORLD_START = 63_150_420
SURFACE_START = 85_007_995
SURFACE_COUNT = 5_614
SURFACE_BYTES = 80
VERTEX_COUNT = 146_764
VD0_START = 76_182_996
VD0_END = 81_468_084
VD0_SHA256 = "7a5be06b14564a2dafd065d77204ff808e7cbbaac1ab0f06f1c6ef3f3e29ca76"
VD1_START = 81_468_084
VD1_END = 81_501_848
VD1_SHA256 = "77018ac13744f39244f29ce2c4cce0f0eb1204071a679654bd4eb67374537897"
INDEX_START = 81_501_848
INDEX_END = 82_103_528
INDEX_SHA256 = "70344c3cfbc8eb12a2e29b37deb55b5767a33b5b97beb3681215bf393c346fa7"
INDEX_COUNT = 300_840
MATERIAL_START = 84_465_666
MATERIAL_COUNT = 327
MATERIAL_LAST_END = 84_618_654
ASSET_POINTER_VIRTUAL_BASE = 13_472
TECH_Q0 = 565
TECH_Q1 = 623
EXPECTED_MATERIAL_FORMATS = {0: 207, 1: 95, 2: 7, 3: 17, 6: 1}
EXPECTED_GROUP_FORMATS = {0: 220, 1: 95, 2: 7, 3: 17, 6: 1}
EXPECTED_GROUP_COUNT = 340


class SidecarError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _record(path: Path, payload: bytes) -> dict:
    return {"file": path.name, "path": str(path), "bytes": len(payload), "sha256": _sha(payload)}


def _finite(values) -> bool:
    return all(math.isfinite(float(v)) for v in values)


def _surface_rows(data: bytes, world: dict) -> list[dict]:
    rows: list[dict] = []
    for index in range(SURFACE_COUNT):
        p = SURFACE_START + SURFACE_BYTES * index
        if p + SURFACE_BYTES > len(data):
            raise SidecarError(f"surface {index}: record exceeds expanded source")
        mins = list(struct.unpack_from("<3f", data, p + 0))
        off0 = struct.unpack_from("<i", data, p + 12)[0]
        maxs = list(struct.unpack_from("<3f", data, p + 16))
        off1 = struct.unpack_from("<i", data, p + 28)[0]
        first_vertex = struct.unpack_from("<i", data, p + 32)[0]
        himip = struct.unpack_from("<f", data, p + 36)[0]
        vertex_count, tri_count = struct.unpack_from("<HH", data, p + 40)
        base_index = struct.unpack_from("<i", data, p + 44)[0]
        material = struct.unpack_from("<I", data, p + 48)[0]
        lightmap = data[p + 52]
        reflection = data[p + 53]
        primary = data[p + 54]
        flags = data[p + 55]
        bounds0 = list(struct.unpack_from("<3f", data, p + 56))
        bounds1 = list(struct.unpack_from("<3f", data, p + 68))

        if not _finite(mins + maxs + [himip] + bounds0 + bounds1):
            raise SidecarError(f"surface {index}: non-finite serialized float")
        if not (0 <= off0 < int(world["vd0Bytes"])):
            raise SidecarError(f"surface {index}: vd0 offset outside source buffer")
        if not (0 <= off1 <= int(world["vd1Bytes"])):
            raise SidecarError(f"surface {index}: vd1 offset outside source buffer")
        if first_vertex < 0 or first_vertex >= VERTEX_COUNT:
            raise SidecarError(f"surface {index}: invalid firstVertex {first_vertex}")
        if base_index < 0 or base_index + tri_count * 3 > INDEX_COUNT:
            raise SidecarError(f"surface {index}: invalid index range")
        if material in (0, worldproof.FOLLOW, worldproof.INSERT):
            raise SidecarError(f"surface {index}: material pointer is not packed")
        if lightmap != 31 and lightmap >= int(world["lightmapCount"]):
            raise SidecarError(f"surface {index}: invalid lightmapIndex {lightmap}")

        rows.append(
            {
                "index": index,
                "mins": mins,
                "vertexDataOffset0": off0,
                "maxs": maxs,
                "vertexDataOffset1": off1,
                "firstVertex": first_vertex,
                "himipRadiusInvSq": himip,
                "vertexCount": vertex_count,
                "triCount": tri_count,
                "baseIndex": base_index,
                "materialPointerRaw": f"0x{material:08x}",
                "lightmapIndex": lightmap,
                "reflectionProbeIndex": reflection,
                "primaryLightIndex": primary,
                "flags": flags,
                "bounds": [bounds0, bounds1],
            }
        )
    return rows


def _material_chain(data: bytes, blocks: tuple[int, ...], identity_rows: list[dict]) -> tuple[list[dict], list[int]]:
    cursor = MATERIAL_START
    materials: list[dict] = []
    q_values: list[int] = []
    for index, identity in enumerate(identity_rows):
        parsed = matstate.material(data, cursor, blocks)
        if parsed["name"] != identity["material"]:
            raise SidecarError(
                f"material {index}: direct state parser name {parsed['name']!r} != binding {identity['material']!r}"
            )
        raw_tech = struct.unpack_from("<I", data, cursor + 84)[0]
        kind, block, offset = worldproof.dec(raw_tech, blocks)
        if kind != "packed" or block != 5:
            raise SidecarError(f"{parsed['name']!r}: TechniqueSet pointer is not packed VIRTUAL")
        delta = offset - ASSET_POINTER_VIRTUAL_BASE - 4
        if delta < 0 or delta % 8:
            raise SidecarError(f"{parsed['name']!r}: TechniqueSet pointer is not XAsset-array aligned")
        q = delta // 8
        q_values.append(q)
        materials.append(
            {
                "materialIndex": index,
                "name": parsed["name"],
                "rawStart": cursor,
                "rawEnd": parsed["end"],
                "archiveSha256": parsed["archiveSha256"],
                "family": identity["family"],
                "worldVertFormat": int(identity["worldVertFormat"]),
                "techniqueSet": {
                    "name": identity["techniqueSet"],
                    "assetIndex": q,
                    "rawPointerHex": f"0x{raw_tech:08x}",
                    "pointer": {"kind": "offset", "block": 5, "offset": offset},
                },
            }
        )
        cursor = parsed["end"] + 8
    if materials[-1]["rawEnd"] != MATERIAL_LAST_END:
        raise SidecarError(
            f"final Material end {materials[-1]['rawEnd']} != canonical {MATERIAL_LAST_END}"
        )
    return materials, q_values


def build(expanded: Path, output_dir: Path) -> dict:
    data = expanded.read_bytes()
    if len(data) != EXPANDED_BYTES or _sha(data) != EXPANDED_SHA256:
        raise SidecarError("expanded retail Nuketown source identity mismatch")

    blocks, assets = worldproof.front(data)
    w = worldproof.world(data, GFXWORLD_START, SURFACE_COUNT, MATERIAL_COUNT)
    expected_world = {
        "surfaceCount": SURFACE_COUNT,
        "lightmapCount": 2,
        "vertexCount": VERTEX_COUNT,
        "vd0Bytes": VD0_END - VD0_START,
        "vd1Bytes": VD1_END - VD1_START,
        "indexCount": INDEX_COUNT,
        "materialMemoryCount": MATERIAL_COUNT,
    }
    for key, value in expected_world.items():
        if int(w[key]) != value:
            raise SidecarError(f"GfxWorld {key} {w[key]} != canonical {value}")

    vd0 = data[VD0_START:VD0_END]
    vd1 = data[VD1_START:VD1_END]
    indices = data[INDEX_START:INDEX_END]
    if _sha(vd0) != VD0_SHA256 or _sha(vd1) != VD1_SHA256 or _sha(indices) != INDEX_SHA256:
        raise SidecarError("one or more canonical GfxWorld draw-buffer hashes changed")
    if len(indices) != INDEX_COUNT * 2:
        raise SidecarError("index byte length does not equal canonical uint16 count")

    surface_rows = _surface_rows(data, w)
    raw_surface_tuples, groups, _allocs = worldproof.surfaces_and_groups(
        data, SURFACE_START, SURFACE_COUNT, w
    )
    if len(raw_surface_tuples) != len(surface_rows):
        raise SidecarError("independent surface parser count mismatch")
    for minimal, full in zip(raw_surface_tuples, surface_rows):
        i, off0, off1, vc, mat = minimal
        if (
            i != full["index"]
            or off0 != full["vertexDataOffset0"]
            or off1 != full["vertexDataOffset1"]
            or vc != full["vertexCount"]
            or mat != int(full["materialPointerRaw"], 16)
        ):
            raise SidecarError(f"surface {i}: independent parser disagreement")

    identity_rows = family.bind_map(MAP, expanded)
    if len(identity_rows) != MATERIAL_COUNT:
        raise SidecarError("direct Material/TechniqueSet binding count mismatch")
    materials, tech_qs = _material_chain(data, blocks, identity_rows)
    if Counter(int(r["worldVertFormat"]) for r in identity_rows) != Counter(EXPECTED_MATERIAL_FORMATS):
        raise SidecarError("retail Material worldVertFormat histogram changed")
    if not all(TECH_Q0 <= q <= TECH_Q1 for q in tech_qs):
        raise SidecarError("referenced TechniqueSet XAsset escaped canonical Nuketown block")

    # Re-resolve the exact TechniqueSet body used by the material binder.  This
    # builds only the compatibility rows consumed by the legacy vertex auditor.
    tech_body = family.techs(data, blocks, GFXWORLD_START)[-(TECH_Q1 - TECH_Q0 + 1):]
    if len(tech_body) != TECH_Q1 - TECH_Q0 + 1:
        raise SidecarError("TechniqueSet body length changed")
    by_q = {TECH_Q0 + i: row for i, row in enumerate(tech_body)}
    for material in materials:
        q = int(material["techniqueSet"]["assetIndex"])
        row = by_q[q]
        if row["name"] != material["techniqueSet"]["name"] or int(row["fmt"]) != material["worldVertFormat"]:
            raise SidecarError(f"{material['name']!r}: TechniqueSet compatibility projection disagrees")

    # Surface Material pointers themselves resolve into the same top-level XAsset
    # pointer array.  This is the direct replacement for the historical catalog.
    surface_ptrs = sorted({int(r["materialPointerRaw"], 16) for r in surface_rows})
    if len(surface_ptrs) != MATERIAL_COUNT or any(b - a != 8 for a, b in zip(surface_ptrs, surface_ptrs[1:])):
        raise SidecarError("surface Material pointer population is not the canonical contiguous 327-entry set")
    material_asset_qs: list[int] = []
    for raw in surface_ptrs:
        kind, block, offset = worldproof.dec(raw, blocks)
        delta = offset - ASSET_POINTER_VIRTUAL_BASE - 4
        if kind != "packed" or block != 5 or delta < 0 or delta % 8:
            raise SidecarError(f"surface Material pointer 0x{raw:08x} is not an aligned VIRTUAL XAsset pointer")
        q = delta // 8
        if q < 0 or q >= len(assets) or assets[q][0] != 6:
            raise SidecarError(f"surface Material pointer 0x{raw:08x} does not resolve to MATERIAL XAsset")
        material_asset_qs.append(q)
    if any(b - a != 1 for a, b in zip(material_asset_qs, material_asset_qs[1:])):
        raise SidecarError("resolved MATERIAL XAsset indices are not contiguous")

    catalog_rows = []
    for index, (raw, q, material) in enumerate(zip(surface_ptrs, material_asset_qs, materials)):
        catalog_rows.append(
            {
                "materialIndex": index,
                "surfacePointerHex": f"0x{raw:08x}",
                "materialAssetIndex": q,
                "name": material["name"],
                "worldVertFormat": material["worldVertFormat"],
                "techniqueSet": material["techniqueSet"]["name"],
            }
        )

    material_by_ptr = {int(r["surfacePointerHex"], 16): r for r in catalog_rows}
    group_formats = Counter()
    for group in groups:
        fmts = {
            int(material_by_ptr[p]["worldVertFormat"])
            for p in group["mats"]
        }
        if len(fmts) != 1:
            raise SidecarError(f"vertex group {group['i']} has mixed formats {sorted(fmts)}")
        group_formats[next(iter(fmts))] += 1
    if len(groups) != EXPECTED_GROUP_COUNT or group_formats != Counter(EXPECTED_GROUP_FORMATS):
        raise SidecarError(
            f"vertex-group census changed: groups={len(groups)} formats={dict(sorted(group_formats.items()))}"
        )

    lightmaps = Counter(r["lightmapIndex"] for r in surface_rows)
    if lightmaps != Counter({0: 4779, 1: 750, 31: 85}):
        raise SidecarError(f"surface lightmap census changed: {dict(sorted(lightmaps.items()))}")

    prefix_rows = []
    for index, (asset_type, raw_pointer) in enumerate(assets):
        row = {
            "index": index,
            "type": "techniqueset" if asset_type == 7 else f"xasset_type_{asset_type}",
            "rawHeaderPointerHex": f"0x{raw_pointer:08x}",
            "name": None,
            "details": {},
        }
        if index in by_q:
            row["name"] = by_q[index]["name"]
            row["details"] = {"worldVertFormat": int(by_q[index]["fmt"])}
        prefix_rows.append(row)

    surfaces_doc = {
        "format": "t6-gfxworld-surfaces-source-sidecar-v1",
        "name": MAP,
        "surfaceCount": SURFACE_COUNT,
        "vertexCount": VERTEX_COUNT,
        "source": {"expandedSha256": EXPANDED_SHA256, "arrayStart": SURFACE_START, "recordBytes": SURFACE_BYTES},
        "surfaces": surface_rows,
    }
    materials_doc = {
        "format": "t6-world-material-detail-compat-v1",
        "map": MAP,
        "source": {"expandedSha256": EXPANDED_SHA256, "firstMaterialStart": MATERIAL_START, "lastMaterialEnd": MATERIAL_LAST_END},
        "materials": materials,
    }
    catalog_doc = {
        "format": "t6-world-surface-material-catalog-source-v1",
        "map": MAP,
        "source": {"expandedSha256": EXPANDED_SHA256, "method": "packed GfxSurface Material pointer -> VIRTUAL XAsset index -> serialized Material order"},
        "materials": catalog_rows,
    }
    prefix_doc = {
        "format": "t6-world-technique-prefix-compat-v1",
        "map": MAP,
        "source": {
            "expandedSha256": EXPANDED_SHA256,
            "assetPointerVirtualBase": ASSET_POINTER_VIRTUAL_BASE,
            "proofBoundary": "Compatibility projection for t6_world_vertex_audit_v2; referenced TechniqueSet rows only are semantically populated from direct retail TechniqueSet proof.",
        },
        "walkedAssets": prefix_rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict] = {}
    documents = {
        "surfaces": (output_dir / f"{MAP}.surfaces_source_v1.json", _json_bytes(surfaces_doc)),
        "materials": (output_dir / f"{MAP}.materials_compat_v1.json", _json_bytes(materials_doc)),
        "catalog": (output_dir / f"{MAP}.material_catalog_source_v1.json", _json_bytes(catalog_doc)),
        "prefix": (output_dir / f"{MAP}.technique_prefix_compat_v1.json", _json_bytes(prefix_doc)),
        "vd0": (output_dir / f"{MAP}.vd0.bin", vd0),
        "vd1": (output_dir / f"{MAP}.vd1.bin", vd1),
        "indices": (output_dir / f"{MAP}.indices.bin", indices),
    }
    for key, (path, payload) in documents.items():
        path.write_bytes(payload)
        outputs[key] = _record(path, payload)

    summary = {
        "surfaceCount": len(surface_rows),
        "materialCount": len(materials),
        "materialAssetIndexRange": [material_asset_qs[0], material_asset_qs[-1]],
        "referencedTechniqueSetCount": len(set(tech_qs)),
        "techniqueAssetIndexRange": [TECH_Q0, TECH_Q1],
        "assetPointerVirtualBase": ASSET_POINTER_VIRTUAL_BASE,
        "vertexGroupCount": len(groups),
        "materialFormatCounts": {str(k): v for k, v in sorted(Counter(EXPECTED_MATERIAL_FORMATS).items())},
        "groupFormatCounts": {str(k): v for k, v in sorted(group_formats.items())},
        "surfaceLightmapCounts": {str(k): v for k, v in sorted(lightmaps.items())},
        "mixedFormatGroupCount": 0,
        "unresolvedSurfaceMaterialCount": 0,
    }
    manifest = {
        "format": "t6-nuketown-world-source-sidecars-v1",
        "map": MAP,
        "source": {"file": expanded.name, "bytes": len(data), "sha256": _sha(data)},
        "canonicalRanges": {
            "gfxWorldFixedStart": GFXWORLD_START,
            "surfaceArray": [SURFACE_START, SURFACE_START + SURFACE_COUNT * SURFACE_BYTES],
            "vd0": [VD0_START, VD0_END],
            "vd1": [VD1_START, VD1_END],
            "indices": [INDEX_START, INDEX_END],
            "materialChain": [MATERIAL_START, MATERIAL_LAST_END],
        },
        "outputs": outputs,
        "summary": summary,
        "proofBoundary": (
            "Exact canonical expanded Nuketown bytes -> direct GfxSurface records/draw buffers -> packed Material XAsset pointers -> strict serialized Material chain -> exact TechniqueSet XAssets/worldVertFormat. "
            "The prefix JSON is only a deterministic compatibility projection for the legacy vertex auditor; no missing historical walker state is invented."
        ),
    }
    manifest_payload = _json_bytes(manifest)
    manifest_path = output_dir / "T6_NUKETOWN_WORLD_SOURCE_SIDECARS_V1.json"
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
