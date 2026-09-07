#!/usr/bin/env python3
"""Blender-safe T6 XModel static export v3 with exact retail tangent basis.

v2 correctly demoted the packed T6 color field from standard glTF ``COLOR_0``
to ``_T6_COLOR_RGBA`` so stock glTF PBR cannot silently reinterpret it.

The retail normal-lit vertex shaders additionally consume a tangent stream. v1
and v2 did not transport it, which forced Blender to recompute tangent space from
UVs. That is not source-equivalent. v3 preserves v2's complete BIN payload as a
byte-identical prefix and appends one FLOAT VEC4 tangent stream per primitive
from normalized ``GfxPackedVertex.tangentXYZ`` + ``binormalSign``.

Blender-readable exact basis aliases are emitted as:

    _T6_XMODEL_NORMAL
    _T6_XMODEL_TANGENT
    _T6_TANGENT_HANDEDNESS

The T6->glTF coordinate transform is a proper rotation (determinant +1), so the
retail binormal sign is unchanged. No tangent is derived from UVs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

import t6_xmodel_blender_static_bindpose_export_v2 as v2
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes

FORMAT = "t6-xmodel-blender-static-bindpose-v3"
FLOAT = 5126
ARRAY_BUFFER = 34962


class XModelBlenderStaticV3Error(RuntimeError):
    pass


def _align4(raw: bytearray) -> None:
    while len(raw) % 4:
        raw.append(0)


def _unit_tangent(vertex: dict) -> list[float]:
    tx, ty, tz = (float(v) for v in vertex["tangentXYZ"])
    xyz = [tx, tz, -ty]
    length = math.sqrt(sum(v * v for v in xyz))
    if not math.isfinite(length) or length <= 1.0e-12:
        raise XModelBlenderStaticV3Error("retail tangent is zero/nonfinite")
    xyz = [v / length for v in xyz]
    w = float(vertex["binormalSign"])
    if not math.isfinite(w) or abs(abs(w) - 1.0) > 1.0e-4:
        raise XModelBlenderStaticV3Error(f"unexpected retail binormalSign {w!r}")
    return [*xyz, 1.0 if w >= 0.0 else -1.0]


def _append_tangent_stream(document: dict, raw: bytearray, rows: list[list[float]]) -> tuple[int, int, int]:
    _align4(raw)
    offset = len(raw)
    values = [component for row in rows for component in row]
    payload = struct.pack("<" + "f" * len(values), *values)
    raw.extend(payload)

    views = document.setdefault("bufferViews", [])
    accessors = document.setdefault("accessors", [])
    view_index = len(views)
    views.append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
        "byteStride": 16,
        "target": ARRAY_BUFFER,
        "name": "T6 exact XModel tangent stream",
        "extras": {"T6": {"source": "GfxPackedVertex.tangentXYZ+binormalSign"}},
    })

    tangent = len(accessors)
    accessors.append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": len(rows),
        "type": "VEC4",
        "byteOffset": 0,
        "name": "TANGENT",
        "extras": {"T6": {"source": "exact retail packed tangent + binormal sign"}},
    })
    tangent_xyz = len(accessors)
    accessors.append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": len(rows),
        "type": "VEC3",
        "byteOffset": 0,
        "name": "_T6_XMODEL_TANGENT",
        "extras": {"T6": {"sourceAccessor": tangent, "components": "xyz"}},
    })
    handedness = len(accessors)
    accessors.append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": len(rows),
        "type": "SCALAR",
        "byteOffset": 12,
        "name": "_T6_TANGENT_HANDEDNESS",
        "extras": {"T6": {"sourceAccessor": tangent, "component": "w"}},
    })
    return tangent, tangent_xyz, handedness


def export(mesh_doc: dict, lod: int = 0) -> bytes:
    base = v2.export(mesh_doc, lod)
    document, raw_bytes = parse_glb(base)
    raw = bytearray(raw_bytes)
    base_raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    base_raw_len = len(raw_bytes)

    lod_meta = next(
        (row for row in mesh_doc["xmodel"]["lods"] if int(row["index"]) == int(lod)),
        None,
    )
    if lod_meta is None:
        raise XModelBlenderStaticV3Error(f"LOD{lod} unavailable")
    surfaces = mesh_doc["surfaces"][
        int(lod_meta["surfIndex"]): int(lod_meta["surfIndex"]) + int(lod_meta["numSurfs"])
    ]
    primitives = document["meshes"][0]["primitives"]
    if len(primitives) != len(surfaces):
        raise XModelBlenderStaticV3Error("v2 primitive count does not match normalized LOD surface count")

    proof_rows = []
    for primitive_index, (primitive, surface) in enumerate(zip(primitives, surfaces)):
        attrs = primitive.get("attributes")
        if not isinstance(attrs, dict) or "NORMAL" not in attrs or "_T6_COLOR_RGBA" not in attrs:
            raise XModelBlenderStaticV3Error(
                f"primitive {primitive_index} lacks required v2 NORMAL/_T6_COLOR_RGBA"
            )
        if "COLOR_0" in attrs:
            raise XModelBlenderStaticV3Error("v3 must preserve v2 COLOR_0 demotion")
        if "TANGENT" in attrs or any(
            name in attrs for name in ("_T6_XMODEL_NORMAL", "_T6_XMODEL_TANGENT", "_T6_TANGENT_HANDEDNESS")
        ):
            raise XModelBlenderStaticV3Error(f"primitive {primitive_index} already contains tangent/basis aliases")

        tangents = [_unit_tangent(vertex) for vertex in surface["vertices"]]
        tangent, tangent_xyz, handedness = _append_tangent_stream(document, raw, tangents)
        normal_accessor = int(attrs["NORMAL"])
        if int(document["accessors"][normal_accessor]["count"]) != len(tangents):
            raise XModelBlenderStaticV3Error(f"primitive {primitive_index} NORMAL/tangent counts disagree")
        attrs["TANGENT"] = tangent
        attrs["_T6_XMODEL_NORMAL"] = normal_accessor
        attrs["_T6_XMODEL_TANGENT"] = tangent_xyz
        attrs["_T6_TANGENT_HANDEDNESS"] = handedness
        primitive.setdefault("extras", {}).setdefault("T6", {})["xmodelNormalBasisAttributes"] = FORMAT
        proof_rows.append({
            "primitive": primitive_index,
            "surfaceIndex": int(surface["index"]),
            "vertexCount": len(tangents),
            "normalAccessor": normal_accessor,
            "tangentAccessor": tangent,
            "tangentAliasAccessor": tangent_xyz,
            "handednessAccessor": handedness,
        })

    if bytes(raw[:base_raw_len]) != raw_bytes:
        raise XModelBlenderStaticV3Error("v3 changed the complete v2 BIN prefix")
    _align4(raw)
    document["buffers"][0]["byteLength"] = len(raw)
    document.setdefault("asset", {})["generator"] = "bo2-t6-assets t6_xmodel_blender_static_bindpose_export_v3.py"
    document.setdefault("extras", {}).setdefault("T6", {})["xmodelNormalBasisAttributes"] = {
        "format": FORMAT,
        "source": "normalized GfxPackedVertex tangentXYZ/binormalSign",
        "coordinateTransform": "(x,y,z)->(x,z,-y), determinant +1; handedness unchanged",
        "baseV2BinBytes": base_raw_len,
        "baseV2BinSha256": base_raw_sha,
        "baseV2BinPrefixByteIdentical": True,
        "primitives": proof_rows,
        "rendererPolicy": (
            "Blender shader reconstruction must consume the custom exact basis attributes; "
            "do not recompute tangent from UVs when reproducing a T6 shader that routes code.tangent"
        ),
    }
    return glb_bytes(document, bytes(raw))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh_json", type=Path)
    parser.add_argument("output_glb", type=Path)
    parser.add_argument("--lod", type=int, default=0)
    args = parser.parse_args()
    mesh = json.loads(args.mesh_json.read_text(encoding="utf-8"))
    out = export(mesh, args.lod)
    args.output_glb.write_bytes(out)
    print(json.dumps({
        "format": FORMAT,
        "out": str(args.output_glb),
        "bytes": len(out),
        "sha256": hashlib.sha256(out).hexdigest(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
