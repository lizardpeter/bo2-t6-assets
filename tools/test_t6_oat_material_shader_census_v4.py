#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_material_shader_census_v4 as census


def write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def material(root: Path, rel: str, techset: str) -> None:
    write(root / "materials" / f"{rel}.json", json.dumps({
        "_game": "t6",
        "_type": "material",
        "name": rel,
        "techniqueSet": techset,
    }))


def techset(root: Path, name: str, technique_name: str, type_name: str = "lit") -> None:
    write(root / "techsets" / f"{name}.techset", f'"{type_name}":\n{technique_name};\n')


def technique(root: Path, name: str, vs: str, ps: str) -> None:
    write(root / "techniques" / f"{name}.tech", f'''{{
stateMap "default";
vertexShader 4.0 "{vs}"
{{
}}
pixelShader 4.0 "{ps}"
{{
}}
}}
''')
    write(root / "shader_bin" / f"vs_{vs}.cso", ("VS:" + vs).encode())
    write(root / "shader_bin" / f"ps_{ps}.cso", ("PS:" + ps).encode())


def expect_failure(fn, needle: str) -> None:
    try:
        fn()
    except census.MaterialShaderCensusError as exc:
        assert needle in str(exc), exc
    else:
        raise AssertionError("expected MaterialShaderCensusError")


def test_unique_parent_ignores_divergent_nonparent_same_name(base: Path) -> None:
    map_root = base / "unique_map"
    patch_root = base / "unique_patch"
    material(map_root, "wpc/m", "parent_set")
    techset(map_root, "parent_set", "shared_name")
    technique(map_root, "shared_name", "map_vs", "map_ps")
    technique(patch_root, "shared_name", "patch_vs", "patch_ps")

    result = census.build(map_root, [map_root, patch_root])
    assert result["summary"]["ordinaryNativeMaterialCount"] == 1
    assert result["summary"]["divergentParentOwnedDependencyCount"] == 0
    assert result["summary"]["nonParentAlternateTechniqueDefinitionCount"] == 1
    assert result["summary"]["divergentNonParentAlternateTechniqueDefinitionCount"] == 1
    program = result["materials"][0]["programs"][0]
    assert program["techniqueOwner"] == str(map_root.resolve())
    alt = result["nonParentAlternateTechniqueDefinitions"][0]
    assert alt["alternateOwner"] == str(patch_root.resolve())
    assert alt["sameParsedPassStageIdentity"] is False


def test_duplicate_parent_identical_child_passes_allowed(base: Path) -> None:
    map_root = base / "dup_ok_map"
    patch_root = base / "dup_ok_patch"
    material(map_root, "wpc/m", "parent_set")
    techset(map_root, "parent_set", "same_child")
    techset(patch_root, "parent_set", "same_child")
    technique(map_root, "same_child", "same_vs", "same_ps")
    technique(patch_root, "same_child", "same_vs", "same_ps")

    result = census.build(map_root, [map_root, patch_root])
    assert result["summary"]["ordinaryNativeMaterialCount"] == 1
    assert result["summary"]["duplicateDependencyIdentityCheckCount"] == 2
    assert result["summary"]["nonParentAlternateTechniqueDefinitionCount"] == 0
    assert len(result["materials"][0]["techniqueSetOwners"]) == 2


def test_duplicate_parent_divergent_child_fails(base: Path) -> None:
    map_root = base / "dup_bad_map"
    patch_root = base / "dup_bad_patch"
    material(map_root, "wpc/m", "parent_set")
    techset(map_root, "parent_set", "same_child")
    techset(patch_root, "parent_set", "same_child")
    technique(map_root, "same_child", "map_vs", "map_ps")
    technique(patch_root, "same_child", "patch_vs", "patch_ps")

    expect_failure(
        lambda: census.build(map_root, [map_root, patch_root]),
        "duplicate parent TechniqueSet owners emit divergent child pass/stage identities",
    )


def test_parent_missing_own_child_fails(base: Path) -> None:
    map_root = base / "missing_map"
    patch_root = base / "missing_patch"
    material(map_root, "wpc/m", "parent_set")
    techset(map_root, "parent_set", "external_name")
    technique(patch_root, "external_name", "patch_vs", "patch_ps")

    expect_failure(
        lambda: census.build(map_root, [map_root, patch_root]),
        "parent TechniqueSet owner(s) did not emit declared child",
    )


def test_generated_exclusion_and_nonlit(base: Path) -> None:
    root = base / "ordinary"
    material(root, "wpc/nonlit", "depth_set")
    material(root, "generated/fake_generated", "generated_set")
    techset(root, "depth_set", "depth_child", "depthPrepass")
    technique(root, "depth_child", "depth_vs", "depth_ps")

    result = census.build(root, [root])
    s = result["summary"]
    assert s["ordinaryNativeMaterialCount"] == 1
    assert s["excludedGeneratedMaterialCount"] == 1
    assert s["litBindingMaterialCount"] == 0
    assert s["nonLitOnlyMaterialCount"] == 1
    assert s["declaredTechniqueTypeUseCounts"] == {"depthPrepass": 1}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        test_unique_parent_ignores_divergent_nonparent_same_name(base)
        test_duplicate_parent_identical_child_passes_allowed(base)
        test_duplicate_parent_divergent_child_fails(base)
        test_parent_missing_own_child_fails(base)
        test_generated_exclusion_and_nonlit(base)
    print("PASS: v4 parent-owned Technique provenance and fail-closed boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
