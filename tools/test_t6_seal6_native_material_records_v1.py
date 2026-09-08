#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import t6_seal6_native_material_records_v1 as seal

TARGET = "mtl_gen_pc_usa_milcas_mcknight_head_camo"
TECHSET = "mc/mtl_usa_character"


def _doc(images=("head_c", "head_n", "head_s")) -> dict:
    semantics = ("colorMap", "normalMap", "specularMap")
    return {
        "$schema": "http://openassettools.dev/schema/material.v1.json",
        "_game": "t6",
        "_type": "material",
        "_version": 1,
        "techniqueSet": TECHSET,
        "textures": [
            {
                "image": image,
                "name": semantic,
                "semantic": semantic,
                "samplerState": {"filter": "aniso4x", "clampU": False},
                "isMatureContent": False,
            }
            for image, semantic in zip(images, semantics)
        ],
    }


def _write(root: Path, doc: dict) -> bytes:
    path = root / "materials" / f"{TARGET}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return raw


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        a, b, shader = base / "a", base / "b", base / "shader"
        a.mkdir(); b.mkdir(); shader.mkdir()
        raw = _write(a, _doc())
        _write(b, _doc())

        real_build = seal.v4.build
        def fake_v4(material_root: Path, shader_roots: list[Path]) -> dict:
            staged = material_root / "materials" / f"{TARGET}.json"
            assert staged.read_bytes() == raw
            owner = str(shader.resolve())
            return {
                "summary": {"unresolvedMaterialCount": 0, "divergentParentOwnedDependencyCount": 0},
                "materials": [{
                    "material": TARGET,
                    "materialJsonSha256": seal._sha(raw),
                    "techniqueSet": TECHSET,
                    "techniqueSetOwners": [owner],
                    "declaredTechniqueTypes": ["lit"],
                    "hasLitBinding": True,
                    "programs": [{
                        "techniqueType": "lit",
                        "technique": "pimp_technique_character_test",
                        "groupKey": "g",
                        "passStageIdentitySha256": "p",
                        "passCount": 1,
                        "parentTechniqueSetOwners": [owner],
                        "techniqueOwner": owner,
                    }],
                }],
                "techniqueProvenance": [{
                    "techniqueSet": TECHSET,
                    "technique": "pimp_technique_character_test",
                    "parentOwners": [owner],
                    "chosenOwner": owner,
                    "parsedPassStageIdentitySha256": "p",
                }],
            }
        seal.v4.build = fake_v4
        try:
            result = seal.build(
                [("a", a), ("b", b)],
                [("shader", shader)],
                [TARGET],
            )
        finally:
            seal.v4.build = real_build

        row = result["materials"][0]
        assert result["summary"]["closedTargetMaterialCount"] == 1
        assert result["summary"]["physicalMaterialCopyCount"] == 2
        assert [t["semantic"] for t in row["orderedTextureRecords"]] == [
            "colorMap", "normalMap", "specularMap"
        ]
        assert [t["image"] for t in row["orderedTextureRecords"]] == [
            "head_c", "head_n", "head_s"
        ]
        assert row["orderedTextureRecords"][2]["nativeRecord"]["samplerState"]["filter"] == "aniso4x"
        assert row["techniqueSetOwners"][0]["rootLabel"] == "shader"
        assert row["programs"][0]["techniqueOwner"]["rootLabel"] == "shader"

        # Any divergent physical Material JSON is a hard failure; content-equivalent
        # but differently serialized records are intentionally not promoted as one.
        divergent = copy.deepcopy(_doc())
        divergent["textures"][0]["image"] = "wrong_head_c"
        _write(b, divergent)
        try:
            seal._physical_material_records([("a", a), ("b", b)], TARGET)
        except seal.Seal6MaterialClosureError as exc:
            assert "divergent physical native Material records" in str(exc)
        else:
            raise AssertionError("divergent duplicate Material was accepted")

        try:
            seal._physical_material_records([("shader", shader)], TARGET)
        except seal.Seal6MaterialClosureError as exc:
            assert "no native Material JSON" in str(exc)
        else:
            raise AssertionError("missing target Material was accepted")

    print("PASS t6_seal6_native_material_records_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
