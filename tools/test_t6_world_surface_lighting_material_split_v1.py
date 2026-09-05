#!/usr/bin/env python3
from __future__ import annotations

from t6_world_surface_lighting_material_split_v1 import (
    SurfaceLightingSplitError,
    restore_source_material_indices,
    split_surface_lighting_materials,
    validate_surface_lighting_split,
)


def _primitive(material, index, lm, rp, pl):
    return {
        "material": material,
        "extras": {
            "T6": {
                "index": index,
                "lightmapIndex": lm,
                "reflectionProbeIndex": rp,
                "primaryLightIndex": pl,
            }
        },
    }


def main() -> int:
    source = {
        "asset": {"version": "2.0"},
        "materials": [
            {"name": "mat_a", "extras": {"T6": {"sourceMaterial": "mat_a"}}},
            {"name": "mat_b", "extras": {"T6": {"sourceMaterial": "mat_b"}}},
        ],
        "meshes": [
            {"primitives": [
                _primitive(0, 10, 2, 7, 1),
                _primitive(0, 11, 2, 7, 1),  # same exact lighting tuple -> same clone
                _primitive(0, 12, 3, 7, 1),  # different lightmap -> different clone
                _primitive(1, 13, 2, 7, 1),  # different source material -> different clone
                _primitive(1, 14, -1, 9, 0),
            ]},
        ],
        "extras": {"T6": {"sentinel": "preserved"}},
    }

    split = split_surface_lighting_materials(source)
    assert source["meshes"][0]["primitives"][0]["material"] == 0  # input unchanged
    assert validate_surface_lighting_split(split)
    meta = split["extras"]["T6"]["surfaceLightingMaterialSplit"]
    assert meta["sourceMaterialPrefixCount"] == 2
    assert meta["cloneMaterialCount"] == 4
    assert meta["primitiveCount"] == 5
    assert meta["uniqueLightingTupleCount"] == 4
    assert split["extras"]["T6"]["sentinel"] == "preserved"

    refs = [p["material"] for p in split["meshes"][0]["primitives"]]
    assert refs[0] == refs[1]
    assert refs[2] != refs[0]
    assert refs[3] != refs[0]
    assert refs[4] != refs[3]
    assert all(index >= 2 for index in refs)

    first_clone = split["materials"][refs[0]]
    provenance = first_clone["extras"]["T6"]["surfaceLightingSplitV1"]
    assert provenance["sourceMaterialIndex"] == 0
    assert provenance["sourceMaterialName"] == "mat_a"
    assert provenance["lightmapIndex"] == 2
    assert provenance["reflectionProbeIndex"] == 7
    assert provenance["primaryLightIndex"] == 1
    assert first_clone["extras"]["T6"]["sourceMaterial"] == "mat_a"

    restored = restore_source_material_indices(split)
    assert len(restored["materials"]) == 2
    assert [p["material"] for p in restored["meshes"][0]["primitives"]] == [0, 0, 0, 1, 1]
    assert "surfaceLightingMaterialSplit" not in restored["extras"]["T6"]

    bad = {
        "materials": [{"name": "mat"}],
        "meshes": [{"primitives": [{"material": 0, "extras": {"T6": {"lightmapIndex": 1}}}]}],
    }
    try:
        split_surface_lighting_materials(bad)
    except SurfaceLightingSplitError:
        pass
    else:
        raise AssertionError("missing reflection/primary-light provenance did not fail closed")

    print("PASS: reversible T6 surface lighting material split v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
