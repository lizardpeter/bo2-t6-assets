#!/usr/bin/env python3
"""Augment a proven full-retail GLB with exact T6 XModel shader attributes.

This stage is deliberately separate from geometry rebasing.  The carrier must
already have authoritative geometry/skin/animations/materials and must not have
standard glTF COLOR_0.  The authority is the static GLB emitted by
``t6_xmodel_blender_static_bindpose_export_v3.py`` from the exact normalized
retail mesh.

Before copying any shader-only vertex stream, POSITION/NORMAL/TEXCOORD_0 are
compared value-for-value for every primitive.  This proves the authority and
carrier use the same primitive-local vertex ordering.  Then only these custom
attributes are added:

    _T6_COLOR_RGBA
    _T6_XMODEL_NORMAL      (aliases the carrier's already-proven NORMAL)
    _T6_XMODEL_TANGENT
    _T6_TANGENT_HANDEDNESS

Standard COLOR_0 remains absent.  Standard TANGENT is intentionally not added;
shader reconstruction consumes the custom exact aliases and cannot silently
fall back to generic glTF PBR semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

MAGIC = b"glTF"
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FLOAT = 5126
ARRAY_BUFFER = 34962
COMP = {
    5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
    5125: ("I", 4), 5126: ("f", 4),
}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
BASE_ATTRS = ("POSITION", "NORMAL", "TEXCOORD_0")
CUSTOM_ATTRS = ("_T6_COLOR_RGBA", "_T6_XMODEL_NORMAL", "_T6_XMODEL_TANGENT", "_T6_TANGENT_HANDEDNESS")


class ShaderAttributeAugmentError(RuntimeError):
    pass


def _load_glb(path: Path) -> tuple[dict[str, Any], bytearray]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ShaderAttributeAugmentError(f"invalid short GLB: {path}")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != MAGIC or version != 2 or total != len(data):
        raise ShaderAttributeAugmentError(f"invalid GLB header: {path}")
    off = 12
    doc = None
    binary = None
    while off < len(data):
        if off + 8 > len(data):
            raise ShaderAttributeAugmentError("truncated GLB chunk header")
        length, typ = struct.unpack_from("<II", data, off)
        off += 8
        chunk = data[off:off + length]
        off += length
        if typ == JSON_CHUNK:
            doc = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
        elif typ == BIN_CHUNK:
            binary = bytearray(chunk)
    if doc is None or binary is None:
        raise ShaderAttributeAugmentError(f"missing JSON/BIN GLB chunk: {path}")
    return doc, binary


def _save_glb(path: Path, doc: dict[str, Any], binary: bytearray) -> None:
    while len(binary) % 4:
        binary.append(0)
    doc["buffers"] = [{"byteLength": len(binary)}]
    raw_json = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    raw_json += b" " * ((-len(raw_json)) % 4)
    total = 12 + 8 + len(raw_json) + 8 + len(binary)
    payload = (
        struct.pack("<4sII", MAGIC, 2, total)
        + struct.pack("<II", len(raw_json), JSON_CHUNK) + raw_json
        + struct.pack("<II", len(binary), BIN_CHUNK) + bytes(binary)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _accessor_values(doc: dict[str, Any], binary: bytes | bytearray, index: int) -> list[tuple[Any, ...]]:
    accessor = doc["accessors"][index]
    if "sparse" in accessor:
        raise ShaderAttributeAugmentError("sparse accessors are unsupported")
    component = accessor["componentType"]
    if component not in COMP or accessor["type"] not in NCOMP:
        raise ShaderAttributeAugmentError(f"unsupported accessor layout {component}/{accessor['type']}")
    fmt, size = COMP[component]
    count = NCOMP[accessor["type"]]
    view = doc["bufferViews"][accessor["bufferView"]]
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    stride = int(view.get("byteStride", size * count))
    values = []
    for i in range(int(accessor["count"])):
        values.append(struct.unpack_from("<" + fmt * count, binary, base + i * stride))
    return values


def _align4(binary: bytearray) -> None:
    while len(binary) % 4:
        binary.append(0)


def _append_float_accessor(doc: dict[str, Any], binary: bytearray, rows: list[tuple[Any, ...]], typ: str, name: str, source: str) -> int:
    components = NCOMP[typ]
    if any(len(row) != components for row in rows):
        raise ShaderAttributeAugmentError(f"{name}: row width does not match {typ}")
    _align4(binary)
    offset = len(binary)
    values = [float(v) for row in rows for v in row]
    raw = struct.pack("<" + "f" * len(values), *values)
    binary.extend(raw)
    view_index = len(doc.setdefault("bufferViews", []))
    doc["bufferViews"].append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(raw),
        "byteStride": components * 4 if components > 1 else 4,
        "target": ARRAY_BUFFER,
        "name": name,
        "extras": {"T6": {"source": source}},
    })
    accessor_index = len(doc.setdefault("accessors", []))
    doc["accessors"].append({
        "bufferView": view_index,
        "componentType": FLOAT,
        "count": len(rows),
        "type": typ,
        "byteOffset": 0,
        "name": name,
        "extras": {"T6": {"source": source}},
    })
    return accessor_index


def _single_mesh_primitives(doc: dict[str, Any], label: str) -> list[dict[str, Any]]:
    meshes = doc.get("meshes")
    if not isinstance(meshes, list) or len(meshes) != 1:
        raise ShaderAttributeAugmentError(f"{label} must contain exactly one source mesh")
    prims = meshes[0].get("primitives")
    if not isinstance(prims, list) or not prims:
        raise ShaderAttributeAugmentError(f"{label} has no primitives")
    return prims


def augment(carrier_path: Path, authority_path: Path, output_path: Path, report_path: Path, *, require_primitives: int = 14) -> dict[str, Any]:
    carrier, cbin = _load_glb(carrier_path)
    authority, abin = _load_glb(authority_path)
    cp = _single_mesh_primitives(carrier, "carrier")
    ap = _single_mesh_primitives(authority, "authority")
    if len(cp) != len(ap) or len(cp) != require_primitives:
        raise ShaderAttributeAugmentError(f"primitive count mismatch carrier={len(cp)} authority={len(ap)} expected={require_primitives}")

    # The carrier is already the geometry-v3 full-retail rebase and therefore
    # must retain skin/animations/materials while standard COLOR_0 stays absent.
    if len(carrier.get("materials", [])) != 12:
        raise ShaderAttributeAugmentError("carrier must retain 12 exact Material identities")
    if len(carrier.get("animations", [])) != 6:
        raise ShaderAttributeAugmentError("carrier must retain six exact animations")
    skins = carrier.get("skins", [])
    if len(skins) != 1 or len(skins[0].get("joints", [])) != 102:
        raise ShaderAttributeAugmentError("carrier must retain one 102-joint skin")

    proof = []
    total_vertices = 0
    for i, (cprim, aprim) in enumerate(zip(cp, ap)):
        ca = cprim.get("attributes") or {}
        aa = aprim.get("attributes") or {}
        if "COLOR_0" in ca or "COLOR_0" in aa:
            raise ShaderAttributeAugmentError(f"primitive {i}: COLOR_0 is forbidden in carrier and authority")
        if any(name in ca for name in CUSTOM_ATTRS):
            raise ShaderAttributeAugmentError(f"primitive {i}: carrier already contains T6 shader custom attributes")
        for name in BASE_ATTRS:
            if name not in ca or name not in aa:
                raise ShaderAttributeAugmentError(f"primitive {i}: missing base attribute {name}")
            cv = _accessor_values(carrier, cbin, int(ca[name]))
            av = _accessor_values(authority, abin, int(aa[name]))
            if cv != av:
                raise ShaderAttributeAugmentError(f"primitive {i}: {name} differs between carrier and shader authority")
        for name in CUSTOM_ATTRS:
            if name not in aa:
                raise ShaderAttributeAugmentError(f"primitive {i}: shader authority lacks {name}")

        colors = _accessor_values(authority, abin, int(aa["_T6_COLOR_RGBA"]))
        normals = _accessor_values(authority, abin, int(aa["_T6_XMODEL_NORMAL"]))
        tangents = _accessor_values(authority, abin, int(aa["_T6_XMODEL_TANGENT"]))
        signs = _accessor_values(authority, abin, int(aa["_T6_TANGENT_HANDEDNESS"]))
        count = len(_accessor_values(carrier, cbin, int(ca["POSITION"])))
        if not all(len(rows) == count for rows in (colors, normals, tangents, signs)):
            raise ShaderAttributeAugmentError(f"primitive {i}: shader attribute vertex count mismatch")
        # _T6_XMODEL_NORMAL is an exact alias of the already-validated carrier
        # NORMAL accessor, so do not duplicate data.
        if normals != _accessor_values(carrier, cbin, int(ca["NORMAL"])):
            raise ShaderAttributeAugmentError(f"primitive {i}: XModel normal alias differs from carrier NORMAL")
        ca["_T6_XMODEL_NORMAL"] = int(ca["NORMAL"])
        ca["_T6_COLOR_RGBA"] = _append_float_accessor(
            carrier, cbin, colors, "VEC4", f"T6 exact shader color primitive {i}", "normalized GfxPackedVertex.colorRGBA"
        )
        ca["_T6_XMODEL_TANGENT"] = _append_float_accessor(
            carrier, cbin, tangents, "VEC3", f"T6 exact XModel tangent primitive {i}", "normalized GfxPackedVertex.tangentXYZ"
        )
        ca["_T6_TANGENT_HANDEDNESS"] = _append_float_accessor(
            carrier, cbin, signs, "SCALAR", f"T6 exact tangent handedness primitive {i}", "normalized GfxPackedVertex.binormalSign"
        )
        cprim.setdefault("extras", {}).setdefault("T6", {})["shaderAttributeAugmentation"] = {
            "format": "t6-gltf-augment-xmodel-shader-attributes-v1",
            "authorityPrimitive": i,
            "baseVertexOrderProvenBy": list(BASE_ATTRS),
            "customAttributes": list(CUSTOM_ATTRS),
            "color0Present": False,
        }
        total_vertices += count
        proof.append({
            "primitive": i,
            "vertexCount": count,
            "positionNormalUvExact": True,
            "xmodelNormalAliasesCarrierNormal": True,
            "shaderColorCopied": True,
            "retailTangentCopied": True,
            "retailHandednessCopied": True,
            "color0Present": False,
        })

    if total_vertices != 13490:
        raise ShaderAttributeAugmentError(f"LOD0 vertex total {total_vertices} != 13490")
    if any("COLOR_0" in p.get("attributes", {}) for p in cp):
        raise ShaderAttributeAugmentError("COLOR_0 survived augmentation")
    if any(not all(name in p.get("attributes", {}) for name in CUSTOM_ATTRS) for p in cp):
        raise ShaderAttributeAugmentError("one or more custom T6 shader attributes missing after augmentation")

    carrier.setdefault("asset", {})["generator"] = (
        str(carrier.get("asset", {}).get("generator", ""))
        + " | T6 exact XModel shader attributes v1"
    ).strip()
    carrier.setdefault("extras", {}).setdefault("T6", {})["xmodelShaderAttributeAugmentation"] = {
        "format": "t6-gltf-augment-xmodel-shader-attributes-v1",
        "authority": authority_path.name,
        "noStandardColor0": True,
        "noStandardTangentAdded": True,
        "customAttributes": list(CUSTOM_ATTRS),
        "rendererPolicy": "consume exact custom shader attributes; do not recreate COLOR_0 or derive tangent from UVs",
    }
    _save_glb(output_path, carrier, cbin)

    out_doc, out_bin = _load_glb(output_path)
    out_prims = _single_mesh_primitives(out_doc, "output")
    for i, p in enumerate(out_prims):
        attrs = p.get("attributes") or {}
        if "COLOR_0" in attrs or "TANGENT" in attrs:
            raise ShaderAttributeAugmentError(f"output primitive {i}: forbidden standard COLOR_0/TANGENT present")
        for name in CUSTOM_ATTRS:
            if name not in attrs:
                raise ShaderAttributeAugmentError(f"output primitive {i}: missing {name}")
        # Re-read every custom stream to prove the serialized GLB matches authority.
        aa = ap[i]["attributes"]
        for name in CUSTOM_ATTRS:
            ov = _accessor_values(out_doc, out_bin, int(attrs[name]))
            av = _accessor_values(authority, abin, int(aa[name]))
            if ov != av:
                raise ShaderAttributeAugmentError(f"output primitive {i}: serialized {name} differs from authority")

    report = {
        "format": "t6-gltf-augment-xmodel-shader-attributes-v1",
        "carrier": str(carrier_path),
        "carrierSha256": hashlib.sha256(carrier_path.read_bytes()).hexdigest(),
        "authority": str(authority_path),
        "authoritySha256": hashlib.sha256(authority_path.read_bytes()).hexdigest(),
        "output": str(output_path),
        "outputSha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "primitiveCount": len(cp),
        "vertices": total_vertices,
        "materials": len(out_doc.get("materials", [])),
        "animations": len(out_doc.get("animations", [])),
        "joints": len(out_doc.get("skins", [{}])[0].get("joints", [])),
        "customAttributesPerPrimitive": list(CUSTOM_ATTRS),
        "color0Present": False,
        "standardTangentPresent": False,
        "allBaseVertexOrdersProven": True,
        "allCustomShaderAttributesExact": True,
        "primitives": proof,
        "proofBoundary": (
            "Custom T6 shader vertex streams are copied only after exact per-primitive POSITION/NORMAL/UV equality "
            "proves vertex-order equivalence. Geometry/skin/animations/materials remain the carrier's previously "
            "proven data. Standard COLOR_0/TANGENT are deliberately absent from the augmented carrier."
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carrier", type=Path, required=True)
    ap.add_argument("--authority", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--require-primitives", type=int, default=14)
    args = ap.parse_args()
    report = augment(args.carrier, args.authority, args.output, args.report, require_primitives=args.require_primitives)
    print(json.dumps({
        "output": report["output"], "sha256": report["outputSha256"],
        "primitives": report["primitiveCount"], "vertices": report["vertices"],
        "customAttributesExact": report["allCustomShaderAttributesExact"], "color0Present": report["color0Present"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
