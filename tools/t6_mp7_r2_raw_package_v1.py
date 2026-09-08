#!/usr/bin/env python3
"""Build an R2-authoritative raw MP7 package/diff from native OAT records.

This adapter intentionally separates current retail values from runtime semantic
interpretation. It consumes only native records produced from SHA-pinned R2
FastFiles. Legacy dedicated-server/PDB-derived formulas are not evaluated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT = "t6-mp7-r2-raw-package-v1"
ZONES = ("common_mp", "common_patch_mp", "patch_mp")
FF_SHA = {
    "common_mp": "93fe48b0f0d8cc6844be875ccad94e0cfcf635f62eeff00ac33f2f668a77cb77",
    "common_patch_mp": "95622d93d4fb761db311a123cd073bed34ea48c9c711d2c11bce4170dd08bae9",
    "patch_mp": "459077cda8e4a1457f7ee7d8f6c5e0abf30f41767a21ff6744df6a4307cbce1e",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_info_rows(path: Path, header: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(header + "\\"):
        raise ValueError(f"{path}: expected {header!r} header")
    parts = text[len(header) + 1 :].split("\\")
    if len(parts) % 2:
        raise ValueError(f"{path}: odd InfoString token count {len(parts)}")
    occurrence: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for i in range(0, len(parts), 2):
        name, value = parts[i], parts[i + 1]
        rows.append(
            {
                "rowIndex": len(rows),
                "name": name,
                "nameOccurrence": occurrence[name],
                "value": value,
            }
        )
        occurrence[name] += 1
    return rows


def row_identity(row: dict[str, Any]) -> tuple[str, int]:
    return row["name"], int(row["nameOccurrence"])


def require_same_row_identity(a: list[dict[str, Any]], b: list[dict[str, Any]], label: str) -> None:
    ia = [row_identity(r) for r in a]
    ib = [row_identity(r) for r in b]
    if ia != ib:
        raise ValueError(f"{label}: emitted row identities/order diverge")


def diffs(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    require_same_row_identity(a, b, "diff")
    out = []
    for ra, rb in zip(a, b):
        if ra["value"] != rb["value"]:
            out.append(
                {
                    "rowIndex": ra["rowIndex"],
                    "name": ra["name"],
                    "nameOccurrence": ra["nameOccurrence"],
                    "commonMp": ra["value"],
                    "commonPatchMp": rb["value"],
                }
            )
    return out


def unique_value(rows: list[dict[str, Any]], name: str) -> str:
    found = [r["value"] for r in rows if r["name"] == name]
    if len(found) != 1:
        raise ValueError(f"{name}: expected one emitted value, got {len(found)}")
    return found[0]


def attachment_candidates(package: Path, name: str) -> list[dict[str, Any]]:
    found = []
    for zone in ZONES:
        path = package / zone / "attachment" / "attachment" / name
        if not path.is_file():
            continue
        rows = parse_info_rows(path, "ATTACHMENTFILE")
        found.append(
            {
                "zone": zone,
                "path": path.relative_to(package).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows": rows,
            }
        )
    return found


def build(package: Path) -> dict[str, Any]:
    weapon_paths = {
        "common_mp": package / "common_mp/weapon/weapons/mp7_mp",
        "common_patch_mp": package / "common_patch_mp/weapon/weapons/mp7_mp",
    }
    if not all(p.is_file() for p in weapon_paths.values()):
        raise ValueError("both exact MP7 weapon physical copies are required")

    weapon_rows = {z: parse_info_rows(p, "WEAPONFILE") for z, p in weapon_paths.items()}
    require_same_row_identity(weapon_rows["common_mp"], weapon_rows["common_patch_mp"], "MP7 weapon")
    weapon_diffs = diffs(weapon_rows["common_mp"], weapon_rows["common_patch_mp"])

    weapon_attachment_names = {
        z: unique_value(rows, "attachments").splitlines() for z, rows in weapon_rows.items()
    }
    changed_attachment_names = {
        "removedFromCommonPatchMp": sorted(set(weapon_attachment_names["common_mp"]) - set(weapon_attachment_names["common_patch_mp"])),
        "addedInCommonPatchMp": sorted(set(weapon_attachment_names["common_patch_mp"]) - set(weapon_attachment_names["common_mp"])),
    }

    relevant_attachment_names = sorted(set().union(*weapon_attachment_names.values()))
    attachment_records = []
    for name in relevant_attachment_names:
        copies = attachment_candidates(package, name)
        if not copies:
            raise ValueError(f"attachment {name!r}: no physical copy in retained owner universe")
        copy_diffs = []
        if len(copies) >= 2:
            base = copies[0]
            for other in copies[1:]:
                require_same_row_identity(base["rows"], other["rows"], f"attachment {name}")
                ds = diffs(base["rows"], other["rows"])
                if ds:
                    copy_diffs.append({"fromZone": base["zone"], "toZone": other["zone"], "fieldDiffs": ds})
        attachment_records.append(
            {
                "name": name,
                "referencedByWeaponCopies": [z for z, names in weapon_attachment_names.items() if name in names],
                "physicalCopies": copies,
                "copyDiffs": copy_diffs,
            }
        )

    au_by_zone: dict[str, dict[str, Path]] = {}
    for zone in ("common_mp", "common_patch_mp"):
        d = package / zone / "attachmentunique/attachmentunique"
        au_by_zone[zone] = {p.name: p for p in sorted(d.glob("au_mp7_*")) if p.is_file()}
    if set(au_by_zone["common_mp"]) != set(au_by_zone["common_patch_mp"]):
        raise ValueError("MP7 AttachmentUnique identity set differs across common/common_patch")
    if len(au_by_zone["common_mp"]) != 15:
        raise ValueError(f"expected 15 exact MP7 AU identities, got {len(au_by_zone['common_mp'])}")

    au_records = []
    divergent_au = 0
    for name in sorted(au_by_zone["common_mp"]):
        cp = au_by_zone["common_mp"][name]
        pp = au_by_zone["common_patch_mp"][name]
        cr = parse_info_rows(cp, "ATTACHMENTUNIQUEFILE")
        pr = parse_info_rows(pp, "ATTACHMENTUNIQUEFILE")
        require_same_row_identity(cr, pr, name)
        ds = diffs(cr, pr)
        if ds:
            divergent_au += 1
        au_records.append(
            {
                "name": name,
                "byteIdenticalAcrossCopies": sha256(cp) == sha256(pp),
                "fieldDiffs": ds,
                "copies": [
                    {"zone": "common_mp", "bytes": cp.stat().st_size, "sha256": sha256(cp), "rows": cr},
                    {"zone": "common_patch_mp", "bytes": pp.stat().st_size, "sha256": sha256(pp), "rows": pr},
                ],
            }
        )

    camo_paths = {
        "common_mp": package / "common_mp/camo/camo/camo_mp7.json",
        "common_patch_mp": package / "common_patch_mp/camo/camo/camo_mp7.json",
    }
    camo = {z: json.loads(p.read_text(encoding="utf-8")) for z, p in camo_paths.items()}
    for z, d in camo.items():
        if d.get("_game") != "t6" or d.get("_type") != "weaponCamo":
            raise ValueError(f"{z}: unexpected camo header")
    set_diffs = []
    for i in range(max(len(camo["common_mp"]["camoSets"]), len(camo["common_patch_mp"]["camoSets"]))):
        a = camo["common_mp"]["camoSets"][i] if i < len(camo["common_mp"]["camoSets"]) else None
        b = camo["common_patch_mp"]["camoSets"][i] if i < len(camo["common_patch_mp"]["camoSets"]) else None
        if a != b:
            set_diffs.append({"index": i, "commonMp": a, "commonPatchMp": b})
    mat_diffs = []
    for i in range(max(len(camo["common_mp"]["camoMaterials"]), len(camo["common_patch_mp"]["camoMaterials"]))):
        a = camo["common_mp"]["camoMaterials"][i] if i < len(camo["common_mp"]["camoMaterials"]) else None
        b = camo["common_patch_mp"]["camoMaterials"][i] if i < len(camo["common_patch_mp"]["camoMaterials"]) else None
        if a != b:
            mat_diffs.append({"index": i, "commonMp": a, "commonPatchMp": b})

    return {
        "format": FORMAT,
        "authority": {
            "rawRetailValue": "native OAT records decoded from SHA-pinned r2.houseofkublai.com retail FastFiles",
            "legacyServerPdb": "guidance_only_not_used_to_compute_any_value_in_this_manifest",
            "runtimeWinnerSelected": False,
        },
        "sourceFastFiles": {f"{k}.ff": v for k, v in FF_SHA.items()},
        "weapon": {
            "physicalCopies": [
                {
                    "zone": z,
                    "path": p.relative_to(package).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": sha256(p),
                    "rows": weapon_rows[z],
                }
                for z, p in weapon_paths.items()
            ],
            "emittedFieldRowCount": len(weapon_rows["common_mp"]),
            "fieldDiffCount": len(weapon_diffs),
            "fieldDiffs": weapon_diffs,
            "attachmentLists": weapon_attachment_names,
            "attachmentListDelta": changed_attachment_names,
        },
        "attachments": {
            "relevantIdentityCount": len(relevant_attachment_names),
            "records": attachment_records,
        },
        "attachmentUnique": {
            "identityCount": len(au_records),
            "physicalCopyCount": 2 * len(au_records),
            "divergentIdentityCount": divergent_au,
            "records": au_records,
        },
        "camo": {
            "physicalCopies": [
                {
                    "zone": z,
                    "path": p.relative_to(package).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": sha256(p),
                    "camoSetCount": len(camo[z]["camoSets"]),
                    "camoMaterialSetCount": len(camo[z]["camoMaterials"]),
                    "payload": camo[z],
                }
                for z, p in camo_paths.items()
            ],
            "camoSetDiffCount": len(set_diffs),
            "camoSetDiffs": set_diffs,
            "camoMaterialDiffCount": len(mat_diffs),
            "camoMaterialDiffs": mat_diffs,
        },
        "summary": {
            "weaponPhysicalCopies": 2,
            "weaponFieldRowsPerCopy": len(weapon_rows["common_mp"]),
            "weaponFieldDiffCount": len(weapon_diffs),
            "weaponAttachmentIdentityCountCommonMp": len(weapon_attachment_names["common_mp"]),
            "weaponAttachmentIdentityCountCommonPatchMp": len(weapon_attachment_names["common_patch_mp"]),
            "mp7AttachmentUniqueIdentityCount": len(au_records),
            "mp7AttachmentUniquePhysicalCopyCount": 2 * len(au_records),
            "mp7AttachmentUniqueDivergentIdentityCount": divergent_au,
            "commonMpCamoSets": len(camo["common_mp"]["camoSets"]),
            "commonPatchMpCamoSets": len(camo["common_patch_mp"]["camoSets"]),
            "commonMpCamoMaterialSets": len(camo["common_mp"]["camoMaterials"]),
            "commonPatchMpCamoMaterialSets": len(camo["common_patch_mp"]["camoMaterials"]),
        },
        "proofBoundary": (
            "This manifest reports exact physical current-retail authored records and cross-copy diffs only. "
            "It does not choose common_mp versus common_patch_mp as the active retail-client winner and does not evaluate any legacy-server-derived attachment arithmetic."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.package_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print("weaponFieldDiffs")
    for row in doc["weapon"]["fieldDiffs"]:
        print(row["name"], repr(row["commonMp"]), "->", repr(row["commonPatchMp"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
