#!/usr/bin/env python3
"""Bind native T6 WeaponCamo semantics to exact serialized asset identities.

V1 incorrectly required every nested Image/Material to be a top-level XAsset in
common_mp. T6 asset pointers can instead serialize a referenced asset definition
inline (FOLLOWING/INSERT) and later reuse it through a packed alias. A leading
comma asset name is itself a source semantic: an indirect/reference asset.

This v2 binder therefore identifies each non-null dependency as exactly one of:
  * xassetOrdinal: a top-level XAsset row in this exact expanded XFile;
  * serializedAssetDefinition: a non-reference asset whose first definition is
    source-anchored by expanded-stream byte offset;
  * assetReference: a leading-comma retail reference, retaining the exact
    reference name and its serialized reference-definition site.

Native addresses are proof joins only. They never become canonical identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import defaultdict
from pathlib import Path

from t6_raw_xasset_inventory import ASSET_TYPES, parse_front

IMAGE = ASSET_TYPES.index("IMAGE")
MATERIAL = ASSET_TYPES.index("MATERIAL")
WEAPON_CAMO = ASSET_TYPES.index("WEAPON_CAMO")
RELEVANT = {IMAGE, MATERIAL, WEAPON_CAMO}
PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pointer(text: str) -> int | None:
    if text in {"(nil)", "0", "0x0", "<null>"}:
        return None
    if not text.startswith("0x"):
        raise ValueError(f"bad native pointer token {text!r}")
    value = int(text, 16)
    return value or None


def raw_pointer(text: str) -> int:
    if not text.startswith("0x"):
        raise ValueError(f"bad raw zone-pointer token {text!r}")
    value = int(text, 16)
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"raw zone-pointer outside T6 PC32 range {text!r}")
    return value


def pointer_kind(value: int) -> str:
    if value == 0:
        return "null"
    if value == PTR_FOLLOWING:
        return "following"
    if value == PTR_INSERT:
        return "insert"
    return "offset"


def finite_hex_float(text: str) -> str:
    try:
        value = float.fromhex(text)
    except ValueError as exc:
        raise ValueError(f"bad hex float {text!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"non-finite retail camo float {text!r}")
    return text


def parse_native_log(lines: list[str]) -> tuple[dict, dict, dict, dict, dict, list, list]:
    targets: dict[int, dict] = {}
    roots: dict[int, dict] = {}
    sets = defaultdict(dict)
    material_sets = defaultdict(dict)
    materials = defaultdict(dict)
    overrides = defaultdict(dict)
    violations = []
    asset_load_events = []

    for sequence, line in enumerate(lines):
        if line.startswith("T6_ASSET_LOAD_EVENT"):
            cols = line.split("\t")
            if len(cols) != 5:
                raise ValueError(f"bad ASSET_LOAD_EVENT row: {line}")
            asset_type = int(cols[1])
            if not 0 <= asset_type < len(ASSET_TYPES):
                raise ValueError(f"asset load event has bad type {asset_type}")
            raw = raw_pointer(cols[2])
            serialized_pos = int(cols[3])
            if serialized_pos < 0:
                raise ValueError(f"negative serialized position in ASSET_LOAD_EVENT: {line}")
            asset_load_events.append({
                "sequence": sequence,
                "assetType": asset_type,
                "assetTypeName": ASSET_TYPES[asset_type],
                "rawZonePointer": f"0x{raw:08X}",
                "rawZonePointerKind": pointer_kind(raw),
                "serializedPositionBeforeLoad": serialized_pos,
                "resolvedPointer": cols[4],
            })
            continue

        if not line.startswith("T6_WEAPON_CAMO_"):
            continue
        cols = line.split("\t")
        tag = cols[0]
        if tag == "T6_WEAPON_CAMO_VIOLATION":
            violations.append(cols[1:])
            continue
        if tag == "T6_WEAPON_CAMO_TARGET":
            if len(cols) != 5:
                raise ValueError(f"bad TARGET row: {line}")
            ordinal, asset_type = int(cols[1]), int(cols[2])
            if ordinal in targets:
                raise ValueError(f"duplicate target ordinal {ordinal}")
            targets[ordinal] = {
                "ordinal": ordinal,
                "assetType": asset_type,
                "assetTypeName": ASSET_TYPES[asset_type] if 0 <= asset_type < len(ASSET_TYPES) else None,
                "pointer": cols[3],
                "name": cols[4],
            }
        elif tag == "T6_WEAPON_CAMO_ROOT":
            if len(cols) != 10:
                raise ValueError(f"bad ROOT row: {line}")
            ordinal = int(cols[1])
            if ordinal in roots:
                raise ValueError(f"duplicate camo root ordinal {ordinal}")
            roots[ordinal] = {
                "ordinal": ordinal,
                "pointer": cols[2],
                "name": cols[3],
                "numCamoSets": int(cols[4]),
                "numCamoMaterials": int(cols[5]),
                "solidBaseImagePointer": cols[6],
                "solidBaseImageName": cols[7],
                "patternBaseImagePointer": cols[8],
                "patternBaseImageName": cols[9],
            }
        elif tag == "T6_WEAPON_CAMO_SET":
            if len(cols) != 10:
                raise ValueError(f"bad SET row: {line}")
            ordinal, set_index = int(cols[1]), int(cols[2])
            if set_index in sets[ordinal]:
                raise ValueError(f"duplicate camo set {ordinal}:{set_index}")
            sets[ordinal][set_index] = {
                "index": set_index,
                "solidCamoImagePointer": cols[3],
                "solidCamoImageName": cols[4],
                "patternCamoImagePointer": cols[5],
                "patternCamoImageName": cols[6],
                "patternOffsetHex": [finite_hex_float(cols[7]), finite_hex_float(cols[8])],
                "patternScaleHex": finite_hex_float(cols[9]),
            }
        elif tag == "T6_WEAPON_CAMO_MATERIAL_SET":
            if len(cols) != 4:
                raise ValueError(f"bad MATERIAL_SET row: {line}")
            ordinal, set_index = int(cols[1]), int(cols[2])
            if set_index in material_sets[ordinal]:
                raise ValueError(f"duplicate material set {ordinal}:{set_index}")
            material_sets[ordinal][set_index] = {"index": set_index, "numMaterials": int(cols[3])}
        elif tag == "T6_WEAPON_CAMO_MATERIAL":
            if len(cols) != 14:
                raise ValueError(f"bad MATERIAL row: {line}")
            ordinal, set_index, material_index = map(int, cols[1:4])
            key = (set_index, material_index)
            if key in materials[ordinal]:
                raise ValueError(f"duplicate camo material {ordinal}:{set_index}:{material_index}")
            flags = int(cols[4])
            if flags & ~0x7:
                raise ValueError(f"unknown WeaponCamoMaterial replaceFlags 0x{flags:X}")
            materials[ordinal][key] = {
                "index": material_index,
                "replaceFlags": flags,
                "useColorMap": bool(flags & 0x1),
                "useNormalMap": bool(flags & 0x2),
                "useSpecularMap": bool(flags & 0x4),
                "numBaseMaterials": int(cols[5]),
                "shaderConstsHex": [finite_hex_float(v) for v in cols[6:14]],
            }
        elif tag == "T6_WEAPON_CAMO_OVERRIDE":
            if len(cols) != 9:
                raise ValueError(f"bad OVERRIDE row: {line}")
            ordinal, set_index, material_index, override_index = map(int, cols[1:5])
            key = (set_index, material_index, override_index)
            if key in overrides[ordinal]:
                raise ValueError(f"duplicate camo override {ordinal}:{key}")
            overrides[ordinal][key] = {
                "index": override_index,
                "baseMaterialPointer": cols[5],
                "baseMaterialName": cols[6],
                "camoMaterialPointer": cols[7],
                "camoMaterialName": cols[8],
            }
        else:
            raise ValueError(f"unknown WeaponCamo trace tag {tag}")

    return targets, roots, sets, material_sets, materials, overrides, violations, asset_load_events


def definition_events_for(asset_type: int, native_ptr: int, events_by_resolved: dict[tuple[int, int], list[dict]]) -> list[dict]:
    candidates = events_by_resolved.get((asset_type, native_ptr), [])
    return [e for e in candidates if e["rawZonePointerKind"] in {"following", "insert"}]


def exact_dependency_identity(
    ptr_text: str,
    name: str,
    expected_type: int,
    role: str,
    anchors_by_pointer: dict[int, dict],
    events_by_resolved: dict[tuple[int, int], list[dict]],
    expanded_bytes: int,
) -> dict | None:
    native_ptr = pointer(ptr_text)
    if native_ptr is None:
        if name != "<null>":
            raise ValueError(f"{role}: null pointer has non-null name {name!r}")
        return None
    if name == "<null>" or not name:
        raise ValueError(f"{role}: non-null pointer has null/empty name")

    candidates = events_by_resolved.get((expected_type, native_ptr), [])
    if not candidates:
        raise ValueError(f"{role}: resolved pointer {ptr_text} has no typed T6 asset-load provenance")
    definitions = definition_events_for(expected_type, native_ptr, events_by_resolved)
    if len(definitions) != 1:
        raise ValueError(
            f"{role}: resolved pointer {ptr_text} has {len(definitions)} serialized definition events; expected exactly one"
        )
    definition = definitions[0]
    source_offset = definition["serializedPositionBeforeLoad"]
    if not 0 <= source_offset < expanded_bytes:
        raise ValueError(f"{role}: definition serialized offset {source_offset} outside expanded stream")

    anchor = anchors_by_pointer.get(native_ptr)
    if anchor is not None:
        if anchor["assetType"] != expected_type:
            raise ValueError(f"{role}: local XAsset pointer resolves to wrong type")
        if anchor["name"] != name:
            raise ValueError(f"{role}: local XAsset pointer/name disagreement {name!r} != {anchor['name']!r}")

    base = {
        "role": role,
        "targetAssetType": expected_type,
        "targetAssetTypeName": ASSET_TYPES[expected_type],
        "targetName": name,
        "definitionSerializedOffset": source_offset,
        "definitionRawZonePointer": definition["rawZonePointer"],
        "definitionRawZonePointerKind": definition["rawZonePointerKind"],
        "nativeLoadOccurrenceCount": len(candidates),
    }

    if name.startswith(","):
        referenced = name[1:]
        if not referenced:
            raise ValueError(f"{role}: empty leading-comma asset reference")
        return {
            **base,
            "targetKind": "assetReference",
            "referencedName": referenced,
            "localReferenceXAssetOrdinal": anchor["ordinal"] if anchor is not None else None,
        }

    if anchor is not None:
        return {
            **base,
            "targetKind": "xassetOrdinal",
            "targetOrdinal": anchor["ordinal"],
        }

    return {
        **base,
        "targetKind": "serializedAssetDefinition",
        "definitionIdentity": {
            "assetType": expected_type,
            "serializedOffset": source_offset,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--native-log", type=Path, required=True)
    ap.add_argument("--oat-commit", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    expanded = args.expanded.read_bytes()
    front = parse_front(expanded)
    asset_count = front["asset_count"]
    asset_array = front["asset_array_raw_offset"]
    raw_types = []
    for ordinal in range(asset_count):
        asset_type, _raw_pointer = struct.unpack_from("<II", expanded, asset_array + ordinal * 8)
        if not 0 <= asset_type < len(ASSET_TYPES):
            raise ValueError(f"bad raw XAsset type {asset_type} at ordinal {ordinal}")
        raw_types.append(asset_type)

    log_bytes = args.native_log.read_bytes()
    lines = log_bytes.decode("utf-8", errors="strict").splitlines()
    targets, roots, sets, material_sets, materials, overrides, violations, asset_load_events = parse_native_log(lines)
    if violations:
        raise ValueError(f"native WeaponCamo structural violations: {violations[:8]}")
    if not asset_load_events:
        raise ValueError("native log contains no serialized T6 asset-load provenance events")

    expected_target_ordinals = {i for i, t in enumerate(raw_types) if t in RELEVANT}
    if set(targets) != expected_target_ordinals:
        missing = sorted(expected_target_ordinals - set(targets))[:20]
        extra = sorted(set(targets) - expected_target_ordinals)[:20]
        raise ValueError(f"relevant target census mismatch missing={missing} extra={extra}")

    anchors_by_pointer: dict[int, dict] = {}
    for ordinal, row in sorted(targets.items()):
        if row["assetType"] != raw_types[ordinal]:
            raise ValueError(f"native/raw type mismatch at ordinal {ordinal}")
        ptr = pointer(row["pointer"])
        if ptr is None:
            raise ValueError(f"relevant XAsset ordinal {ordinal} has null native pointer")
        prior = anchors_by_pointer.get(ptr)
        if prior is not None:
            raise ValueError(f"ambiguous relevant loaded pointer {row['pointer']} at ordinals {prior['ordinal']} and {ordinal}")
        if row["name"] == "<null>":
            raise ValueError(f"relevant XAsset ordinal {ordinal} has null name")
        anchors_by_pointer[ptr] = row

    events_by_resolved: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for event in asset_load_events:
        resolved = pointer(event["resolvedPointer"])
        if resolved is None:
            continue
        events_by_resolved[(event["assetType"], resolved)].append(event)

    expected_camo_ordinals = {i for i, t in enumerate(raw_types) if t == WEAPON_CAMO}
    if set(roots) != expected_camo_ordinals:
        missing = sorted(expected_camo_ordinals - set(roots))
        extra = sorted(set(roots) - expected_camo_ordinals)
        raise ValueError(f"WeaponCamo root census mismatch missing={missing} extra={extra}")

    out_camos = []
    all_dependencies = []
    for ordinal in sorted(expected_camo_ordinals):
        root = roots[ordinal]
        anchor = targets[ordinal]
        if pointer(root["pointer"]) != pointer(anchor["pointer"]) or root["name"] != anchor["name"]:
            raise ValueError(f"WeaponCamo root/anchor mismatch at ordinal {ordinal}")

        deps = []
        for role, pp, nn in (
            ("solidBaseImage", root["solidBaseImagePointer"], root["solidBaseImageName"]),
            ("patternBaseImage", root["patternBaseImagePointer"], root["patternBaseImageName"]),
        ):
            dep = exact_dependency_identity(pp, nn, IMAGE, role, anchors_by_pointer, events_by_resolved, len(expanded))
            if dep is not None:
                deps.append(dep)

        expected_sets = list(range(root["numCamoSets"]))
        if sorted(sets[ordinal]) != expected_sets:
            raise ValueError(f"camo set index mismatch for ordinal {ordinal}")
        set_rows = []
        for i in expected_sets:
            row = dict(sets[ordinal][i])
            row_deps = []
            for role, pp, nn in (
                (f"camoSets[{i}].solidCamoImage", row.pop("solidCamoImagePointer"), row.pop("solidCamoImageName")),
                (f"camoSets[{i}].patternCamoImage", row.pop("patternCamoImagePointer"), row.pop("patternCamoImageName")),
            ):
                dep = exact_dependency_identity(pp, nn, IMAGE, role, anchors_by_pointer, events_by_resolved, len(expanded))
                if dep is not None:
                    row_deps.append(dep)
                    deps.append(dep)
            row["dependencies"] = row_deps
            set_rows.append(row)

        expected_material_sets = list(range(root["numCamoMaterials"]))
        if sorted(material_sets[ordinal]) != expected_material_sets:
            raise ValueError(f"material-set index mismatch for ordinal {ordinal}")
        material_set_rows = []
        for si in expected_material_sets:
            ms = material_sets[ordinal][si]
            expected_materials = list(range(ms["numMaterials"]))
            actual_materials = sorted(mi for s, mi in materials[ordinal] if s == si)
            if actual_materials != expected_materials:
                raise ValueError(f"material index mismatch for ordinal {ordinal} set {si}")
            mat_rows = []
            for mi in expected_materials:
                mat = dict(materials[ordinal][(si, mi)])
                expected_overrides = list(range(mat["numBaseMaterials"]))
                actual_overrides = sorted(oi for s, m, oi in overrides[ordinal] if s == si and m == mi)
                if actual_overrides != expected_overrides:
                    raise ValueError(f"override index mismatch for ordinal {ordinal} set {si} material {mi}")
                override_rows = []
                for oi in expected_overrides:
                    ov = overrides[ordinal][(si, mi, oi)]
                    base = exact_dependency_identity(
                        ov["baseMaterialPointer"], ov["baseMaterialName"], MATERIAL,
                        f"camoMaterials[{si}].materials[{mi}].overrides[{oi}].baseMaterial",
                        anchors_by_pointer, events_by_resolved, len(expanded))
                    camo = exact_dependency_identity(
                        ov["camoMaterialPointer"], ov["camoMaterialName"], MATERIAL,
                        f"camoMaterials[{si}].materials[{mi}].overrides[{oi}].camoMaterial",
                        anchors_by_pointer, events_by_resolved, len(expanded))
                    if base is None or camo is None:
                        raise ValueError(f"required Material override is null at {ordinal}:{si}:{mi}:{oi}")
                    deps.extend((base, camo))
                    override_rows.append({"index": oi, "baseMaterial": base, "camoMaterial": camo})
                mat["overrides"] = override_rows
                mat_rows.append(mat)
            material_set_rows.append({"index": si, "numMaterials": ms["numMaterials"], "materials": mat_rows})

        all_dependencies.extend((ordinal, d) for d in deps)
        out_camos.append({
            "ordinal": ordinal,
            "assetType": WEAPON_CAMO,
            "assetTypeName": "WEAPON_CAMO",
            "name": root["name"],
            "numCamoSets": root["numCamoSets"],
            "numCamoMaterials": root["numCamoMaterials"],
            "dependencies": deps,
            "camoSets": set_rows,
            "camoMaterials": material_set_rows,
        })

    kind_counts = defaultdict(int)
    unique_identities = set()
    for _owner, dep in all_dependencies:
        kind = dep["targetKind"]
        kind_counts[kind] += 1
        if kind == "xassetOrdinal":
            ident = (kind, dep["targetAssetType"], dep["targetOrdinal"])
        elif kind == "serializedAssetDefinition":
            ident = (kind, dep["targetAssetType"], dep["definitionSerializedOffset"])
        elif kind == "assetReference":
            ident = (kind, dep["targetAssetType"], dep["referencedName"], dep["definitionSerializedOffset"])
        else:
            raise AssertionError(kind)
        unique_identities.add(ident)

    result = {
        "format": "T6_OAT_WEAPON_CAMO_SEMANTIC_BINDING_V2",
        "status": "source_closed_native_semantics_and_exact_serialized_dependency_identities",
        "rawDirectFastFileBodyParserComplete": False,
        "semanticPromotionEligibleWithVerifiedConsumer": True,
        "crossZoneReferenceResolutionComplete": False,
        "oatCommit": args.oat_commit,
        "expandedSha256": sha256(expanded),
        "nativeLogSha256": sha256(log_bytes),
        "xassetCount": asset_count,
        "weaponCamoCount": len(out_camos),
        "relevantTopLevelPointerAnchorCount": len(targets),
        "assetLoadEventCount": len(asset_load_events),
        "dependencyOccurrenceCount": len(all_dependencies),
        "uniqueDependencyIdentityCount": len(unique_identities),
        "dependencyKindCounts": dict(sorted(kind_counts.items())),
        "layoutContract": "manifests/runtime/T6_WEAPON_FAMILY_X86_LAYOUT_V1.json",
        "serializationCardinalitySource": "OpenAssetTools src/ZoneCode/Game/T6/XAssets/WeaponCamo.txt at pinned oatCommit",
        "assetPointerSemanticsSource": "OpenAssetTools ZoneLoadTemplate.cpp PrintLoadPtrMethod/LoadMember_Asset at pinned oatCommit",
        "referenceSemanticsSource": "OpenAssetTools XAssetInfoGeneric::IsReference at pinned oatCommit",
        "identityRule": "expandedSha256 + assetType + definitionSerializedOffset for serialized definitions; leading-comma names retain explicit asset-reference semantics; native pointers are proof joins only",
        "camos": out_camos,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "format", "status", "xassetCount", "weaponCamoCount", "assetLoadEventCount",
        "dependencyOccurrenceCount", "uniqueDependencyIdentityCount", "dependencyKindCounts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
