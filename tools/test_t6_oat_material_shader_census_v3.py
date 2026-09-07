#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_material_shader_census_v3 as census


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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        map_root = base / "map"
        patch_root = base / "patch"

        material(map_root, "wpc/lit_mat", "lit_set")
        material(map_root, "wpc/trivial_mat", "trivial_9z33feqw")
        material(map_root, "generated/fake_generated", "generated_set")

        write(map_root / "techsets" / "lit_set.techset", '"lit":\nlit_tech;\n')
        write(map_root / "techsets" / "trivial_9z33feqw.techset", '"depthPrepass":\ntrivial_tech;\n')
        write(patch_root / "techsets" / "trivial_9z33feqw.techset", '"depthPrepass":\ntrivial_tech;\n')
        technique(map_root, "lit_tech", "lit_vs", "lit_ps")
        technique(map_root, "trivial_tech", "trivial_vs", "trivial_ps")
        # Duplicate Technique text and shader payloads in patch must be accepted.
        technique(patch_root, "trivial_tech", "trivial_vs", "trivial_ps")

        result = census.build(map_root, [map_root, patch_root])
        s = result["summary"]
        assert s["ordinaryNativeMaterialCount"] == 2, s
        assert s["excludedGeneratedMaterialCount"] == 1, s
        assert s["litBindingMaterialCount"] == 1, s
        assert s["nonLitOnlyMaterialCount"] == 1, s
        assert s["declaredTechniqueTypeUseCounts"] == {"depthPrepass": 1, "lit": 1}, s
        assert s["divergentDuplicateDependencyCount"] == 0, s
        assert s["duplicateDependencyIdentityCheckCount"] == 2, result["duplicateDependencies"]
        mats = {row["material"]: row for row in result["materials"]}
        assert mats["wpc/trivial_mat"]["declaredTechniqueTypes"] == ["depthPrepass"]
        assert mats["wpc/trivial_mat"]["hasLitBinding"] is False
        assert len(result["shaderGroups"]) == 2

    print("PASS: all-TechniqueSet native shader census accepts non-lit-only ordinary materials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
