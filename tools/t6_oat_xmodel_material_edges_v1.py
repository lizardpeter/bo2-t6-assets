#!/usr/bin/env python3
"""Extract exact T6 XModel -> Material identity edges from pinned OAT glTF/GLB.

Pinned OpenAssetTools' T6 XModelToCommonConverter assigns each distinct surface
material from `material->info.name`; GltfWriter then writes that exact identity to
`materials[].name`.  This tool only consumes those names and primitive material
indices.  It does not infer textures from filenames or generic-PBR slots.

The resulting material identities are intended to join to this repository's
exact T6 Material -> GfxImage manifests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

GLB_MAGIC = b"glTF"
GLB_JSON_CHUNK = 0x4E4F534A
PINNED_OAT_COMMIT = "7d027e8f89118196713e955b0e11f8404149c54d"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_gltf(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".gltf":
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: glTF root must be object")
        return doc
    if suffix != ".glb":
        raise ValueError(f"unsupported OAT model payload {path.suffix!r}; use GLTF or GLB output")
    raw = path.read_bytes()
    if len(raw) < 20 or raw[:4] != GLB_MAGIC:
        raise ValueError(f"{path}: invalid GLB header")
    version, declared = struct.unpack_from("<II", raw, 4)
    if version != 2 or declared != len(raw):
        raise ValueError(f"{path}: GLB version/length mismatch")
    pos = 12
    json_chunk = None
    while pos + 8 <= len(raw):
        size, kind = struct.unpack_from("<II", raw, pos)
        pos += 8
        end = pos + size
        if end > len(raw):
            raise ValueError(f"{path}: truncated GLB chunk")
        if kind == GLB_JSON_CHUNK:
            if json_chunk is not None:
                raise ValueError(f"{path}: multiple JSON chunks")
            json_chunk = raw[pos:end]
        pos = end
    if pos != len(raw) or json_chunk is None:
        raise ValueError(f"{path}: malformed GLB chunk layout")
    return json.loads(json_chunk.rstrip(b" \t\r\n\0").decode("utf-8"))


def material_table(doc: dict[str, Any], source: Path) -> list[str]:
    materials = doc.get("materials", [])
    if not isinstance(materials, list):
        raise ValueError(f"{source}: materials must be array")
    names = []
    for i, row in enumerate(materials):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"]:
            raise ValueError(f"{source}: material[{i}] missing exact name")
        names.append(row["name"])
    return names


def primitive_edges(doc: dict[str, Any], materials: list[str], source: Path) -> list[dict[str, Any]]:
    meshes = doc.get("meshes", [])
    if not isinstance(meshes, list):
        raise ValueError(f"{source}: meshes must be array")
    edges = []
    for mi, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            raise ValueError(f"{source}: mesh[{mi}] not object")
        primitives = mesh.get("primitives", [])
        if not isinstance(primitives, list):
            raise ValueError(f"{source}: mesh[{mi}].primitives not array")
        for pi, prim in enumerate(primitives):
            if not isinstance(prim, dict):
                raise ValueError(f"{source}: mesh[{mi}].primitive[{pi}] not object")
            material_index = prim.get("material")
            if material_index is None:
                edges.append({
                    "meshIndex": mi,
                    "meshName": mesh.get("name"),
                    "primitiveIndex": pi,
                    "materialIndex": None,
                    "materialName": None,
                    "status": "primitive-without-material",
                })
                continue
            if not isinstance(material_index, int) or not 0 <= material_index < len(materials):
                raise ValueError(f"{source}: invalid primitive material index {material_index!r}")
            edges.append({
                "meshIndex": mi,
                "meshName": mesh.get("name"),
                "primitiveIndex": pi,
                "materialIndex": material_index,
                "materialName": materials[material_index],
                "status": "exact-oat-material-identity",
            })
    return edges


def process_model(model: dict[str, Any]) -> dict[str, Any]:
    lod_rows = []
    all_names = set()
    blockers = []
    for lod in model.get("lods", []):
        path = Path(lod.get("resolvedPath", ""))
        if not lod.get("present") or not path.is_file():
            blockers.append({"lod": lod.get("index"), "reason": "declared LOD payload missing", "path": str(path)})
            continue
        if path.suffix.lower() not in {".gltf", ".glb"}:
            blockers.append({
                "lod": lod.get("index"),
                "reason": "material-edge extraction requires OAT GLTF or GLB model output",
                "path": str(path),
            })
            continue
        doc = load_gltf(path)
        materials = material_table(doc, path)
        edges = primitive_edges(doc, materials, path)
        names = sorted({e["materialName"] for e in edges if e["materialName"] is not None})
        all_names.update(names)
        no_material = sum(e["materialName"] is None for e in edges)
        if no_material:
            blockers.append({"lod": lod.get("index"), "reason": "primitive without material", "count": no_material})
        lod_rows.append({
            "index": lod.get("index"),
            "path": str(path),
            "sha256": sha256(path),
            "materialTable": materials,
            "usedMaterialNames": names,
            "primitiveCount": len(edges),
            "primitiveEdges": edges,
        })
    return {
        "name": model["name"],
        "xmodelType": model.get("type"),
        "materialNames": sorted(all_names),
        "materialCount": len(all_names),
        "lods": lod_rows,
        "blockers": blockers,
        "status": "exact-material-edges" if not blockers and lod_rows else "blocked",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xmodel-catalog", type=Path, required=True)
    ap.add_argument("--only", action="append", default=[], help="exact XModel identity; repeat to limit catalog")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    catalog = json.loads(args.xmodel_catalog.read_text(encoding="utf-8-sig"))
    if catalog.get("format") != "t6-oat-xmodel-catalog-v1":
        raise ValueError("input is not t6-oat-xmodel-catalog-v1")
    producer = catalog.get("producer", {})
    if producer.get("commit") != PINNED_OAT_COMMIT:
        raise ValueError("XModel catalog is not from the project-pinned OAT commit")
    selected = set(args.only)
    models = [m for m in catalog.get("models", []) if not selected or m.get("name") in selected]
    if selected:
        found = {m.get("name") for m in models}
        missing = sorted(selected - found)
        if missing:
            raise ValueError(f"requested XModels absent from catalog: {missing}")
    rows = [process_model(m) for m in models]
    material_usage = Counter()
    for row in rows:
        for name in row["materialNames"]:
            material_usage[name] += 1
    blocked = [r["name"] for r in rows if r["status"] != "exact-material-edges"]
    out = {
        "format": "t6-oat-xmodel-material-edges-v1",
        "authority": {
            "oatCommit": PINNED_OAT_COMMIT,
            "materialIdentityRule": "T6 XModelToCommonConverter: XModel.materialHandles[surface] -> material->info.name; GltfWriter -> materials[].name",
            "texturePolicy": "no texture identity is inferred here; join exact Material identities to T6 Material manifests",
        },
        "source": {
            "xmodelCatalogPath": str(args.xmodel_catalog),
            "xmodelCatalogSha256": sha256(args.xmodel_catalog),
            "retailSource": catalog.get("source"),
        },
        "summary": {
            "models": len(rows),
            "modelsWithExactMaterialEdges": len(rows) - len(blocked),
            "blockedModels": blocked,
            "distinctMaterialNames": len(material_usage),
            "materialModelUsageCounts": dict(sorted(material_usage.items())),
        },
        "models": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0 if not blocked else 2


if __name__ == "__main__":
    raise SystemExit(main())
