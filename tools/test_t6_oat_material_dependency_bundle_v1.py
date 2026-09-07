#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_material_dependency_bundle_v1 as bundle


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def material(root: Path, techset: str) -> None:
    write(root / "materials" / "shadowoverlay.json", json.dumps({
        "_game": "t6",
        "_type": "material",
        "name": "shadowoverlay",
        "techniqueSet": techset,
    }))


def techset(root: Path, name: str, technique: str) -> None:
    write(root / "techsets" / f"{name}.techset", f'"lit":\n{technique};\n')


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
        a = base / "code_post_gfx"
        b = base / "code_post_gfx_mp"
        out = base / "bundle"
        tset = "trivial_shadowoverlay_14e2e827"
        tech = "pimp_technique_shadowoverlay_5255c888"

        material(a, tset)
        material(b, tset)
        techset(a, tset, tech)
        techset(b, tset, tech)
        technique(a, tech, "a_vs", "a_ps")
        technique(b, tech, "b_vs", "b_ps")

        result = bundle.build(
            [("code_post_gfx", a.resolve()), ("code_post_gfx_mp", b.resolve())],
            [("code_post_gfx", a.resolve()), ("code_post_gfx_mp", b.resolve())],
            "shadowoverlay",
            out,
        )
        s = result["summary"]
        assert s["materialPhysicalCopyCount"] == 2
        assert s["uniqueTechniqueSetCount"] == 1
        assert s["uniqueDeclaredTechniqueCount"] == 1
        assert s["techniquePhysicalCopyCount"] == 2
        assert s["shaderPhysicalCopyCount"] == 4

        row = result["techniques"][0]
        assert row["technique"] == tech
        assert len(row["physicalCopies"]) == 2
        assert row["physicalCopies"][0]["parsedPassStageIdentitySha256"] != row["physicalCopies"][1]["parsedPassStageIdentitySha256"]

        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["format"] == "t6-oat-material-dependency-bundle-v1"
        archived = list((out / "files").rglob("*"))
        files = [p for p in archived if p.is_file()]
        assert len(files) == 10, files  # 2 Materials + 2 TechSets + 2 Techniques + 4 shaders

    print("PASS: exact Material dependency bundle preserves divergent physical definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
