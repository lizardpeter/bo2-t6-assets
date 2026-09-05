#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_INSTANCES = 1943
EXPECTED_MESHES = 297
EXPECTED_USED_MESHES = 295
EXPECTED_MATERIALS = 344
EXPECTED_UNIQUE_PRIMITIVE_SLOTS = 538
EXPECTED_RENDERED_PRIMITIVES = 2790
EXPECTED_RENDERED_TRIANGLES = 932451
EXPECTED_UNUSED_MESH_NAMES = {
    "mlv/nt_2020_vista_kiosk_blue",
    "mlv/nt_2020_vista_ufo_01",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"{path}: truncated GLB")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError(f"{path}: invalid GLB header")
    off = 12
    root = None
    while off < len(data):
        length, chunk_type = struct.unpack_from("<I4s", data, off)
        off += 8
        chunk = data[off:off + length]
        off += length
        if chunk_type == b"JSON":
            root = json.loads(chunk.rstrip(b" \0"))
    if root is None:
        raise ValueError(f"{path}: no JSON chunk")
    return root


def primitive_triangle_count(gltf: dict, primitive: dict) -> int:
    mode = primitive.get("mode", 4)
    if mode != 4:
        raise ValueError(f"non-TRIANGLES primitive mode {mode}")
    if "indices" in primitive:
        accessor = gltf["accessors"][primitive["indices"]]
    else:
        pos = primitive.get("attributes", {}).get("POSITION")
        if pos is None:
            raise ValueError("non-indexed primitive without POSITION")
        accessor = gltf["accessors"][pos]
    count = int(accessor["count"])
    if count % 3:
        raise ValueError(f"triangle primitive accessor count {count} is not divisible by 3")
    return count // 3


def validate(path: Path) -> dict:
    gltf = read_glb_json(path)
    meshes = gltf.get("meshes", [])
    nodes = gltf.get("nodes", [])
    materials = gltf.get("materials", [])

    mesh_nodes = [n for n in nodes if "mesh" in n]
    if len(meshes) != EXPECTED_MESHES:
        raise ValueError(f"mesh definitions {len(meshes)} != {EXPECTED_MESHES}")
    if len(mesh_nodes) != EXPECTED_INSTANCES:
        raise ValueError(f"mesh instances {len(mesh_nodes)} != {EXPECTED_INSTANCES}")
    if len(materials) != EXPECTED_MATERIALS:
        raise ValueError(f"materials {len(materials)} != {EXPECTED_MATERIALS}")

    unique_slots = sum(len(m.get("primitives", [])) for m in meshes)
    if unique_slots != EXPECTED_UNIQUE_PRIMITIVE_SLOTS:
        raise ValueError(f"unique-model primitive slots {unique_slots} != {EXPECTED_UNIQUE_PRIMITIVE_SLOTS}")

    mesh_primitive_counts = []
    mesh_triangle_counts = []
    for mi, mesh in enumerate(meshes):
        prims = mesh.get("primitives", [])
        if not prims:
            raise ValueError(f"mesh {mi} has no primitives")
        mesh_primitive_counts.append(len(prims))
        mesh_triangle_counts.append(sum(primitive_triangle_count(gltf, p) for p in prims))

    rendered_primitives = 0
    rendered_triangles = 0
    used_meshes = set()
    for ni, node in enumerate(mesh_nodes):
        mi = int(node["mesh"])
        if not 0 <= mi < len(meshes):
            raise ValueError(f"node mesh index out of range: node={ni} mesh={mi}")
        used_meshes.add(mi)
        rendered_primitives += mesh_primitive_counts[mi]
        rendered_triangles += mesh_triangle_counts[mi]

    if len(used_meshes) != EXPECTED_USED_MESHES:
        raise ValueError(f"referenced mesh definitions {len(used_meshes)} != {EXPECTED_USED_MESHES}")
    unused_names = {meshes[i].get("name") for i in range(len(meshes)) if i not in used_meshes}
    if unused_names != EXPECTED_UNUSED_MESH_NAMES:
        raise ValueError(f"unexpected uninstantiated definitions: {sorted(unused_names)}")
    if rendered_primitives != EXPECTED_RENDERED_PRIMITIVES:
        raise ValueError(f"rendered primitive instances {rendered_primitives} != {EXPECTED_RENDERED_PRIMITIVES}")
    if rendered_triangles != EXPECTED_RENDERED_TRIANGLES:
        raise ValueError(f"rendered triangles {rendered_triangles} != {EXPECTED_RENDERED_TRIANGLES}")

    summary = {
        "format": "t6-nuketown-recovered-static-scene-acceptance-v2",
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "meshDefinitions": len(meshes),
        "referencedMeshDefinitions": len(used_meshes),
        "uninstantiatedMeshDefinitions": sorted(unused_names),
        "meshInstances": len(mesh_nodes),
        "materials": len(materials),
        "uniqueModelPrimitiveSlots": unique_slots,
        "renderedPrimitiveInstances": rendered_primitives,
        "renderedTriangles": rendered_triangles,
        "accepted": True,
        "expected": {
            "meshDefinitions": EXPECTED_MESHES,
            "referencedMeshDefinitions": EXPECTED_USED_MESHES,
            "meshInstances": EXPECTED_INSTANCES,
            "materials": EXPECTED_MATERIALS,
            "uniqueModelPrimitiveSlots": EXPECTED_UNIQUE_PRIMITIVE_SLOTS,
            "renderedPrimitiveInstances": EXPECTED_RENDERED_PRIMITIVES,
            "renderedTriangles": EXPECTED_RENDERED_TRIANGLES,
        },
        "proofBoundary": (
            "Independent post-assembly accounting for the newly recovered 1943-row full-bounds partition. "
            "The 297/538/344 definition totals are independently retained proof. The 295 referenced definitions, "
            "2790 rendered primitive instances, and 932451 rendered triangles are deterministic consequences of "
            "that recovered partition plus exact OAT v0.33.0 LOD0 geometry; they are not represented here as "
            "independently preserved numeric totals from the lost historical v6 exporter."
        ),
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("glb", type=Path)
    ap.add_argument("--summary", type=Path)
    args = ap.parse_args()
    result = validate(args.glb)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.summary:
        args.summary.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
