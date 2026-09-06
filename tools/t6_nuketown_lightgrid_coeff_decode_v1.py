#!/usr/bin/env python3
"""Source-close T6 Nuketown GfxLightGrid coefficient decoder and static SH reconstruction.

This tool is intentionally map-specific at v1. It verifies the canonical expanded
mp_nuketown_2020 stream and the 2,992 source-derived GfxStaticModelDrawInst records,
then reproduces the PC renderer coefficient path established from CoDMPServer_PC.exe:

  R_DecodeLightGridCoeffsWeighted       0x00A6EF30
  R_CalculateLightGridColorFromCoeffs   0x00A6EE90
  GenerateLightGridBasisDirs            0x00A98020
  R_BlendAndSetLightGridColors          0x00A6FD40

No old GLB is read or used as geometry/source input.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

MAP = "mp_nuketown_2020"
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
GFXWORLD_FIXED_START = 63_150_420
LIGHTGRID_FIXED_OFFSET = 464
ROW_DATA_START = 82_103_528
ROW_COUNT = 132
RAW_ROW_DATA_SIZE = 3_524
ENTRY_COUNT = 37_685
COEFF_COUNT = 40_615
COEFF_RECORD_BYTES = 54
ENTRIES_START = ROW_DATA_START + ROW_COUNT * 2 + RAW_ROW_DATA_SIZE
COEFF_START = ENTRIES_START + ENTRY_COUNT * 4
COEFF_END = COEFF_START + COEFF_COUNT * COEFF_RECORD_BYTES
COEFF_SHA256 = "cb78afcf9fd6abd008b2beeb56eedc355885bd681b384f92b261152c8eebb1e5"
STATIC_COUNT = 2_992

# Exact PC float constants read from the retail server executable.
INV_65535 = np.float32(struct.unpack("<f", bytes.fromhex("80008037"))[0])
SCALE_32 = np.float32(32.0)
BIAS_NEG16 = np.float32(-16.0)
QUARTER = np.float32(0.25)
HALF = np.float32(0.5)
EPSILON = np.float32(struct.unpack("<f", bytes.fromhex("17b7d138"))[0])
ONE = np.float32(1.0)
THREE = np.float32(3.0)
TWO_THIRDS = np.float32(struct.unpack("<f", bytes.fromhex("abaa2a3f"))[0])
ZERO = np.float32(0.0)


def f32(x) -> np.float32:
    return np.float32(x)


def fadd(a, b):
    return f32(f32(a) + f32(b))


def fsub(a, b):
    return f32(f32(a) - f32(b))


def fmul(a, b):
    return f32(f32(a) * f32(b))


def fdiv(a, b):
    return f32(f32(a) / f32(b))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def float_bits(x) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', float(f32(x))))[0]:08x}"


def decode_coeff_record(raw54: bytes, weight=np.float32(1.0)) -> np.ndarray:
    """Exact scalar equivalent of the PC SIMD decode for one 9xRGB uint16 record."""
    if len(raw54) != 54:
        raise ValueError("coefficient record must be exactly 54 bytes")
    u = np.frombuffer(raw54, dtype="<u2").reshape(9, 3)
    out = np.empty((9, 3), dtype=np.float32)
    w = f32(weight)
    for i in range(9):
        for c in range(3):
            v = f32(int(u[i, c]))
            v = fmul(v, INV_65535)
            v = fmul(v, SCALE_32)
            v = fadd(v, BIAS_NEG16)
            v = fmul(v, w)
            out[i, c] = v
    return out


def generate_grid_basis_dirs() -> np.ndarray:
    """Exact float32 scalar equivalent of T6 GenerateLightGridBasisDirs."""
    dirs = []
    for z_i in range(4):
        z = fsub(fmul(f32(z_i), TWO_THIRDS), ONE)
        for y_i in range(4):
            y = fsub(fmul(f32(y_i), TWO_THIRDS), ONE)
            for x_i in range(4):
                # Retail condition retains the 4x4x4 cube shell, skipping 2x2x2 interior.
                if (x_i <= 0 or x_i >= 3 or y_i <= 0 or y_i >= 3 or z_i <= 0 or z_i >= 3):
                    x = fsub(fmul(f32(x_i), TWO_THIRDS), ONE)
                    l2 = fadd(fadd(fmul(x, x), fmul(y, y)), fmul(z, z))
                    length = f32(math.sqrt(float(l2)))
                    # Retail normalization path divides by max(length, tiny); these 56 shell points are nonzero.
                    inv = fdiv(ONE, length)
                    dirs.append([fmul(x, inv), fmul(y, inv), fmul(z, inv)])
    arr = np.asarray(dirs, dtype=np.float32)
    assert arr.shape == (56, 3)
    return arr


def eval_directional_color(coeff: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Exact operation order of R_CalculateLightGridColorFromCoeffs for RGB lanes."""
    x, y, z = [f32(v) for v in direction]
    out = np.empty(3, dtype=np.float32)
    zx = fmul(z, x)
    zy = fmul(z, y)
    yx = fmul(y, x)
    z2 = fmul(z, z)
    z_basis = fsub(fmul(z2, THREE), ONE)
    x2 = fmul(x, x)
    y2 = fmul(y, y)
    xy_basis = fsub(x2, y2)
    for lane in range(3):
        v = fmul(x, coeff[1, lane])
        v = fadd(v, coeff[0, lane])
        v = fadd(v, fmul(y, coeff[2, lane]))
        v = fadd(v, fmul(z, coeff[3, lane]))
        v = fadd(v, fmul(zx, coeff[4, lane]))
        v = fadd(v, fmul(zy, coeff[5, lane]))
        v = fadd(v, fmul(yx, coeff[6, lane]))
        v = fadd(v, fmul(z_basis, coeff[7, lane]))
        v = fadd(v, fmul(xy_basis, coeff[8, lane]))
        out[lane] = v if v > ZERO else ZERO
    return out


def luminance_025_050_025(v: np.ndarray) -> np.float32:
    # Exact PC instruction order: r*.25, g*.5, add, b*.25, add.
    x = fmul(v[0], QUARTER)
    x = fadd(x, fmul(v[1], HALF))
    x = fadd(x, fmul(v[2], QUARTER))
    return x


def pack_gfx_lighting_sh(coeff: np.ndarray) -> np.ndarray:
    """Pack decoded 9xRGB coeffs into the exact T6 GfxLightingSH 3xvec4 layout."""
    L = [luminance_025_050_025(coeff[i]) for i in range(9)]
    denom = fadd(L[0], EPSILON)
    if denom == ZERO:
        # PC code has no special branch; preserve IEEE behavior only if encountered.
        raise ValueError("unexpected zero GfxLightingSH normalization denominator")
    out = np.empty((3, 4), dtype=np.float32)
    out[0, 0] = fdiv(coeff[0, 0], denom)
    out[0, 1] = fdiv(coeff[0, 1], denom)
    out[0, 2] = fdiv(coeff[0, 2], denom)
    out[0, 3] = fmul(L[7], THREE)
    out[1, 0] = L[1]
    out[1, 1] = L[2]
    out[1, 2] = L[3]
    out[1, 3] = fsub(denom, L[7])
    out[2, 0] = L[4]
    out[2, 1] = L[5]
    out[2, 2] = L[6]
    out[2, 3] = L[8]
    return out


def canonical_floats(a: np.ndarray):
    # Decimal floats are transport convenience; bit patterns are authoritative and also retained per vector.
    return [float(f32(x)) for x in a.reshape(-1)]


def vector_bits(a: np.ndarray):
    return [float_bits(x) for x in a.reshape(-1)]


def parse_grid_fixed(d: bytes):
    p = GFXWORLD_FIXED_START + LIGHTGRID_FIXED_OFFSET
    sun = struct.unpack_from("<I", d, p)[0]
    mins = struct.unpack_from("<3H", d, p + 4)
    maxs = struct.unpack_from("<3H", d, p + 10)
    offset = struct.unpack_from("<f", d, p + 16)[0]
    row_axis, col_axis = struct.unpack_from("<II", d, p + 20)
    row_ptr = struct.unpack_from("<I", d, p + 28)[0]
    raw_size = struct.unpack_from("<I", d, p + 32)[0]
    raw_ptr = struct.unpack_from("<I", d, p + 36)[0]
    entry_count = struct.unpack_from("<I", d, p + 40)[0]
    entries_ptr = struct.unpack_from("<I", d, p + 44)[0]
    color_count = struct.unpack_from("<I", d, p + 48)[0]
    colors_ptr = struct.unpack_from("<I", d, p + 52)[0]
    coeff_count = struct.unpack_from("<I", d, p + 56)[0]
    coeff_ptr = struct.unpack_from("<I", d, p + 60)[0]
    sky_count = struct.unpack_from("<I", d, p + 64)[0]
    sky_ptr = struct.unpack_from("<I", d, p + 68)[0]
    return dict(sunPrimaryLightIndex=sun, mins=list(mins), maxs=list(maxs), offset=offset,
                rowAxis=row_axis, colAxis=col_axis, rowDataStartPtr=row_ptr,
                rawRowDataSize=raw_size, rawRowDataPtr=raw_ptr, entryCount=entry_count,
                entriesPtr=entries_ptr, colorCount=color_count, colorsPtr=colors_ptr,
                coeffCount=coeff_count, coeffsPtr=coeff_ptr, skyGridVolumeCount=sky_count,
                skyGridVolumesPtr=sky_ptr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--placements", type=Path, required=True)
    ap.add_argument("--summary-out", type=Path, required=True)
    ap.add_argument("--static-out", type=Path, required=True, help="full static-lighting JSON or .zlib.b64")
    args = ap.parse_args()

    d = args.expanded.read_bytes()
    actual_sha = sha256_bytes(d)
    if actual_sha != EXPANDED_SHA256:
        raise SystemExit(f"expanded SHA mismatch: {actual_sha}")
    grid = parse_grid_fixed(d)
    expected_grid = dict(sunPrimaryLightIndex=1, mins=[4027,4035,2046], maxs=[4163,4166,2065],
                         rowAxis=1, colAxis=0, rawRowDataSize=RAW_ROW_DATA_SIZE,
                         entryCount=ENTRY_COUNT, colorCount=0, coeffCount=COEFF_COUNT,
                         skyGridVolumeCount=0)
    for k,v in expected_grid.items():
        if grid[k] != v:
            raise SystemExit(f"GfxLightGrid {k} mismatch: {grid[k]!r} != {v!r}")

    coeff_blob = d[COEFF_START:COEFF_END]
    if len(coeff_blob) != COEFF_COUNT * COEFF_RECORD_BYTES:
        raise SystemExit("coefficient payload truncated")
    actual_coeff_sha = sha256_bytes(coeff_blob)
    if actual_coeff_sha != COEFF_SHA256:
        raise SystemExit(f"coefficient SHA mismatch: {actual_coeff_sha}")

    placement_doc = json.loads(args.placements.read_text("utf-8"))
    instances = placement_doc.get("instances", [])
    if len(instances) != STATIC_COUNT:
        raise SystemExit(f"static placement count mismatch: {len(instances)}")
    static_indices = [int(x["colorsIndex"]) for x in instances]
    if len(set(static_indices)) != STATIC_COUNT:
        raise SystemExit("static colorsIndex values are not unique")
    if min(static_indices) < 0 or max(static_indices) >= COEFF_COUNT:
        raise SystemExit("static colorsIndex outside coefficient table")

    # Decode all records once to close range/finiteness of the serialized coefficient bank.
    coeff_all = np.empty((COEFF_COUNT, 9, 3), dtype=np.float32)
    raw_u16_min = 65535
    raw_u16_max = 0
    for idx in range(COEFF_COUNT):
        rec = coeff_blob[idx*54:(idx+1)*54]
        u = np.frombuffer(rec, dtype="<u2")
        raw_u16_min = min(raw_u16_min, int(u.min()))
        raw_u16_max = max(raw_u16_max, int(u.max()))
        coeff_all[idx] = decode_coeff_record(rec)
    if not np.isfinite(coeff_all).all():
        raise SystemExit("non-finite decoded coefficient")

    dirs = generate_grid_basis_dirs()
    dir_lengths = np.sqrt(np.sum(dirs.astype(np.float64)**2, axis=1))

    static_records = []
    sh_min = np.full(12, np.inf, dtype=np.float64)
    sh_max = np.full(12, -np.inf, dtype=np.float64)
    directional_min = np.full(3, np.inf, dtype=np.float64)
    directional_max = np.full(3, -np.inf, dtype=np.float64)
    directional_zero_lanes = 0
    primary_counts = Counter()
    visibility_counts = Counter()
    model_counts = Counter()

    for inst in instances:
        ci = int(inst["colorsIndex"])
        coeff = coeff_all[ci]
        sh = pack_gfx_lighting_sh(coeff)
        if not np.isfinite(sh).all():
            raise SystemExit(f"non-finite GfxLightingSH at static {inst['index']}")
        flat = sh.reshape(-1).astype(np.float64)
        sh_min = np.minimum(sh_min, flat)
        sh_max = np.maximum(sh_max, flat)

        # This is the exact 56-direction decode consumed by model-lighting/hero-light code.
        for direction in dirs:
            rgb = eval_directional_color(coeff, direction)
            directional_min = np.minimum(directional_min, rgb.astype(np.float64))
            directional_max = np.maximum(directional_max, rgb.astype(np.float64))
            directional_zero_lanes += int(np.count_nonzero(rgb == 0.0))
            if np.any(rgb < 0.0) or not np.isfinite(rgb).all():
                raise SystemExit(f"invalid directional color at static {inst['index']}")

        primary_counts[int(inst["primaryLightIndex"])] += 1
        visibility_counts[int(inst["visibility"])] += 1
        model_counts[str(inst["modelName"])] += 1
        static_records.append({
            "staticIndex": int(inst["index"]),
            "modelName": str(inst["modelName"]),
            "colorsIndex": ci,
            "primaryLightIndex": int(inst["primaryLightIndex"]),
            "visibility": int(inst["visibility"]),
            "lightingSH": {
                "V0": canonical_floats(sh[0]),
                "V1": canonical_floats(sh[1]),
                "V2": canonical_floats(sh[2]),
                "float32Bits": vector_bits(sh),
            }
        })

    full = {
        "format": "t6-nuketown-static-lighting-sh-v1",
        "map": MAP,
        "producer": "tools/t6_nuketown_lightgrid_coeff_decode_v1.py",
        "source": {
            "expandedSha256": EXPANDED_SHA256,
            "coefficientStart": COEFF_START,
            "coefficientEnd": COEFF_END,
            "coefficientCount": COEFF_COUNT,
            "coefficientRecordBytes": COEFF_RECORD_BYTES,
            "coefficientPayloadSha256": COEFF_SHA256,
            "staticPlacementSource": args.placements.name,
            "staticPlacementCount": STATIC_COUNT,
        },
        "retailPcFunctions": {
            "R_CalculateLightGridColorFromCoeffs": "0x00a6ee90",
            "R_DecodeLightGridCoeffsWeighted": "0x00a6ef30",
            "R_BlendAndSetLightGridColors": "0x00a6fd40",
            "GenerateLightGridBasisDirs": "0x00a98020",
        },
        "staticLighting": static_records,
    }
    full_bytes = json_bytes(full)
    full_sha = sha256_bytes(full_bytes)
    compressed = zlib.compress(full_bytes, 9)
    if args.static_out.name.endswith(".zlib.b64"):
        args.static_out.parent.mkdir(parents=True, exist_ok=True)
        args.static_out.write_bytes(base64.b64encode(compressed) + b"\n")
        stored_kind = "zlib+base64"
        stored_bytes = args.static_out.stat().st_size
        stored_sha = sha256_bytes(args.static_out.read_bytes())
    else:
        args.static_out.parent.mkdir(parents=True, exist_ok=True)
        args.static_out.write_bytes(full_bytes)
        stored_kind = "json"
        stored_bytes = len(full_bytes)
        stored_sha = full_sha

    summary = {
        "format": "t6-nuketown-lightgrid-coeff-decode-v1",
        "map": MAP,
        "producer": "tools/t6_nuketown_lightgrid_coeff_decode_v1.py",
        "source": {
            "expandedBytes": len(d),
            "expandedSha256": actual_sha,
            "gfxWorldFixedStart": GFXWORLD_FIXED_START,
            "gfxLightGridFixedStart": GFXWORLD_FIXED_START + LIGHTGRID_FIXED_OFFSET,
            "coefficientStart": COEFF_START,
            "coefficientEnd": COEFF_END,
            "coefficientCount": COEFF_COUNT,
            "coefficientRecordBytes": COEFF_RECORD_BYTES,
            "coefficientPayloadBytes": len(coeff_blob),
            "coefficientPayloadSha256": actual_coeff_sha,
            "staticPlacementFile": args.placements.name,
            "staticPlacementCount": STATIC_COUNT,
        },
        "retailPcProof": {
            "binary": "CoDMPServer_PC.exe",
            "R_CalculateLightGridColorFromCoeffs": {"va":"0x00a6ee90","bytes":156},
            "R_DecodeLightGridCoeffsWeighted": {"va":"0x00a6ef30"},
            "R_BlendAndSetLightGridColors": {"va":"0x00a6fd40"},
            "GenerateLightGridBasisDirs": {"va":"0x00a98020"},
            "decodeEquation": "float32((float32(float32(uint16 * 1/65535) * 32) + -16) * weight)",
            "constants": {
                "inv65535": {"value":float(INV_65535),"bits":float_bits(INV_65535),"va":"0x00d23240"},
                "scale32": {"value":32.0,"bits":float_bits(SCALE_32),"va":"0x00d23250"},
                "biasMinus16": {"value":-16.0,"bits":float_bits(BIAS_NEG16),"va":"0x00d23260"},
                "twoThirds": {"value":float(TWO_THIRDS),"bits":float_bits(TWO_THIRDS),"va":"0x00ba8ae0"},
                "quarter": {"value":0.25,"bits":float_bits(QUARTER),"va":"0x00b91034"},
                "half": {"value":0.5,"bits":float_bits(HALF),"va":"0x00becb58"},
                "epsilon": {"value":float(EPSILON),"bits":float_bits(EPSILON),"va":"0x00be6c34"},
                "three": {"value":3.0,"bits":float_bits(THREE),"va":"0x00b95c08"},
            },
            "directionalEquation": "max(c0 + x*c1 + y*c2 + z*c3 + zx*c4 + zy*c5 + yx*c6 + (3*z*z-1)*c7 + (x*x-y*y)*c8, 0)",
            "gfxLightingSHPack": {
                "L": "L(ci)=0.25*ci.r+0.5*ci.g+0.25*ci.b, in PC scalar instruction order",
                "V0": ["c0.r/(L(c0)+eps)","c0.g/(L(c0)+eps)","c0.b/(L(c0)+eps)","3*L(c7)"],
                "V1": ["L(c1)","L(c2)","L(c3)","L(c0)+eps-L(c7)"],
                "V2": ["L(c4)","L(c5)","L(c6)","L(c8)"],
            },
        },
        "gridBasisDirs": {
            "count": 56,
            "float32BytesSha256": sha256_bytes(dirs.astype("<f4").tobytes()),
            "first": canonical_floats(dirs[0]),
            "last": canonical_floats(dirs[-1]),
            "lengthRangeUsingFloat64Check": [float(dir_lengths.min()), float(dir_lengths.max())],
        },
        "coefficientBank": {
            "rawUint16Range": [raw_u16_min, raw_u16_max],
            "decodedFloatRange": [float(coeff_all.min()), float(coeff_all.max())],
            "allFinite": bool(np.isfinite(coeff_all).all()),
        },
        "staticReconstruction": {
            "count": STATIC_COUNT,
            "uniqueColorsIndexCount": len(set(static_indices)),
            "colorsIndexRange": [min(static_indices), max(static_indices)],
            "primaryLightIndexCounts": {str(k):v for k,v in sorted(primary_counts.items())},
            "visibilityCounts": {str(k):v for k,v in sorted(visibility_counts.items())},
            "uniqueModelCount": len(model_counts),
            "gfxLightingSHComponentMin": [float(x) for x in sh_min],
            "gfxLightingSHComponentMax": [float(x) for x in sh_max],
            "directionalRgbMin": [float(x) for x in directional_min],
            "directionalRgbMax": [float(x) for x in directional_max],
            "directionalZeroLaneCount": directional_zero_lanes,
            "directionalSampleLaneCount": STATIC_COUNT * 56 * 3,
            "allDirectionalSamplesNonnegative": True,
            "allGfxLightingSHFinite": True,
        },
        "artifact": {
            "fullJsonUncompressedBytes": len(full_bytes),
            "fullJsonUncompressedSha256": full_sha,
            "storedFile": args.static_out.name,
            "storedEncoding": stored_kind,
            "storedBytes": stored_bytes,
            "storedSha256": stored_sha,
            "zlibBytes": len(compressed),
            "zlibSha256": sha256_bytes(compressed),
        },
        "proofBoundary": {
            "proven": "Exact PC uint16 coefficient decode, exact 56-direction basis generation, exact second-order directional evaluation, and exact coeff->GfxLightingSH packing for all 2,992 source-derived Nuketown static draw instances.",
            "notClaimed": "This does not by itself reproduce dynamic hero-light additions, material lightmap equations, runtime visibility traces, or a full retail framebuffer.",
            "oldGlbUsedAsInput": False,
        },
    }
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)+"\n", "utf-8")
    print(json.dumps({
        "staticCount": STATIC_COUNT,
        "coeffCount": COEFF_COUNT,
        "coeffSha256": actual_coeff_sha,
        "basisSha256": summary["gridBasisDirs"]["float32BytesSha256"],
        "fullStaticJsonBytes": len(full_bytes),
        "fullStaticJsonSha256": full_sha,
        "storedBytes": stored_bytes,
        "storedSha256": stored_sha,
        "directionalRgbMin": summary["staticReconstruction"]["directionalRgbMin"],
        "directionalRgbMax": summary["staticReconstruction"]["directionalRgbMax"],
    }, indent=2))


if __name__ == "__main__":
    main()
