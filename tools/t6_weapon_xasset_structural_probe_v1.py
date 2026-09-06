#!/usr/bin/env python3
"""Structurally bind T6 top-level WEAPON XAssets to WeaponVariantDef bodies.

Purpose
-------
The older named WeaponVariantDef locator requires an inline szInternalName.
Patch zones can serialize the name as a packed pointer, so this probe starts
from the XAsset list and the 716-byte PC32 WeaponVariantDef shape instead.

Proof boundary
--------------
- A FOLLOWING/INSERT WEAPON header proves that a WeaponVariantDef fixed body is
  serialized in the zone stream.
- A fixed body is accepted only when the recovered T6 scalar/pointer invariants
  hold. Packed pointers must fall inside their declared XFile block.
- Cardinality binding is stricter: the candidate must also expose a direct
  FOLLOWING/INSERT WeaponDef whose recovered selector enums validate. This
  prevents shifted child bytes from masquerading as top-level WVD records.
- A single inline WEAPON header plus a single bindable WeaponVariantDef body is
  cardinality-bound to that asset. Multiple bindable candidates stay ambiguous.
- szInternalName is promoted only when its serialized pointer is FOLLOWING and
  the string can therefore be read directly. Packed-name targets are emitted as
  unresolved block offsets; they are never guessed from nearby strings.
- A direct WeaponDef selector is promoted only when the reusable weapDef pointer
  is FOLLOWING/INSERT and the preceding inline-name payload length is known.

This is deliberately a P3-capable structural tool. Retail promotion requires a
retained expanded stream and manifest under the project proof standard.
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

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
WEAPON_TYPE_INDEX = 25
WVD_SIZE = 716

# Independently retained T6 PC32 WeaponVariantDef pointer fields.
WVD_POINTER_OFFSETS = {
    "szInternalName": 0,
    "weapDef": 8,
    "szDisplayName": 12,
    "szAltWeaponName": 16,
    "szAttachmentUnique": 20,
    "attachments": 24,
    "attachmentUniques": 28,
    "szXAnims": 32,
    "hideTags": 36,
    "attachViewModel": 40,
    "attachWorldModel": 44,
    "attachViewModelTag": 48,
    "attachWorldModelTag": 52,
    "szAmmoDisplayName": 508,
    "szAmmoName": 512,
    "szClipName": 520,
    "overlayMaterial": 596,
    "overlayMaterialLowRes": 600,
    "dpadIcon": 604,
}

BOOL_OFFSETS = (472, 580, 581, 582, 583, 592, 612, 613, 614)

PLAYER_ANIM_TYPES = [
    "none", "default", "other", "sniper", "m203", "hold", "briefcase",
    "reviver", "radio", "dualwield", "remotecontrol", "crossbow", "minigun",
    "beltfed", "g11", "rearclip", "handleclip", "rearclipsniper",
    "ballisticknife", "singleknife", "nopump", "hatchet", "grimreaper",
    "zipline", "riotshield", "tablet", "turned", "screecher", "staff",
]
WEAP_TYPES = ["bullet", "grenade", "projectile", "binoculars", "gas", "bomb", "mine", "melee", "riotshield"]
WEAP_CLASSES = [
    "rifle", "mg", "smg", "spread", "pistol", "grenade", "rocketlauncher",
    "turret", "non-player", "gas", "item", "melee",
    "Killstreak Alt Stored Weapon", "pistol spread",
]
FIRE_TYPES = [
    "Full Auto", "Single Shot", "2-Round Burst", "3-Round Burst",
    "4-Round Burst", "5-Round Burst", "Stacked Fire", "Minigun",
    "Charge Shot", "Jetgun",
]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("t6_raw_xasset_inventory_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import raw parser {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pointer_valid(rawmod, value: int, blocks: list[int]) -> bool:
    dec = rawmod.decode_zone_pointer(value, blocks)
    if dec.get("kind") == "packed":
        return bool(dec.get("valid_for_declared_block_size", dec.get("valid", False)))
    return dec.get("kind") in {"null", "following", "insert"}


def read_ascii_cstring(data: bytes, pos: int, maxlen: int = 256) -> tuple[str, int] | None:
    if pos < 0 or pos >= len(data):
        return None
    end = data.find(b"\0", pos, min(len(data), pos + maxlen + 1))
    if end < 0 or end == pos:
        return None
    raw = data[pos:end]
    if any(c < 32 or c > 126 for c in raw):
        return None
    return raw.decode("ascii"), end + 1


def candidate_at(data: bytes, start: int, blocks: list[int], rawmod) -> dict[str, Any] | None:
    if start < 0 or start + WVD_SIZE > len(data):
        return None

    # Cheap rejection first: these are retained uint8 booleans in the proven PC32 layout.
    if any(data[start + off] not in (0, 1) for off in BOOL_OFFSETS):
        return None

    variants = struct.unpack_from("<i", data, start + 4)[0]
    attachments = struct.unpack_from("<i", data, start + 468)[0]

    name_raw = struct.unpack_from("<I", data, start)[0]
    weap_raw = struct.unpack_from("<I", data, start + 8)[0]
    if name_raw == 0 or weap_raw == 0:
        return None

    pointers = {}
    for name, off in WVD_POINTER_OFFSETS.items():
        raw = struct.unpack_from("<I", data, start + off)[0]
        if not pointer_valid(rawmod, raw, blocks):
            return None
        pointers[name] = {
            "raw": f"0x{raw:08X}",
            "raw_u32": raw,
            "decoded": rawmod.decode_zone_pointer(raw, blocks),
        }

    for off in (616, 620, 624):
        value = struct.unpack_from("<f", data, start + off)[0]
        if not math.isfinite(value) or abs(value) > 1_000_000:
            return None

    non_null = sum(p["raw_u32"] != 0 for p in pointers.values())
    return {
        "rawStructOffset": start,
        "rawStructSize": WVD_SIZE,
        "iVariantCount": variants,
        "iAttachments": attachments,
        "pointers": pointers,
        "nonNullKnownPointerCount": non_null,
        "rawFixedSha256": sha256_bytes(data[start:start + WVD_SIZE]),
    }


def scan_candidates(data: bytes, body_start: int, blocks: list[int], rawmod) -> list[dict[str, Any]]:
    out = []
    last = len(data) - WVD_SIZE
    # Source bytes are intentionally not alignment-rounded in T6 expanded streams.
    for start in range(max(0, body_start), last + 1):
        rec = candidate_at(data, start, blocks, rawmod)
        if rec is not None:
            out.append(rec)
    return out


def parse_weapondef_selector(data: bytes, start: int) -> dict[str, Any]:
    if start < 0 or start + 56 > len(data):
        return {"status": "truncated-direct-weapdef-prefix", "rawOffset": start}
    pat, wt, wc, penetrate, impact, inventory, ft, clip = struct.unpack_from("<8i", data, start + 24)
    sane = (
        0 <= pat < len(PLAYER_ANIM_TYPES)
        and 0 <= wt < len(WEAP_TYPES)
        and 0 <= wc < len(WEAP_CLASSES)
        and 0 <= ft < len(FIRE_TYPES)
    )
    if not sane:
        return {
            "status": "invalid-direct-weapdef-prefix",
            "rawOffset": start,
            "rawEnums": {"playerAnimType": pat, "weaponType": wt, "weaponClass": wc, "fireType": ft},
        }
    return {
        "status": "exact-direct-weapdef-prefix",
        "rawOffset": start,
        "rawPrefixSha256": sha256_bytes(data[start:start + 56]),
        "playerAnimType": PLAYER_ANIM_TYPES[pat],
        "weaponType": WEAP_TYPES[wt],
        "weaponClass": WEAP_CLASSES[wc],
        "fireType": FIRE_TYPES[ft],
        "penetrateTypeRaw": penetrate,
        "impactTypeRaw": impact,
        "inventoryTypeRaw": inventory,
        "clipTypeRaw": clip,
        "selector": {"weaponclass": WEAP_CLASSES[wc], "playerAnimType": PLAYER_ANIM_TYPES[pat]},
    }


def resolve_bound_candidate(data: bytes, rec: dict[str, Any]) -> dict[str, Any]:
    start = int(rec["rawStructOffset"])
    name_ptr = rec["pointers"]["szInternalName"]
    weap_ptr = rec["pointers"]["weapDef"]
    cursor = start + WVD_SIZE

    name_dec = name_ptr["decoded"]
    name = None
    name_status = "unresolved"
    if name_dec.get("kind") == "following":
        parsed = read_ascii_cstring(data, cursor)
        if parsed is not None:
            name, cursor = parsed
            name_status = "exact-inline-following"
        else:
            name_status = "invalid-inline-following-string"
    elif name_dec.get("kind") == "packed":
        name_status = "unresolved-packed-name-pointer"
    elif name_dec.get("kind") == "insert":
        # String INSERT behavior is not yet retail-proven for this T6 field.
        name_status = "unresolved-insert-name-pointer"
    else:
        name_status = f"unsupported-name-pointer-{name_dec.get('kind')}"

    selector = {"status": "unresolved-weapdef-pointer"}
    weap_kind = weap_ptr["decoded"].get("kind")
    if name_status.startswith("exact-inline") or name_dec.get("kind") == "packed":
        # Packed name consumes no source bytes. FOLLOWING name was consumed above.
        if weap_kind in {"following", "insert"}:
            selector = parse_weapondef_selector(data, cursor)
        elif weap_kind == "packed":
            selector = {
                "status": "unresolved-packed-weapdef-pointer",
                "pointer": weap_ptr,
            }
        else:
            selector = {"status": f"unsupported-weapdef-pointer-{weap_kind}"}

    return {
        **rec,
        "internalName": name,
        "internalNameStatus": name_status,
        "internalNamePointer": name_ptr,
        "weaponDefPointer": weap_ptr,
        "selector": selector,
    }


def probe(data: bytes, rawmod) -> dict[str, Any]:
    front = rawmod.parse_front(data)
    blocks = list(front.get("_blocks", []))
    if len(blocks) != 8:
        blocks = [int(x["bytes"]) for x in front.get("block_sizes", [])]
    if len(blocks) != 8:
        raise ValueError("raw parser did not expose eight XFile block sizes")

    assets = list(front.get("assets", []))
    if not assets:
        raise ValueError("raw parser did not expose top-level XAsset rows")
    weapon_assets = [a for a in assets if int(a.get("type_index", -1)) == WEAPON_TYPE_INDEX or a.get("type") == "WEAPON"]
    inline_weapon_assets = [a for a in weapon_assets if (a.get("header") or {}).get("kind") in {"following", "insert"}]
    packed_weapon_assets = [a for a in weapon_assets if (a.get("header") or {}).get("kind") == "packed"]

    candidates = scan_candidates(data, int(front["asset_body_stream_raw_offset"]), blocks, rawmod)
    resolved_candidates = [resolve_bound_candidate(data, c) for c in candidates]
    bindable_candidates = [
        c for c in resolved_candidates
        if (c.get("selector") or {}).get("status") == "exact-direct-weapdef-prefix"
        and c.get("internalNameStatus") in {"exact-inline-following", "unresolved-packed-name-pointer"}
    ]
    bindings = []
    if len(inline_weapon_assets) == 1 and len(bindable_candidates) == 1 and not packed_weapon_assets:
        bound = bindable_candidates[0]
        bindings.append({
            "status": "exact-by-single-inline-weapon-cardinality",
            "assetIndex": inline_weapon_assets[0]["index"],
            "assetHeader": inline_weapon_assets[0],
            "weaponVariantDef": bound,
        })
    elif inline_weapon_assets or candidates:
        bindings.append({
            "status": "ambiguous-cardinality",
            "inlineWeaponAssetCount": len(inline_weapon_assets),
            "packedWeaponAssetCount": len(packed_weapon_assets),
            "structuralCandidateCount": len(candidates),
            "bindableStructuralCandidateCount": len(bindable_candidates),
        })

    exact_names = sum(
        1 for b in bindings
        if b.get("status") == "exact-by-single-inline-weapon-cardinality"
        and b["weaponVariantDef"].get("internalNameStatus") == "exact-inline-following"
    )
    exact_selectors = sum(
        1 for b in bindings
        if b.get("status") == "exact-by-single-inline-weapon-cardinality"
        and (b["weaponVariantDef"].get("selector") or {}).get("status") == "exact-direct-weapdef-prefix"
    )
    return {
        "format": "t6-weapon-xasset-structural-probe-v1",
        "authority": "retail expanded XAssetList + PC32 WeaponVariantDef structural invariants",
        "expandedBytes": len(data),
        "expandedSha256": sha256_bytes(data),
        "front": {
            "assetCount": front.get("asset_count"),
            "weaponAssetCount": len(weapon_assets),
            "inlineWeaponAssetCount": len(inline_weapon_assets),
            "packedWeaponAssetCount": len(packed_weapon_assets),
            "assetBodyStreamRawOffset": front.get("asset_body_stream_raw_offset"),
        },
        "weaponAssets": weapon_assets,
        "structuralCandidates": resolved_candidates,
        "bindableStructuralCandidates": bindable_candidates,
        "bindings": bindings,
        "summary": {
            "weaponAssets": len(weapon_assets),
            "structuralCandidates": len(candidates),
            "bindableStructuralCandidates": len(bindable_candidates),
            "exactCardinalityBindings": sum(b.get("status") == "exact-by-single-inline-weapon-cardinality" for b in bindings),
            "exactInternalNames": exact_names,
            "exactDirectSelectors": exact_selectors,
        },
        "proofBoundary": (
            "Cardinality binding uses only structural WVD candidates whose reusable weapDef is serialized inline and whose direct WeaponDef selector prefix validates. "
            "This rejects shifted lookalikes inside child payloads instead of ranking candidates heuristically. "
            "Packed szInternalName targets are emitted but not named until TEMP-block allocation identity is replayed. "
            "Packed weapDef targets block binding/selector promotion. Multiple bindable WVD records or multiple inline WEAPON assets remain ambiguous."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--raw-parser", type=Path, default=Path(__file__).with_name("t6_raw_xasset_inventory_v2.py"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    rawmod = load_module(args.raw_parser)
    out = probe(data, rawmod)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    complete = (
        out["summary"]["weaponAssets"] > 0
        and out["summary"]["exactCardinalityBindings"] == out["summary"]["weaponAssets"]
        and out["summary"]["exactInternalNames"] == out["summary"]["weaponAssets"]
        and out["summary"]["exactDirectSelectors"] == out["summary"]["weaponAssets"]
    )
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
