#!/usr/bin/env python3
"""Build a fail-closed T6 WeaponFullDef gameplay-field contract.

Authority is the exact pinned OpenAssetTools T6 ``weapon_fields`` table supplied
as input.  This adapter does not read retail values yet; it freezes the source
field names, owning struct members and parse-field types that the retail parser
must later match.

Important boundaries:
- ``CSPFT_MILLISECONDS`` is an internal millisecond integer field.  The pinned
  InfoString writer divides that integer by 1000 when emitting authored seconds.
- RPM is therefore permitted only as the derived expression
  ``60000 / fireTimeMilliseconds`` after a retail ``iFireTime`` value is closed.
- Damage is a six-point native curve.  The adapter preserves all six damage and
  range fields; it never collapses them to only max/min.
- Plain ``CSPFT_FLOAT`` range values stay in native T6 units.  No inch/meter
  conversion is asserted here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT = "t6-weapon-gameplay-field-contract-v1"
OAT_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
OAT_WEAPON_FIELDS_BLOB_SHA1 = "913e81a417d14516fc131ff5cb864ada3fcaf661"
OAT_PATH = "src/ObjCommon/Game/T6/Weapon/WeaponFields.h"

ROW_RE = re.compile(
    r'\{\s*"(?P<name>[^"]+)"\s*,\s*offsetof\(WeaponFullDef,\s*(?P<member>.+?)\)\s*,\s*(?P<type>[A-Z0-9_]+)\s*\},?'
)

# These are the minimum fields that must remain source-exact before any package
# can claim gameplay/stat closure.  All parsed fields are emitted, not just this
# canary set.
REQUIRED: dict[str, tuple[str, str]] = {
    "fireTime": ("weapDef.iFireTime", "CSPFT_MILLISECONDS"),
    "burstFireDelay": ("weapDef.iBurstDelayTime", "CSPFT_MILLISECONDS"),
    "reloadTime": ("weapVariantDef.iReloadTime", "CSPFT_MILLISECONDS"),
    "reloadEmptyTime": ("weapVariantDef.iReloadEmptyTime", "CSPFT_MILLISECONDS"),
    "adsTransInTime": ("weapVariantDef.iAdsTransInTime", "CSPFT_MILLISECONDS"),
    "adsTransOutTime": ("weapVariantDef.iAdsTransOutTime", "CSPFT_MILLISECONDS"),
    "clipSize": ("weapVariantDef.iClipSize", "CSPFT_INT"),
    "maxAmmo": ("weapDef.iMaxAmmo", "CSPFT_INT"),
    "shotCount": ("weapDef.shotCount", "CSPFT_INT"),
    "damage": ("weapDef.damage[0]", "CSPFT_INT"),
    "damage2": ("weapDef.damage[1]", "CSPFT_INT"),
    "damage3": ("weapDef.damage[2]", "CSPFT_INT"),
    "damage4": ("weapDef.damage[3]", "CSPFT_INT"),
    "damage5": ("weapDef.damage[4]", "CSPFT_INT"),
    "minDamage": ("weapDef.damage[5]", "CSPFT_INT"),
    "maxDamageRange": ("weapDef.damageRange[0]", "CSPFT_FLOAT"),
    "damageRange2": ("weapDef.damageRange[1]", "CSPFT_FLOAT"),
    "damageRange3": ("weapDef.damageRange[2]", "CSPFT_FLOAT"),
    "damageRange4": ("weapDef.damageRange[3]", "CSPFT_FLOAT"),
    "damageRange5": ("weapDef.damageRange[4]", "CSPFT_FLOAT"),
    "minDamageRange": ("weapDef.damageRange[5]", "CSPFT_FLOAT"),
    "playerDamage": ("weapDef.playerDamage", "CSPFT_INT"),
    "minPlayerDamage": ("weapDef.minPlayerDamage", "CSPFT_INT"),
    "meleeDamage": ("weapDef.iMeleeDamage", "CSPFT_INT"),
}


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def parse_fields(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = ROW_RE.search(line)
        if not match:
            continue
        row = {k: match.group(k).strip() for k in ("name", "member", "type")}
        if row["name"] in seen:
            raise ValueError(f"duplicate weapon field name {row['name']!r}")
        seen.add(row["name"])
        rows.append(row)
    if not rows:
        raise ValueError("no WeaponFullDef weapon_fields rows parsed")
    return rows


def category(name: str, field_type: str) -> str:
    low = name.lower()
    if field_type == "CSPFT_MILLISECONDS" or any(x in low for x in ("time", "delay")):
        return "timing"
    if any(x in low for x in ("damage", "explosion", "projectile", "destabil")):
        return "damage_projectile"
    if any(x in low for x in ("ammo", "clip", "reload", "shotcount")):
        return "ammo_reload"
    if any(x in low for x in ("spread", "kick", "recoil", "sway", "idleamount", "idlespeed")):
        return "accuracy_recoil"
    if low.startswith("ads") or "fov" in low or "zoom" in low:
        return "ads_view"
    if field_type in {"CSPFT_XMODEL", "CSPFT_MATERIAL", "CSPFT_MATERIAL_STREAM", "CSPFT_FX", "CSPFT_TRACER"}:
        return "asset_reference"
    if field_type in {"WFT_ANIM_NAME", "WFT_NOTETRACKSOUNDMAP"}:
        return "animation_audio_reference"
    if "sound" in low or field_type == "CSPFT_SOUND_ALIAS_ID":
        return "audio_reference"
    return "other"


def build(data: bytes, *, require_pinned_blob: bool = True) -> dict[str, Any]:
    blob = git_blob_sha1(data)
    if require_pinned_blob and blob != OAT_WEAPON_FIELDS_BLOB_SHA1:
        raise ValueError(f"WeaponFields.h git blob SHA-1 {blob} != pinned {OAT_WEAPON_FIELDS_BLOB_SHA1}")
    text = data.decode("utf-8")
    rows = parse_fields(text)
    by_name = {row["name"]: row for row in rows}
    for name, (member, field_type) in REQUIRED.items():
        row = by_name.get(name)
        if row is None:
            raise ValueError(f"required gameplay field {name!r} missing")
        if (row["member"], row["type"]) != (member, field_type):
            raise ValueError(
                f"{name}: source mapping {(row['member'], row['type'])!r} != expected {(member, field_type)!r}"
            )

    emitted = []
    categories = Counter()
    types = Counter()
    for row in rows:
        cat = category(row["name"], row["type"])
        categories[cat] += 1
        types[row["type"]] += 1
        emitted.append({**row, "category": cat})

    damage_curve = [
        {"point": i, "damageField": d, "rangeField": r}
        for i, (d, r) in enumerate(
            zip(
                ["damage", "damage2", "damage3", "damage4", "damage5", "minDamage"],
                ["maxDamageRange", "damageRange2", "damageRange3", "damageRange4", "damageRange5", "minDamageRange"],
            )
        )
    ]
    return {
        "format": FORMAT,
        "source": {
            "repository": "Laupetin/OpenAssetTools",
            "commit": OAT_COMMIT,
            "path": OAT_PATH,
            "gitBlobSha1": blob,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        "summary": {
            "fieldCount": len(emitted),
            "requiredGameplayCanaries": len(REQUIRED),
            "allRequiredGameplayCanariesExact": True,
            "categoryCounts": dict(sorted(categories.items())),
            "fieldTypeCounts": dict(sorted(types.items())),
            "fireTimeInternalUnit": "milliseconds",
            "damageCurvePoints": 6,
            "nativeDamageRangeUnitConversionAsserted": False,
        },
        "derivedRules": {
            "rateOfFireRpm": {
                "sourceField": "fireTime",
                "sourceMember": "weapDef.iFireTime",
                "sourceInternalUnit": "milliseconds",
                "formula": "60000 / fireTimeMilliseconds",
                "precondition": "retail fireTimeMilliseconds > 0 and exact retail WeaponDef value closed",
            }
        },
        "damageCurve": damage_curve,
        "fields": emitted,
        "proofBoundary": (
            "This contract closes field identity and source parse type only. It does not yet assert any retail weapon value. "
            "CSPFT_MILLISECONDS is permitted as internal milliseconds because the pinned writer reads an unsigned integer and divides by 1000. "
            "Plain FLOAT damage ranges remain native T6 values with no world-unit conversion. Every weapon package must later bind these fields to exact retail WeaponDef/WeaponVariantDef bytes or an independently equivalent native dump."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weapon-fields", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = build(args.weapon_fields.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
