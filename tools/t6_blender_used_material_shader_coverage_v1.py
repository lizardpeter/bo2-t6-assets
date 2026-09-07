#!/usr/bin/env python3
"""Join a canonical T6 full-map GLB to exact shader-family coverage evidence.

This is the final coverage gate before material compilation.  It considers only
Materials actually referenced by mesh primitives, resolves preview-only
lightmap-specialization shells back to their canonical retail Material identity,
and classifies each used identity as either:

- generated: exact embedded generatedShaderRecipeV1 with exact shader identity;
- native: exact row from t6-oat-material-shader-census-v1;
- unresolved: no exact shader evidence (never generic-PBR fallback).

No shader family semantics are inferred here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

FORMAT = "t6-blender-used-material-shader-coverage-v1"
NATIVE_FORMAT = "t6-oat-material-shader-census-v1"
GENERATED_KEY = "generatedShaderRecipeV1"
LIGHTMAP_BINDING_KEY = "lightmapPreviewBindingV1"


class UsedMaterialCoverageError(RuntimeError):
    pass


def _gltf_json(path: Path) -> dict:
    raw = path.read_bytes()
    if path.suffix.lower() == ".gltf":
        return json.loads(raw.decode("utf-8"))
    if path.suffix.lower() != ".glb" or len(raw) < 20 or raw[:4] != b"glTF":
        raise UsedMaterialCoverageError("input is not glTF/GLB")
    version, total = struct.unpack_from("<II", raw, 4)
    if version != 2 or total != len(raw):
        raise UsedMaterialCoverageError("invalid GLB header")
    p = 12
    while p + 8 <= len(raw):
        size, kind = struct.unpack_from("<II", raw, p)
        p += 8
        payload = raw[p:p + size]
        p += size
        if kind == 0x4E4F534A:
            return json.loads(payload.rstrip(b" \t\r\n\0").decode("utf-8"))
    raise UsedMaterialCoverageError("GLB has no JSON chunk")


def _used_indices(doc: dict) -> tuple[set[int], int]:
    materials = doc.get("materials")
    if not isinstance(materials, list):
        raise UsedMaterialCoverageError("glTF has no materials list")
    used = set()
    primitive_count = 0
    for mesh in doc.get("meshes", []):
        primitives = mesh.get("primitives", [])
        if not isinstance(primitives, list):
            raise UsedMaterialCoverageError("mesh primitives is not an array")
        for primitive in primitives:
            primitive_count += 1
            if "material" not in primitive:
                continue
            index = int(primitive["material"])
            if index < 0 or index >= len(materials):
                raise UsedMaterialCoverageError(f"primitive references invalid Material {index}")
            used.add(index)
    return used, primitive_count


def _retail_identity(material: dict) -> tuple[str, str]:
    name = str(material.get("name") or "")
    if not name:
        raise UsedMaterialCoverageError("used glTF Material has empty name")
    t6 = material.get("extras", {}).get("T6", {})
    if not isinstance(t6, dict):
        t6 = {}
    binding = t6.get(LIGHTMAP_BINDING_KEY)
    if isinstance(binding, dict):
        retail = str(binding.get("retailMaterialName") or "")
        variant = str(binding.get("variantMaterialName") or "")
        if not retail or variant != name:
            raise UsedMaterialCoverageError(f"{name!r}: malformed lightmap preview retail identity")
        return retail, "lightmapPreviewBindingV1.retailMaterialName"
    direct = t6.get("retailMaterialName")
    if isinstance(direct, str) and direct:
        return direct, "extras.T6.retailMaterialName"
    return name, "material.name"


def _generated(material: dict, retail: str) -> dict | None:
    t6 = material.get("extras", {}).get("T6", {})
    if not isinstance(t6, dict):
        return None
    recipe = t6.get(GENERATED_KEY)
    if recipe is None:
        return None
    if not isinstance(recipe, dict):
        raise UsedMaterialCoverageError(f"{retail!r}: generated recipe is not an object")
    recipe_material = str(recipe.get("material") or "")
    if recipe_material != retail:
        raise UsedMaterialCoverageError(
            f"{retail!r}: embedded generated recipe belongs to {recipe_material!r}"
        )
    technique_set = str(recipe.get("techniqueSet") or "")
    shader = str(recipe.get("pixelShaderArchetype") or "")
    if not technique_set or not shader.startswith("sha256:") or len(shader) != 71:
        raise UsedMaterialCoverageError(
            f"{retail!r}: generated recipe lacks exact TechniqueSet/sha256 shader identity"
        )
    return {
        "techniqueSet": technique_set,
        "pixelShaderArchetype": shader,
        "worldVertFormats": recipe.get("worldVertFormats"),
    }


def build(gltf_path: Path, native_census: dict) -> dict:
    if native_census.get("format") != NATIVE_FORMAT:
        raise UsedMaterialCoverageError(f"unsupported native census {native_census.get('format')!r}")
    native_by_name = {}
    for row in native_census.get("materials", []):
        name = str(row.get("material") or "")
        if not name or name in native_by_name:
            raise UsedMaterialCoverageError(f"invalid/duplicate native census identity {name!r}")
        native_by_name[name] = row

    raw = gltf_path.read_bytes()
    doc = _gltf_json(gltf_path)
    used_indices, primitive_count = _used_indices(doc)
    materials = doc["materials"]

    identities: dict[str, dict] = {}
    used_rows = []
    native_indices = set()
    generated_indices = set()
    unresolved_indices = set()

    for index in sorted(used_indices):
        material = materials[index]
        retail, identity_source = _retail_identity(material)
        generated = _generated(material, retail)
        if generated is not None:
            classification = "generated-exact-recipe"
            evidence = generated
            generated_indices.add(index)
        else:
            native = native_by_name.get(retail)
            if native is not None:
                classification = "native-exact-shader-pair"
                evidence = {
                    "techniqueSet": native.get("techniqueSet"),
                    "technique": native.get("technique"),
                    "pairKey": native.get("pairKey"),
                    "passCount": native.get("passCount"),
                }
                native_indices.add(index)
            else:
                classification = "unresolved"
                evidence = None
                unresolved_indices.add(index)
        row = {
            "materialIndex": index,
            "materialName": str(material.get("name") or ""),
            "retailMaterial": retail,
            "identitySource": identity_source,
            "classification": classification,
            "evidence": evidence,
        }
        used_rows.append(row)
        key = retail
        agg = identities.setdefault(key, {
            "retailMaterial": retail,
            "classifications": set(),
            "materialIndices": [],
            "evidence": evidence,
        })
        agg["classifications"].add(classification)
        agg["materialIndices"].append(index)
        if agg["evidence"] != evidence:
            raise UsedMaterialCoverageError(f"{retail!r}: duplicate used shells disagree on shader evidence")

    identity_rows = []
    for name in sorted(identities):
        row = identities[name]
        if len(row["classifications"]) != 1:
            raise UsedMaterialCoverageError(f"{name!r}: conflicting classifications {row['classifications']}")
        identity_rows.append({
            "retailMaterial": name,
            "classification": next(iter(row["classifications"])),
            "materialIndices": row["materialIndices"],
            "evidence": row["evidence"],
        })

    unresolved_retail = sorted(
        row["retailMaterial"] for row in identity_rows if row["classification"] == "unresolved"
    )
    return {
        "format": FORMAT,
        "source": {
            "file": gltf_path.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "proofBoundary": (
            "Used glTF Material indices only; preview shells resolve through explicit retail identity metadata. "
            "Generated coverage requires exact embedded generatedShaderRecipeV1; native coverage requires exact Material row in the OAT shader-pair census. No name-pattern shader inference or generic-PBR fallback."
        ),
        "summary": {
            "primitiveCount": primitive_count,
            "usedMaterialIndexCount": len(used_indices),
            "usedRetailMaterialIdentityCount": len(identity_rows),
            "nativeCoveredMaterialIndexCount": len(native_indices),
            "generatedCoveredMaterialIndexCount": len(generated_indices),
            "unresolvedMaterialIndexCount": len(unresolved_indices),
            "unresolvedRetailMaterialIdentityCount": len(unresolved_retail),
            "allUsedMaterialsHaveExactShaderEvidence": not unresolved_retail,
        },
        "usedMaterials": used_rows,
        "retailMaterialIdentities": identity_rows,
        "unresolvedRetailMaterials": unresolved_retail,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("gltf", type=Path)
    p.add_argument("--native-census", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.gltf, json.loads(a.native_census.read_text(encoding="utf-8")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    if result["unresolvedRetailMaterials"]:
        print(json.dumps(result["unresolvedRetailMaterials"][:50], indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
