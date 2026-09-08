#!/usr/bin/env python3
from __future__ import annotations

import copy

import t6_nuketown_special_material_census_v1 as mod


def stage(kind: str, hh: str) -> dict:
    return {"kind": kind, "sha256": hh, "asset": kind, "shaderModel": "4.0", "relativeFile": "x", "bytes": 4, "arguments": []}


def make_docs():
    techsets = [
        ("ts_raw", "rawnormal_special", 1),
        ("ts_shadow", "shadowcaster", 2),
        ("ts_u1", "unlit", 1),
        ("ts_u2", "unlit", 1),
        ("ts_u3", "unlit", 1),
        ("ts_u4", "unlit", 2),
        ("ts_u5", "unlit", 3),
    ]
    family = {
        "format": mod.SOURCE_FAMILY_FORMAT,
        "specialTechniqueSets": [
            {
                "techniqueSet": ts,
                "family": fam,
                "maps": {mod.MAP: count},
                "examples": [{"map": mod.MAP, "material": f"example/{ts}"}],
            }
            for ts, fam, count in techsets
        ],
    }
    groups = []
    materials = []
    n = 0
    for ti, (ts, fam, count) in enumerate(techsets):
        gk = f"group-{ti}"
        hh = f"{ti + 1:064x}"
        groups.append({
            "groupKey": gk,
            "techniqueType": "lit" if fam != "shadowcaster" else "shadowcaster",
            "passStageIdentitySha256": f"{ti + 20:064x}",
            "techniqueSets": [ts],
            "techniques": [f"tech-{ti}"],
            "passes": [{
                "index": 0,
                "stateMap": f"state-{ti}",
                "vertexRouting": [],
                "stages": [stage("vertexShader", f"{ti + 40:064x}"), stage("pixelShader", hh)],
            }],
        })
        for j in range(count):
            n += 1
            materials.append({
                "material": f"wpc/m{n}",
                "materialJsonSha256": f"{n + 100:064x}",
                "techniqueSet": ts,
                "techniqueSetOwners": ["/tmp/map_out"],
                "declaredTechniqueTypes": [groups[-1]["techniqueType"]],
                "hasLitBinding": groups[-1]["techniqueType"] == "lit",
                "programs": [{
                    "techniqueType": groups[-1]["techniqueType"],
                    "technique": f"tech-{ti}",
                    "groupKey": gk,
                    "passStageIdentitySha256": groups[-1]["passStageIdentitySha256"],
                    "passCount": 1,
                    "parentTechniqueSetOwners": ["/tmp/map_out"],
                    "techniqueOwner": "/tmp/map_out",
                }],
            })
    census = {
        "format": mod.SOURCE_CENSUS_FORMAT,
        "authoritativeForPcDedicatedServerBuild": True,
        "authoritativeForRetailClient": False,
        "summary": {"unresolvedMaterialCount": 0},
        "materials": materials,
        "shaderGroups": groups,
        "pcServerTechniqueSetSelections": [],
    }
    return census, family


def main() -> int:
    census, family = make_docs()
    out = mod.build(census, family)
    s = out["summary"]
    assert s["specialMaterialUseCount"] == 11
    assert s["specialTechniqueSetCount"] == 7
    assert s["familyUseCounts"] == mod.EXPECTED_FAMILY_USE_COUNTS
    assert s["referencedExactTechniqueTypeShaderGroupCount"] == 7
    assert s["pcServerDuplicateParentSelectionDependencyCount"] == 0
    assert len(out["materials"]) == 11
    assert len(out["shaderGroups"]) == 7

    # One relevant duplicate parent must be surfaced, never converted to retail authority.
    c2 = copy.deepcopy(census)
    c2["pcServerTechniqueSetSelections"] = [{"name": "ts_u1", "selectedOwner": "/tmp/patch_out", "selectedPriority": 65}]
    out2 = mod.build(c2, family)
    assert out2["summary"]["pcServerDuplicateParentSelectionDependencyCount"] == 1
    assert out2["summary"]["retailClientAuthoritativeWinnerCount"] == 0
    assert any(x["dependsOnPcServerDuplicateParentSelection"] for x in out2["materials"])

    # Family/use-count drift must fail closed.
    f2 = copy.deepcopy(family)
    f2["specialTechniqueSets"][0]["maps"][mod.MAP] = 2
    try:
        mod.build(census, f2)
    except mod.NuketownSpecialCensusError:
        pass
    else:
        raise AssertionError("expected special-family drift failure")

    # A missing exact group must fail closed.
    c3 = copy.deepcopy(census)
    c3["shaderGroups"] = c3["shaderGroups"][1:]
    try:
        mod.build(c3, family)
    except mod.NuketownSpecialCensusError:
        pass
    else:
        raise AssertionError("expected missing-group failure")

    print("PASS t6_nuketown_special_material_census_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
