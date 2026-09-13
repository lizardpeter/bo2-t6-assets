#!/usr/bin/env python3
"""Extract the embedded retail Nuketown initial GfxWorld fog record.

The fixed GfxWorld begins at the already-proved mp_nuketown_2020 world offset.
On the 32-bit T6 asset ABI its prefix is:
  name ptr32, baseName ptr32, 3 x int32,
  GfxWorldStreamInfo { int32, ptr32, int32, ptr32 },
  skyBoxModel ptr32,
  SunLightParseParams sunParse.
This puts sunParse at byte 40.  SunLightParseParams contains name[64], the
84-byte GfxWorldSun, fogTransitionTime float, then the 64-byte GfxWorldFog, so
initWorldFog begins at GfxWorld + 192.

Only the exact 16 serialized float32 values are reported.  No runtime shader
constant formula is inferred here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

FORMAT = "t6-nuketown-init-world-fog-v1"
MAP = "mp_nuketown_2020"
EXPANDED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
GFXWORLD_START = 63_150_420
SUN_PARSE_OFFSET = 40
SUN_PARSE_INIT_FOG_OFFSET = 152
FOG_OFFSET = GFXWORLD_START + SUN_PARSE_OFFSET + SUN_PARSE_INIT_FOG_OFFSET
FOG_BYTES = 64
FIELD_NAMES = (
    "baseDist", "halfDist", "baseHeight", "halfHeight",
    "sunFogPitch", "sunFogYaw", "sunFogInner", "sunFogOuter",
    "fogColorR", "fogColorG", "fogColorB", "fogOpacity",
    "sunFogColorR", "sunFogColorG", "sunFogColorB", "sunFogOpacity",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    raw = a.expanded.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != EXPANDED_SHA256:
        raise SystemExit(f"expanded SHA {got} != pinned {EXPANDED_SHA256}")
    end = FOG_OFFSET + FOG_BYTES
    if end > len(raw):
        raise SystemExit("initial fog range exceeds expanded FastFile")
    payload = raw[FOG_OFFSET:end]
    values = struct.unpack("<16f", payload)
    if not all(math.isfinite(v) for v in values):
        raise SystemExit("initial fog contains non-finite float")
    fields = dict(zip(FIELD_NAMES, values))
    # Structural sanity only. These are not replacement/default values.
    if fields["halfDist"] <= 0.0 or fields["halfHeight"] <= 0.0:
        raise SystemExit(f"implausible authored fog half distance/height: {fields}")
    doc = {
        "format": FORMAT,
        "map": MAP,
        "source": {"sha256": EXPANDED_SHA256, "bytes": len(raw)},
        "layout": {
            "gfxWorldStart": GFXWORLD_START,
            "sunParseOffset": SUN_PARSE_OFFSET,
            "initWorldFogOffsetWithinSunParse": SUN_PARSE_INIT_FOG_OFFSET,
            "initWorldFogAbsoluteOffset": FOG_OFFSET,
            "byteCount": FOG_BYTES,
            "payloadSha256": hashlib.sha256(payload).hexdigest(),
        },
        "fields": fields,
        "vectors": {
            "fogColor": [fields["fogColorR"], fields["fogColorG"], fields["fogColorB"]],
            "sunFogColor": [fields["sunFogColorR"], fields["sunFogColorG"], fields["sunFogColorB"]],
        },
        "proofBoundary": (
            "Direct float32 decode of the embedded GfxWorld.sunParse.initWorldFog record from the SHA-pinned expanded retail Nuketown FastFile. "
            "The byte offset follows the published 32-bit T6 GfxWorld/GfxWorldStreamInfo/GfxWorldSun/SunLightParseParams/GfxWorldFog field order. "
            "This proves authored fog inputs only; it does not infer the engine's derived cb0 fog constants."
        ),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["fields"], indent=2, sort_keys=True))
    print("payloadSha256", doc["layout"]["payloadSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
