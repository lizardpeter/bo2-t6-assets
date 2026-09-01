#!/usr/bin/env python3
"""Census native dynamic T6 XAnim deltaPart key domains from an expanded retail XFile.

This tool sits directly on the source-closed serialized walker. It never decodes
or repairs frame domains. For every inline dynamic delta translation/quat2/quat
track it records the exact serialized key indices and checks the runtime domain
invariants required by the retail XAnim_GetTimeIndex helpers:

- first index == 0;
- final index == XAnimParts.numframes;
- indices strictly increase;
- all indices lie in 0..numframes;
- index width is u8 for numframes < 256, otherwise u16.

A failed invariant is evidence, not something to clamp or extend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from t6_xanim_serialized_walker import XAnimWalker


class CensusError(RuntimeError):
    pass


def _indices(data: bytes, section: dict) -> list[int]:
    start = int(section["indicesStart"])
    count = int(section["indexCount"])
    width = int(section["indexWidthBytes"])
    if count < 2:
        raise CensusError(f"{section['name']}: dynamic track has {count} indices")
    if width == 1:
        end = start + count
        if end > len(data):
            raise CensusError(f"{section['name']}: u8 index span out of range")
        return list(data[start:end])
    if width == 2:
        end = start + count * 2
        if end > len(data):
            raise CensusError(f"{section['name']}: u16 index span out of range")
        return list(struct.unpack_from("<" + "H" * count, data, start))
    raise CensusError(f"{section['name']}: unsupported index width {width}")


def census(data: bytes, *, start: int, count: int, expected_end: int | None = None) -> dict:
    if start < 0 or count <= 0:
        raise CensusError("start must be >=0 and count must be >0")
    pos = int(start)
    dynamic: list[dict] = []
    constant = Counter()
    asset_hashes: list[dict] = []
    blocker_count = 0

    for ordinal in range(int(count)):
        walk = XAnimWalker(data, pos).walk()
        if int(walk["assetFixedStart"]) != pos:
            raise CensusError(f"asset {ordinal}: walker start mismatch")
        next_pos = int(walk["assetSerializedEnd"])
        if next_pos <= pos:
            raise CensusError(f"asset {ordinal}: non-advancing serialized endpoint")
        blocker_count += len(walk.get("blockers", []))
        header = walk["header"]
        numframes = int(header["numframes"])
        expected_width = 1 if numframes < 256 else 2
        asset_hashes.append({
            "ordinal": ordinal,
            "name": walk.get("name"),
            "start": pos,
            "end": next_pos,
            "sha256": walk["assetSerializedSha256"],
        })

        delta = walk.get("delta") or {}
        for typ in ("trans", "quat2", "quat"):
            meta = delta.get(typ)
            if not meta:
                continue
            mode = str(meta.get("frameMode"))
            if mode == "constant":
                constant[typ] += 1
                continue
            if mode != "dynamic":
                raise CensusError(f"asset {ordinal} {typ}: unexpected mode {mode!r}")
            sec_name = f"XAnimParts.deltaPart.{typ}"
            section = next((s for s in walk["sections"] if s.get("name") == sec_name), None)
            if section is None:
                raise CensusError(f"asset {ordinal} {typ}: missing serialized section")
            idx = _indices(data, section)
            width = int(section["indexWidthBytes"])
            if width != expected_width:
                raise CensusError(
                    f"asset {ordinal} {typ}: index width {width} != expected {expected_width}"
                )
            strictly = all(b > a for a, b in zip(idx, idx[1:]))
            in_range = all(0 <= v <= numframes for v in idx)
            row = {
                "assetOrdinal": ordinal,
                "name": walk.get("name"),
                "type": typ,
                "numframes": numframes,
                "indexWidthBytes": width,
                "keyCount": len(idx),
                "firstIndex": idx[0],
                "lastIndex": idx[-1],
                "firstIsZero": idx[0] == 0,
                "lastIsNumframes": idx[-1] == numframes,
                "strictlyIncreasing": strictly,
                "allIndicesInRange": in_range,
                "indicesSha256": hashlib.sha256(
                    struct.pack("<" + ("B" if width == 1 else "H") * len(idx), *idx)
                ).hexdigest(),
            }
            dynamic.append(row)
        pos = next_pos

    if expected_end is not None and pos != int(expected_end):
        raise CensusError(f"serialized chain ended at {pos}, expected {expected_end}")

    bad = [
        row for row in dynamic
        if not (
            row["firstIsZero"]
            and row["lastIsNumframes"]
            and row["strictlyIncreasing"]
            and row["allIndicesInRange"]
        )
    ]
    by_type = Counter(row["type"] for row in dynamic)
    by_width = Counter(str(row["indexWidthBytes"]) for row in dynamic)
    return {
        "format": "t6-xanim-delta-endpoint-census-v1",
        "source": {
            "expandedBytes": len(data),
            "expandedSha256": hashlib.sha256(data).hexdigest(),
            "sourceStart": int(start),
            "sourceEnd": pos,
            "assetCount": int(count),
        },
        "summary": {
            "dynamicTrackCount": len(dynamic),
            "dynamicByType": dict(sorted(by_type.items())),
            "dynamicByIndexWidthBytes": dict(sorted(by_width.items())),
            "constantByType": dict(sorted(constant.items())),
            "firstIndexZeroCount": sum(row["firstIsZero"] for row in dynamic),
            "lastIndexNumframesCount": sum(row["lastIsNumframes"] for row in dynamic),
            "strictlyIncreasingCount": sum(row["strictlyIncreasing"] for row in dynamic),
            "allIndicesInRangeCount": sum(row["allIndicesInRange"] for row in dynamic),
            "badDynamicTrackCount": len(bad),
            "walkerBlockerCount": blocker_count,
            "allNativeDomainsExact": len(bad) == 0 and blocker_count == 0,
        },
        "dynamicTracks": dynamic,
        "badDynamicTracks": bad,
        "assetSerializedSpans": asset_hashes,
        "policy": (
            "Observed native endpoints are evidence. This tool never fabricates, clamps, "
            "extends, or repairs delta key domains."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--start", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--expected-end", type=lambda x: int(x, 0))
    ap.add_argument("--expected-sha256")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if args.expected_sha256 and sha.lower() != args.expected_sha256.lower():
        raise CensusError(f"expanded SHA-256 {sha} != expected {args.expected_sha256}")
    doc = census(data, start=args.start, count=args.count, expected_end=args.expected_end)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(json.dumps({"source": doc["source"], "summary": doc["summary"]}, indent=2, sort_keys=True))
    return 0 if doc["summary"]["allNativeDomainsExact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
