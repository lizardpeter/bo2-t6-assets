#!/usr/bin/env python3
"""Empirically classify T6 PC IWI27 mip-boundary semantics.

This probe deliberately does not convert or decode image payloads.  It inspects
only the retained IWI27 header fields and compares the eight serialized size
words at 0x20 against exact block-compressed mip byte counts.

The output records which candidate boundary model(s) fit each payload.  A model
is only promoted by a caller after the full source-gated corpus agrees; this
probe itself never chooses a model from one sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

FORMAT = "t6-iwi27-mip-layout-probe-v1"
IWI_VERSION = 27
HEADER_BYTES = 64
BLOCK_BYTES = {
    0x0B: 8,   # DXT1 / BC1
    0x0C: 16,  # DXT3 / BC2
    0x0D: 16,  # DXT5 / BC3
    0x0E: 16,  # DXN / BC5
}
FORMAT_NAMES = {0x0B: "DXT1", 0x0C: "DXT3", 0x0D: "DXT5", 0x0E: "DXN"}


class ProbeError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mip_bytes(width: int, height: int, block_bytes: int) -> int:
    return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_bytes


def expected_mips(width: int, height: int, block_bytes: int, limit: int = 16) -> list[int]:
    out = []
    w, h = width, height
    while True:
        out.append(mip_bytes(w, h, block_bytes))
        if (w == 1 and h == 1) or len(out) >= limit:
            return out
        w = max(1, w // 2)
        h = max(1, h // 2)


def _positive_prefix(values: tuple[int, ...]) -> list[int]:
    out = []
    for v in values:
        if v == 0:
            break
        out.append(v)
    return out


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < HEADER_BYTES or data[:3] != b"IWi" or data[3] != IWI_VERSION:
        raise ProbeError(f"{path}: not T6 IWI27")
    fmt, flags = data[4], data[5]
    if fmt not in BLOCK_BYTES:
        raise ProbeError(f"{path}: unsupported IWI27 format 0x{fmt:02x}")
    width, height, depth = struct.unpack_from("<3H", data, 6)
    gamma = struct.unpack_from("<f", data, 12)[0]
    sizes = struct.unpack_from("<8I", data, 32)
    if width <= 0 or height <= 0 or depth <= 0:
        raise ProbeError(f"{path}: invalid dimensions {width}x{height}x{depth}")
    if sizes[0] != len(data):
        raise ProbeError(f"{path}: size[0] {sizes[0]} != file bytes {len(data)}")

    block = BLOCK_BYTES[fmt]
    expected = expected_mips(width, height, block)
    nonzero = _positive_prefix(sizes)
    if any(v < HEADER_BYTES or v > len(data) for v in nonzero):
        raise ProbeError(f"{path}: nonzero size word outside file bounds")
    if any(a < b for a, b in zip(nonzero, nonzero[1:])):
        raise ProbeError(f"{path}: nonzero size words are not non-increasing: {nonzero}")

    # Candidate A: size[i] is the end of mip i and size[i+1] its start, with
    # top/largest mip at i=0.  This is the model suggested by size[0]==EOF and
    # by the retained top-mip extraction rule EOF-topMipBytes.
    deltas = [a - b for a, b in zip(nonzero, nonzero[1:])]
    candidate_a_compared = min(len(deltas), len(expected))
    candidate_a = all(deltas[i] == expected[i] for i in range(candidate_a_compared))

    # Candidate B is the same serialized boundaries but maps the observed
    # deltas to smallest->largest mip sizes.  Keeping it explicit prevents the
    # probe from silently assuming direction.
    rev_expected = list(reversed(expected[: len(deltas)]))
    candidate_b = len(deltas) <= len(expected) and deltas == rev_expected

    top_expected = expected[0]
    top_start_arithmetic = len(data) - top_expected
    top_boundary_word = sizes[1] if len(nonzero) >= 2 else None

    return {
        "file": path.name,
        "bytes": len(data),
        "sha256": sha256(data),
        "formatCode": fmt,
        "format": FORMAT_NAMES[fmt],
        "flags": flags,
        "width": width,
        "height": height,
        "depth": depth,
        "gamma": gamma,
        "sizeWords": list(sizes),
        "nonzeroSizeWordCount": len(nonzero),
        "nonzeroSizeWords": nonzero,
        "boundaryDeltas": deltas,
        "expectedMipBytesLargestToSmallest": expected,
        "topMipBytes": top_expected,
        "topMipArithmeticStart": top_start_arithmetic,
        "sizeWord1": top_boundary_word,
        "sizeWord1EqualsTopMipArithmeticStart": top_boundary_word == top_start_arithmetic,
        "candidateA_LargestToSmallestBoundaryDeltas": candidate_a,
        "candidateAComparedDeltaCount": candidate_a_compared,
        "candidateB_SmallestToLargestBoundaryDeltas": candidate_b,
    }


def build(root: Path) -> dict:
    files = sorted(root.rglob("*.iwi"))
    if not files:
        raise ProbeError(f"no .iwi files under {root}")
    rows = [inspect(path) for path in files]
    formats = Counter(row["format"] for row in rows)
    nonzero_counts = Counter(row["nonzeroSizeWordCount"] for row in rows)
    a = sum(bool(row["candidateA_LargestToSmallestBoundaryDeltas"]) for row in rows)
    b = sum(bool(row["candidateB_SmallestToLargestBoundaryDeltas"]) for row in rows)
    top = sum(bool(row["sizeWord1EqualsTopMipArithmeticStart"]) for row in rows)
    return {
        "format": FORMAT,
        "root": str(root),
        "summary": {
            "fileCount": len(rows),
            "formatCounts": dict(sorted(formats.items())),
            "nonzeroSizeWordCounts": {str(k): v for k, v in sorted(nonzero_counts.items())},
            "candidateAFullFitCount": a,
            "candidateBFullFitCount": b,
            "sizeWord1TopBoundaryFitCount": top,
            "allCandidateA": a == len(rows),
            "allCandidateB": b == len(rows),
            "allSizeWord1TopBoundary": top == len(rows),
        },
        "rows": rows,
        "proofBoundary": (
            "Header-only empirical classification. No image-name inference, no pixel decode, "
            "no DDS conversion, and no model promotion occurs in this document."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.out.write_bytes(payload)
    print(json.dumps({"out": str(args.out), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
