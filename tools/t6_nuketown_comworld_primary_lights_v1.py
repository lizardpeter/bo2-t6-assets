#!/usr/bin/env python3
"""Exact retail ComWorld / ComPrimaryLight extractor for T6 Nuketown 2025.

Consumes only the expanded retail mp_nuketown_2020 FastFile. It proves XAsset
562 (COMWORLD), locates the unique inline ComWorld by exact retail name/header
topology, decodes the native PC32 ComPrimaryLight array, resolves inline/packed
defName aliases, and closes the source cursor through XAssets 563/564
(LIGHT_DEF) onto XAsset 565 (TECHNIQUE_SET).

No old GLB, Blender state, visual fitting, or guessed light placement is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
BLOCK_SHIFT = 29
OFFSET_MASK = (1 << BLOCK_SHIFT) - 1
EXPECTED_SHA256 = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
EXPECTED_ASSET_COUNT = 840
EXPECTED_COMWORLD_XASSET = 562
EXPECTED_COMWORLD_TYPE = 13
EXPECTED_LIGHTDEF_XASSETS = (563, 564)
EXPECTED_LIGHTDEF_TYPE = 18
EXPECTED_NEXT_XASSET = 565
EXPECTED_NEXT_TYPE = 7
EXPECTED_WORLD_NAME = "maps/mp/mp_nuketown_2020.d3dbsp"
COMWORLD_SIZE = 16
COM_PRIMARY_LIGHT_SIZE = 196
GFX_LIGHT_DEF_SIZE = 16
GFX_IMAGE_SIZE = 80
GFX_IMAGE_LOAD_DEF_SIZE = 12


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0]


def vec(data: bytes, off: int, n: int) -> list[float]:
    out = list(struct.unpack_from("<" + "f" * n, data, off))
    if not all(math.isfinite(v) for v in out):
        raise ValueError(f"non-finite vector at source {off}")
    return out


def cstring(data: bytes, off: int) -> tuple[str, int]:
    end = data.find(b"\0", off)
    if end < 0:
        raise ValueError(f"unterminated string at source {off}")
    return data[off:end].decode("ascii"), end + 1


def decode_packed(value: int) -> tuple[int, int]:
    if value in (0, FOLLOW, INSERT):
        raise ValueError(f"not a packed pointer: 0x{value:08X}")
    encoded = (value - 1) & 0xFFFFFFFF
    return encoded >> BLOCK_SHIFT, encoded & OFFSET_MASK


def parse_xasset_list(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError("expanded stream too short")
    string_count, string_ptr, dep_count, dep_ptr, asset_count, asset_ptr = struct.unpack_from("<6I", data, 40)
    if string_ptr != FOLLOW or dep_count != 0 or dep_ptr != 0 or asset_ptr != FOLLOW:
        raise ValueError("unexpected XAssetList pointer topology")
    if asset_count != EXPECTED_ASSET_COUNT:
        raise ValueError(f"unexpected asset count {asset_count}")
    ptrs = struct.unpack_from(f"<{string_count}I", data, 64)
    source = 64 + string_count * 4
    for p in ptrs:
        if p == FOLLOW:
            _, source = cstring(data, source)
    asset_array_source = source
    assets = [struct.unpack_from("<II", data, asset_array_source + 8 * i) for i in range(asset_count)]
    if assets[EXPECTED_COMWORLD_XASSET] != (EXPECTED_COMWORLD_TYPE, FOLLOW):
        raise ValueError(f"XAsset {EXPECTED_COMWORLD_XASSET} is not inline COMWORLD")
    for i in EXPECTED_LIGHTDEF_XASSETS:
        if assets[i] != (EXPECTED_LIGHTDEF_TYPE, FOLLOW):
            raise ValueError(f"XAsset {i} is not inline LIGHT_DEF")
    if assets[EXPECTED_NEXT_XASSET] != (EXPECTED_NEXT_TYPE, FOLLOW):
        raise ValueError(f"XAsset {EXPECTED_NEXT_XASSET} is not inline TECHNIQUE_SET")
    return {"scriptStringCount": string_count, "assetCount": asset_count, "assetArraySource": asset_array_source, "assets": assets}


def find_comworld(data: bytes) -> int:
    needle = EXPECTED_WORLD_NAME.encode("ascii") + b"\0"
    candidates = []
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0:
            break
        fixed = pos - COMWORLD_SIZE
        if fixed >= 0 and u32(data, fixed) == FOLLOW and u32(data, fixed + 4) == 1 and u32(data, fixed + 8) == 18 and u32(data, fixed + 12) == FOLLOW:
            candidates.append(fixed)
        pos += 1
    if len(candidates) != 1:
        raise ValueError(f"expected one exact ComWorld candidate, got {candidates}")
    return candidates[0]


def parse_primary_light(data: bytes, base: int, index: int) -> dict:
    row = {
        "index": index,
        "type": data[base],
        "canUseShadowMap": data[base + 1],
        "exponent": data[base + 2],
        "priority": data[base + 3],
        "cullDist": i16(data, base + 4),
        "useCookie": data[base + 6],
        "shadowmapVolume": data[base + 7],
        "color": vec(data, base + 8, 3),
        "dir": vec(data, base + 20, 3),
        "origin": vec(data, base + 32, 3),
        "radius": f32(data, base + 44),
        "cosHalfFovOuter": f32(data, base + 48),
        "cosHalfFovInner": f32(data, base + 52),
        "cosHalfFovExpanded": f32(data, base + 56),
        "rotationLimit": f32(data, base + 60),
        "translationLimit": f32(data, base + 64),
        "mipDistance": f32(data, base + 68),
        "dAttenuation": f32(data, base + 72),
        "roundness": f32(data, base + 76),
        "diffuseColor": vec(data, base + 80, 4),
        "falloff": vec(data, base + 96, 4),
        "angle": vec(data, base + 112, 4),
        "aAbB": vec(data, base + 128, 4),
        "cookieControl0": vec(data, base + 144, 4),
        "cookieControl1": vec(data, base + 160, 4),
        "cookieControl2": vec(data, base + 176, 4),
        "defNameRawPointer": f"0x{u32(data, base + 192):08X}",
    }
    for k in ("radius", "cosHalfFovOuter", "cosHalfFovInner", "cosHalfFovExpanded", "rotationLimit", "translationLimit", "mipDistance", "dAttenuation", "roundness"):
        if not math.isfinite(row[k]):
            raise ValueError(f"primaryLight[{index}].{k} is non-finite")
    return row


def replay_lightdef(data: bytes, source: int, expected_def_offset: int, expected_image_name: str) -> tuple[int, dict]:
    fixed = source
    if fixed + GFX_LIGHT_DEF_SIZE > len(data):
        raise ValueError("truncated GfxLightDef")
    name_ptr = u32(data, fixed)
    image_ptr = u32(data, fixed + 4)
    sampler_state = data[fixed + 8]
    lmap_lookup_start = struct.unpack_from("<i", data, fixed + 12)[0]
    if decode_packed(name_ptr) != (5, expected_def_offset):
        raise ValueError(f"LIGHT_DEF name alias drift at {fixed}")
    if image_ptr != INSERT:
        raise ValueError(f"LIGHT_DEF attenuation image is not INSERT at {fixed}")
    source += GFX_LIGHT_DEF_SIZE
    image_fixed = source
    if image_fixed + GFX_IMAGE_SIZE > len(data):
        raise ValueError("truncated GfxImage")
    load_def_ptr = u32(data, image_fixed)
    image_name_ptr = u32(data, image_fixed + 72)
    if load_def_ptr != INSERT or image_name_ptr != FOLLOW:
        raise ValueError(f"unexpected LIGHT_DEF GfxImage topology at {image_fixed}")
    source += GFX_IMAGE_SIZE
    image_name, source = cstring(data, source)
    if image_name != expected_image_name:
        raise ValueError(f"LIGHT_DEF image name drift: {image_name!r}")
    load_def_source = source
    resource_size = u32(data, load_def_source + 8)
    source += GFX_IMAGE_LOAD_DEF_SIZE + resource_size
    if source > len(data):
        raise ValueError("truncated GfxImageLoadDef data")
    return source, {
        "fixedSource": fixed,
        "namePackedBlock": 5,
        "namePackedOffset": expected_def_offset,
        "attenuationImagePointer": "insert",
        "samplerState": sampler_state,
        "lmapLookupStart": lmap_lookup_start,
        "imageFixedSource": image_fixed,
        "imageName": image_name,
        "imageLoadDefSource": load_def_source,
        "imageResourceSize": resource_size,
        "serializedEnd": source,
    }


def build(expanded: Path) -> dict:
    data = expanded.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"wrong retail expanded SHA-256: {digest}")
    front = parse_xasset_list(data)
    fixed = find_comworld(data)
    name, source = cstring(data, fixed + COMWORLD_SIZE)
    if name != EXPECTED_WORLD_NAME:
        raise ValueError("ComWorld name drift")
    light_count = u32(data, fixed + 8)
    if light_count != 18:
        raise ValueError("Nuketown primary-light count drift")
    lights_source = source
    lights_end = lights_source + light_count * COM_PRIMARY_LIGHT_SIZE
    lights = [parse_primary_light(data, lights_source + i * COM_PRIMARY_LIGHT_SIZE, i) for i in range(light_count)]
    source = lights_end
    inline = []
    packed = []
    for row in lights:
        raw = int(row["defNameRawPointer"], 16)
        if raw == FOLLOW:
            text, end = cstring(data, source)
            inline.append({"index": row["index"], "name": text, "sourceStart": source, "sourceEnd": end})
            row["defName"] = text
            source = end
        elif raw == 0:
            row["defName"] = None
        elif raw == INSERT:
            raise ValueError(f"unexpected INSERT ComPrimaryLight.defName at {row['index']}")
        else:
            block, offset = decode_packed(raw)
            if block != 5:
                raise ValueError(f"non-VIRTUAL ComPrimaryLight.defName alias at {row['index']}")
            packed.append({"index": row["index"], "block": block, "offset": offset})
            row["defNamePackedOffset"] = offset
    if [(r["index"], r["name"]) for r in inline] != [(2, "lava_lamp_gobo"), (4, "white_light")]:
        raise ValueError(f"inline primary-light definition names drift: {inline}")
    lava_offset = next(r["offset"] for r in packed if r["index"] == 3)
    white_offset = next(r["offset"] for r in packed if r["index"] == 5)
    if white_offset != lava_offset + len("lava_lamp_gobo") + 1:
        raise ValueError("packed defName VIRTUAL address spacing drift")
    address_to_name = {lava_offset: "lava_lamp_gobo", white_offset: "white_light"}
    for row in lights:
        if "defNamePackedOffset" in row:
            off = row["defNamePackedOffset"]
            if off not in address_to_name:
                raise ValueError(f"unresolved packed primary-light defName offset {off}")
            row["defName"] = address_to_name[off]
    comworld_end = source
    if comworld_end != 48636471:
        raise ValueError(f"ComWorld end drift: {comworld_end}")
    source, lightdef563 = replay_lightdef(data, source, lava_offset, "nt_2020_lava_lamp_gobo")
    if source != 48636602:
        raise ValueError(f"XAsset 563 end drift: {source}")
    source, lightdef564 = replay_lightdef(data, source, white_offset, "whitesquare")
    if source != 48636722:
        raise ValueError(f"XAsset 564 end drift: {source}")
    if u32(data, source) != FOLLOW:
        raise ValueError("XAsset 565 TechniqueSet does not begin at closed boundary")
    type_counts = Counter(r["type"] for r in lights)
    shadow_counts = Counter(r["canUseShadowMap"] for r in lights)
    def_counts = Counter(r["defName"] for r in lights if r["defName"] is not None)
    return {
        "format": "t6-nuketown-comworld-primary-lights-v1",
        "map": "mp_nuketown_2020",
        "source": {"file": expanded.name, "bytes": len(data), "sha256": digest},
        "xassetIdentity": {"assetCount": front["assetCount"], "assetArraySource": front["assetArraySource"], "comWorldXassetIndex": EXPECTED_COMWORLD_XASSET, "lightDefXassetIndices": list(EXPECTED_LIGHTDEF_XASSETS), "nextXassetIndex": EXPECTED_NEXT_XASSET},
        "comWorld": {"fixedSource": fixed, "fixedBytes": COMWORLD_SIZE, "name": name, "isInUse": u32(data, fixed + 4), "primaryLightCount": light_count, "primaryLightsSource": lights_source, "primaryLightRecordBytes": COM_PRIMARY_LIGHT_SIZE, "primaryLightsFixedEnd": lights_end, "serializedEnd": comworld_end, "serializedBytes": comworld_end - fixed, "serializedSha256": hashlib.sha256(data[fixed:comworld_end]).hexdigest(), "defNameVirtualAliases": {"lava_lamp_gobo": lava_offset, "white_light": white_offset}},
        "summary": {"primaryLightCount": light_count, "typeCounts": {str(k): v for k, v in sorted(type_counts.items())}, "canUseShadowMapCounts": {str(k): v for k, v in sorted(shadow_counts.items())}, "cookieEnabledCount": sum(1 for r in lights if r["useCookie"] != 0), "shadowmapVolumeNonzeroCount": sum(1 for r in lights if r["shadowmapVolume"] != 0), "definitionNameCounts": dict(sorted(def_counts.items()))},
        "primaryLights": lights,
        "downstreamBoundaryProof": {"lightDef563": lightdef563, "lightDef564": lightdef564, "techniqueSet565FixedStart": source, "exactBoundaryClosed": True},
        "contracts": {"oatPinnedCommit": "2ca512abe7cb82d70a94d5ad7846043c3978862d", "ComWorld": "TEMP fixed; name string; primaryLights[count]", "ComPrimaryLight": "196-byte PC32 fixed record; defName string/packed alias", "GfxLightDef": "TEMP fixed; name string/packed alias; attenuation GfxImage asset reference", "proofBoundary": "Exact retail bytes and pointer topology only. Raw light type values are preserved without inventing renderer semantics."},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = build(args.expanded)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
