#!/usr/bin/env python3
"""Targeted direct-retail T6 PC32 XModel identity probe.

This is deliberately a *probe*, not a guessed all-XModel scanner. Given an
expanded T6 XFile and exact target identities, it finds inline-named 248-byte
XModel records and validates their fixed PC32 structure and every top-level
zone pointer against the declared XFile block sizes.

Why targeted first:
- common/non-map zones contain many asset classes, so scanning the body by
  filename-like strings alone is unsafe;
- the project already knows several exact player/viewhand/weapon identities
  from independent discovery sources;
- a hit is promoted only when the bytes immediately preceding the exact name
  form a structurally valid retail XModel record.

Packed/reused XModel names are not guessed. They are reported unresolved and
remain a separate generic catalog problem.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import struct
from pathlib import Path
from typing import Any

FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
XMODEL_PC32 = 248
LOD_COUNT = 4
LOD_BYTES = 28

POINTER_FIELDS = {
    "boneNames": 8,
    "parentList": 12,
    "quats": 16,
    "trans": 20,
    "partClassification": 24,
    "baseMat": 28,
    "surfs": 32,
    "materialHandles": 36,
    "collSurfs": 152,
    "boneInfo": 164,
    "himipInvSqRadii": 200,
    "physPreset": 216,
    "collmaps": 224,
    "physConstraints": 228,
}


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("t6raw", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_slice(data: bytes, start: int, end: int) -> str:
    return hashlib.sha256(memoryview(data)[start:end]).hexdigest()


def exact_cstring(data: bytes, pos: int, expected: str) -> int | None:
    raw = expected.encode("ascii") + b"\0"
    if data[pos:pos + len(raw)] != raw:
        return None
    return pos + len(raw)


def read_u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def read_i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def read_f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0]


def _decode_packed(rawmod, value: int, block_sizes: list[int]) -> dict[str, Any]:
    """Support both retained raw-parser APIs without changing pointer semantics."""
    if hasattr(rawmod, "decode_zone_pointer"):
        return dict(rawmod.decode_zone_pointer(value, block_sizes))
    if hasattr(rawmod, "zone_pointer"):
        return dict(rawmod.zone_pointer(value, block_sizes))
    raise RuntimeError("raw parser must expose decode_zone_pointer(value, blocks) or zone_pointer(value, blocks)")


def decode_pointer(rawmod, value: int, block_sizes: list[int]) -> dict[str, Any]:
    if value == 0:
        return {"kind": "null", "raw": "0x00000000", "valid": True}
    if value == FOLLOWING:
        return {"kind": "following", "raw": "0xFFFFFFFF", "valid": True}
    if value == INSERT:
        return {"kind": "insert", "raw": "0xFFFFFFFE", "valid": True}
    dec = _decode_packed(rawmod, value, block_sizes)
    valid = bool(dec.get("valid_for_declared_block_size", dec.get("valid", False)))
    dec.update({"raw": f"0x{value:08X}", "valid": valid})
    return dec


def validate_candidate(data: bytes, start: int, name: str, rawmod, block_sizes: list[int]) -> dict[str, Any] | None:
    if start < 0 or start + XMODEL_PC32 > len(data):
        return None
    name_ptr = read_u32(data, start)
    if name_ptr not in (FOLLOWING, INSERT):
        return None
    name_end = exact_cstring(data, start + XMODEL_PC32, name)
    if name_end is None:
        return None

    num_bones = data[start + 4]
    num_roots = data[start + 5]
    num_surfs = data[start + 6]
    lod_ramp = data[start + 7]
    num_lods = read_u16(data, start + 196)
    coll_lod = read_i16(data, start + 198)
    radius = read_f32(data, start + 168)
    if num_roots > num_bones:
        return None
    if lod_ramp not in (0, 1):
        return None
    if num_lods > 4:
        return None
    if not math.isfinite(radius) or radius < 0.0 or radius > 1.0e7:
        return None

    pointers = {}
    for field, off in POINTER_FIELDS.items():
        value = read_u32(data, start + off)
        dec = decode_pointer(rawmod, value, block_sizes)
        if not dec.get("valid"):
            return None
        pointers[field] = dec

    lods = []
    for i in range(LOD_COUNT):
        off = start + 40 + i * LOD_BYTES
        dist = read_f32(data, off)
        if not math.isfinite(dist):
            return None
        lods.append({
            "index": i,
            "dist": dist,
            "numSurfs": read_u16(data, off + 4),
            "surfIndex": read_u16(data, off + 6),
            "partBits": [read_u32(data, off + 8 + j * 4) for j in range(5)],
        })
    for lod in lods[:num_lods]:
        if lod["surfIndex"] + lod["numSurfs"] > num_surfs:
            return None

    mins = list(struct.unpack_from("<3f", data, start + 172))
    maxs = list(struct.unpack_from("<3f", data, start + 184))
    if not all(math.isfinite(v) for v in mins + maxs):
        return None

    return {
        "status": "exact_inline_xmodel",
        "name": name,
        "rawStructOffset": start,
        "rawNameOffset": start + XMODEL_PC32,
        "fixedRecordBytes": XMODEL_PC32,
        "fixedRecordSha256": sha256_slice(data, start, start + XMODEL_PC32),
        "fixedPlusNameSha256": sha256_slice(data, start, name_end),
        "numBones": num_bones,
        "numRootBones": num_roots,
        "numSurfs": num_surfs,
        "lodRampType": lod_ramp,
        "numLods": num_lods,
        "collLod": coll_lod,
        "radius": radius,
        "mins": mins,
        "maxs": maxs,
        "lods": lods[:num_lods],
        "pointers": pointers,
    }


def load_targets(path: Path) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict) and isinstance(doc.get("models"), list):
        rows = doc["models"]
    else:
        raise ValueError("targets must be a list or an object containing models[]")
    out = []
    seen = set()
    for row in rows:
        if isinstance(row, str):
            row = {"name": row}
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            raise ValueError("each target must contain string name")
        name = row["name"]
        name.encode("ascii")
        if name in seen:
            raise ValueError(f"duplicate target {name}")
        seen.add(name)
        out.append(dict(row))
    return out


def probe_name(data: bytes, target: dict[str, Any], rawmod, block_sizes: list[int]) -> dict[str, Any]:
    name = target["name"]
    needle = name.encode("ascii") + b"\0"
    candidates = []
    search = 0
    raw_occurrences = 0
    while True:
        at = data.find(needle, search)
        if at < 0:
            break
        raw_occurrences += 1
        candidate = validate_candidate(data, at - XMODEL_PC32, name, rawmod, block_sizes)
        if candidate is not None:
            candidates.append(candidate)
        search = at + 1
    if len(candidates) == 1:
        result = dict(candidates[0])
    elif not candidates:
        result = {
            "status": "not_inline_locatable",
            "name": name,
            "rawStringOccurrences": raw_occurrences,
            "reason": "exact identity not preceded by a valid inline-name PC32 XModel record",
        }
    else:
        result = {
            "status": "ambiguous_inline_xmodel",
            "name": name,
            "rawStringOccurrences": raw_occurrences,
            "candidateCount": len(candidates),
            "candidates": candidates,
        }
    for key in ("role", "required", "expectedClass", "notes"):
        if key in target:
            result[key] = target[key]
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True, help="expanded retail T6 XFile")
    ap.add_argument("--raw-parser", type=Path, required=True, help="parser exposing parse_front and zone_pointer/decode_zone_pointer")
    ap.add_argument("--targets", type=Path, required=True, help="JSON list or benchmark spec containing models[]")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = args.stream.read_bytes()
    rawmod = load_module(args.raw_parser)
    front = rawmod.parse_front(data)
    block_sizes = [int(x["bytes"]) for x in front["block_sizes"]]
    targets = load_targets(args.targets)
    results = [probe_name(data, t, rawmod, block_sizes) for t in targets]
    required = [r for r in results if r.get("required", True)]
    exact_required = [r for r in required if r["status"] == "exact_inline_xmodel"]

    out = {
        "format": "t6-xmodel-target-probe-v1",
        "authority": "direct expanded retail T6 XFile bytes",
        "source": {
            "path": str(args.stream),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "declaredBlockSizes": front["block_sizes"],
        },
        "rules": {
            "exactIdentityMatch": True,
            "fixedRecordBytes": XMODEL_PC32,
            "allTopLevelPointersValidatedAgainstDeclaredBlocks": True,
            "packedOrReusedNamesAreNotGuessed": True,
            "rawStringOccurrenceAloneIsNotProof": True,
        },
        "summary": {
            "targets": len(results),
            "requiredTargets": len(required),
            "exactRequired": len(exact_required),
            "allRequiredExactInline": len(exact_required) == len(required),
            "unresolvedRequired": [r["name"] for r in required if r["status"] != "exact_inline_xmodel"],
        },
        "targets": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0 if out["summary"]["allRequiredExactInline"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
