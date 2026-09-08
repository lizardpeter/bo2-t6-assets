#!/usr/bin/env python3
"""Close exact native OAT records for selected SEAL6 Materials.

This adapter is intentionally narrow.  It does not infer texture roles from
filenames, material order, or visual appearance.  For each requested Material it:

* finds every physical OAT Material JSON in the supplied Material-root universe;
* requires all duplicate physical records to be byte-identical;
* preserves the complete native Material JSON plus the texture array verbatim and
  in serialized order;
* resolves the Material's TechniqueSet and every declared Technique through the
  existing provenance-aware native OAT v4 census; and
* emits the exact physical owner labels, byte sizes and SHA-256 identities.

The result is authoritative only inside the explicitly supplied root universe.
A missing Material, divergent duplicate Material JSON, missing TechniqueSet,
parent-owned child mismatch, or divergent parent-owned shader dependency fails
closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import t6_oat_material_shader_census_v4 as v4

FORMAT = "t6-seal6-native-material-records-v1"


class Seal6MaterialClosureError(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("root must be LABEL=PATH")
    label, raw = value.split("=", 1)
    label = label.strip()
    path = Path(raw).resolve()
    if not label or not path.is_dir():
        raise argparse.ArgumentTypeError(f"invalid root {value!r}")
    return label, path


def _read_native_material(path: Path, target: str) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise Seal6MaterialClosureError(f"{target}: invalid native Material JSON {path}: {exc}") from exc
    if doc.get("_game") != "t6" or doc.get("_type") != "material":
        raise Seal6MaterialClosureError(
            f"{target}: {path} is not native T6 material JSON: game={doc.get('_game')!r} type={doc.get('_type')!r}"
        )
    if not str(doc.get("techniqueSet") or ""):
        raise Seal6MaterialClosureError(f"{target}: native Material has empty techniqueSet: {path}")
    textures = doc.get("textures")
    if not isinstance(textures, list):
        raise Seal6MaterialClosureError(f"{target}: native Material textures is not a list: {path}")
    for index, texture in enumerate(textures):
        if not isinstance(texture, dict):
            raise Seal6MaterialClosureError(f"{target}: texture {index} is not an object")
        if not str(texture.get("image") or ""):
            raise Seal6MaterialClosureError(f"{target}: texture {index} has empty image")
        if not str(texture.get("semantic") or texture.get("name") or ""):
            raise Seal6MaterialClosureError(
                f"{target}: texture {index} has neither native semantic nor native name"
            )
    return raw, doc


def _physical_material_records(
    roots: list[tuple[str, Path]], target: str
) -> tuple[list[dict[str, Any]], bytes, dict[str, Any]]:
    relative = Path("materials") / f"{target}.json"
    rows: list[dict[str, Any]] = []
    copies: list[tuple[bytes, dict[str, Any]]] = []
    for label, root in roots:
        path = root / relative
        if not path.is_file():
            continue
        raw, doc = _read_native_material(path, target)
        copies.append((raw, doc))
        rows.append(
            {
                "rootLabel": label,
                "root": str(root),
                "relativeFile": relative.as_posix(),
                "bytes": len(raw),
                "sha256": _sha(raw),
            }
        )
    if not rows:
        raise Seal6MaterialClosureError(
            f"{target}: no native Material JSON in supplied Material-root universe"
        )
    identities = {(row["bytes"], row["sha256"]) for row in rows}
    if len(identities) != 1:
        raise Seal6MaterialClosureError(
            f"{target}: divergent physical native Material records: "
            f"{[(row['rootLabel'], row['bytes'], row['sha256']) for row in rows]}"
        )
    return rows, copies[0][0], copies[0][1]


def _root_label_map(roots: list[tuple[str, Path]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, root in roots:
        key = str(root.resolve())
        if key in out and out[key] != label:
            raise Seal6MaterialClosureError(f"duplicate shader root path with different labels: {root}")
        out[key] = label
    return out


def _label_path(path: str, labels: dict[str, str]) -> dict[str, str]:
    resolved = str(Path(path).resolve())
    label = labels.get(resolved)
    if label is None:
        raise Seal6MaterialClosureError(f"v4 returned owner outside supplied shader roots: {path}")
    return {"rootLabel": label, "root": resolved}


def _close_one(
    material_roots: list[tuple[str, Path]],
    shader_roots: list[tuple[str, Path]],
    target: str,
) -> dict[str, Any]:
    physical, raw, doc = _physical_material_records(material_roots, target)
    shader_paths = [root for _label, root in shader_roots]
    labels = _root_label_map(shader_roots)

    with tempfile.TemporaryDirectory(prefix="t6-seal6-material-") as td:
        staged_root = Path(td)
        staged = staged_root / "materials" / f"{target}.json"
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(raw)
        census = v4.build(staged_root, shader_paths)

    rows = [row for row in census.get("materials", []) if row.get("material") == target]
    if len(rows) != 1:
        raise Seal6MaterialClosureError(
            f"{target}: provenance-aware v4 census returned {len(rows)} exact Material rows"
        )
    row = rows[0]
    if row.get("materialJsonSha256") != _sha(raw):
        raise Seal6MaterialClosureError(f"{target}: v4 Material JSON identity drift")
    if row.get("techniqueSet") != doc.get("techniqueSet"):
        raise Seal6MaterialClosureError(f"{target}: v4 TechniqueSet identity drift")

    programs = []
    for program in row.get("programs", []):
        p = dict(program)
        p["parentTechniqueSetOwners"] = [
            _label_path(value, labels) for value in program.get("parentTechniqueSetOwners", [])
        ]
        p["techniqueOwner"] = _label_path(str(program.get("techniqueOwner") or ""), labels)
        programs.append(p)

    technique_set_owners = [
        _label_path(value, labels) for value in row.get("techniqueSetOwners", [])
    ]
    relevant_techniques = {str(p.get("technique") or "") for p in row.get("programs", [])}
    relevant_provenance = []
    for prov in census.get("techniqueProvenance", []):
        if prov.get("techniqueSet") != doc.get("techniqueSet"):
            continue
        if prov.get("technique") not in relevant_techniques:
            continue
        q = dict(prov)
        q["parentOwners"] = [_label_path(value, labels) for value in prov.get("parentOwners", [])]
        q["chosenOwner"] = _label_path(str(prov.get("chosenOwner") or ""), labels)
        relevant_provenance.append(q)

    texture_records = []
    for index, texture in enumerate(doc.get("textures", [])):
        # Preserve the entire native OAT texture object.  The convenience fields
        # are duplicated only to make downstream Blender role joins explicit.
        texture_records.append(
            {
                "textureIndex": index,
                "image": texture.get("image"),
                "name": texture.get("name"),
                "semantic": texture.get("semantic"),
                "nativeRecord": texture,
            }
        )

    return {
        "material": target,
        "physicalMaterialCopies": physical,
        "canonicalMaterialBytes": len(raw),
        "canonicalMaterialSha256": _sha(raw),
        "nativeMaterialRecord": doc,
        "orderedTextureRecords": texture_records,
        "techniqueSet": doc.get("techniqueSet"),
        "techniqueSetOwners": technique_set_owners,
        "declaredTechniqueTypes": row.get("declaredTechniqueTypes", []),
        "hasLitBinding": bool(row.get("hasLitBinding")),
        "programs": programs,
        "techniqueProvenance": relevant_provenance,
        "v4ProofSummary": census.get("summary", {}),
    }


def build(
    material_roots: list[tuple[str, Path]],
    shader_roots: list[tuple[str, Path]],
    targets: list[str],
) -> dict[str, Any]:
    if not material_roots or not shader_roots:
        raise Seal6MaterialClosureError("material and shader root universes must both be non-empty")
    if not targets:
        raise Seal6MaterialClosureError("at least one target Material is required")
    if len(set(targets)) != len(targets):
        raise Seal6MaterialClosureError("duplicate target Material identity")

    materials = [_close_one(material_roots, shader_roots, target) for target in targets]
    unique_images = {
        str(tex["image"])
        for material in materials
        for tex in material["orderedTextureRecords"]
    }
    return {
        "format": FORMAT,
        "materialRoots": [{"label": label, "root": str(root)} for label, root in material_roots],
        "shaderRoots": [{"label": label, "root": str(root)} for label, root in shader_roots],
        "targets": targets,
        "summary": {
            "targetMaterialCount": len(materials),
            "closedTargetMaterialCount": len(materials),
            "physicalMaterialCopyCount": sum(len(row["physicalMaterialCopies"]) for row in materials),
            "orderedTextureRecordCount": sum(len(row["orderedTextureRecords"]) for row in materials),
            "uniqueImageAssetCount": len(unique_images),
            "allTargetsHaveLitBinding": all(row["hasLitBinding"] for row in materials),
            "unresolvedTargetCount": 0,
        },
        "materials": materials,
        "proofBoundary": (
            "Exact pinned-OAT Material JSON content inside the explicitly supplied Material-root universe. "
            "Every physical duplicate Material record must be byte-identical. Native textures[] order and full records are preserved verbatim; role names come only from OAT semantic/name fields. TechniqueSet -> declared Technique -> emitted shader ownership is resolved by the parent-provenance-aware t6-oat-material-shader-census-v4 path. No filename role inference, material adjacency, surface order, visual matching, or guessed zone precedence participates. A missing/divergent target or parent-owned dependency fails closed. This does not claim global absence or ownership outside the supplied roots."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--material-root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--shader-root", type=_parse_root, action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--target", action="append", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.material_root, a.shader_root, a.target)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    a.out.write_text(payload, encoding="utf-8")
    print(json.dumps({**result["summary"], "out": str(a.out), "sha256": _sha(payload.encode("utf-8"))}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
