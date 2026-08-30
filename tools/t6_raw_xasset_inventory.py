#!/usr/bin/env python3
"""Direct T6 expanded-fastfile XAsset inventory and WeaponVariantDef locator.

No OpenAssetTools executable is used. Input is the expanded XFile byte stream
produced by the independently recovered retail T6 decrypt/inflate path.

Proof scope:
- XFile size/external-size + eight block sizes
- ScriptStringList
- XAssetList / XAsset array and exact type counts
- T6 packed 32-bit zone-pointer decoding
- 716-byte PC WeaponVariantDef fixed-record location by inline internal name

Important: XBlock alignment advances destination memory only; it consumes no
serialized source bytes. Never align the physical stream cursor here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import struct

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
POINTER_BITS = 32
BLOCK_BITS = 3
BLOCK_SHIFT = POINTER_BITS - BLOCK_BITS
OFFSET_MASK = (1 << BLOCK_SHIFT) - 1
WVD_SIZE = 716

BLOCK_NAMES = [
    "TEMP", "RUNTIME_VIRTUAL", "RUNTIME_PHYSICAL", "DELAY_VIRTUAL",
    "DELAY_PHYSICAL", "VIRTUAL", "PHYSICAL", "STREAMER_RESERVE",
]

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

# Independently validated PC32 offsets in the 716-byte T6 WeaponVariantDef.
WVD_FIELDS = {
    "szInternalName": (0, "ptr"), "iVariantCount": (4, "i32"),
    "weapDef": (8, "ptr"), "szDisplayName": (12, "ptr"),
    "szAltWeaponName": (16, "ptr"), "szAttachmentUnique": (20, "ptr"),
    "attachments": (24, "ptr"), "attachmentUniques": (28, "ptr"),
    "szXAnims": (32, "ptr"), "hideTags": (36, "ptr"),
    "attachViewModel": (40, "ptr"), "attachWorldModel": (44, "ptr"),
    "attachViewModelTag": (48, "ptr"), "attachWorldModelTag": (52, "ptr"),
    "altWeaponIndex": (464, "u32"), "iAttachments": (468, "i32"),
    "bIgnoreAttachments": (472, "u8"), "iClipSize": (476, "i32"),
    "iReloadTime": (480, "i32"), "iReloadEmptyTime": (484, "i32"),
    "iReloadQuickTime": (488, "i32"), "iReloadQuickEmptyTime": (492, "i32"),
    "iAdsTransInTime": (496, "i32"), "iAdsTransOutTime": (500, "i32"),
    "iAltRaiseTime": (504, "i32"), "szAmmoDisplayName": (508, "ptr"),
    "szAmmoName": (512, "ptr"), "iAmmoIndex": (516, "i32"),
    "szClipName": (520, "ptr"), "iClipIndex": (524, "i32"),
    "bSilenced": (580, "u8"), "bDualMag": (581, "u8"),
    "bInfraRed": (582, "u8"), "bTVGuided": (583, "u8"),
    "bAntiQuickScope": (592, "u8"), "overlayMaterial": (596, "ptr"),
    "overlayMaterialLowRes": (600, "ptr"), "dpadIcon": (604, "ptr"),
    "noAmmoOnDpadIcon": (612, "u8"), "mmsWeapon": (613, "u8"),
    "mmsInScope": (614, "u8"), "mmsFOV": (616, "f32"),
    "mmsAspect": (620, "f32"), "mmsMaxDist": (624, "f32"),
}


def cstring(data: bytes, pos: int):
    end = data.index(b"\0", pos)
    return data[pos:end].decode("latin1"), end + 1


def zone_pointer(value: int, blocks: list[int]):
    if value == 0:
        return {"kind": "null"}
    if value == PTR_FOLLOWING:
        return {"kind": "following"}
    if value == PTR_INSERT:
        return {"kind": "insert"}
    encoded = (value - 1) & 0xFFFFFFFF
    block = encoded >> BLOCK_SHIFT
    offset = encoded & OFFSET_MASK
    return {
        "kind": "packed", "block": block,
        "block_name": BLOCK_NAMES[block] if block < len(BLOCK_NAMES) else None,
        "offset": offset,
        "valid": block < len(blocks) and offset < blocks[block],
    }


def parse_front(data: bytes):
    size, external = struct.unpack_from("<II", data, 0)
    blocks = list(struct.unpack_from("<8I", data, 8))
    pos = 40
    sc, sp, dc, dp, ac, ap = struct.unpack_from("<6I", data, pos)
    pos += 24
    if sc and sp != PTR_FOLLOWING:
        raise ValueError("ScriptStringList is not inline")
    if sc:
        ptrs = struct.unpack_from(f"<{sc}I", data, pos)
        pos += sc * 4
        for ptr in ptrs:
            if ptr == PTR_FOLLOWING:
                _, pos = cstring(data, pos)
    if dc:
        if dp != PTR_FOLLOWING:
            raise ValueError("dependency list is not inline")
        ptrs = struct.unpack_from(f"<{dc}I", data, pos)
        pos += dc * 4
        for ptr in ptrs:
            if ptr == PTR_FOLLOWING:
                _, pos = cstring(data, pos)
    if ap != PTR_FOLLOWING:
        raise ValueError("XAsset array is not inline")

    asset_array = pos
    counts = Counter()
    for index in range(ac):
        asset_type, _ = struct.unpack_from("<II", data, pos)
        pos += 8
        if not 0 <= asset_type < len(ASSET_TYPES):
            raise ValueError(f"bad XAsset type {asset_type} at index {index}")
        counts[ASSET_TYPES[asset_type]] += 1

    return {
        "expanded_bytes": len(data),
        "expanded_sha256": hashlib.sha256(data).hexdigest(),
        "declared_zone_size": size, "declared_external_size": external,
        "block_sizes": [{"index": i, "name": BLOCK_NAMES[i], "bytes": n}
                        for i, n in enumerate(blocks)],
        "script_string_count": sc, "dependency_count": dc,
        "asset_count": ac, "asset_array_raw_offset": asset_array,
        "asset_body_stream_raw_offset": pos,
        "asset_type_counts": dict(sorted(counts.items())),
        "_blocks": blocks,
    }


def fixed_wvd(data: bytes, start: int, blocks: list[int]):
    out = {"raw_struct_offset": start, "raw_struct_size": WVD_SIZE}
    for name, (off, kind) in WVD_FIELDS.items():
        if kind == "u8": value = data[start + off]
        elif kind == "i32": value = struct.unpack_from("<i", data, start + off)[0]
        elif kind == "u32": value = struct.unpack_from("<I", data, start + off)[0]
        elif kind == "f32": value = struct.unpack_from("<f", data, start + off)[0]
        else:
            raw = struct.unpack_from("<I", data, start + off)[0]
            value = {"raw": f"0x{raw:08X}", "decoded": zone_pointer(raw, blocks)}
        out[name] = value
    return out


def locate_wvd(data: bytes, name: str, blocks: list[int]):
    needle = name.encode("ascii") + b"\0"
    found = []
    pos = 0
    while True:
        at = data.find(needle, pos)
        if at < 0: break
        start = at - WVD_SIZE
        if start >= 0:
            n = struct.unpack_from("<I", data, start)[0]
            variants = struct.unpack_from("<i", data, start + 4)[0]
            weap = struct.unpack_from("<I", data, start + 8)[0]
            if n == PTR_FOLLOWING and -1 <= variants <= 100 and weap != 0:
                rec = fixed_wvd(data, start, blocks)
                rec.update(internal_name=name, raw_internal_name_offset=at,
                           status="exact_inline_fixed_record")
                found.append(rec)
        pos = at + 1
    if len(found) == 1: return found[0]
    return {"internal_name": name, "status": "ambiguous_or_missing",
            "candidate_count": len(found), "candidates": found}


def root_names(path: Path):
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, list): raise ValueError("roots JSON must be a list")
        return [str(x) for x in value]
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [r.get("internal_name") or r.get("name") for r in rows
                if r.get("internal_name") or r.get("name")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--roots", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = parse_front(data)
    blocks = result.pop("_blocks")
    result["format_proof"] = {
        "pointer_bits": 32, "offset_block_bit_count": 3,
        "packed_pointer_block_shift": 29, "packed_pointer_offset_mask": "0x1FFFFFFF",
        "weapon_variant_def_pc32_fixed_size": 716,
        "physical_stream_alignment_rule": "destination XBlock alignment consumes no source bytes",
    }
    if args.roots:
        names = root_names(args.roots)
        roots = [locate_wvd(data, name, blocks) for name in names]
        result["weapon_variant_roots"] = roots
        result["weapon_variant_root_summary"] = {
            "requested": len(names),
            "exact": sum(r["status"] == "exact_inline_fixed_record" for r in roots),
            "unresolved": [r["internal_name"] for r in roots if r["status"] != "exact_inline_fixed_record"],
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"asset_count": result["asset_count"],
                      "asset_type_counts": result["asset_type_counts"],
                      "weapon_variant_root_summary": result.get("weapon_variant_root_summary")}, indent=2))


if __name__ == "__main__":
    main()
