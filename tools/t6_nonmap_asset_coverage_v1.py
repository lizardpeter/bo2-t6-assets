#!/usr/bin/env python3
"""Build a measurable non-map T6 XAsset extraction coverage report.

Consumes JSON inventories emitted by tools/t6_raw_xasset_inventory.py and maps
every T6 XAsset class to the strongest currently retained extraction family.
Unsupported classes remain explicit and can never disappear into an "other"
bucket.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

FORMAT = "t6-nonmap-asset-coverage-v1"

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

# Status is intentionally conservative. "usable" means a retained,
# production-oriented decoder/export path exists for a meaningful standalone
# form. It does not imply universal P8 closure.
REGISTRY = {
    "XANIMPARTS": ("animation", "usable",
        ["tools/t6_xanim_normalize_v1.py", "tools/t6_xanim_skinned_gltf_export_v7.py"]),
    "XMODEL": ("model", "usable",
        ["tools/t6_xmodel_mesh_normalize_v1.py", "tools/t6_xmodel_skeleton_normalize_v2.py",
         "tools/t6_xanim_skinned_gltf_export_v7.py"]),
    "MATERIAL": ("material", "usable",
        ["tools/t6_oat_material_manifest_v3.py", "tools/t6_oat_material_manifest_v4.py"]),
    "IMAGE": ("texture", "usable", ["tools/t6_dds_texture_stage_v2.py"]),
    "WEAPON_VARIANT": ("weapon-definition", "partial", ["tools/t6_raw_xasset_inventory.py"]),
    "WEAPON": ("weapon-definition", "partial", []),
    "WEAPONDEF": ("weapon-definition", "partial", []),
    "WEAPON_FULL": ("weapon-definition", "partial", []),
    "ATTACHMENT": ("weapon-definition", "partial", []),
    "ATTACHMENT_UNIQUE": ("weapon-definition", "partial", []),
    "WEAPON_CAMO": ("weapon-definition", "partial", []),
    "TRACER": ("weapon-definition", "partial", []),
    "MPBODY": ("character-definition", "inventory-only", []),
    "MPHEAD": ("character-definition", "inventory-only", []),
    "CHARACTER": ("character-definition", "inventory-only", []),
    "AITYPE": ("character-definition", "inventory-only", []),
    "MPTYPE": ("character-definition", "inventory-only", []),
    "XMODELALIAS": ("character-definition", "inventory-only", []),
    "VEHICLEDEF": ("vehicle-definition", "inventory-only", []),
    "FX": ("fx", "partial", []),
    "IMPACT_FX": ("fx", "partial", []),
    "SOUND": ("audio", "partial", []),
    "SOUND_PATCH": ("audio", "partial", []),
    "SNDDRIVER_GLOBALS": ("audio", "inventory-only", []),
    "RAWFILE": ("script-data", "inventory-only", []),
    "STRINGTABLE": ("script-data", "inventory-only", []),
    "LOCALIZE_ENTRY": ("script-data", "inventory-only", []),
    "SCRIPTPARSETREE": ("script-data", "inventory-only", []),
    "KEYVALUEPAIRS": ("script-data", "inventory-only", []),
    "DDL": ("script-data", "inventory-only", []),
    "UI_MAP": ("ui", "inventory-only", []),
    "FONT": ("ui", "inventory-only", []),
    "FONTICON": ("ui", "inventory-only", []),
    "MENULIST": ("ui", "inventory-only", []),
    "MENU": ("ui", "inventory-only", []),
    "EMBLEMSET": ("ui", "inventory-only", []),
    "PHYSPRESET": ("physics", "inventory-only", []),
    "PHYSCONSTRAINTS": ("physics", "inventory-only", []),
    "DESTRUCTIBLEDEF": ("physics", "partial", []),
    "SKINNEDVERTS": ("model", "inventory-only", []),
    "FOOTSTEP_TABLE": ("audio-fx", "inventory-only", []),
    "FOOTSTEPFX_TABLE": ("audio-fx", "inventory-only", []),
    "ZBARRIER": ("gameplay-definition", "inventory-only", []),
}

MAP_ONLY = {
    "CLIPMAP", "CLIPMAP_PVS", "COMWORLD", "GAMEWORLD_SP", "GAMEWORLD_MP",
    "MAP_ENTS", "GFXWORLD", "LIGHT_DEF", "ADDON_MAP_ENTS",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_inventory(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: inventory must be an object")
    counts = doc.get("asset_type_counts")
    if not isinstance(counts, dict):
        raise ValueError(f"{path}: missing asset_type_counts")
    unknown = sorted(set(counts) - set(ASSET_TYPES))
    if unknown:
        raise ValueError(f"{path}: unknown asset types {unknown}")
    return doc


def classification(asset_type: str) -> tuple[str, str, list[str]]:
    if asset_type in MAP_ONLY:
        return "map", "handled-by-map-track", []
    return REGISTRY.get(asset_type, ("unclassified", "open", []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inventories", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    total = Counter()
    sources = []
    per_type_sources = defaultdict(list)
    for path in args.inventories:
        doc = load_inventory(path)
        counts = Counter({k: int(v) for k, v in doc["asset_type_counts"].items()})
        total.update(counts)
        sources.append({
            "path": str(path),
            "sha256": sha256(path),
            "expandedSha256": doc.get("expanded_sha256"),
            "assetCount": int(doc.get("asset_count", sum(counts.values()))),
            "assetTypeCount": sum(1 for v in counts.values() if v),
        })
        for k, v in counts.items():
            if v:
                per_type_sources[k].append({"path": str(path), "count": v})

    rows = []
    status_counts = Counter()
    category_counts = Counter()
    nonmap_assets = 0
    for asset_type in ASSET_TYPES:
        count = int(total.get(asset_type, 0))
        category, status, tools = classification(asset_type)
        if asset_type not in MAP_ONLY:
            nonmap_assets += count
        if count:
            status_counts[status] += count
            category_counts[category] += count
        rows.append({
            "assetType": asset_type,
            "count": count,
            "category": category,
            "status": status,
            "tools": tools,
            "observedIn": per_type_sources.get(asset_type, []),
        })

    unresolved = [
        r["assetType"] for r in rows
        if r["count"] and r["assetType"] not in MAP_ONLY and r["status"] in {"open", "inventory-only"}
    ]
    priority = [
        r["assetType"] for r in rows
        if r["count"] and r["assetType"] not in MAP_ONLY and r["status"] != "usable"
    ]

    out = {
        "format": FORMAT,
        "goal": "Make every non-map T6 XAsset class measurable until all observed classes have deterministic extraction and retained retail proof.",
        "rules": {
            "everyKnownT6AssetTypeListed": True,
            "unsupportedTypesRemainExplicit": True,
            "mapTrackSeparatedButNotDiscarded": True,
            "countsAreOccurrencesAcrossSuppliedZoneInventories": True,
            "usableDoesNotMeanP8UniversalClosure": True,
        },
        "sourceInventories": sources,
        "summary": {
            "inventoryFiles": len(sources),
            "assetOccurrences": sum(total.values()),
            "nonMapAssetOccurrences": nonmap_assets,
            "observedAssetTypes": sum(1 for r in rows if r["count"]),
            "unresolvedObservedNonMapTypes": unresolved,
            "priorityObservedNonMapTypes": priority,
            "statusOccurrenceCounts": dict(sorted(status_counts.items())),
            "categoryOccurrenceCounts": dict(sorted(category_counts.items())),
        },
        "assetTypes": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
