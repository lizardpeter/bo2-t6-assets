#!/usr/bin/env python3
"""Create a normalized T6 GLB export-state manifest and validate parent lineage.

The state is deliberately independent of any one map/model exporter.  It records
stable geometry/placement fingerprints plus exact material/image identity sets that
can be compared monotonically against one or more parent states.

A child state may add evidence.  For the same declared asset scope it may not silently
lose a parent's geometry, placements, material identities, proven texture-bearing
material identities, visible render-state identities or image identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Iterable


class ExportStateError(RuntimeError):
    pass


_COMPONENT_BYTES = {
    5120: 1,  # BYTE
    5121: 1,  # UNSIGNED_BYTE
    5122: 2,  # SHORT
    5123: 2,  # UNSIGNED_SHORT
    5125: 4,  # UNSIGNED_INT
    5126: 4,  # FLOAT
}
_TYPE_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def read_glb(path: Path) -> tuple[dict[str, Any], bytes, bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ExportStateError(f"{path}: too small for GLB2")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ExportStateError(f"{path}: invalid GLB2 header")
    off = 12
    document = None
    raw = b""
    while off < total:
        length, kind = struct.unpack_from("<I4s", data, off)
        off += 8
        payload = data[off:off + length]
        if len(payload) != length:
            raise ExportStateError(f"{path}: truncated chunk")
        off += length
        if kind == b"JSON":
            if document is not None:
                raise ExportStateError(f"{path}: duplicate JSON chunk")
            document = json.loads(payload.rstrip(b" \0"))
        elif kind == b"BIN\0":
            if raw:
                raise ExportStateError(f"{path}: multiple BIN chunks unsupported")
            raw = payload
    if document is None:
        raise ExportStateError(f"{path}: missing JSON")
    if raw:
        buffers = document.get("buffers", [])
        if len(buffers) != 1 or int(buffers[0].get("byteLength", -1)) != len(raw):
            raise ExportStateError(f"{path}: BIN byteLength mismatch")
    return document, raw, data


def material_name(material: dict[str, Any]) -> str:
    t6 = ((material.get("extras") or {}).get("T6") or {})
    return str(t6.get("sourceMaterial") or material.get("name") or "")


def image_name(image: dict[str, Any], index: int) -> str:
    t6 = ((image.get("extras") or {}).get("T6") or {})
    return str(t6.get("sourceImage") or image.get("name") or f"@image:{index}")


def accessor_digest(document: dict[str, Any], raw: bytes, accessor_index: int) -> dict[str, Any]:
    accessors = document.get("accessors", [])
    views = document.get("bufferViews", [])
    if not 0 <= accessor_index < len(accessors):
        raise ExportStateError(f"invalid accessor {accessor_index}")
    accessor = accessors[accessor_index]
    if "sparse" in accessor:
        # Sparse accessors are retained as an explicit unsupported fingerprint branch
        # rather than ignored.  The complete sparse description is hashed fail-closed.
        return {
            "index": accessor_index,
            "sparse": True,
            "sha256": sha256_bytes(canonical_bytes(accessor)),
        }
    if "bufferView" not in accessor:
        # Legal zero/default accessor. Preserve metadata exactly.
        return {
            "index": accessor_index,
            "bufferView": None,
            "sha256": sha256_bytes(canonical_bytes(accessor)),
        }
    view_index = int(accessor["bufferView"])
    if not 0 <= view_index < len(views):
        raise ExportStateError(f"accessor {accessor_index}: invalid bufferView {view_index}")
    view = views[view_index]
    if int(view.get("buffer", 0)) != 0:
        raise ExportStateError(f"accessor {accessor_index}: external/multi-buffer geometry unsupported")
    component_type = int(accessor["componentType"])
    type_name = str(accessor["type"])
    if component_type not in _COMPONENT_BYTES or type_name not in _TYPE_COMPONENTS:
        raise ExportStateError(f"accessor {accessor_index}: unsupported component/type")
    element_bytes = _COMPONENT_BYTES[component_type] * _TYPE_COMPONENTS[type_name]
    count = int(accessor["count"])
    stride = int(view.get("byteStride", element_bytes))
    if stride < element_bytes:
        raise ExportStateError(f"accessor {accessor_index}: byteStride {stride} < {element_bytes}")
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    payload = bytearray()
    for i in range(count):
        start = base + i * stride
        end = start + element_bytes
        if start < 0 or end > len(raw):
            raise ExportStateError(f"accessor {accessor_index}: data range outside BIN")
        payload.extend(raw[start:end])
    meta = {
        "componentType": component_type,
        "type": type_name,
        "count": count,
        "normalized": bool(accessor.get("normalized", False)),
        "elementBytes": element_bytes,
    }
    return {
        "index": accessor_index,
        "meta": meta,
        "sha256": sha256_bytes(canonical_bytes(meta) + bytes(payload)),
    }


def geometry_fingerprint(document: dict[str, Any], raw: bytes) -> tuple[str, dict[str, Any]]:
    digest_cache: dict[int, str] = {}

    def ad(index: int) -> str:
        if index not in digest_cache:
            digest_cache[index] = accessor_digest(document, raw, index)["sha256"]
        return digest_cache[index]

    meshes = []
    primitive_count = 0
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        prims = []
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            primitive_count += 1
            attrs = {str(k): ad(int(v)) for k, v in sorted((primitive.get("attributes") or {}).items())}
            targets = [
                {str(k): ad(int(v)) for k, v in sorted(target.items())}
                for target in primitive.get("targets", [])
            ]
            prims.append({
                "primitiveIndex": primitive_index,
                "mode": int(primitive.get("mode", 4)),
                "indices": None if primitive.get("indices") is None else ad(int(primitive["indices"])),
                "attributes": attrs,
                "targets": targets,
            })
        meshes.append({"meshIndex": mesh_index, "primitives": prims})
    document_for_hash = {"meshes": meshes}
    return sha256_bytes(canonical_bytes(document_for_hash)), {
        "meshCount": len(meshes),
        "primitiveCount": primitive_count,
        "uniqueGeometryAccessorCount": len(digest_cache),
    }


def placement_fingerprint(document: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    nodes = document.get("nodes", [])
    rows = []
    mesh_nodes = 0
    for index, node in enumerate(nodes):
        if "mesh" in node:
            mesh_nodes += 1
        row = {
            "nodeIndex": index,
            "mesh": node.get("mesh"),
            "skin": node.get("skin"),
            "matrix": node.get("matrix"),
            "translation": node.get("translation"),
            "rotation": node.get("rotation"),
            "scale": node.get("scale"),
            "children": node.get("children", []),
        }
        rows.append(row)
    scenes = [
        {"nodes": list(scene.get("nodes", []))}
        for scene in document.get("scenes", [])
    ]
    payload = {"defaultScene": document.get("scene", 0), "nodes": rows, "scenes": scenes}
    return sha256_bytes(canonical_bytes(payload)), {
        "nodeCount": len(nodes),
        "meshNodeCount": mesh_nodes,
        "sceneCount": len(scenes),
        "topLevelNodeCount": sum(len(x["nodes"]) for x in scenes),
    }


def referenced_material_indices(document: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    material_count = len(document.get("materials", []))
    for mesh_index, mesh in enumerate(document.get("meshes", [])):
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            value = primitive.get("material")
            if value is None:
                continue
            if not isinstance(value, int) or not 0 <= value < material_count:
                raise ExportStateError(
                    f"mesh {mesh_index} primitive {primitive_index}: invalid material {value!r}"
                )
            out.add(value)
    return out


def sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({v for v in values if v})


def evidence_sets(document: dict[str, Any]) -> dict[str, list[str]]:
    materials = document.get("materials", [])
    referenced = referenced_material_indices(document)
    names = [material_name(m) for m in materials]
    images = document.get("images", [])
    return {
        "materialIdentities": sorted_unique(names),
        "referencedMaterialIdentities": sorted_unique(names[i] for i in referenced),
        "baseColorMaterialIdentities": sorted_unique(
            names[i]
            for i, m in enumerate(materials)
            if (m.get("pbrMetallicRoughness") or {}).get("baseColorTexture") is not None
        ),
        "normalMaterialIdentities": sorted_unique(
            names[i] for i, m in enumerate(materials) if m.get("normalTexture") is not None
        ),
        "nonOpaqueMaterialIdentities": sorted_unique(
            names[i] for i, m in enumerate(materials) if m.get("alphaMode", "OPAQUE") != "OPAQUE"
        ),
        "doubleSidedMaterialIdentities": sorted_unique(
            names[i] for i, m in enumerate(materials) if m.get("doubleSided") is True
        ),
        "genericReferencedMaterialIdentities": sorted_unique(
            names[i]
            for i in referenced
            if names[i].startswith("material_surface_")
        ),
        "imageIdentities": sorted_unique(image_name(image, i) for i, image in enumerate(images)),
    }


def validate_parent(parent: dict[str, Any], child: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    if parent.get("format") != "t6-export-state-v1":
        raise ExportStateError("parent has unsupported export-state format")
    pa = parent.get("asset") or {}
    ca = child.get("asset") or {}
    if pa.get("type") != ca.get("type") or pa.get("name") != ca.get("name"):
        failures.append({"kind": "asset-scope", "parent": pa, "child": ca})
        return failures
    if parent.get("geometry", {}).get("fingerprint") != child.get("geometry", {}).get("fingerprint"):
        failures.append({"kind": "geometry-fingerprint"})
    if parent.get("placements", {}).get("fingerprint") != child.get("placements", {}).get("fingerprint"):
        failures.append({"kind": "placement-fingerprint"})

    pe = parent.get("evidence") or {}
    ce = child.get("evidence") or {}
    monotonic_keys = (
        "materialIdentities",
        "referencedMaterialIdentities",
        "baseColorMaterialIdentities",
        "normalMaterialIdentities",
        "nonOpaqueMaterialIdentities",
        "imageIdentities",
    )
    for key in monotonic_keys:
        before = set(pe.get(key, []))
        after = set(ce.get(key, []))
        missing = sorted(before - after)
        if missing:
            failures.append({"kind": "evidence-regression", "set": key, "missing": missing})
    parent_generic = set(pe.get("genericReferencedMaterialIdentities", []))
    child_generic = set(ce.get("genericReferencedMaterialIdentities", []))
    introduced = sorted(child_generic - parent_generic)
    if introduced:
        failures.append({"kind": "new-generic-material-regression", "introduced": introduced})
    return failures


def build_state(
    glb_path: Path,
    *,
    asset_type: str,
    asset_name: str,
    parent_paths: list[Path],
    capabilities_path: Path | None,
) -> dict[str, Any]:
    document, raw, full = read_glb(glb_path)
    geometry_hash, geometry_stats = geometry_fingerprint(document, raw)
    placement_hash, placement_stats = placement_fingerprint(document)
    evidence = evidence_sets(document)
    capabilities = None
    if capabilities_path is not None:
        capabilities = json.loads(capabilities_path.read_text(encoding="utf-8"))

    parents = []
    parent_docs = []
    for path in parent_paths:
        payload = path.read_bytes()
        doc = json.loads(payload.decode("utf-8"))
        parent_docs.append(doc)
        parents.append({
            "file": path.name,
            "sha256": sha256_bytes(payload),
            "outputSha256": (doc.get("output") or {}).get("sha256"),
        })

    state = {
        "format": "t6-export-state-v1",
        "asset": {"type": asset_type, "name": asset_name},
        "output": {
            "file": glb_path.name,
            "bytes": len(full),
            "sha256": sha256_bytes(full),
        },
        "geometry": {"fingerprint": geometry_hash, **geometry_stats},
        "placements": {"fingerprint": placement_hash, **placement_stats},
        "evidence": evidence,
        "parents": parents,
        "capabilities": capabilities,
        "stats": {
            "materialIdentityCount": len(evidence["materialIdentities"]),
            "referencedMaterialIdentityCount": len(evidence["referencedMaterialIdentities"]),
            "baseColorMaterialIdentityCount": len(evidence["baseColorMaterialIdentities"]),
            "normalMaterialIdentityCount": len(evidence["normalMaterialIdentities"]),
            "nonOpaqueMaterialIdentityCount": len(evidence["nonOpaqueMaterialIdentities"]),
            "doubleSidedMaterialIdentityCount": len(evidence["doubleSidedMaterialIdentities"]),
            "genericReferencedMaterialIdentityCount": len(evidence["genericReferencedMaterialIdentities"]),
            "imageIdentityCount": len(evidence["imageIdentities"]),
        },
        "policy": (
            "Exact identity sets are monotonic for a fixed asset scope. A child may add evidence "
            "but may not silently lose a parent's geometry, placements, material/image identities, "
            "texture-bearing material identities or visible alpha-state identities."
        ),
    }

    lineage_failures = []
    for parent_doc in parent_docs:
        lineage_failures.extend(validate_parent(parent_doc, state))
    state["lineageValidation"] = {
        "parentCount": len(parent_docs),
        "passed": not lineage_failures,
        "failureCount": len(lineage_failures),
        "failures": lineage_failures,
    }
    if lineage_failures:
        raise ExportStateError(json.dumps(state["lineageValidation"], indent=2))
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--asset-type", required=True)
    parser.add_argument("--asset-name", required=True)
    parser.add_argument("--parent", type=Path, action="append", default=[])
    parser.add_argument("--capabilities", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    state = build_state(
        args.glb,
        asset_type=args.asset_type,
        asset_name=args.asset_name,
        parent_paths=args.parent,
        capabilities_path=args.capabilities,
    )
    args.out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
