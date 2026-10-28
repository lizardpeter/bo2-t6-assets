#!/usr/bin/env python3
"""Independent original-byte GfxWorld integrity gate for T6 PC Nuketown.

Input is the *decompressed*, SHA-verified XFile; no copyrighted source bytes
are stored in Git. This is an offline source fixture, not runtime map logic.
It does not prove Vulkan draw admission, XModel coverage, or animation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import struct

EXPANDED_HASH = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
EXPANDED_SIZE = 154_653_476
SURFACE_START, SURFACE_COUNT, SURFACE_STRIDE = 85_007_995, 5_614, 80
VD0_START, VD0_END, VD0_STRIDE = 76_182_996, 81_468_084, 36
INDEX_START, INDEX_END = 81_501_848, 82_103_528
VD0_HASH = "7a5be06b14564a2dafd065d77204ff808e7cbbaac1ab0f06f1c6ef3f3e29ca76"
INDEX_HASH = "70344c3cfbc8eb12a2e29b37deb55b5767a33b5b97beb3681215bf393c346fa7"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def exact_group_count(byte_span):
    # Local T6 VD0 batches have 36-byte rows aligned to 16 bytes.
    choices = [n for n in range(max(0, byte_span // 36 - 2), byte_span // 36 + 2)
               if ((n * 36 + 15) & ~15) == byte_span]
    if len(choices) != 1:
        raise ValueError(f"ambiguous source VD0 group span {byte_span}: {choices}")
    return choices[0]


def audit(expanded):
    if len(expanded) != EXPANDED_SIZE or sha256(expanded) != EXPANDED_HASH:
        raise ValueError("original expanded Nuketown XFile identity mismatch")
    vd0 = memoryview(expanded)[VD0_START:VD0_END]
    idx = memoryview(expanded)[INDEX_START:INDEX_END]
    if sha256(vd0) != VD0_HASH or sha256(idx) != INDEX_HASH:
        raise ValueError("original VD0/index SHA-256 mismatch")
    rows, groups = [], defaultdict(list)
    for surface_id in range(SURFACE_COUNT):
        at = SURFACE_START + surface_id * SURFACE_STRIDE
        offset = struct.unpack_from("<i", expanded, at + 12)[0]
        first_vertex = struct.unpack_from("<i", expanded, at + 32)[0]
        vertex_count, triangle_count = struct.unpack_from("<HH", expanded, at + 40)
        first_index = struct.unpack_from("<i", expanded, at + 44)[0]
        material = struct.unpack_from("<I", expanded, at + 48)[0]
        if not 0 <= offset < len(vd0):
            raise ValueError(f"surface {surface_id}: invalid VD0 group offset")
        if first_index < 0 or (first_index + triangle_count * 3) * 2 > len(idx):
            raise ValueError(f"surface {surface_id}: invalid index slice")
        row = (surface_id, offset, first_vertex, vertex_count,
               triangle_count, first_index, material)
        rows.append(row)
        groups[offset].append(row)
    offsets = sorted(groups)
    if len(offsets) != 340:
        raise ValueError(f"expected 340 VD0 groups, got {len(offsets)}")
    counts = {}
    for i, offset in enumerate(offsets):
        stop = offsets[i + 1] if i + 1 < len(offsets) else len(vd0)
        counts[offset] = exact_group_count(stop - offset)
        if not counts[offset] or len({row[2] for row in groups[offset]}) != 1:
            raise ValueError(f"invalid local VD0 group {offset}")
    accepted, bad_index, nonfinite, degenerate = 0, 0, 0, 0
    materials = Counter()
    for sid, offset, _, advertised, triangles, first, material in rows:
        capacity = counts[offset]
        if advertised and advertised != capacity:
            raise ValueError(f"surface {sid}: source group count disagreement")
        for t in range(triangles):
            corners = struct.unpack_from("<HHH", idx, (first + t * 3) * 2)
            if max(corners) >= capacity:
                bad_index += 1
                continue
            points = [struct.unpack_from("<3f", vd0, offset + c * VD0_STRIDE)
                      for c in corners]
            if any(not math.isfinite(v) for point in points for v in point):
                nonfinite += 1
                continue
            u = [points[1][k] - points[0][k] for k in range(3)]
            v = [points[2][k] - points[0][k] for k in range(3)]
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2],
                     u[0]*v[1]-u[1]*v[0])
            if sum(c*c for c in cross) < 1e-14:
                degenerate += 1
            accepted += 1
            materials[material] += 1
    report = {
        "format": "t6-nuketown-original-gfxworld-integrity-v1",
        "expandedSha256": EXPANDED_HASH,
        "sourceSurfaceCount": len(rows),
        "sourceVertexGroupCount": len(groups),
        "sourceTriangleCount": sum(row[4] for row in rows),
        "acceptedTriangleCount": accepted,
        "rejectedLocalIndexCount": bad_index,
        "rejectedNonfiniteCount": nonfinite,
        "zeroAreaTriangleCount": degenerate,
        "uniqueMaterialPointerCount": len(materials),
        "proofBoundary": "Original GfxWorld triangle/index integrity only. Not a parity claim for XModels, material draw admission, visibility, Vulkan depth/alpha/cull state, or animation.",
    }
    if accepted != 100_280 or bad_index or nonfinite or degenerate:
        raise ValueError(f"original GfxWorld integrity regression: {report}")
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("expanded_xfile", type=Path)
    cli.add_argument("--report", type=Path)
    args = cli.parse_args()
    result = json.dumps(audit(args.expanded_xfile.read_bytes()), indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(result)
    print(result)


if __name__ == "__main__":
    main()
