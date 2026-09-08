#!/usr/bin/env python3
"""Fail-closed proof of the observed T6 PC IWI27 mip layout.

The v1 probe exposed the exact edge case: IWI27 stores eight cumulative size
words, but when a texture has fewer mip levels than the table can address, the
remaining words clamp to the smallest mip start rather than to the 64-byte
header boundary.

For block-compressed 2D IWI27 payloads the candidate proven here is:

  file layout after the 64-byte header = smallest mip -> ... -> largest mip
  size[i] = 64 + sum(mips[min(i, lastMip):])   for i=0..7

where ``mips`` is the exact largest->smallest BC byte-count sequence.  The tool
requires every supplied payload to satisfy the complete eight-word equation and
also requires the payload byte count to equal the complete mip-chain byte sum.
It does not decode or transcode pixels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import t6_iwi27_mip_layout_probe_v1 as v1

FORMAT = "t6-iwi27-mip-layout-proof-v2"


class ProofError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_size_words(width: int, height: int, fmt: int) -> tuple[list[int], list[int]]:
    block = v1.BLOCK_BYTES[fmt]
    mips = v1.expected_mips(width, height, block)
    last = len(mips) - 1
    words = [v1.HEADER_BYTES + sum(mips[min(i, last):]) for i in range(8)]
    return words, mips


def inspect(path: Path) -> dict:
    row = v1.inspect(path)
    if int(row["depth"]) != 1:
        raise ProofError(f"{path}: v2 proof is deliberately 2D-only, depth={row['depth']}")
    expected_words, mips = expected_size_words(
        int(row["width"]), int(row["height"]), int(row["formatCode"])
    )
    actual_words = [int(x) for x in row["sizeWords"]]
    total_mip_bytes = sum(mips)
    payload_bytes = int(row["bytes"]) - v1.HEADER_BYTES
    mismatches = [
        {
            "index": i,
            "actual": actual_words[i],
            "expected": expected_words[i],
            "difference": actual_words[i] - expected_words[i],
        }
        for i in range(8)
        if actual_words[i] != expected_words[i]
    ]
    return {
        "file": row["file"],
        "bytes": row["bytes"],
        "sha256": row["sha256"],
        "formatCode": row["formatCode"],
        "format": row["format"],
        "flags": row["flags"],
        "width": row["width"],
        "height": row["height"],
        "depth": row["depth"],
        "mipCount": len(mips),
        "mipBytesLargestToSmallest": mips,
        "totalMipBytes": total_mip_bytes,
        "payloadBytesAfterHeader": payload_bytes,
        "payloadBytesEqualCompleteMipChain": payload_bytes == total_mip_bytes,
        "actualSizeWords": actual_words,
        "expectedClampedCumulativeSizeWords": expected_words,
        "sizeWordMismatches": mismatches,
        "completeEightWordFit": not mismatches,
        "serializedPayloadOrder": "smallest-to-largest",
        "largestMipStart": expected_words[1],
        "largestMipEnd": expected_words[0],
    }


def build(root: Path) -> dict:
    files = sorted(root.rglob("*.iwi"))
    if not files:
        raise ProofError(f"no .iwi files under {root}")
    rows = [inspect(path) for path in files]
    bad_words = [row for row in rows if not row["completeEightWordFit"]]
    bad_total = [row for row in rows if not row["payloadBytesEqualCompleteMipChain"]]
    formats = Counter(row["format"] for row in rows)
    flags = Counter(int(row["flags"]) for row in rows)
    mip_counts = Counter(int(row["mipCount"]) for row in rows)
    if bad_words or bad_total:
        raise ProofError(
            "retail IWI27 corpus rejected clamped cumulative layout: "
            f"sizeWordFailures={len(bad_words)} totalMipFailures={len(bad_total)} "
            f"firstSizeWordFailure={bad_words[:1]} firstTotalFailure={bad_total[:1]}"
        )
    return {
        "format": FORMAT,
        "summary": {
            "fileCount": len(rows),
            "formatCounts": dict(sorted(formats.items())),
            "flagCounts": {str(k): v for k, v in sorted(flags.items())},
            "mipCountCounts": {str(k): v for k, v in sorted(mip_counts.items())},
            "completeEightWordFitCount": len(rows),
            "completeMipPayloadFitCount": len(rows),
            "failureCount": 0,
            "allTwoDimensional": True,
            "serializedPayloadOrder": "smallest-to-largest",
        },
        "equation": {
            "headerBytes": v1.HEADER_BYTES,
            "mipOrderForSizeEquation": "largest-to-smallest",
            "sizeWordCount": 8,
            "sizeWord": "64 + sum(mips[min(i,lastMip):])",
            "physicalPayloadOrder": "smallest-to-largest",
            "supportedObservedFormats": {
                "0x0b": "DXT1/BC1",
                "0x0d": "DXT5/BC3",
                "0x0e": "DXN/BC5",
            },
        },
        "rows": rows,
        "proofBoundary": (
            "Exact IWI27 header and block-compressed byte-count proof only. Every supplied "
            "file must satisfy all eight serialized size words and the complete mip-chain "
            "byte sum. No pixel decode, image-name inference, DDS header synthesis, or "
            "unobserved IWI format is promoted here."
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
