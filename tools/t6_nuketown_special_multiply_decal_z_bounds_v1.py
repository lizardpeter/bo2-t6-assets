#!/usr/bin/env python3
"""Prove native-T6 Z bounds and fog-branch closure for Nuketown multiply decals.

The proof stays entirely on retained retail bytes:
  expanded FastFile -> exact GfxSurface rows -> exact MaterialMemory alias slots
  -> strict serialized Material child order -> three pinned multiply-decal names.

For the exact multiply-decal VS, after substituting the recovered fog-vector
construction and an eye-relative native-T6 worldMatrix,

    x = P.z * fogConsts.w + fogConsts.x
      = ln(density/maxDensity)
        - heightDensity * ln(2) * (sourceVertexZ - baseHeight).

With positive heightDensity, x is monotonically decreasing in sourceVertexZ.
Therefore the serialized minimum Z of each GfxSurface is sufficient to prove
whether *all* vertices on that surface remain in the retail shader's x < 0
exponential branch.  No vertex decode or geometric approximation is needed.
"""
from __future__ import annotations

import argparse
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

# Authoritative MaterialMemory ownership closure retained by sidecars v3.
MATERIAL_MEMORY_PHYSICAL_START = 84_463_050
MATERIAL_MEMORY_PHYSICAL_END = 84_465_666
MATERIAL_MEMORY_VIRTUAL_BLOCK = 5
MATERIAL_MEMORY_VIRTUAL_START = 71_642_512
MATERIAL_MEMORY_VIRTUAL_END = 71_645_128
MATERIAL_MEMORY_RECORD_BYTES = 8

# SHA-pinned authored GfxWorldFog values, duplicated here only as exact proof
# constants so this tool does not depend on a generated sidecar artifact.
BASE_HEIGHT = -400.0
HALF_HEIGHT = 3333.74560546875
DENSITY_OVER_MAX_DENSITY = 0.01  # 1 / 100 for the lineage-backed conditioning scale.


class ProofError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(expanded: Path) -> dict:
    data = expanded.read_bytes()
    if len(data) != sidecar.EXPANDED_BYTES or sha(data) != sidecar.EXPANDED_SHA256:
        raise ProofError("expanded retail Nuketown identity mismatch")

    blocks, _assets = worldproof.front(data)
    world = worldproof.world(data, sidecar.GFXWORLD_START, sidecar.SURFACE_COUNT, sidecar.MATERIAL_COUNT)
    surfaces = sidecar._surface_rows(data, world)
    if len(surfaces) != sidecar.SURFACE_COUNT:
        raise ProofError("GfxSurface count drift")

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
    material_by_ptr = {
        raw: material for raw, material in zip(surface_ptrs, materials)
    }

    height_density = 1.0 / HALF_HEIGHT
    log_ratio = math.log(DENSITY_OVER_MAX_DENSITY)
    threshold_z = BASE_HEIGHT + log_ratio / (height_density * math.log(2.0))

    grouped: dict[str, list[dict]] = {name: [] for name in TARGETS}
    for surface in surfaces:
        raw = int(surface["materialPointerRaw"], 16)
        material = material_by_ptr[raw]
        name = material["name"]
        if name not in grouped:
            continue
        min_z = float(surface["mins"][2])
        max_z = float(surface["maxs"][2])
        if not (math.isfinite(min_z) and math.isfinite(max_z) and min_z <= max_z):
            raise ProofError(f"surface {surface['index']} invalid native Z bounds")
        x_at_min_z = log_ratio - height_density * math.log(2.0) * (min_z - BASE_HEIGHT)
        x_at_max_z = log_ratio - height_density * math.log(2.0) * (max_z - BASE_HEIGHT)
        if not x_at_min_z < 0.0:
            raise ProofError(
                f"{name} surface {surface['index']} reaches non-exponential fog branch: "
                f"minZ={min_z} x(max)={x_at_min_z} threshold={threshold_z}"
            )
        grouped[name].append(
            {
                "surfaceIndex": int(surface["index"]),
                "materialPointerRaw": surface["materialPointerRaw"],
                "firstVertex": int(surface["firstVertex"]),
                "vertexCount": int(surface["vertexCount"]),
                "baseIndex": int(surface["baseIndex"]),
                "triCount": int(surface["triCount"]),
                "nativeMinZ": min_z,
                "nativeMaxZ": max_z,
                "xAtMinZ": x_at_min_z,
                "xAtMaxZ": x_at_max_z,
                "allVerticesXNegative": True,
            }
        )

    missing = [name for name, rows in grouped.items() if not rows]
    if missing:
        raise ProofError(f"target multiply-decal Materials have no GfxSurface rows: {missing}")

    material_rows = []
    all_min_z = math.inf
    all_max_z = -math.inf
    max_x = -math.inf
    surface_count = 0
    vertex_upper_bound_count = 0
    for name in TARGETS:
        rows = sorted(grouped[name], key=lambda row: row["surfaceIndex"])
        surface_count += len(rows)
        vertex_upper_bound_count += sum(row["vertexCount"] for row in rows)
        min_z = min(row["nativeMinZ"] for row in rows)
        max_z = max(row["nativeMaxZ"] for row in rows)
        material_max_x = max(row["xAtMinZ"] for row in rows)
        all_min_z = min(all_min_z, min_z)
        all_max_z = max(all_max_z, max_z)
        max_x = max(max_x, material_max_x)
        material_rows.append(
            {
                "material": name,
                "surfaceCount": len(rows),
                "nativeMinZ": min_z,
                "nativeMaxZ": max_z,
                "maximumXOverSerializedBounds": material_max_x,
                "allSurfacesExponentialBranch": material_max_x < 0.0,
                "surfaces": rows,
            }
        )

    # In x<0 branch, q and G both carry density/maxDensity while F.y carries
    # -maxDensity, so the conditioning maxDensity cancels exactly. Seal the
    # algebra as a machine-readable identity rather than an explanatory note.
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
        },
        "fogBranch": {
            "baseHeight": BASE_HEIGHT,
            "halfHeight": HALF_HEIGHT,
            "densityOverMaxDensity": DENSITY_OVER_MAX_DENSITY,
            "xZeroNativeZ": threshold_z,
            "cohortNativeMinZ": all_min_z,
            "cohortNativeMaxZ": all_max_z,
            "maximumXOverCohortBounds": max_x,
            "allTargetGeometryXNegative": max_x < 0.0,
        },
        "cohort": {
            "materialCount": len(TARGETS),
            "surfaceCount": surface_count,
            "surfaceVertexCountUpperBound": vertex_upper_bound_count,
            "materials": material_rows,
        },
        "maxDensityCancellation": cancellation,
        "proofBoundary": (
            "Exact retained retail GfxSurface native bounds and exact MaterialMemory-to-Material ownership prove every vertex of the three multiply-decal Materials lies in the VS x<0 exponential branch. Within that branch the symbolic T6 equation cancels maxDensity algebraically, so the original CPU choice of maxDensity conditioning scale cannot affect this cohort's shader output. This does not close the independent sunFogPitch/sunFogYaw direction convention."
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
            "minZ": row["nativeMinZ"],
            "maxZ": row["nativeMaxZ"],
            "maxX": row["maximumXOverSerializedBounds"],
        }
        for row in doc["cohort"]["materials"]
    }, indent=2, sort_keys=True))
    print("proofSha256", doc["proofSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
