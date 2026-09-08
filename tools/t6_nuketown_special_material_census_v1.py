#!/usr/bin/env python3
"""Close the finite Nuketown special-world-material tail against the native OAT census.

This adapter consumes two already-proven evidence layers:

* the retained five-map special-family manifest, which identifies the exact
  TechniqueSet families used by mp_nuketown_2020; and
* the complete native OAT Material -> TechniqueSet -> Technique -> pass ->
  shader census produced under the exact PC dedicated-server parent precedence
  proof.

It does not infer shader semantics from names.  It only narrows the complete
Nuketown census to the seven exact special TechniqueSets / eleven Material uses,
retains every declared technique type and exact pass/state/shader identity, and
reports whether any selected parent belongs to the separately unresolved
retail-client duplicate-parent set.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-material-census-v1"
SOURCE_CENSUS_FORMAT = "t6-oat-material-shader-census-pc-server-projection-v1"
SOURCE_FAMILY_FORMAT = "t6-retail-special-material-family-census-v1"
MAP = "mp_nuketown_2020"
EXPECTED_USE_COUNT = 11
EXPECTED_TECHNIQUE_SET_COUNT = 7
EXPECTED_FAMILY_USE_COUNTS = {
    "rawnormal_special": 1,
    "shadowcaster": 2,
    "unlit": 8,
}


class NuketownSpecialCensusError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise NuketownSpecialCensusError(f"expected object in {path}")
    return obj


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _map_special_techsets(family_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if family_doc.get("format") != SOURCE_FAMILY_FORMAT:
        raise NuketownSpecialCensusError(f"unexpected family format {family_doc.get('format')!r}")
    out: dict[str, dict[str, Any]] = {}
    for row in family_doc.get("specialTechniqueSets", []):
        maps = row.get("maps", {})
        if not isinstance(maps, dict):
            raise NuketownSpecialCensusError("special TechniqueSet maps field is not an object")
        count = int(maps.get(MAP, 0) or 0)
        if not count:
            continue
        name = str(row.get("techniqueSet") or "")
        family = str(row.get("family") or "")
        if not name or not family or name in out:
            raise NuketownSpecialCensusError(f"invalid/duplicate special TechniqueSet row {row}")
        examples = [
            str(x.get("material") or "")
            for x in row.get("examples", [])
            if isinstance(x, dict) and x.get("map") == MAP and x.get("material")
        ]
        out[name] = {
            "techniqueSet": name,
            "family": family,
            "expectedMaterialUseCount": count,
            "manifestExamples": sorted(examples),
        }
    if len(out) != EXPECTED_TECHNIQUE_SET_COUNT:
        raise NuketownSpecialCensusError(
            f"{MAP}: special TechniqueSet count {len(out)} != {EXPECTED_TECHNIQUE_SET_COUNT}"
        )
    use_counts = collections.Counter()
    total = 0
    for row in out.values():
        use_counts[row["family"]] += row["expectedMaterialUseCount"]
        total += row["expectedMaterialUseCount"]
    if total != EXPECTED_USE_COUNT:
        raise NuketownSpecialCensusError(f"{MAP}: special use count {total} != {EXPECTED_USE_COUNT}")
    if dict(sorted(use_counts.items())) != EXPECTED_FAMILY_USE_COUNTS:
        raise NuketownSpecialCensusError(f"{MAP}: family use counts changed: {dict(use_counts)}")
    return out


def build(census_doc: dict[str, Any], family_doc: dict[str, Any]) -> dict[str, Any]:
    if census_doc.get("format") != SOURCE_CENSUS_FORMAT:
        raise NuketownSpecialCensusError(f"unexpected census format {census_doc.get('format')!r}")
    if census_doc.get("authoritativeForPcDedicatedServerBuild") is not True:
        raise NuketownSpecialCensusError("source census is not exact PC-server authority")
    if census_doc.get("authoritativeForRetailClient") is not False:
        raise NuketownSpecialCensusError("source census retail-client boundary changed")
    if int(census_doc.get("summary", {}).get("unresolvedMaterialCount", -1)) != 0:
        raise NuketownSpecialCensusError("source census is not fully resolved")

    special = _map_special_techsets(family_doc)
    group_by_key = {
        str(row.get("groupKey")): row
        for row in census_doc.get("shaderGroups", [])
        if isinstance(row, dict) and row.get("groupKey")
    }
    materials = [
        row for row in census_doc.get("materials", [])
        if isinstance(row, dict) and str(row.get("techniqueSet") or "") in special
    ]
    if len(materials) != EXPECTED_USE_COUNT:
        raise NuketownSpecialCensusError(
            f"native special Material count {len(materials)} != {EXPECTED_USE_COUNT}"
        )

    duplicate_selection_by_name = {
        str(row.get("name")): row
        for row in census_doc.get("pcServerTechniqueSetSelections", [])
        if isinstance(row, dict) and row.get("name")
    }

    use_counts = collections.Counter()
    techset_materials: dict[str, list[str]] = collections.defaultdict(list)
    technique_type_uses = collections.Counter()
    shader_hashes: dict[str, set[str]] = collections.defaultdict(set)
    referenced_group_keys: set[str] = set()
    output_materials = []

    for material in sorted(materials, key=lambda row: str(row.get("material") or "")):
        name = str(material.get("material") or "")
        techset = str(material.get("techniqueSet") or "")
        meta = special[techset]
        family = meta["family"]
        use_counts[family] += 1
        techset_materials[techset].append(name)
        programs_out = []
        for program in material.get("programs", []):
            if not isinstance(program, dict):
                raise NuketownSpecialCensusError(f"{name}: invalid program row")
            group_key = str(program.get("groupKey") or "")
            if group_key not in group_by_key:
                raise NuketownSpecialCensusError(f"{name}: missing exact shader group {group_key!r}")
            group = group_by_key[group_key]
            if techset not in group.get("techniqueSets", []):
                raise NuketownSpecialCensusError(f"{name}: shader group does not retain TechniqueSet {techset}")
            type_name = str(program.get("techniqueType") or "")
            technique_type_uses[type_name] += 1
            referenced_group_keys.add(group_key)
            pass_rows = group.get("passes", [])
            if int(program.get("passCount", -1)) != len(pass_rows):
                raise NuketownSpecialCensusError(f"{name}: pass count disagrees with exact group")
            for p in pass_rows:
                for stage in p.get("stages", []):
                    kind = str(stage.get("kind") or "")
                    hh = str(stage.get("sha256") or "").lower()
                    if not kind or len(hh) != 64:
                        raise NuketownSpecialCensusError(f"{name}: malformed exact shader stage {stage}")
                    shader_hashes[kind].add(hh)
            programs_out.append({
                "techniqueType": type_name,
                "technique": str(program.get("technique") or ""),
                "groupKey": group_key,
                "passStageIdentitySha256": str(program.get("passStageIdentitySha256") or ""),
                "passCount": len(pass_rows),
                "techniqueOwner": str(program.get("techniqueOwner") or ""),
            })
        output_materials.append({
            "material": name,
            "family": family,
            "techniqueSet": techset,
            "techniqueSetOwners": list(material.get("techniqueSetOwners", [])),
            "declaredTechniqueTypes": list(material.get("declaredTechniqueTypes", [])),
            "hasLitBinding": bool(material.get("hasLitBinding")),
            "programs": programs_out,
            "dependsOnPcServerDuplicateParentSelection": techset in duplicate_selection_by_name,
        })

    if dict(sorted(use_counts.items())) != EXPECTED_FAMILY_USE_COUNTS:
        raise NuketownSpecialCensusError(f"native family use counts changed: {dict(use_counts)}")
    for techset, meta in special.items():
        actual = len(techset_materials.get(techset, []))
        if actual != meta["expectedMaterialUseCount"]:
            raise NuketownSpecialCensusError(
                f"{techset}: native Material use count {actual} != retained-world manifest {meta['expectedMaterialUseCount']}"
            )

    groups = [group_by_key[key] for key in sorted(referenced_group_keys)]
    duplicate_special = [
        duplicate_selection_by_name[name]
        for name in sorted(special)
        if name in duplicate_selection_by_name
    ]
    techset_rows = []
    for name in sorted(special):
        row = dict(special[name])
        row["materials"] = sorted(techset_materials[name])
        row["dependsOnPcServerDuplicateParentSelection"] = name in duplicate_selection_by_name
        techset_rows.append(row)

    compact_groups = []
    for group in groups:
        compact_groups.append({
            "groupKey": group["groupKey"],
            "techniqueType": group.get("techniqueType"),
            "passStageIdentitySha256": group.get("passStageIdentitySha256"),
            "techniqueSets": [x for x in group.get("techniqueSets", []) if x in special],
            "techniques": list(group.get("techniques", [])),
            "passes": group.get("passes", []),
        })

    summary = {
        "specialMaterialUseCount": len(output_materials),
        "specialTechniqueSetCount": len(special),
        "familyUseCounts": dict(sorted(use_counts.items())),
        "referencedExactTechniqueTypeShaderGroupCount": len(compact_groups),
        "declaredTechniqueTypeUseCounts": dict(sorted(technique_type_uses.items())),
        "uniqueShaderStageCounts": {kind: len(vals) for kind, vals in sorted(shader_hashes.items())},
        "pcServerDuplicateParentSelectionDependencyCount": len(duplicate_special),
        "retailClientAuthoritativeWinnerCount": 0,
    }
    evidence_digest = _digest({
        "techniqueSets": techset_rows,
        "materials": output_materials,
        "shaderGroups": compact_groups,
        "duplicateSelections": duplicate_special,
    })
    return {
        "format": FORMAT,
        "map": MAP,
        "authority": {
            "physicalRetailFastFileAndPinnedOatEvidence": True,
            "pcDedicatedServerDuplicateParentSelection": True,
            "retailClientDuplicateParentSelection": False,
        },
        "summary": summary,
        "specialTechniqueSets": techset_rows,
        "materials": output_materials,
        "shaderGroups": compact_groups,
        "pcServerDuplicateParentSelections": duplicate_special,
        "evidenceDigestSha256": evidence_digest,
        "proofBoundary": (
            "The retained special-family manifest defines only the finite mp_nuketown_2020 TechniqueSet population/family labels. "
            "Every Material, technique type, child Technique, pass, render-state identifier, vertex routing and shader hash is inherited from the complete pinned-OAT native census. "
            "Duplicate parents, if any, are selected only by the exact PC dedicated-server proof and remain non-authoritative for retail t6mp.exe. "
            "No family label is treated as shader arithmetic and no shader is approximated."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--census", type=Path, required=True)
    p.add_argument(
        "--family-manifest",
        type=Path,
        default=Path("manifests/render/T6_RETAIL_SPECIAL_MATERIAL_FAMILY_CENSUS_V1.json"),
    )
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(_load(a.census), _load(a.family_manifest))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(result["evidenceDigestSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
