#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

import t6_generated_slot4_final_output_symbolic_v3 as v3


def sha(i: int) -> str:
    return f"{i + 1:064x}"


def fixture():
    formats = [1] * 95 + [2] * 7 + [3] * 17 + [6]
    validated = {}
    materials = []
    for i in range(120):
        technique_index = i % 34
        shader_sha = sha(technique_index)
        name = f"*fixture_{i:03d}(base:layer)"
        validated[name] = {
            "material": name,
            "techniqueSet": f"lit_sm_fixture_{technique_index:02d}",
            "pixelShaderArchetype": f"sha256:{shader_sha}",
            "worldVertFormats": [formats[i]],
            "proof": {"pixelShaderSha256": shader_sha},
        }
        materials.append({
            "material": name,
            "techniqueSet": f"lit_sm_fixture_{technique_index:02d}",
            "pixelShaderSha256": shader_sha,
            "pixelShaderAsset": f"ps_{technique_index:02d}",
        })

    shaders = []
    for i in range(34):
        shaders.append({
            "sha256": sha(i),
            "asset": f"ps_{i:02d}",
            "techniqueSets": [f"lit_sm_fixture_{i:02d}"],
            "shaderModel": "4.0",
            "outputs": [{"register": 0, "lanes": [
                {"channel": "x", "written": True, "node": 0, "resources": []},
                {"channel": "y", "written": True, "node": 0, "resources": []},
                {"channel": "z", "written": True, "node": 0, "resources": []},
                {"channel": "w", "written": True, "node": 0, "resources": []},
            ]}],
        })
    manifest = {
        "format": "t6-generated-world-shader-recipe-manifest-v1",
        "materials": list(validated.values()),
        "recovery": {
            "map": v3.MAP,
            "generatedMaterialCount": 120,
            "uniqueTechniqueSetCount": 34,
            "uniqueSlot4PixelShaderCount": 34,
            "crossTechniqueSetShaderReuseCount": 0,
            "worldVertFormatHistogram": {"1": 95, "2": 7, "3": 17, "6": 1},
        },
    }
    result = {
        "format": v3.v2.FORMAT,
        "materials": materials,
        "shaders": shaders,
        "summary": {
            "materialCount": 120,
            "techniqueSetCount": 34,
            "uniquePixelShaderCount": 34,
        },
    }
    return manifest, validated, result


def run(manifest, validated, result, strict=True):
    old_validate = v3.recipe_contract.validate_manifest
    old_build = v3.v2.build
    try:
        v3.recipe_contract.validate_manifest = lambda doc: copy.deepcopy(validated)
        v3.v2.build = lambda doc, *, oat_root, strict_nuketown=False: copy.deepcopy(result)
        return v3.build(manifest, oat_root=Path("."), strict_nuketown=strict)
    finally:
        v3.recipe_contract.validate_manifest = old_validate
        v3.v2.build = old_build


def expect_fail(manifest, validated, result, phrase, strict=True):
    try:
        run(manifest, validated, result, strict=strict)
    except v3.GeneratedFinalOutputSymbolicV3Error as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"expected failure containing {phrase!r}")


def main() -> int:
    manifest, validated, result = fixture()
    out = run(manifest, validated, result)
    assert out["format"] == v3.FORMAT
    assert out["baseFormat"] == v3.v2.FORMAT
    assert out["summary"]["canonicalShaderIdentityMismatchCount"] == 0
    assert out["summary"]["strictNuketownInvariantRecheck"] is True
    assert out["strictNuketown"]["materialCount"] == 120
    assert out["strictNuketown"]["techniqueSetCount"] == 34
    assert out["strictNuketown"]["uniquePixelShaderCount"] == 34
    assert out["strictNuketown"]["worldVertFormatHistogram"] == {"1": 95, "2": 7, "3": 17, "6": 1}
    assert len(out["summary"]["exactPixelShaderSetSha256"]) == 64

    m, v, r = fixture()
    first = next(iter(v))
    v[first]["pixelShaderArchetype"] = sha(0)
    expect_fail(m, v, r, "not exact sha256:<64hex>")

    m, v, r = fixture()
    first = next(iter(v))
    v[first]["proof"]["pixelShaderSha256"] = sha(33)
    expect_fail(m, v, r, "proof.pixelShaderSha256")

    m, v, r = fixture()
    first = next(iter(v))
    r["materials"][0]["pixelShaderSha256"] = sha(33)
    expect_fail(m, v, r, "exact OAT slot-4 shader")

    m, v, r = fixture()
    r["shaders"][0]["techniqueSets"] = ["lit_sm_fixture_00", "lit_sm_fixture_01"]
    expect_fail(m, v, r, "cross-TechniqueSet slot-4 shader reuse")

    m, v, r = fixture()
    # Move one material from format 1 to format 2 while keeping total rows 120.
    first = next(iter(v))
    v[first]["worldVertFormats"] = [2]
    expect_fail(m, v, r, "worldVertFormat histogram")

    m, v, r = fixture()
    m["recovery"]["uniqueSlot4PixelShaderCount"] = 33
    expect_fail(m, v, r, "uniqueSlot4PixelShaderCount")

    m, v, r = fixture()
    r["shaders"][0]["shaderModel"] = "5.0"
    expect_fail(m, v, r, "not uniformly SM4.0")

    # Relaxed mode still enforces exact canonical material<->OAT shader identity,
    # but does not impose Nuketown population constants.
    m, v, r = fixture()
    m.pop("recovery")
    relaxed = run(m, v, r, strict=False)
    assert relaxed["summary"]["strictNuketownInvariantRecheck"] is False
    assert "strictNuketown" not in relaxed

    print("PASS: generated slot-4 final-output symbolic v3 canonical identity gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
