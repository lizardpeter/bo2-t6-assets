#!/usr/bin/env python3
"""Build a fail-closed T6 attachment + WeaponCamo equip schema contract.

This closes authored field/schema identity from the exact pinned OpenAssetTools
source revision. It deliberately does NOT infer attachment runtime composition
math from friendly field names. Effective-stat evaluation remains blocked until
retail/source application semantics are independently closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT = "t6-weapon-attachment-camo-contract-v1"
OAT_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"

SOURCES = {
    "attachment": {
        "path": "src/ObjCommon/Game/T6/Weapon/AttachmentFields.h",
        "blob": "7fd2d40de567ee1846a1e58567b59540ce154e8a",
    },
    "attachmentUnique": {
        "path": "src/ObjCommon/Game/T6/Weapon/AttachmentUniqueFields.h",
        "blob": "b80663ce2743a0a44612218f31ea1d605089e431",
    },
    "weaponCamoJson": {
        "path": "src/ObjCommon/Game/T6/Json/JsonWeaponCamo.h",
        "blob": "6b76cc2ff8ee3f10b3d6fb46f112939dd7beb548",
    },
}

FIELD_RE = re.compile(
    r'\{\s*"(?P<name>[^"]+)"\s*,\s*offsetof\((?P<owner>[^,]+),\s*(?P<member>.+?)\)\s*,\s*(?P<type>[A-Z0-9_]+)\s*\},?'
)

REQUIRED_ATTACHMENT: dict[str, tuple[str, str]] = {
    "damageRangeScale": ("fDamageRangeScale", "CSPFT_FLOAT"),
    "fireType": ("fireType", "AFT_FIRETYPE"),
    "adsTransInTimeScale": ("fAdsTransInTimeScale", "CSPFT_FLOAT"),
    "adsTransOutTimeScale": ("fAdsTransOutTimeScale", "CSPFT_FLOAT"),
    "adsRecoilReductionRate": ("fAdsRecoilReductionRate", "CSPFT_FLOAT"),
    "adsRecoilReductionLimit": ("fAdsRecoilReductionLimit", "CSPFT_FLOAT"),
    "adsMoveSpeedScale": ("adsMoveSpeedScale", "CSPFT_FLOAT"),
    "hipSpreadMinScale": ("fHipSpreadMinScale", "CSPFT_FLOAT"),
    "hipSpreadMaxScale": ("fHipSpreadMaxScale", "CSPFT_FLOAT"),
    "fireTimeScale": ("fFireTimeScale", "CSPFT_FLOAT"),
    "reloadTimeScale": ("fReloadTimeScale", "CSPFT_FLOAT"),
    "reloadEmptyTimeScale": ("fReloadEmptyTimeScale", "CSPFT_FLOAT"),
    "reloadAddTimeScale": ("fReloadAddTimeScale", "CSPFT_FLOAT"),
    "reloadQuickTimeScale": ("fReloadQuickTimeScale", "CSPFT_FLOAT"),
    "reloadQuickEmptyTimeScale": ("fReloadQuickEmptyTimeScale", "CSPFT_FLOAT"),
    "reloadQuickAddTimeScale": ("fReloadQuickAddTimeScale", "CSPFT_FLOAT"),
    "silenced": ("bSilenced", "CSPFT_BOOL"),
    "dualMag": ("bDualMag", "CSPFT_BOOL"),
    "laserSight": ("laserSight", "CSPFT_BOOL"),
    "infrared": ("bInfraRed", "CSPFT_BOOL"),
    "dualWield": ("bDualWield", "CSPFT_BOOL"),
    "clipSizeScale": ("clipSizeScale", "CSPFT_FLOAT"),
    "clipSize": ("iClipSize", "CSPFT_INT"),
}

REQUIRED_UNIQUE: dict[str, tuple[str, str]] = {
    "locHead": ("locationDamageMultipliers[HITLOC_HEAD]", "CSPFT_FLOAT"),
    "viewModel": ("attachment.viewModel", "CSPFT_XMODEL"),
    "worldModel": ("attachment.worldModel", "CSPFT_XMODEL"),
    "camo": ("attachment.weaponCamo", "AUFT_CAMO"),
    "disableBaseWeaponAttachment": ("attachment.disableBaseWeaponAttachment", "CSPFT_BOOL"),
    "disableBaseWeaponClip": ("attachment.disableBaseWeaponClip", "CSPFT_BOOL"),
    "altWeapon": ("attachment.szAltWeaponName", "CSPFT_STRING"),
    "firstRaiseTime": ("attachment.iFirstRaiseTime", "CSPFT_MILLISECONDS"),
    "reloadAmmoAdd": ("attachment.iReloadAmmoAdd", "CSPFT_INT"),
    "reloadStartAdd": ("attachment.iReloadStartAdd", "CSPFT_INT"),
    "fireSound": ("attachment.fireSound", "CSPFT_STRING"),
    "fireSoundPlayer": ("attachment.fireSoundPlayer", "CSPFT_STRING"),
    "viewFlashEffect": ("attachment.viewFlashEffect", "CSPFT_FX"),
    "worldFlashEffect": ("attachment.worldFlashEffect", "CSPFT_FX"),
    "tracerType": ("attachment.tracerType", "CSPFT_TRACER"),
    "enemyTracerType": ("attachment.enemyTracerType", "CSPFT_TRACER"),
}

CAMO_REQUIRED_MARKERS = {
    "solidBaseImage": "std::optional<std::string> solidBaseImage;",
    "patternBaseImage": "std::optional<std::string> patternBaseImage;",
    "camoSets": "std::vector<JsonWeaponCamoSet> camoSets;",
    "camoMaterials": "std::vector<JsonWeaponCamoMaterialSet> camoMaterials;",
    "solidCamoImage": "std::optional<std::string> solidCamoImage;",
    "patternCamoImage": "std::optional<std::string> patternCamoImage;",
    "patternOffset": "JsonVec2 patternOffset;",
    "patternScale": "float patternScale;",
    "useColorMap": "bool useColorMap;",
    "useNormalMap": "bool useNormalMap;",
    "useSpecularMap": "bool useSpecularMap;",
    "materialOverrides": "std::vector<JsonWeaponCamoMaterialOverride> materialOverrides;",
    "baseMaterial": "std::string baseMaterial;",
    "camoMaterial": "std::string camoMaterial;",
    "shaderConsts": "std::array<float, SHADER_CONST_COUNT> shaderConsts;",
    "shaderConstCount": "constexpr auto SHADER_CONST_COUNT = 8;",
}


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def parse_fields(data: bytes, expected_owner: str) -> list[dict[str, str]]:
    text = data.decode("utf-8")
    rows: list[dict[str, str]] = []
    for m in FIELD_RE.finditer(text):
        row = {k: m.group(k).strip() for k in ("name", "owner", "member", "type")}
        if row["owner"] != expected_owner:
            raise ValueError(f"unexpected offsetof owner {row['owner']!r}; expected {expected_owner!r}")
        row["sourceRow"] = str(len(rows))
        rows.append(row)
    if not rows:
        raise ValueError(f"no fields parsed for {expected_owner}")
    return rows


def require_fields(rows: list[dict[str, str]], required: dict[str, tuple[str, str]]) -> None:
    by_name: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_name.setdefault(row["name"], []).append(row)
    for name, (member, typ) in required.items():
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError(f"required field {name!r} occurrence count {len(matches)} != 1")
        got = (matches[0]["member"], matches[0]["type"])
        if got != (member, typ):
            raise ValueError(f"{name}: {got!r} != {(member, typ)!r}")


def classify_attachment(name: str, typ: str) -> str:
    n = name.lower()
    if any(x in n for x in ("damage", "firetime", "reloadtime", "reloadquick", "clipsize", "spread", "recoil", "sway", "movespeed")):
        return "gameplay_modifier"
    if name in {"fireType", "penetrateType", "silenced", "dualMag", "laserSight", "infrared", "dualWield", "sharedAmmo", "useAsMelee"}:
        return "gameplay_behavior"
    if typ in {"CSPFT_XMODEL", "CSPFT_MATERIAL", "CSPFT_MATERIAL_STREAM", "CSPFT_FX", "CSPFT_TRACER"}:
        return "asset_reference"
    return "other"


def classify_unique(name: str, typ: str) -> str:
    n = name.lower()
    if n.startswith("loc") or any(x in n for x in ("reloadammo", "reloadstart")):
        return "weapon_specific_gameplay"
    if typ == "AUFT_ANIM_NAME":
        return "animation_override"
    if "sound" in n:
        return "audio_override"
    if typ in {"CSPFT_XMODEL", "CSPFT_MATERIAL", "CSPFT_MATERIAL_STREAM", "CSPFT_FX", "CSPFT_TRACER", "AUFT_CAMO"}:
        return "asset_override"
    if any(x in n for x in ("offset", "rotation", "ik", "hidetag")):
        return "presentation_override"
    return "other"


def build(attachment: bytes, unique: bytes, camo: bytes, *, require_pinned: bool = True) -> dict[str, Any]:
    blobs = {
        "attachment": git_blob_sha1(attachment),
        "attachmentUnique": git_blob_sha1(unique),
        "weaponCamoJson": git_blob_sha1(camo),
    }
    if require_pinned:
        for key, got in blobs.items():
            exp = SOURCES[key]["blob"]
            if got != exp:
                raise ValueError(f"{key} git blob {got} != pinned {exp}")

    arows = parse_fields(attachment, "WeaponAttachment")
    urows = parse_fields(unique, "WeaponAttachmentUniqueFull")
    require_fields(arows, REQUIRED_ATTACHMENT)
    require_fields(urows, REQUIRED_UNIQUE)

    camo_text = camo.decode("utf-8")
    for key, marker in CAMO_REQUIRED_MARKERS.items():
        if marker not in camo_text:
            raise ValueError(f"WeaponCamo schema marker {key!r} missing")

    ac = Counter()
    uc = Counter()
    for r in arows:
        r["category"] = classify_attachment(r["name"], r["type"])
        ac[r["category"]] += 1
    for r in urows:
        r["category"] = classify_unique(r["name"], r["type"])
        uc[r["category"]] += 1

    return {
        "format": FORMAT,
        "source": {
            key: {
                "repository": "Laupetin/OpenAssetTools",
                "commit": OAT_COMMIT,
                "path": SOURCES[key]["path"],
                "gitBlobSha1": blobs[key],
            }
            for key in SOURCES
        },
        "summary": {
            "attachmentFieldRows": len(arows),
            "attachmentUniqueFieldRows": len(urows),
            "requiredAttachmentCanaries": len(REQUIRED_ATTACHMENT),
            "requiredAttachmentUniqueCanaries": len(REQUIRED_UNIQUE),
            "weaponCamoRequiredSchemaMarkers": len(CAMO_REQUIRED_MARKERS),
            "attachmentCategoryCounts": dict(sorted(ac.items())),
            "attachmentUniqueCategoryCounts": dict(sorted(uc.items())),
            "allRequiredCanariesExact": True,
            "runtimeCompositionSemanticsClosed": False,
            "camoEquipSchemaClosed": True,
        },
        "attachmentFields": arows,
        "attachmentUniqueFields": urows,
        "weaponCamoSchema": {
            "shaderConstCount": 8,
            "root": ["solidBaseImage", "patternBaseImage", "camoSets", "camoMaterials"],
            "camoSet": ["solidCamoImage", "patternCamoImage", "patternOffset", "patternScale"],
            "material": ["useColorMap", "useNormalMap", "useSpecularMap", "materialOverrides", "shaderConsts"],
            "materialOverride": ["baseMaterial", "camoMaterial"],
        },
        "equipStateContract": {
            "canonicalBaseWeaponImmutable": True,
            "selectedAttachments": "ordered retail-valid attachment identities plus exact per-weapon attachment-unique identities",
            "selectedCamo": "zero or one exact WeaponCamo identity unless retail semantics prove a different cardinality",
            "rawAuthoredModifiersAlwaysPreserved": True,
            "effectiveStatDerivation": "fail_closed_until_runtime_application_semantics_are_source_closed",
            "camoMaterialApplication": "preserve exact WeaponCamo material overrides, replacement flags, camo sets and shader constants; no generic-PBR reinterpretation without shader proof",
        },
        "proofBoundary": (
            "This contract closes source field/schema identity only. Names ending in Scale/Reduction/Override do not by themselves prove runtime arithmetic, order, clamping, attachment precedence or interaction. "
            "The future equip resolver must retain canonical base values and raw attachment values even when effective-value derivation is blocked. WeaponCamo schema identity is closed, but the all-retail camo population and per-weapon validity graph are separate census/ownership tasks."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attachment-fields", type=Path, required=True)
    ap.add_argument("--attachment-unique-fields", type=Path, required=True)
    ap.add_argument("--weapon-camo-json", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(
        args.attachment_fields.read_bytes(),
        args.attachment_unique_fields.read_bytes(),
        args.weapon_camo_json.read_bytes(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
