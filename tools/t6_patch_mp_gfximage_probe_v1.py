#!/usr/bin/env python3
"""Targeted retail T6 GfxImage identity probe for patch_mp expanded streams.

This is deliberately *not* a filename/OAT-output matcher. It joins the current
Nuketown unresolved-primary list to the canonical live GfxImage identity bank,
then searches the expanded retail XFile for 80-byte PC32 GfxImage records that
match the canonical identity fields.

A candidate is accepted only when all available authoritative fields agree:
- GfxImage.hash == canonical live imageHash (and R_HashString(name))
- width/height/depth/streaming/streamedPartCount match
- streamedParts[0] full hash and dimensions match when present
- the fixed record is structurally plausible for T6 PC32
- when the name pointer is FOLLOWING, the serialized inline name must match

The XAssetList front matter is independently parsed and reports the number of
IMAGE XAssets in the patch. This tool does not claim that every top-level IMAGE
body has been generically walked; it is a fail-closed target-identity probe.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import zlib
from collections import Counter, defaultdict
from pathlib import Path

FOLLOWING = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
BLOCK_SHIFT = 29
OFFSET_MASK = (1 << 29) - 1
IMAGE_ASSET_TYPE = 8
GFXIMAGE_SIZE = 80

ASSET_TYPES = [
    "XMODELPIECES", "PHYSPRESET", "PHYSCONSTRAINTS", "DESTRUCTIBLEDEF",
    "XANIMPARTS", "XMODEL", "MATERIAL", "TECHNIQUE_SET", "IMAGE", "SOUND",
    "SOUND_PATCH", "CLIPMAP", "CLIPMAP_PVS", "COMWORLD", "GAMEWORLD_SP",
    "GAMEWORLD_MP", "MAP_ENTS", "GFXWORLD", "LIGHT_DEF", "UI_MAP", "FONT",
    "FONTICON", "MENULIST", "MENU", "LOCALIZE_ENTRY", "WEAPON", "WEAPONDEF",
    "WEAPON_VARIANT", "WEAPON_FULL", "ATTACHMENT", "ATTACHMENT_UNIQUE",
    "WEAPON_CAMO", "SNDDRIVER_GLOBALS", "FX", "IMPACT_FX", "AITYPE", "MPTYPE",
    "MPBODY", "MPHEAD", "CHARACTER", "XMODELALIAS", "RAWFILE", "STRINGTABLE",
    "LEADERBOARD", "XGLOBALS", "DDL", "GLASSES", "EMBLEMSET", "SCRIPTPARSETREE",
    "KEYVALUEPAIRS", "VEHICLEDEF", "MEMORYBLOCK", "ADDON_MAP_ENTS", "TRACER",
    "SKINNEDVERTS", "QDB", "SLUG", "FOOTSTEP_TABLE", "FOOTSTEPFX_TABLE", "ZBARRIER",
]


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def rhash(name: str) -> int:
    h = 0
    for c in name.encode("latin1"):
        h = ((33 * h) ^ (c | 0x20)) & 0xFFFFFFFF
    return h


def cstring(data: bytes, pos: int, limit: int = 1024) -> tuple[str, int] | None:
    if pos < 0 or pos >= len(data):
        return None
    end = data.find(b"\0", pos, min(len(data), pos + limit + 1))
    if end <= pos:
        return None
    raw = data[pos:end]
    if any(c < 0x20 or c > 0x7E for c in raw):
        return None
    return raw.decode("ascii"), end + 1


def ptr_kind(value: int, block_sizes: list[int]) -> dict:
    if value == 0:
        return {"kind": "null", "raw": "0x00000000", "valid": True}
    if value == FOLLOWING:
        return {"kind": "following", "raw": "0xFFFFFFFF", "valid": True}
    if value == INSERT:
        return {"kind": "insert", "raw": "0xFFFFFFFE", "valid": True}
    encoded = (value - 1) & 0xFFFFFFFF
    block = encoded >> BLOCK_SHIFT
    offset = encoded & OFFSET_MASK
    valid = block < len(block_sizes) and offset < block_sizes[block]
    return {
        "kind": "packed", "raw": f"0x{value:08X}", "block": block,
        "offset": offset, "valid": valid,
    }


def parse_front(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError("expanded stream too short")
    declared_size, external_size = struct.unpack_from("<II", data, 0)
    blocks = list(struct.unpack_from("<8I", data, 8))
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, 40)
    pos = 64
    if sc:
        if sp != FOLLOWING:
            raise ValueError("ScriptStringList pointer is not FOLLOWING")
        ptrs = struct.unpack_from(f"<{sc}I", data, pos)
        pos += sc * 4
        for p in ptrs:
            if p == FOLLOWING:
                got = cstring(data, pos, 8192)
                if got is None:
                    raise ValueError(f"bad inline script string at {pos}")
                _, pos = got
    if dc:
        if dp != FOLLOWING:
            raise ValueError("dependency pointer is not FOLLOWING")
        ptrs = struct.unpack_from(f"<{dc}I", data, pos)
        pos += dc * 4
        for p in ptrs:
            if p == FOLLOWING:
                got = cstring(data, pos, 8192)
                if got is None:
                    raise ValueError(f"bad dependency string at {pos}")
                _, pos = got
    if ap != FOLLOWING:
        raise ValueError("XAsset array pointer is not FOLLOWING")
    asset_array = pos
    counts = Counter()
    assets = []
    for i in range(ac):
        if pos + 8 > len(data):
            raise ValueError("truncated XAsset array")
        typ, ptr = struct.unpack_from("<II", data, pos)
        pos += 8
        if not 0 <= typ < len(ASSET_TYPES):
            raise ValueError(f"bad XAsset type {typ} at {i}")
        counts[ASSET_TYPES[typ]] += 1
        assets.append({"index": i, "type": typ, "typeName": ASSET_TYPES[typ], "pointer": ptr})
    return {
        "declaredZoneSize": declared_size,
        "declaredExternalSize": external_size,
        "blockSizes": blocks,
        "scriptStringCount": sc,
        "dependencyCount": dc,
        "assetCount": ac,
        "assetArrayRawOffset": asset_array,
        "assetBodyStreamRawOffset": pos,
        "assetTypeCounts": dict(sorted(counts.items())),
        "imageXassets": [a for a in assets if a["type"] == IMAGE_ASSET_TYPE],
    }


def load_canonical(path: Path) -> dict:
    raw = path.read_bytes()
    if path.name.endswith(".zlib.b64"):
        raw = zlib.decompress(base64.b64decode(raw.strip()))
    return json.loads(raw)


def unresolved_names(coverage: dict) -> list[str]:
    if "unresolvedPrimaryImages" in coverage:
        return sorted({str(r["image"]) for r in coverage["unresolvedPrimaryImages"]})
    out = set()
    for row in coverage.get("materials", []):
        for key in ("firstColor", "firstNormal"):
            rec = row.get(key)
            if rec and not rec.get("validated") and rec.get("image"):
                out.add(str(rec["image"]))
    return sorted(out)


def canonical_targets(canonical: dict, names: list[str]) -> dict[str, dict]:
    by_image = {r["image"]: dict(r) for r in canonical.get("images", [])}
    usage = defaultdict(set)
    for m in canonical.get("materials", []):
        for t in m.get("textures", []):
            if t.get("image") in names:
                usage[t["image"]].add(int(t.get("semantic", -1)))
    out = {}
    for name in names:
        if name not in by_image:
            raise ValueError(f"unresolved target absent from canonical image bank: {name}")
        r = by_image[name]
        expected_hash = int(r["imageHash"])
        calc = rhash(name)
        if r.get("identityClass") != "retail-name-hash-validated":
            raise ValueError(f"target is not ordinary validated retail identity: {name}")
        if expected_hash != calc:
            raise ValueError(f"canonical hash mismatch for {name}: {expected_hash:08x} != {calc:08x}")
        out[name] = {
            "image": name,
            "imageHash": expected_hash,
            "width": int(r["width"]), "height": int(r["height"]), "depth": int(r["depth"]),
            "streaming": int(r["streaming"]),
            "streamedPartCountRaw": int(r["streamedPartCountRaw"]),
            "streamedPart0": r.get("streamedPart0"),
            "materialUsageSemantics": sorted(usage.get(name, set())),
        }
    return out


def parse_fixed(data: bytes, fixed: int, blocks: list[int]) -> dict | None:
    if fixed < 0 or fixed + GFXIMAGE_SIZE > len(data):
        return None
    load_def = u32(data, fixed + 0)
    map_type = data[fixed + 4]
    semantic = data[fixed + 5]
    category = data[fixed + 6]
    delay = data[fixed + 7]
    no_picmip = data[fixed + 10]
    width = u16(data, fixed + 20)
    height = u16(data, fixed + 22)
    depth = u16(data, fixed + 24)
    level_count = data[fixed + 26]
    streaming = data[fixed + 27]
    base_size = u32(data, fixed + 28)
    pixels = u32(data, fixed + 32)
    part_level_size = u32(data, fixed + 36)
    part_hash = u32(data, fixed + 40)
    part_width = u16(data, fixed + 44)
    part_height = u16(data, fixed + 46)
    part_offset = u32(data, fixed + 48)
    part_size_ipak = u32(data, fixed + 52)
    part_adjacent = u32(data, fixed + 56)
    part_count = data[fixed + 60]
    loaded_size = u32(data, fixed + 64)
    skipped_mips = data[fixed + 68]
    name_ptr = u32(data, fixed + 72)
    image_hash = u32(data, fixed + 76)
    load_kind = ptr_kind(load_def, blocks)
    pixels_kind = ptr_kind(pixels, blocks)
    name_kind = ptr_kind(name_ptr, blocks)
    plausible = (
        load_kind["valid"] and pixels_kind["valid"] and name_kind["valid"]
        and 0 <= map_type <= 5 and 0 <= semantic <= 0x1C and 0 <= category <= 6
        and delay in (0, 1) and no_picmip in (0, 1)
        and width > 0 and height > 0 and depth > 0
        and level_count <= 32 and streaming in (0, 1) and part_count <= 4
    )
    inline_name = None
    if name_ptr == FOLLOWING:
        got = cstring(data, fixed + GFXIMAGE_SIZE, 1024)
        inline_name = got[0] if got else None
        plausible = plausible and inline_name is not None
    return {
        "fixedRawOffset": fixed,
        "loadDefPointer": load_kind,
        "mapType": map_type, "semantic": semantic, "category": category,
        "delayLoadPixels": delay, "noPicmip": no_picmip,
        "width": width, "height": height, "depth": depth,
        "levelCount": level_count, "streaming": streaming, "baseSize": base_size,
        "pixelsPointer": pixels_kind,
        "streamedPart0Raw": {
            "levelCountAndSize": part_level_size, "hash": part_hash,
            "width": part_width, "height": part_height, "offset": part_offset,
            "sizeAndIpakIndex": part_size_ipak, "adjacencyFlags": part_adjacent,
        },
        "streamedPartCountRaw": part_count, "loadedSize": loaded_size,
        "skippedMipLevels": skipped_mips,
        "namePointer": name_kind, "inlineName": inline_name,
        "imageHash": image_hash, "structurallyPlausible": bool(plausible),
    }


def identity_match(rec: dict | None, target: dict) -> tuple[bool, list[str]]:
    if rec is None:
        return False, ["record-outside-stream"]
    reasons = []
    if not rec["structurallyPlausible"]:
        reasons.append("structural-plausibility")
    for field in ("imageHash", "width", "height", "depth", "streaming", "streamedPartCountRaw"):
        if rec[field] != target[field]:
            reasons.append(field)
    part = target.get("streamedPart0")
    if int(target["streamedPartCountRaw"]) > 0:
        if not part:
            reasons.append("canonical-streamedPart0-missing")
        else:
            rp = rec["streamedPart0Raw"]
            if rp["hash"] != int(part["hash"]): reasons.append("streamedPart0.hash")
            if rp["width"] != int(part["width"]): reasons.append("streamedPart0.width")
            if rp["height"] != int(part["height"]): reasons.append("streamedPart0.height")
    inline = rec.get("inlineName")
    if rec["namePointer"]["kind"] == "following" and inline != target["image"]:
        reasons.append("inlineName")
    return not reasons, reasons


def scan_target(data: bytes, blocks: list[int], target: dict, body_start: int) -> dict:
    name = target["image"]
    candidates: dict[int, dict] = {}
    needle = name.encode("ascii") + b"\0"
    pos = max(0, body_start)
    while True:
        at = data.find(needle, pos)
        if at < 0: break
        pos = at + 1
        fixed = at - GFXIMAGE_SIZE
        rec = parse_fixed(data, fixed, blocks)
        ok, reasons = identity_match(rec, target)
        if rec is not None:
            candidates.setdefault(fixed, {"record": rec, "discovery": set(), "match": ok, "mismatchReasons": reasons})["discovery"].add("inline-name")
    hneedle = struct.pack("<I", target["imageHash"])
    pos = max(0, body_start + 76)
    while True:
        at = data.find(hneedle, pos)
        if at < 0: break
        pos = at + 1
        fixed = at - 76
        if fixed < body_start: continue
        rec = parse_fixed(data, fixed, blocks)
        ok, reasons = identity_match(rec, target)
        if rec is None: continue
        ent = candidates.setdefault(fixed, {"record": rec, "discovery": set(), "match": ok, "mismatchReasons": reasons})
        ent["discovery"].add("image-hash")
        ent["match"], ent["mismatchReasons"] = ok, reasons
    rows = []
    for fixed, ent in sorted(candidates.items()):
        rec = ent["record"]
        rows.append({
            "fixedRawOffset": fixed,
            "discovery": sorted(ent["discovery"]),
            "match": bool(ent["match"]),
            "mismatchReasons": list(ent["mismatchReasons"]),
            "inlineName": rec.get("inlineName"),
            "imageHash": rec.get("imageHash"),
            "width": rec.get("width"), "height": rec.get("height"), "depth": rec.get("depth"),
            "streaming": rec.get("streaming"), "streamedPartCountRaw": rec.get("streamedPartCountRaw"),
            "streamedPart0Hash": rec.get("streamedPart0Raw", {}).get("hash"),
            "semantic": rec.get("semantic"), "namePointer": rec.get("namePointer"),
        })
    matches = [r for r in rows if r["match"]]
    exact_name_matches = [r for r in matches if r.get("inlineName") == name]
    status = "exact-unique" if len(matches) == 1 else "exact-ambiguous" if len(matches) > 1 else "unresolved"
    return {
        "image": name,
        "canonical": target,
        "status": status,
        "candidateCount": len(rows),
        "exactIdentityMatchCount": len(matches),
        "exactInlineNameMatchCount": len(exact_name_matches),
        "candidates": rows,
    }


def build(expanded: Path, coverage_path: Path, canonical_path: Path) -> dict:
    data = expanded.read_bytes()
    front = parse_front(data)
    coverage = json.loads(coverage_path.read_text())
    canonical = load_canonical(canonical_path)
    names = unresolved_names(coverage)
    targets = canonical_targets(canonical, names)
    rows = [scan_target(data, front["blockSizes"], targets[n], front["assetBodyStreamRawOffset"]) for n in names]
    exact_unique = [r for r in rows if r["status"] == "exact-unique"]
    exact_ambiguous = [r for r in rows if r["status"] == "exact-ambiguous"]
    exact_name = [r for r in rows if r["exactInlineNameMatchCount"] > 0]
    return {
        "format": "t6-patch-mp-nuketown-unresolved-primary-gfximage-probe-v1",
        "authority": "expanded retail T6 XFile + canonical live Nuketown GfxImage identities",
        "expandedStream": {"file": expanded.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "front": {
            "declaredZoneSize": front["declaredZoneSize"],
            "declaredExternalSize": front["declaredExternalSize"],
            "scriptStringCount": front["scriptStringCount"],
            "dependencyCount": front["dependencyCount"],
            "assetCount": front["assetCount"],
            "assetBodyStreamRawOffset": front["assetBodyStreamRawOffset"],
            "assetTypeCounts": front["assetTypeCounts"],
            "imageXassetCount": len(front["imageXassets"]),
        },
        "summary": {
            "unresolvedPrimaryCount": len(names),
            "imageXassetCount": len(front["imageXassets"]),
            "exactUniqueIdentityMatches": len(exact_unique),
            "exactAmbiguousIdentityMatches": len(exact_ambiguous),
            "targetsWithExactInlineNameMatch": len(exact_name),
            "unresolvedTargets": sum(r["status"] == "unresolved" for r in rows),
        },
        "rows": rows,
        "proofBoundary": (
            "This is a target-driven GfxImage identity probe, not a generic walk of every patch XAsset body. "
            "A target is accepted only when the serialized 80-byte T6 PC32 GfxImage record matches the canonical "
            "live image hash, dimensions, streaming/part count, and streamed-part-0 hash/dimensions. When the "
            "serialized name pointer is FOLLOWING, the inline name must also match exactly. No OAT filename, "
            "same-name IPAK fallback, or guessed material alias can promote an identity."
        ),
    }


def synthetic_self_test() -> None:
    name = "~-gnt_2020_test_c"
    ih = rhash(name)
    stream_hash = 0x12345678
    blocks = [4096] * 8
    fixed = bytearray(80)
    struct.pack_into("<I", fixed, 0, 0)
    fixed[4] = 3; fixed[5] = 2; fixed[6] = 3; fixed[7] = 0
    fixed[10] = 0
    struct.pack_into("<HHH", fixed, 20, 512, 256, 1)
    fixed[26] = 10; fixed[27] = 1
    struct.pack_into("<I", fixed, 28, 0)
    struct.pack_into("<I", fixed, 32, 0)
    struct.pack_into("<I", fixed, 36, 1)
    struct.pack_into("<I", fixed, 40, stream_hash)
    struct.pack_into("<HH", fixed, 44, 512, 256)
    fixed[60] = 1
    struct.pack_into("<I", fixed, 72, FOLLOWING)
    struct.pack_into("<I", fixed, 76, ih)
    data = bytes(128) + fixed + name.encode("ascii") + b"\0" + bytes(64)
    target = {
        "image": name, "imageHash": ih, "width": 512, "height": 256, "depth": 1,
        "streaming": 1, "streamedPartCountRaw": 1,
        "streamedPart0": {"hash": stream_hash, "width": 512, "height": 256},
        "materialUsageSemantics": [2],
    }
    row = scan_target(data, blocks, target, 0)
    assert row["status"] == "exact-unique", row
    assert row["exactInlineNameMatchCount"] == 1, row
    bad = dict(target); bad["streamedPart0"] = dict(target["streamedPart0"]); bad["streamedPart0"]["hash"] ^= 1
    row2 = scan_target(data, blocks, bad, 0)
    assert row2["status"] == "unresolved", row2
    print(json.dumps({"selfTest": "pass", "image": name, "imageHash": f"0x{ih:08X}"}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path)
    ap.add_argument("--coverage", type=Path)
    ap.add_argument("--canonical", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--expect-assets", type=int)
    ap.add_argument("--expect-image-xassets", type=int)
    ap.add_argument("--expect-unresolved", type=int)
    args = ap.parse_args()
    if args.self_test:
        synthetic_self_test()
        return 0
    for key in ("expanded", "coverage", "canonical", "out"):
        if getattr(args, key) is None:
            ap.error(f"--{key.replace('_','-')} is required unless --self-test is used")
    doc = build(args.expanded, args.coverage, args.canonical)
    s = doc["summary"]; f = doc["front"]
    if args.expect_assets is not None and f["assetCount"] != args.expect_assets:
        raise SystemExit(f"asset count {f['assetCount']} != {args.expect_assets}")
    if args.expect_image_xassets is not None and f["imageXassetCount"] != args.expect_image_xassets:
        raise SystemExit(f"IMAGE XAsset count {f['imageXassetCount']} != {args.expect_image_xassets}")
    if args.expect_unresolved is not None and s["unresolvedPrimaryCount"] != args.expect_unresolved:
        raise SystemExit(f"unresolved primary count {s['unresolvedPrimaryCount']} != {args.expect_unresolved}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(s, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
