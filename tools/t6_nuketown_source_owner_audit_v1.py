#!/usr/bin/env python3
"""Account for every Nuketown Material without guessing duplicate shader owners.

Observes the original OAT outputs from map and support FastFiles. Identical
techniques are source-closed; divergent same-named owners remain conflicts.
Does not imply native GPU execution or try to choose a convenient patch.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import t6_oat_material_shader_census_v1 as v1
import t6_oat_material_shader_census_v3 as v3


def json_hash(item: object) -> str:
    return v3._jhash(item)


def classify_owner_payload(owners: list[tuple[str, str]]) -> tuple[str, str | None]:
    """Pure, strict identity decision. Missing and divergent records fail closed."""
    if not owners:
        return "missing", None
    hashes = {digest for _, digest in owners}
    if len(hashes) != 1:
        return "divergent", None
    return ("unique" if len(owners) == 1 else "identical-duplicates"), next(iter(hashes))


# Source-owned zone priorities, reversed from the retail PC executable.
# Unsupported/unknown owners must not be assigned an ordering.
# Runtime authority: Rust-test/t6_map.rs retail_dependency_zone_priority.
ZONE_PRIORITY = {"patch_mp": 65, "mp_nuketown_2020": 57,
                 "common_mp": 54, "code_post_gfx_mp": 52}


def choose_retail_owner(
    owners: list[tuple[str, str]]
) -> tuple[str, str | None, str | None]:
    status, digest = classify_owner_payload(owners)
    if status != "divergent":
        return status, (owners[0][0] if owners else None), digest
    if any(zone not in ZONE_PRIORITY for zone, _ in owners):
        return "unknown-zone-priority", None, None
    highest = max(ZONE_PRIORITY[zone] for zone, _ in owners)
    winners = [(zone, h) for zone, h in owners if ZONE_PRIORITY[zone] == highest]
    if len({h for _,h in winners}) != 1:
        return "equal-priority-divergence", None, None
    return "retail-priority-selected", winners[0][0], winners[0][1]


def evidence(material_root: Path, roots: list[Path]) -> dict:
    materials, generated = v3._ordinary_materials(material_root)
    techset_cache: dict[str, dict] = {}
    technique_cache: dict[str, dict] = {}
    rows = []
    blocked = Counter()
    impacts: dict[tuple[str, str], set[str]] = defaultdict(set)
    digest_samples = {}
    techniques_per_type = Counter()
    shader_shas: dict[str, set[str]] = defaultdict(set)
    successes = 0
    priority_closed = 0

    def techset_status(name: str) -> dict:
        if name in techset_cache:
            return techset_cache[name]
        locs = [(root.name, root / "techsets" / f"{name}.techset")
                for root in roots if (root / "techsets" / f"{name}.techset").is_file()]
        found = [(owner, v3._sha(p)) for owner, p in locs]
        status, chosen, digest = choose_retail_owner(found)
        outcome = {"identity": name, "status": status, "selectedZone": chosen,
                   "owners": [{"zone": o, "sha256": h, "priority": ZONE_PRIORITY.get(o)}
                              for o, h in found],
                   "sha256": digest, "bindings": []}
        if digest is not None:
            p = next(path for zone, path in locs if zone == chosen)
            parsed, errs = v1.oat.parse_techset(p.read_text(encoding="utf-8"))
            if errs or not parsed:
                outcome["status"] = "invalid"
                outcome["error"] = str(errs[:3]) if errs else "no technique bindings"
            else:
                outcome["bindings"] = parsed
        techset_cache[name] = outcome
        return outcome

    def technique_status(name: str) -> dict:
        if name in technique_cache:
            return technique_cache[name]
        locs = [root for root in roots
                if (root / "techniques" / f"{name}.tech").is_file()]
        found = []
        parsed_by_zone = {}
        errors = []
        for owner in locs:
            try:
                passes, _file = v3._parse_passes_from_owner(owner, name)
                digest = json_hash(passes)
                found.append((owner.name, digest))
                parsed_by_zone[owner.name] = passes
            except Exception as exc:
                errors.append(f"{owner.name}: {type(exc).__name__}: {exc}")
        status, chosen, digest = choose_retail_owner(found)
        if errors:
            status = "invalid"
        outcome = {"identity": name, "status": status, "selectedZone": chosen,
                   "owners": [{"zone": o, "passSha256": h, "priority": ZONE_PRIORITY.get(o)}
                              for o, h in found],
                   "passSha256": digest, "errors": errors,
                   "passes": parsed_by_zone[chosen] if digest is not None and chosen is not None else []}
        technique_cache[name] = outcome
        return outcome

    for item in materials:
        material_name = str(item["material"])
        ts_name = str(item.get("techniqueSet") or "")
        ts = techset_status(ts_name)
        reasons = []
        shader_refs = []
        type_names = set()
        if ts["status"] not in {"unique", "identical-duplicates", "retail-priority-selected"}:
            reasons.append(f"techset:{ts_name}:{ts['status']}")
            impacts[("techset", ts_name)].add(material_name)
        else:
            for binding in ts["bindings"]:
                tech = str(binding.get("technique") or "")
                t = technique_status(tech)
                names = [str(v) for v in binding.get("types", [])]
                type_names.update(names)
                if t["status"] not in {"unique", "identical-duplicates", "retail-priority-selected"}:
                    reasons.append(f"technique:{tech}:{t['status']}")
                    impacts[("technique", tech)].add(material_name)
                    continue
                for type_name in names:
                    techniques_per_type[type_name] += 1
                for p in t["passes"]:
                    for stage in p["stages"]:
                        shader_shas[stage["kind"]].add(stage["sha256"])
                        shader_refs.append({"technique": tech, "stage": stage["kind"],
                                            "sha256": stage["sha256"], "pass": p["index"]})
        if reasons:
            for r in sorted(set(reasons)):
                blocked[r.split(":")[-1]] += 1
        else:
            successes += 1
            if ts["status"] == "retail-priority-selected" or any(
                technique_status(str(b.get("technique") or ""))["status"] == "retail-priority-selected"
                for b in ts["bindings"]
            ):
                priority_closed += 1
        rows.append({"material": material_name, "techniqueSet": ts_name,
                     "techsetStatus": ts["status"], "techniqueTypes": sorted(type_names),
                     "sourceIdentityClosed": not reasons,
                     "blockers": sorted(set(reasons)),
                     "reachedShaderStages": shader_refs})
    impact_rows = []
    for (kind, identity), affected in impacts.items():
        details = (techset_cache if kind == "techset" else technique_cache)[identity]
        impact_rows.append({"kind": kind, "name": identity,
                            "status": details["status"],
                            "materialCount": len(affected),
                            "affectedMaterials": sorted(affected),
                            "owners": details["owners"],
                            "parseErrors": details.get("errors", [])})
    impact_rows.sort(key=lambda r: (-r["materialCount"], r["kind"], r["name"]))
    return {
        "format": "t6-retail-nuketown-source-ownership-audit-v1",
        "proofBoundary": "Only exact OAT source Material -> TechniqueSet -> Technique -> emitted shader SHA-256. Divergent owners are source-selected only under recovered zone priorities (patch_mp=65, world map=57, common_mp=54, code_post_gfx_mp=52); owners such as common_patch_mp with unknown priority remain withheld. No executable shader/lighting parity asserted.",
        "retailZonePriority": ZONE_PRIORITY,
        "summary": {
            "ordinaryMaterials": len(materials),
            "generatedMaterialsExcluded": len(generated),
            "ordinaryWithSourceSelectedShaderIdentity": successes,
            "ordinaryRequiringRetailZonePriority": priority_closed,
            "ordinaryBlockedByOwnershipOrMissingPayload": len(materials) - successes,
            "blockerKinds": dict(sorted(blocked.items())),
            "distinctReferencedTechniqueSets": len(techset_cache),
            "distinctReferencedTechniques": len(technique_cache),
            "uniqueShaderStageCountsOnUnambiguousPaths":
                {k: len(v) for k, v in sorted(shader_shas.items())},
            "techniqueTypeUsesOnUnambiguousPaths": dict(sorted(techniques_per_type.items())),
        },
        "materialRows": rows,
        "ownerConflictsAndMissing": impact_rows,
        "techniqueSets": list(techset_cache.values()),
        "techniques": [{k: v for k,v in obj.items() if k != "passes"}
                       for obj in technique_cache.values()],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--map-root", type=Path, required=True)
    p.add_argument("--shader-root", type=Path, action="append", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    doc = evidence(args.map_root, args.shader_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print("TOP OWNER GAPS")
    for row in doc["ownerConflictsAndMissing"][:30]:
        print(f"{row['materialCount']:4d} {row['kind']:<10} {row['status']:<11} {row['name']}")


if __name__ == "__main__":
    main()
