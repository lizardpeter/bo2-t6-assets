#!/usr/bin/env python3
"""Augment a full-retail skinned T6 XModel GLB with exact shader-only attributes.

Unlike v1, this adapter uses the normalized retail XModel mesh JSON directly as
authority.  That is necessary because the animated/skinned GLB keeps vertex data
in raw T6 local coordinates and applies the T6->glTF axis/unit conversion on its
parent node, while the static bind-pose exporter bakes that conversion into its
vertex streams.

For every LOD0 primitive, v2 requires the carrier's surfaceIndex and exact
POSITION/NORMAL/TEXCOORD_0/JOINTS_0/WEIGHTS_0 values to reproduce the normalized
retail surface after the same float32 normalization used by the skinned exporter.
Only then are these shader-only attributes appended in the carrier's raw T6 local
basis:

    _T6_COLOR_RGBA
    _T6_XMODEL_NORMAL      (aliases carrier NORMAL)
    _T6_XMODEL_TANGENT
    _T6_TANGENT_HANDEDNESS

Standard glTF COLOR_0 and TANGENT remain forbidden.  The Blender shader backend
must consume the custom attributes and perform its explicit custom-attribute
axis conversion before OBJECT->WORLD transport.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

import t6_gltf_augment_xmodel_shader_attributes_v1 as v1

FORMAT = "t6-gltf-augment-xmodel-shader-attributes-v2"
CUSTOM_ATTRS = v1.CUSTOM_ATTRS
BASE_ATTRS = ("POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0")


class ShaderAttributeAugmentV2Error(RuntimeError):
    pass


def _f32(value: Any) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _f32_rows(rows: list[list[Any]] | list[tuple[Any, ...]]) -> list[tuple[float, ...]]:
    return [tuple(_f32(v) for v in row) for row in rows]


def _normalized_rows(surface: dict[str, Any]) -> dict[str, list[tuple[Any, ...]]]:
    vertices = surface.get("vertices")
    if not isinstance(vertices, list) or not vertices:
        raise ShaderAttributeAugmentV2Error(f"surface {surface.get('index')}: vertices missing")

    positions: list[list[float]] = []
    normals: list[list[float]] = []
    uvs: list[list[float]] = []
    colors: list[list[float]] = []
    tangents: list[list[float]] = []
    signs: list[list[float]] = []
    for i, vertex in enumerate(vertices):
        positions.append([float(x) for x in vertex["position"]])
        n = [float(x) for x in vertex["normal"]]
        nl = math.sqrt(sum(x * x for x in n))
        if not math.isfinite(nl) or nl <= 1.0e-12:
            raise ShaderAttributeAugmentV2Error(f"surface {surface.get('index')} vertex {i}: invalid normal")
        normals.append([x / nl for x in n])
        uvs.append([float(x) for x in vertex["texcoord0"]])
        colors.append([float(x) for x in vertex["colorRGBA"]])

        t = [float(x) for x in vertex["tangentXYZ"]]
        tl = math.sqrt(sum(x * x for x in t))
        if not math.isfinite(tl) or tl <= 1.0e-12:
            raise ShaderAttributeAugmentV2Error(f"surface {surface.get('index')} vertex {i}: invalid tangent")
        tangents.append([x / tl for x in t])
        sign = float(vertex["binormalSign"])
        if not math.isfinite(sign) or abs(abs(sign) - 1.0) > 1.0e-4:
            raise ShaderAttributeAugmentV2Error(f"surface {surface.get('index')} vertex {i}: invalid binormalSign {sign}")
        signs.append([1.0 if sign >= 0.0 else -1.0])

    joints = surface.get("joints0")
    weights = surface.get("weights0")
    if not isinstance(joints, list) or not isinstance(weights, list):
        raise ShaderAttributeAugmentV2Error(f"surface {surface.get('index')}: joints0/weights0 missing")
    if len(joints) != len(vertices) or len(weights) != len(vertices):
        raise ShaderAttributeAugmentV2Error(f"surface {surface.get('index')}: skin row count mismatch")

    return {
        "POSITION": _f32_rows(positions),
        "NORMAL": _f32_rows(normals),
        "TEXCOORD_0": _f32_rows(uvs),
        "JOINTS_0": [tuple(int(x) for x in row) for row in joints],
        "WEIGHTS_0": _f32_rows([[float(x) for x in row] for row in weights]),
        "_T6_COLOR_RGBA": _f32_rows(colors),
        "_T6_XMODEL_TANGENT": _f32_rows(tangents),
        "_T6_TANGENT_HANDEDNESS": _f32_rows(signs),
    }


def _lod_surfaces(mesh: dict[str, Any], lod: int) -> dict[int, dict[str, Any]]:
    if mesh.get("format") != "t6-xmodel-mesh-normalized-v1":
        raise ShaderAttributeAugmentV2Error(f"unsupported normalized mesh format {mesh.get('format')!r}")
    lod_row = next((r for r in mesh.get("xmodel", {}).get("lods", []) if int(r.get("index", -1)) == lod), None)
    if lod_row is None:
        raise ShaderAttributeAugmentV2Error(f"normalized mesh lacks LOD{lod}")
    start = int(lod_row["surfIndex"])
    count = int(lod_row["numSurfs"])
    rows = mesh.get("surfaces", [])[start:start + count]
    if len(rows) != count:
        raise ShaderAttributeAugmentV2Error(f"LOD{lod} surface span truncated")
    out = {int(r["index"]): r for r in rows}
    if len(out) != count:
        raise ShaderAttributeAugmentV2Error(f"LOD{lod} surface indices are not unique")
    return out


def _surface_index(primitive: dict[str, Any]) -> int:
    extra = primitive.get("extras") or {}
    t6 = extra.get("T6") if isinstance(extra, dict) else None
    if not isinstance(t6, dict) or "surfaceIndex" not in t6:
        raise ShaderAttributeAugmentV2Error("carrier primitive lacks exact T6 surfaceIndex")
    return int(t6["surfaceIndex"])


def augment(carrier_path: Path, mesh_path: Path, output_path: Path, report_path: Path, *, lod: int = 0, require_primitives: int = 14) -> dict[str, Any]:
    carrier, cbin = v1._load_glb(carrier_path)
    mesh = json.loads(mesh_path.read_text(encoding="utf-8-sig"))
    cp = v1._single_mesh_primitives(carrier, "carrier")
    surfaces = _lod_surfaces(mesh, lod)
    if len(cp) != require_primitives or len(surfaces) != require_primitives:
        raise ShaderAttributeAugmentV2Error(
            f"primitive/surface count mismatch carrier={len(cp)} surfaces={len(surfaces)} expected={require_primitives}"
        )
    if len(carrier.get("materials", [])) != 12 or len(carrier.get("animations", [])) != 6:
        raise ShaderAttributeAugmentV2Error("carrier must retain 12 materials and six animations")
    skins = carrier.get("skins", [])
    if len(skins) != 1 or len(skins[0].get("joints", [])) != 102:
        raise ShaderAttributeAugmentV2Error("carrier must retain one 102-joint skin")

    proof = []
    total_vertices = 0
    seen_surfaces = set()
    for primitive_index, cprim in enumerate(cp):
        attrs = cprim.get("attributes") or {}
        if "COLOR_0" in attrs or "TANGENT" in attrs:
            raise ShaderAttributeAugmentV2Error(f"primitive {primitive_index}: standard COLOR_0/TANGENT is forbidden")
        if any(name in attrs for name in CUSTOM_ATTRS):
            raise ShaderAttributeAugmentV2Error(f"primitive {primitive_index}: custom shader attributes already present")
        surface_index = _surface_index(cprim)
        if surface_index in seen_surfaces or surface_index not in surfaces:
            raise ShaderAttributeAugmentV2Error(f"primitive {primitive_index}: invalid/repeated surfaceIndex {surface_index}")
        seen_surfaces.add(surface_index)
        expected = _normalized_rows(surfaces[surface_index])

        for name in BASE_ATTRS:
            if name not in attrs:
                raise ShaderAttributeAugmentV2Error(f"primitive {primitive_index}: missing {name}")
            actual = v1._accessor_values(carrier, cbin, int(attrs[name]))
            if actual != expected[name]:
                raise ShaderAttributeAugmentV2Error(
                    f"primitive {primitive_index} surface {surface_index}: {name} differs from normalized retail mesh"
                )

        count = len(expected["POSITION"])
        if count != int(surfaces[surface_index]["vertCount"]):
            raise ShaderAttributeAugmentV2Error(f"surface {surface_index}: vertCount drift")
        attrs["_T6_XMODEL_NORMAL"] = int(attrs["NORMAL"])
        attrs["_T6_COLOR_RGBA"] = v1._append_float_accessor(
            carrier, cbin, expected["_T6_COLOR_RGBA"], "VEC4",
            f"T6 exact shader color surface {surface_index}", "normalized GfxPackedVertex.colorRGBA raw T6 local carrier basis"
        )
        attrs["_T6_XMODEL_TANGENT"] = v1._append_float_accessor(
            carrier, cbin, expected["_T6_XMODEL_TANGENT"], "VEC3",
            f"T6 exact XModel tangent surface {surface_index}", "normalized GfxPackedVertex.tangentXYZ raw T6 local carrier basis"
        )
        attrs["_T6_TANGENT_HANDEDNESS"] = v1._append_float_accessor(
            carrier, cbin, expected["_T6_TANGENT_HANDEDNESS"], "SCALAR",
            f"T6 exact tangent handedness surface {surface_index}", "normalized GfxPackedVertex.binormalSign"
        )
        cprim.setdefault("extras", {}).setdefault("T6", {})["shaderAttributeAugmentation"] = {
            "format": FORMAT,
            "surfaceIndex": surface_index,
            "vertexOrderProofAttributes": list(BASE_ATTRS),
            "customAttributes": list(CUSTOM_ATTRS),
            "basis": "raw T6 local; carrier parent node owns axis/unit transform",
        }
        total_vertices += count
        proof.append({
            "primitive": primitive_index,
            "surfaceIndex": surface_index,
            "vertexCount": count,
            "positionNormalUvJointsWeightsExact": True,
            "xmodelNormalAliasesCarrierNormal": True,
            "shaderColorCopied": True,
            "retailTangentCopied": True,
            "retailHandednessCopied": True,
        })

    if seen_surfaces != set(surfaces):
        raise ShaderAttributeAugmentV2Error(f"carrier surface set drift: {sorted(seen_surfaces)} != {sorted(surfaces)}")
    if total_vertices != 13490:
        raise ShaderAttributeAugmentV2Error(f"LOD0 vertex total {total_vertices} != 13490")

    carrier.setdefault("asset", {})["generator"] = (
        str(carrier.get("asset", {}).get("generator", "")) + " | T6 exact XModel shader attributes v2"
    ).strip()
    carrier.setdefault("extras", {}).setdefault("T6", {})["xmodelShaderAttributeAugmentation"] = {
        "format": FORMAT,
        "authority": mesh_path.name,
        "authoritySha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "lod": lod,
        "customAttributeBasis": "raw T6 local; same numeric basis as carrier POSITION/NORMAL before parent transform",
        "noStandardColor0": True,
        "noStandardTangent": True,
        "rendererPolicy": "consume exact _T6_* attributes; do not recreate COLOR_0 or derive tangent from UVs",
    }
    v1._save_glb(output_path, carrier, cbin)

    out_doc, out_bin = v1._load_glb(output_path)
    out_prims = v1._single_mesh_primitives(out_doc, "output")
    for primitive_index, p in enumerate(out_prims):
        attrs = p.get("attributes") or {}
        if "COLOR_0" in attrs or "TANGENT" in attrs:
            raise ShaderAttributeAugmentV2Error(f"output primitive {primitive_index}: forbidden standard attribute present")
        surface_index = _surface_index(p)
        expected = _normalized_rows(surfaces[surface_index])
        for name in CUSTOM_ATTRS:
            if name not in attrs:
                raise ShaderAttributeAugmentV2Error(f"output primitive {primitive_index}: missing {name}")
        if v1._accessor_values(out_doc, out_bin, int(attrs["_T6_XMODEL_NORMAL"])) != expected["NORMAL"]:
            raise ShaderAttributeAugmentV2Error(f"output primitive {primitive_index}: XModel normal alias drift")
        for name in ("_T6_COLOR_RGBA", "_T6_XMODEL_TANGENT", "_T6_TANGENT_HANDEDNESS"):
            if v1._accessor_values(out_doc, out_bin, int(attrs[name])) != expected[name]:
                raise ShaderAttributeAugmentV2Error(f"output primitive {primitive_index}: serialized {name} drift")

    report = {
        "format": FORMAT,
        "carrier": str(carrier_path),
        "carrierSha256": hashlib.sha256(carrier_path.read_bytes()).hexdigest(),
        "normalizedMeshAuthority": str(mesh_path),
        "normalizedMeshAuthoritySha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "output": str(output_path),
        "outputSha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "lod": lod,
        "primitiveCount": len(cp),
        "vertices": total_vertices,
        "materials": len(out_doc.get("materials", [])),
        "animations": len(out_doc.get("animations", [])),
        "joints": len(out_doc.get("skins", [{}])[0].get("joints", [])),
        "customAttributesPerPrimitive": list(CUSTOM_ATTRS),
        "color0Present": False,
        "standardTangentPresent": False,
        "allBaseVertexOrdersProven": True,
        "vertexOrderProofAttributes": list(BASE_ATTRS),
        "allCustomShaderAttributesExact": True,
        "customAttributeBasis": "raw T6 local carrier basis",
        "primitives": proof,
        "proofBoundary": (
            "Each carrier primitive is matched by exact serialized T6 surfaceIndex, then POSITION/NORMAL/TEXCOORD_0/JOINTS_0/WEIGHTS_0 are compared value-for-value against the normalized retail surface after reproducing the skinned exporter's float32 normalization. Only after that five-channel vertex-order proof are shader color, normalized retail tangent and handedness appended. Standard COLOR_0/TANGENT remain absent; geometry, skin, materials and animations are not modified."
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carrier", type=Path, required=True)
    ap.add_argument("--mesh", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--lod", type=int, default=0)
    ap.add_argument("--require-primitives", type=int, default=14)
    args = ap.parse_args()
    report = augment(args.carrier, args.mesh, args.output, args.report, lod=args.lod, require_primitives=args.require_primitives)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
