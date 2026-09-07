#!/usr/bin/env python3
"""Census native T6 Material -> lit Technique -> exact VS/PS shader pairs.

Consumes OpenAssetTools native T6 Material JSON dumps plus one or more exact OAT
TechniqueSet dump roots (for example the map zone and common_mp).  This is a
coverage/classification tool for the Blender converter, not a shader semantic
inference tool.

For every ordinary dumped Material with a resolved ``techniqueSet`` it:
- resolves the exact owner root containing ``techsets/<name>.techset``;
- resolves T6 technique type ``lit`` from the OAT .techset grammar;
- resolves the dependent .tech in that same OAT dump root when present, falling
  back to an exactly-one-owner search only if the owner root lacks it;
- parses every pass of the exact .tech file;
- records exact emitted VS/PS CSO SHA-256 identities;
- groups Materials only by exact ordered pass shader identities.

Generated compound `*...` Materials are intentionally outside this census;
Nuketown's canonical generated population is already handled by the separate
120-material / 34-TechniqueSet exact recipe/final-output-DAG path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import t6_oat_techset_binding_manifest_v1 as oat

FORMAT = "t6-oat-material-shader-census-v1"
TECHNIQUE_TYPE = "lit"


class MaterialShaderCensusError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _index_materials(root: Path) -> list[dict[str, Any]]:
    material_root = root / "materials" if (root / "materials").is_dir() else root
    if not material_root.is_dir():
        raise MaterialShaderCensusError(f"material root is not a directory: {material_root}")
    rows = []
    names = set()
    for path in sorted(material_root.rglob("*.json")):
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise MaterialShaderCensusError(f"invalid Material JSON {path}: {exc}") from exc
        if doc.get("_game") != "t6" or doc.get("_type") != "material":
            continue
        relative = path.relative_to(material_root).with_suffix("").as_posix()
        name = str(doc.get("name") or relative)
        # OAT disk identity is authoritative when a schema omits/reformats name.
        if not name or name.startswith("*"):
            name = relative
        if name in names:
            raise MaterialShaderCensusError(f"duplicate native Material identity {name!r}")
        names.add(name)
        techset = str(doc.get("techniqueSet") or "")
        rows.append({
            "material": name,
            "relativeMaterial": relative,
            "path": path,
            "jsonSha256": hashlib.sha256(raw).hexdigest(),
            "techniqueSet": techset,
            "doc": doc,
        })
    if not rows:
        raise MaterialShaderCensusError("no native T6 Material JSON dumps found")
    return rows


def _owner(roots: list[Path], relative: Path, label: str) -> tuple[Path, Path]:
    matches = [(root, root / relative) for root in roots if (root / relative).is_file()]
    if len(matches) != 1:
        raise MaterialShaderCensusError(
            f"{label}: expected exactly one dump owner for {relative.as_posix()}, found {[str(r) for r,_ in matches]}"
        )
    return matches[0]


def _lit_technique(root_paths: list[Path], techset: str) -> tuple[str, Path, dict]:
    owner, path = _owner(root_paths, Path("techsets") / f"{techset}.techset", f"TechniqueSet {techset}")
    bindings, errors = oat.parse_techset(path.read_text(encoding="utf-8", errors="strict"))
    if errors:
        raise MaterialShaderCensusError(f"TechniqueSet {techset}: parse errors {errors[:4]}")
    matches = [row for row in bindings if TECHNIQUE_TYPE in row.get("types", [])]
    if len(matches) != 1:
        raise MaterialShaderCensusError(
            f"TechniqueSet {techset}: {len(matches)} exact {TECHNIQUE_TYPE!r} bindings"
        )
    technique = str(matches[0].get("technique") or "")
    if not technique:
        raise MaterialShaderCensusError(f"TechniqueSet {techset}: empty lit technique")
    return technique, owner, {
        "ownerRoot": str(owner),
        "relativeFile": path.relative_to(owner).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _technique_passes(root_paths: list[Path], preferred_owner: Path, technique: str) -> tuple[list[dict], dict]:
    relative = Path("techniques") / f"{technique}.tech"
    preferred = preferred_owner / relative
    if preferred.is_file():
        owner, path = preferred_owner, preferred
    else:
        owner, path = _owner(root_paths, relative, f"Technique {technique}")
    raw_passes, errors = oat.split_top_level_passes(path.read_text(encoding="utf-8", errors="strict"))
    if errors:
        raise MaterialShaderCensusError(f"Technique {technique}: split errors {errors[:4]}")
    result = []
    for index, lines in enumerate(raw_passes):
        parsed, perrors = oat.parse_pass(lines, owner)
        if perrors:
            raise MaterialShaderCensusError(f"Technique {technique} pass {index}: {perrors[:4]}")
        shaders = parsed.get("shaders", [])
        stage = {}
        for shader in shaders:
            kind = str(shader.get("kind") or "")
            binary = shader.get("binary")
            if kind not in {"vertexShader", "pixelShader"} or not isinstance(binary, dict):
                continue
            if kind in stage:
                raise MaterialShaderCensusError(f"Technique {technique} pass {index}: duplicate {kind}")
            stage[kind] = {
                "asset": str(shader.get("name") or ""),
                "shaderModel": str(shader.get("model") or ""),
                "relativeFile": str(binary.get("path") or ""),
                "bytes": int(binary.get("size", -1)),
                "sha256": str(binary.get("sha256") or "").lower(),
                "arguments": shader.get("arguments", []),
            }
        if set(stage) != {"vertexShader", "pixelShader"}:
            raise MaterialShaderCensusError(
                f"Technique {technique} pass {index}: stages {sorted(stage)} != VS+PS"
            )
        result.append({
            "index": index,
            "stateMap": parsed.get("stateMap"),
            "vertexRouting": parsed.get("vertexRouting", []),
            "vertexShader": stage["vertexShader"],
            "pixelShader": stage["pixelShader"],
        })
    if not result:
        raise MaterialShaderCensusError(f"Technique {technique}: no passes")
    return result, {
        "ownerRoot": str(owner),
        "relativeFile": path.relative_to(owner).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha(path),
    }


def _pair_key(passes: list[dict]) -> str:
    # Preserve pass order; multiple-pass techniques are distinct families.
    parts = []
    for row in passes:
        parts.append(f"{row['vertexShader']['sha256']}:{row['pixelShader']['sha256']}")
    return hashlib.sha256("|".join(parts).encode("ascii")).hexdigest()


def build(material_root: Path, shader_roots: list[Path]) -> dict:
    roots = [path.resolve() for path in shader_roots]
    if not roots or any(not path.is_dir() for path in roots):
        raise MaterialShaderCensusError("all shader roots must be existing directories")
    materials = _index_materials(material_root.resolve())
    technique_cache = {}
    pair_groups: dict[str, dict] = {}
    unresolved = []
    out_materials = []

    for material in materials:
        name = material["material"]
        techset = material["techniqueSet"]
        if not techset:
            unresolved.append({"material": name, "reason": "native Material has empty techniqueSet"})
            continue
        if techset not in technique_cache:
            technique, techset_owner, techset_file = _lit_technique(roots, techset)
            passes, technique_file = _technique_passes(roots, techset_owner, technique)
            technique_cache[techset] = {
                "technique": technique,
                "techsetFile": techset_file,
                "techniqueFile": technique_file,
                "passes": passes,
                "pairKey": _pair_key(passes),
            }
        resolved = technique_cache[techset]
        pair_key = resolved["pairKey"]
        group = pair_groups.setdefault(pair_key, {
            "pairKey": pair_key,
            "techniqueSets": set(),
            "techniques": set(),
            "materials": [],
            "passes": resolved["passes"],
        })
        # If one pair key somehow hashes different pass descriptions, fail.
        if group["passes"] != resolved["passes"]:
            raise MaterialShaderCensusError(f"pair key collision {pair_key}")
        group["techniqueSets"].add(techset)
        group["techniques"].add(resolved["technique"])
        group["materials"].append(name)
        out_materials.append({
            "material": name,
            "materialJsonSha256": material["jsonSha256"],
            "techniqueSet": techset,
            "technique": resolved["technique"],
            "pairKey": pair_key,
            "passCount": len(resolved["passes"]),
        })

    groups = []
    for key in sorted(pair_groups):
        group = pair_groups[key]
        groups.append({
            "pairKey": key,
            "materialCount": len(group["materials"]),
            "materials": sorted(group["materials"]),
            "techniqueSets": sorted(group["techniqueSets"]),
            "techniques": sorted(group["techniques"]),
            "passes": group["passes"],
        })

    return {
        "format": FORMAT,
        "techniqueType": TECHNIQUE_TYPE,
        "proofBoundary": (
            "Native OAT T6 Material JSON resolved TechniqueSet name joined to exact OAT .techset/.tech and emitted CSO hashes. "
            "Grouping is exact ordered VS/PS SHA identity only; no shader semantic/family inference. Generated compound materials are separate."
        ),
        "summary": {
            "nativeMaterialCount": len(materials),
            "resolvedMaterialCount": len(out_materials),
            "unresolvedMaterialCount": len(unresolved),
            "uniqueTechniqueSetCount": len(technique_cache),
            "uniqueExactShaderPairGroupCount": len(groups),
            "singlePassGroupCount": sum(1 for row in groups if len(row["passes"]) == 1),
            "multiPassGroupCount": sum(1 for row in groups if len(row["passes"]) > 1),
        },
        "shaderRoots": [str(path) for path in roots],
        "materials": sorted(out_materials, key=lambda row: row["material"]),
        "shaderPairGroups": groups,
        "unresolved": unresolved,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--material-root", type=Path, required=True)
    p.add_argument("--shader-root", type=Path, action="append", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.material_root, a.shader_root)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 1 if result["unresolved"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
