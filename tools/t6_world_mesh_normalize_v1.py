#!/usr/bin/env python3
"""Normalize audited T6 GfxWorld draw buffers into a map-independent mesh archive.

The input contract is intentionally one layer above raw FastFile walking:
- GfxSurface JSON (baseIndex/triCount/firstVertex/vertex data offsets/materials)
- exact vd0/vd1 bytes
- exact global uint16 index buffer
- a zero-error t6-world-vertex-proof-v1 report from t6_world_vertex_audit_v2.py

The output keeps each serialized vertex group once and stores surface indices as
local uint16-style indices into that group. This mirrors the T6 draw contract:
`firstVertex` is the GPU base-vertex destination, while the index values are
local to the group's vertices. No glTF axis conversion is performed here.

Additional normal-transform words are preserved packed until their semantic use
is independently source-closed; they are not guessed into extra normals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_zone_core import (
    GFX_WORLD_VD0_STRIDE,
    WORLD_VERTEX_FORMATS,
    MaterialWorldVertexFormat,
    decode_world_vd0_vertex,
    decode_world_vd1_vertex,
)


class NormalizeError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(path: Path, data: bytes) -> dict:
    return {"file": path.name, "bytes": len(data), "sha256": _sha256(data)}


def _surface_index(surface: dict, fallback: int) -> int:
    return int(surface.get("index", fallback))


def _optional_int(surface: dict, key: str) -> int | None:
    value = surface.get(key)
    return None if value is None else int(value)


def _decode_group_vertices(vd0: bytes, vd1: bytes, group: dict) -> dict:
    fmt = MaterialWorldVertexFormat(int(group["worldVertFormat"]))
    spec = WORLD_VERTEX_FORMATS[fmt]
    count = int(group["vertexCount"])
    off0 = int(group["vd0Offset"])
    off1 = int(group["vd1Offset"])

    end0 = off0 + count * GFX_WORLD_VD0_STRIDE
    end1 = off1 + count * spec.vd1_stride
    if off0 < 0 or end0 > len(vd0):
        raise NormalizeError(
            f"group {group.get('groupIndex')}: vd0 range {off0}:{end0} outside {len(vd0)}"
        )
    if spec.vd1_stride and (off1 < 0 or end1 > len(vd1)):
        raise NormalizeError(
            f"group {group.get('groupIndex')}: vd1 range {off1}:{end1} outside {len(vd1)}"
        )

    attrs: dict[str, list] = {
        "position": [],
        "binormalSign": [],
        "colorRGBA8": [],
        "color": [],
        "uv0": [],
        "normal": [],
        "normalPacked": [],
        "tangent": [],
        "tangentPacked": [],
        "lightmapUV": [],
        "lightmapUVRaw": [],
    }
    for field in spec.vd1_fields:
        key = field if field.startswith("uv") else field + "Packed"
        attrs[key] = []

    for vi in range(count):
        a = off0 + vi * GFX_WORLD_VD0_STRIDE
        row = decode_world_vd0_vertex(vd0[a : a + GFX_WORLD_VD0_STRIDE])
        if spec.vd1_stride:
            b = off1 + vi * spec.vd1_stride
            row.update(decode_world_vd1_vertex(vd1[b : b + spec.vd1_stride], fmt))

        attrs["position"].append(row["position"])
        attrs["binormalSign"].append(float(row["binormalSign"]))
        rgba = [int(v) for v in row["colorRGBA8"]]
        attrs["colorRGBA8"].append(rgba)
        attrs["color"].append([v / 255.0 for v in rgba])
        attrs["uv0"].append(row["uv0"])
        attrs["normal"].append(row["normal"])
        attrs["normalPacked"].append(int(row["normalPacked"]))
        attrs["tangent"].append(row["tangent"])
        attrs["tangentPacked"].append(int(row["tangentPacked"]))
        attrs["lightmapUV"].append(row["lightmapUV"])
        attrs["lightmapUVRaw"].append(row["lightmapUVRaw"])
        for field in spec.vd1_fields:
            key = field if field.startswith("uv") else field + "Packed"
            attrs[key].append(row[key])

    return {
        "groupIndex": int(group["groupIndex"]),
        "vd0Offset": off0,
        "vd1Offset": off1,
        "vertexCount": count,
        "worldVertFormat": int(fmt),
        "formatName": fmt.name,
        "uvCount": spec.uv_count,
        "normalCount": spec.normal_count,
        "vd1Stride": spec.vd1_stride,
        "vd1Fields": list(spec.vd1_fields),
        "attributes": attrs,
    }


def normalize(
    *,
    surfaces_doc: dict,
    vd0: bytes,
    vd1: bytes,
    index_bytes: bytes,
    proof: dict,
    source_meta: dict | None = None,
) -> dict:
    if proof.get("format") != "t6-world-vertex-proof-v1":
        raise NormalizeError(f"unsupported vertex proof format {proof.get('format')!r}")
    if int(proof.get("badGroupCount", 0)) != 0:
        raise NormalizeError(f"vertex proof contains {proof.get('badGroupCount')} bad groups")
    if len(index_bytes) % 2:
        raise NormalizeError(f"index buffer byte length {len(index_bytes)} is not uint16 aligned")

    surfaces = surfaces_doc.get("surfaces")
    if not isinstance(surfaces, list):
        raise NormalizeError("surface document has no surfaces list")
    map_name = surfaces_doc.get("name") or proof.get("map")
    if surfaces_doc.get("name") and proof.get("map") and surfaces_doc["name"] != proof["map"]:
        raise NormalizeError(
            f"map identity mismatch: surfaces={surfaces_doc['name']!r} proof={proof['map']!r}"
        )
    if int(proof.get("surfaceCount", len(surfaces))) != len(surfaces):
        raise NormalizeError(
            f"surface count mismatch: proof={proof.get('surfaceCount')} actual={len(surfaces)}"
        )

    indices = list(struct.unpack("<" + "H" * (len(index_bytes) // 2), index_bytes))
    proof_groups = proof.get("groups", [])
    if len(proof_groups) != int(proof.get("uniqueVertexGroups", len(proof_groups))):
        raise NormalizeError("vertex proof group count mismatch")

    by_surface: dict[int, int] = {}
    groups: list[dict] = []
    group_first_vertices: dict[int, int] = {}
    for expected_group_index, proof_group in enumerate(proof_groups):
        group_index = int(proof_group.get("groupIndex", expected_group_index))
        if group_index != expected_group_index:
            raise NormalizeError(
                f"proof groups must be dense/in order: expected {expected_group_index}, got {group_index}"
            )
        decoded = _decode_group_vertices(vd0, vd1, proof_group)
        surface_indices = [int(v) for v in proof_group.get("surfaceIndices", [])]
        if not surface_indices:
            raise NormalizeError(f"group {group_index}: no surfaces")
        first_vertices: set[int] = set()
        for si in surface_indices:
            if si < 0 or si >= len(surfaces):
                raise NormalizeError(f"group {group_index}: surface index {si} outside {len(surfaces)}")
            if si in by_surface:
                raise NormalizeError(f"surface {si} belongs to multiple vertex groups")
            surface = surfaces[si]
            if int(surface["vertexDataOffset0"]) != decoded["vd0Offset"]:
                raise NormalizeError(
                    f"surface {si}: vd0 offset {surface['vertexDataOffset0']} != group {decoded['vd0Offset']}"
                )
            if int(surface["vertexDataOffset1"]) != decoded["vd1Offset"]:
                raise NormalizeError(
                    f"surface {si}: vd1 offset {surface['vertexDataOffset1']} != group {decoded['vd1Offset']}"
                )
            stored_count = int(surface.get("vertexCount", 0))
            if stored_count not in (0, decoded["vertexCount"]):
                raise NormalizeError(
                    f"surface {si}: stored vertexCount {stored_count} != group {decoded['vertexCount']}"
                )
            first_vertices.add(int(surface["firstVertex"]))
            by_surface[si] = group_index
        if len(first_vertices) != 1:
            raise NormalizeError(
                f"group {group_index}: surfaces disagree on firstVertex {sorted(first_vertices)}"
            )
        first_vertex = next(iter(first_vertices))
        group_first_vertices[group_index] = first_vertex
        decoded["firstVertex"] = first_vertex
        decoded["surfaceIndices"] = surface_indices
        groups.append(decoded)

    if len(by_surface) != len(surfaces):
        missing = sorted(set(range(len(surfaces))) - set(by_surface))
        raise NormalizeError(f"{len(missing)} surfaces missing from proof groups; first={missing[:10]}")

    top_vertex_count = surfaces_doc.get("vertexCount")
    top_vertex_count = None if top_vertex_count is None else int(top_vertex_count)
    normalized_surfaces: list[dict] = []
    referenced_index_positions: set[int] = set()
    total_triangles = 0
    max_local_index = -1

    for list_index, surface in enumerate(surfaces):
        si = _surface_index(surface, list_index)
        if si != list_index:
            raise NormalizeError(
                f"surface record order/index mismatch at list {list_index}: record index {si}"
            )
        group_index = by_surface[list_index]
        group = groups[group_index]
        tri_count = int(surface["triCount"])
        base_index = int(surface["baseIndex"])
        if tri_count < 0 or base_index < 0:
            raise NormalizeError(f"surface {si}: negative triCount/baseIndex")
        index_count = tri_count * 3
        end = base_index + index_count
        if end > len(indices):
            raise NormalizeError(
                f"surface {si}: index slice {base_index}:{end} outside {len(indices)}"
            )
        local_indices = indices[base_index:end]
        if local_indices:
            local_max = max(local_indices)
            max_local_index = max(max_local_index, local_max)
            if local_max >= int(group["vertexCount"]):
                raise NormalizeError(
                    f"surface {si}: local index {local_max} outside group vertexCount {group['vertexCount']}"
                )
            if top_vertex_count is not None:
                gpu_max = int(group["firstVertex"]) + local_max
                if gpu_max >= top_vertex_count:
                    raise NormalizeError(
                        f"surface {si}: GPU vertex {gpu_max} outside top vertexCount {top_vertex_count}"
                    )
        referenced_index_positions.update(range(base_index, end))
        total_triangles += tri_count

        out_surface = {
            "index": si,
            "groupIndex": group_index,
            "baseIndex": base_index,
            "triCount": tri_count,
            "firstVertex": int(surface["firstVertex"]),
            "storedVertexCount": int(surface.get("vertexCount", 0)),
            "indices": local_indices,
            "material": surface.get("material"),
            "materialIndex": _optional_int(surface, "materialIndex"),
            "materialPointerRaw": surface.get("materialPointerRaw"),
            "lightmapIndex": _optional_int(surface, "lightmapIndex"),
            "reflectionProbeIndex": _optional_int(surface, "reflectionProbeIndex"),
            "primaryLightIndex": _optional_int(surface, "primaryLightIndex"),
            "flags": _optional_int(surface, "flags"),
            "bounds": surface.get("bounds"),
        }
        normalized_surfaces.append(out_surface)

    serialized_vertex_count = sum(int(g["vertexCount"]) for g in groups)
    if int(proof.get("vd0Bytes", len(vd0))) != len(vd0):
        raise NormalizeError(f"vd0 byte count differs from proof: {len(vd0)} != {proof.get('vd0Bytes')}")
    if int(proof.get("vd1Bytes", len(vd1))) != len(vd1):
        raise NormalizeError(f"vd1 byte count differs from proof: {len(vd1)} != {proof.get('vd1Bytes')}")
    if top_vertex_count is not None and serialized_vertex_count != top_vertex_count:
        raise NormalizeError(
            f"serialized group vertices {serialized_vertex_count} != top vertexCount {top_vertex_count}"
        )

    format_counts: dict[str, int] = {}
    for group in groups:
        key = str(group["worldVertFormat"])
        format_counts[key] = format_counts.get(key, 0) + 1

    stats = {
        "surfaceCount": len(normalized_surfaces),
        "vertexGroupCount": len(groups),
        "serializedVertexCount": serialized_vertex_count,
        "topVertexCount": top_vertex_count,
        "triangleCount": total_triangles,
        "referencedIndexCount": total_triangles * 3,
        "inputIndexCount": len(indices),
        "uniqueReferencedIndexPositions": len(referenced_index_positions),
        "unusedIndexPositions": len(indices) - len(referenced_index_positions),
        "maxLocalIndex": max_local_index,
        "worldVertFormatGroupCounts": dict(sorted(format_counts.items(), key=lambda kv: int(kv[0]))),
    }

    return {
        "format": "t6-world-mesh-normalized-v1",
        "map": map_name,
        "coordinatePolicy": "native T6 coordinates; no glTF axis/unit conversion applied",
        "indexPolicy": (
            "surface indices are uint16 local indices into group attributes; "
            "firstVertex is retained as original GPU base-vertex provenance"
        ),
        "normalTransformPolicy": (
            "normalTransformN words preserved packed; semantic application pending source closure"
        ),
        "source": source_meta or {},
        "stats": stats,
        "groups": groups,
        "surfaces": normalized_surfaces,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surfaces", type=Path, required=True)
    ap.add_argument("--vd0", type=Path, required=True)
    ap.add_argument("--vd1", type=Path, required=True)
    ap.add_argument("--indices", type=Path, required=True)
    ap.add_argument("--vertex-proof", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    surfaces_raw = args.surfaces.read_bytes()
    vd0 = args.vd0.read_bytes()
    vd1 = args.vd1.read_bytes()
    index_bytes = args.indices.read_bytes()
    proof_raw = args.vertex_proof.read_bytes()
    surfaces_doc = json.loads(surfaces_raw.decode("utf-8"))
    proof = json.loads(proof_raw.decode("utf-8"))
    source_meta = {
        "surfaces": _source(args.surfaces, surfaces_raw),
        "vd0": _source(args.vd0, vd0),
        "vd1": _source(args.vd1, vd1),
        "indices": _source(args.indices, index_bytes),
        "vertexProof": _source(args.vertex_proof, proof_raw),
    }
    doc = normalize(
        surfaces_doc=surfaces_doc,
        vd0=vd0,
        vd1=vd1,
        index_bytes=index_bytes,
        proof=proof,
        source_meta=source_meta,
    )
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.write_text(text, encoding="utf-8")
    print(json.dumps({"out": str(args.out), **doc["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
