#!/usr/bin/env python3
"""Prove native-T6 Z bounds and fog-branch closure for Nuketown multiply decals.

The proof stays entirely on retained retail bytes:
  expanded FastFile -> exact GfxSurface rows -> exact MaterialMemory alias slots
  -> strict serialized Material child order -> exact surface index slices
  -> local indices into the exact 36-byte VD0 vertex groups -> float32 POSITION.z.

For the exact multiply-decal VS, after substituting the recovered fog-vector
construction and an eye-relative native-T6 worldMatrix,

    x = P.z * fogConsts.w + fogConsts.x
      = ln(density/maxDensity)
        - heightDensity * ln(2) * (sourceVertexZ - baseHeight).

With positive heightDensity, x is monotonically decreasing in sourceVertexZ.
The proof therefore computes the minimum Z from the *actual indexed retail
vertices* used by each target surface. Serialized GfxSurface mins/maxs are kept
only as diagnostics because this decal cohort stores zeros there.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import struct
from pathlib import Path

import t6_nuketown_world_source_sidecars_v1 as sidecar
import t6_retail_special_material_family_census_v1 as family
import t6_retail_world_formats_45_proof_v1 as worldproof

FORMAT = "t6-nuketown-special-multiply-decal-z-bounds-v1"
MAP = "mp_nuketown_2020"
TARGETS = (
    "wpc/decal_damage_wall_fillet",
    "wpc/decal_grunge_lightstain_04",
    "wpc/me_decal_adobe_top_01",
)

MATERIAL_MEMORY_PHYSICAL_START = 84_463_050
MATERIAL_MEMORY_PHYSICAL_END = 84_465_666
MATERIAL_MEMORY_VIRTUAL_BLOCK = 5
MATERIAL_MEMORY_VIRTUAL_START = 71_642_512
MATERIAL_MEMORY_VIRTUAL_END = 71_645_128
MATERIAL_MEMORY_RECORD_BYTES = 8

VD0_STRIDE = 36
BASE_HEIGHT = -400.0
HALF_HEIGHT = 3333.74560546875
DENSITY_OVER_MAX_DENSITY = 0.01


class ProofError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def group_vertex_counts(surfaces: list[dict], vd0_bytes: int) -> dict[int, int]:
    grouped: dict[int, list[dict]] = collections.defaultdict(list)
    for surface in surfaces:
        grouped[int(surface["vertexDataOffset0"])].append(surface)
    offsets = sorted(grouped)
    out: dict[int, int] = {}
    for ordinal, offset in enumerate(offsets):
        next_offset = offsets[ordinal + 1] if ordinal + 1 < len(offsets) else vd0_bytes
        span = next_offset - offset
        candidates = [
            n
            for n in range(max(0, span // VD0_STRIDE - 2), span // VD0_STRIDE + 2)
            if align_up(VD0_STRIDE * n, 16) == span
        ]
        if len(candidates) != 1:
            raise ProofError(
                f"VD0 group at {offset} does not have one source-closed vertex count: "
                f"span={span} candidates={candidates}"
            )
        count = candidates[0]
        stored = sorted({int(s["vertexCount"]) for s in grouped[offset] if int(s["vertexCount"]) > 0})
        if stored and stored != [count]:
            raise ProofError(f"VD0 group {offset} stored vertex counts {stored} != span count {count}")
        first_vertices = {int(s["firstVertex"]) for s in grouped[offset]}
        if len(first_vertices) != 1:
            raise ProofError(f"VD0 group {offset} surfaces disagree on firstVertex: {first_vertices}")
        out[offset] = count
    return out


def build(expanded: Path) -> dict:
    data = expanded.read_bytes()
    if len(data) != sidecar.EXPANDED_BYTES or sha(data) != sidecar.EXPANDED_SHA256:
        raise ProofError("expanded retail Nuketown identity mismatch")

    blocks, _assets = worldproof.front(data)
    world = worldproof.world(data, sidecar.GFXWORLD_START, sidecar.SURFACE_COUNT, sidecar.MATERIAL_COUNT)
    surfaces = sidecar._surface_rows(data, world)
    if len(surfaces) != sidecar.SURFACE_COUNT:
        raise ProofError("GfxSurface count drift")

    vd0 = data[sidecar.VD0_START:sidecar.VD0_END]
    index_bytes = data[sidecar.INDEX_START:sidecar.INDEX_END]
    if sha(vd0) != sidecar.VD0_SHA256:
        raise ProofError("canonical VD0 identity drift")
    if sha(index_bytes) != sidecar.INDEX_SHA256 or len(index_bytes) != sidecar.INDEX_COUNT * 2:
        raise ProofError("canonical index-buffer identity drift")
    group_counts = group_vertex_counts(surfaces, len(vd0))
    if len(group_counts) != sidecar.EXPECTED_GROUP_COUNT:
        raise ProofError(f"VD0 group count {len(group_counts)} != {sidecar.EXPECTED_GROUP_COUNT}")

    # Re-close the v3 MaterialMemory ownership facts locally. The 327 fixed
    # records are FOLLOW-owned children and the 327 packed surface aliases form
    # one exact block-5 VIRTUAL span at 8-byte stride.
    physical = data[MATERIAL_MEMORY_PHYSICAL_START:MATERIAL_MEMORY_PHYSICAL_END]
    if len(physical) != sidecar.MATERIAL_COUNT * MATERIAL_MEMORY_RECORD_BYTES:
        raise ProofError("MaterialMemory physical span is truncated")
    for i in range(sidecar.MATERIAL_COUNT):
        raw = struct.unpack_from("<I", physical, i * MATERIAL_MEMORY_RECORD_BYTES)[0]
        if raw != worldproof.FOLLOW:
            raise ProofError(f"MaterialMemory slot {i} is not FOLLOW-owned")

    surface_ptrs = sorted({int(row["materialPointerRaw"], 16) for row in surfaces})
    if len(surface_ptrs) != sidecar.MATERIAL_COUNT:
        raise ProofError("surface Material alias population is not 327 slots")
    decoded = [worldproof.dec(raw, blocks) for raw in surface_ptrs]
    for i, (kind, block, offset) in enumerate(decoded):
        expected = MATERIAL_MEMORY_VIRTUAL_START + i * MATERIAL_MEMORY_RECORD_BYTES
        if kind != "packed" or block != MATERIAL_MEMORY_VIRTUAL_BLOCK or offset != expected:
            raise ProofError(
                f"surface Material alias slot {i} disagrees with exact MaterialMemory ownership: "
                f"{kind}/{block}/{offset} != packed/{MATERIAL_MEMORY_VIRTUAL_BLOCK}/{expected}"
            )
    if decoded[-1][2] + MATERIAL_MEMORY_RECORD_BYTES != MATERIAL_MEMORY_VIRTUAL_END:
        raise ProofError("MaterialMemory VIRTUAL end drift")

    identity = family.bind_map(MAP, expanded)
    materials, _tech_qs = sidecar._material_chain(data, blocks, identity)
    if len(materials) != sidecar.MATERIAL_COUNT:
        raise ProofError("strict serialized Material child count drift")
    material_by_ptr = {raw: material for raw, material in zip(surface_ptrs, materials)}

    height_density = 1.0 / HALF_HEIGHT
    log_ratio = math.log(DENSITY_OVER_MAX_DENSITY)
    height_factor = height_density * math.log(2.0)
    threshold_z = BASE_HEIGHT + log_ratio / height_factor

    target_surfaces: dict[str, list[dict]] = {name: [] for name in TARGETS}
    for surface in surfaces:
        raw = int(surface["materialPointerRaw"], 16)
        material = material_by_ptr[raw]
        name = material["name"]
        if name not in target_surfaces:
            continue

        group_offset = int(surface["vertexDataOffset0"])
        group_count = group_counts[group_offset]
        first_index = int(surface["baseIndex"])
        index_count = int(surface["triCount"]) * 3
        end_index = first_index + index_count
        if not (0 <= first_index <= end_index <= sidecar.INDEX_COUNT):
            raise ProofError(f"surface {surface['index']} invalid retail index slice {first_index}:{end_index}")
        local_indices = [
            struct.unpack_from("<H", index_bytes, 2 * i)[0]
            for i in range(first_index, end_index)
        ]
        if not local_indices:
            raise ProofError(f"target surface {surface['index']} has no retail indices")
        if max(local_indices) >= group_count:
            raise ProofError(
                f"surface {surface['index']} local index {max(local_indices)} >= VD0 group count {group_count}"
            )

        unique_indices = sorted(set(local_indices))
        positions: list[tuple[float, float, float]] = []
        for local_index in unique_indices:
            offset = group_offset + local_index * VD0_STRIDE
            if offset + 12 > len(vd0):
                raise ProofError(f"surface {surface['index']} indexed POSITION exceeds canonical VD0")
            position = struct.unpack_from("<3f", vd0, offset)
            if not all(math.isfinite(value) for value in position):
                raise ProofError(f"surface {surface['index']} has non-finite indexed POSITION")
            positions.append(position)

        min_z = min(p[2] for p in positions)
        max_z = max(p[2] for p in positions)
        x_at_min_z = log_ratio - height_factor * (min_z - BASE_HEIGHT)
        x_at_max_z = log_ratio - height_factor * (max_z - BASE_HEIGHT)
        if not x_at_min_z < 0.0:
            raise ProofError(
                f"{name} surface {surface['index']} reaches non-exponential fog branch: "
                f"indexedMinZ={min_z} x(max)={x_at_min_z} threshold={threshold_z}"
            )

        target_surfaces[name].append(
            {
                "surfaceIndex": int(surface["index"]),
                "materialPointerRaw": surface["materialPointerRaw"],
                "vd0GroupOffset": group_offset,
                "vd0GroupVertexCount": group_count,
                "firstVertex": int(surface["firstVertex"]),
                "storedVertexCount": int(surface["vertexCount"]),
                "baseIndex": first_index,
                "triCount": int(surface["triCount"]),
                "indexCount": index_count,
                "uniqueIndexedVertexCount": len(unique_indices),
                "indexedNativeMinZ": min_z,
                "indexedNativeMaxZ": max_z,
                "serializedMinsZDiagnostic": float(surface["mins"][2]),
                "serializedMaxsZDiagnostic": float(surface["maxs"][2]),
                "xAtIndexedMinZ": x_at_min_z,
                "xAtIndexedMaxZ": x_at_max_z,
                "allIndexedVerticesXNegative": True,
            }
        )

    missing = [name for name, rows in target_surfaces.items() if not rows]
    if missing:
        raise ProofError(f"target multiply-decal Materials have no GfxSurface rows: {missing}")

    material_rows = []
    all_min_z = math.inf
    all_max_z = -math.inf
    max_x = -math.inf
    surface_count = 0
    unique_vertex_sum = 0
    for name in TARGETS:
        rows = sorted(target_surfaces[name], key=lambda row: row["surfaceIndex"])
        surface_count += len(rows)
        unique_vertex_sum += sum(row["uniqueIndexedVertexCount"] for row in rows)
        min_z = min(row["indexedNativeMinZ"] for row in rows)
        max_z = max(row["indexedNativeMaxZ"] for row in rows)
        material_max_x = max(row["xAtIndexedMinZ"] for row in rows)
        all_min_z = min(all_min_z, min_z)
        all_max_z = max(all_max_z, max_z)
        max_x = max(max_x, material_max_x)
        material_rows.append(
            {
                "material": name,
                "surfaceCount": len(rows),
                "indexedNativeMinZ": min_z,
                "indexedNativeMaxZ": max_z,
                "maximumXOverIndexedVertices": material_max_x,
                "allIndexedVerticesExponentialBranch": material_max_x < 0.0,
                "surfaces": rows,
            }
        )

    cancellation = {
        "branch": "x < 0",
        "q": "(density/maxDensity) * exp(-heightDensity*ln(2)*(sourceZ-baseHeight))",
        "G": "(density/maxDensity) * exp(-heightDensity*ln(2)*(eyeZ-baseHeight))",
        "H": "(q-G) / (-heightDensity*ln(2)*(sourceZ-eyeZ))",
        "F_y": "-maxDensity",
        "observableProduct": "H * F_y",
        "maxDensityCancels": True,
    }

    summary = {
        "format": FORMAT,
        "map": MAP,
        "source": {
            "expandedBytes": len(data),
            "expandedSha256": sha(data),
            "surfaceArrayStart": sidecar.SURFACE_START,
            "surfaceRecordBytes": sidecar.SURFACE_BYTES,
            "surfaceCount": sidecar.SURFACE_COUNT,
            "vd0Start": sidecar.VD0_START,
            "vd0End": sidecar.VD0_END,
            "vd0Sha256": sidecar.VD0_SHA256,
            "vd0Stride": VD0_STRIDE,
            "indexStart": sidecar.INDEX_START,
            "indexEnd": sidecar.INDEX_END,
            "indexSha256": sidecar.INDEX_SHA256,
        },
        "fogBranch": {
            "baseHeight": BASE_HEIGHT,
            "halfHeight": HALF_HEIGHT,
            "densityOverMaxDensity": DENSITY_OVER_MAX_DENSITY,
            "xZeroNativeZ": threshold_z,
            "cohortIndexedNativeMinZ": all_min_z,
            "cohortIndexedNativeMaxZ": all_max_z,
            "maximumXOverIndexedCohort": max_x,
            "allTargetIndexedGeometryXNegative": max_x < 0.0,
        },
        "cohort": {
            "materialCount": len(TARGETS),
            "surfaceCount": surface_count,
            "sumUniqueIndexedVerticesPerSurface": unique_vertex_sum,
            "materials": material_rows,
        },
        "maxDensityCancellation": cancellation,
        "proofBoundary": (
            "Exact retained retail GfxSurface index slices, canonical uint16 index buffer, exact 36-byte VD0 POSITION records, and exact MaterialMemory-to-Material ownership prove every indexed vertex of the three multiply-decal Materials lies in the VS x<0 exponential branch. Within that branch the symbolic T6 equation cancels maxDensity algebraically, so the original CPU choice of maxDensity conditioning scale cannot affect this cohort's shader output. Serialized GfxSurface mins/maxs are diagnostic only for this cohort because they are zero. This does not close the independent sunFogPitch/sunFogYaw direction convention."
        ),
    }
    stable = json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    summary["proofSha256"] = hashlib.sha256(stable).hexdigest()
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.expanded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["fogBranch"], indent=2, sort_keys=True))
    print(json.dumps({
        row["material"]: {
            "surfaces": row["surfaceCount"],
            "minZ": row["indexedNativeMinZ"],
            "maxZ": row["indexedNativeMaxZ"],
            "maxX": row["maximumXOverIndexedVertices"],
        }
        for row in doc["cohort"]["materials"]
    }, indent=2, sort_keys=True))
    print("proofSha256", doc["proofSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
