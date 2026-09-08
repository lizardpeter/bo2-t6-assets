#!/usr/bin/env python3
"""Import a proven T6 full-retail carrier into Blender and inject exact shader attributes.

Blender 4.0.2's glTF importer accepts application attributes beginning with '_',
but its multi-primitive custom-attribute accumulator cannot concatenate mixed
VEC4/VEC3/SCALAR widths reliably.  The source GLB remains authoritative; this
adapter does not alter or reinterpret those accessors.

The adapter creates an import-safe temporary GLB by removing only the four custom
shader attribute bindings from each primitive.  After Blender imports the normal
geometry/skin/material/animation carrier, it proves that Blender vertex index N
still corresponds to source-carrier vertex N using three independent channels:

* object-local POSITION after the source-closed glTF->Blender axis conversion;
* TEXCOORD_0 after Blender's documented importer conversion (u, v)->(u, 1-v);
* JOINTS_0/WEIGHTS_0 resolved to exact imported vertex-group names and weights.

Only after all three sequence checks pass are the exact raw source accessors
injected as Blender POINT attributes:

    _T6_COLOR_RGBA          FLOAT_COLOR
    _T6_XMODEL_NORMAL       FLOAT_VECTOR
    _T6_XMODEL_TANGENT      FLOAT_VECTOR
    _T6_TANGENT_HANDEDNESS  FLOAT

The values remain in the raw T6-local carrier basis.  Shader nodes are responsible
for the explicit custom-attribute axis conversion before OBJECT->WORLD transport.
No standard glTF COLOR_0 or TANGENT is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import bpy  # type: ignore
except ImportError:
    bpy = None

import t6_gltf_augment_xmodel_shader_attributes_v1 as glb

FORMAT = "t6-blender-import-xmodel-shader-carrier-v1"
SOURCE_FORMAT = "t6-gltf-augment-xmodel-shader-attributes-v2"
CUSTOM = (
    "_T6_COLOR_RGBA",
    "_T6_XMODEL_NORMAL",
    "_T6_XMODEL_TANGENT",
    "_T6_TANGENT_HANDEDNESS",
)
TOL = 2.0e-6


class BlenderShaderCarrierError(RuntimeError):
    pass


def _require_bpy() -> None:
    if bpy is None:
        raise BlenderShaderCarrierError("bpy unavailable; run inside Blender")


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(float(a) - float(b)) <= tol


def _row_close(a, b, tol: float = TOL) -> bool:
    return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))


def _gltf_to_blender_vec(row) -> tuple[float, float, float]:
    x, y, z = (float(v) for v in row[:3])
    return (x, -z, y)


def _uv_to_blender(row) -> tuple[float, float]:
    u, v = (float(x) for x in row[:2])
    return (u, 1.0 - v)


def _source(path: Path) -> tuple[dict[str, Any], bytearray, list[dict[str, Any]]]:
    doc, raw = glb._load_glb(path)
    prims = glb._single_mesh_primitives(doc, "shader carrier")
    if len(prims) != 14:
        raise BlenderShaderCarrierError(f"source primitive count {len(prims)} != 14")
    if len(doc.get("materials", [])) != 12 or len(doc.get("animations", [])) != 6:
        raise BlenderShaderCarrierError("source carrier must retain 12 materials and six animations")
    skins = doc.get("skins", [])
    if len(skins) != 1 or len(skins[0].get("joints", [])) != 102:
        raise BlenderShaderCarrierError("source carrier must retain one 102-joint skin")
    extra = doc.get("extras", {}).get("T6", {}).get("xmodelShaderAttributeAugmentation", {})
    if extra.get("format") != SOURCE_FORMAT:
        raise BlenderShaderCarrierError(f"source lacks {SOURCE_FORMAT!r} authority marker")
    for i, prim in enumerate(prims):
        attrs = prim.get("attributes") or {}
        if "COLOR_0" in attrs or "TANGENT" in attrs:
            raise BlenderShaderCarrierError(f"source primitive {i}: forbidden standard COLOR_0/TANGENT present")
        for name in CUSTOM:
            if name not in attrs:
                raise BlenderShaderCarrierError(f"source primitive {i}: missing {name}")
        for name in ("POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"):
            if name not in attrs:
                raise BlenderShaderCarrierError(f"source primitive {i}: missing base attribute {name}")
    return doc, raw, prims


def _make_import_safe(source: Path, out: Path) -> None:
    doc, raw, prims = _source(source)
    for prim in prims:
        attrs = prim["attributes"]
        for name in CUSTOM:
            del attrs[name]
        prim.setdefault("extras", {}).setdefault("T6", {})["blenderCustomAttributeTransport"] = (
            "custom _T6_* bindings removed only for Blender 4.0.2 import; authoritative values reinjected after vertex-order proof"
        )
    doc.setdefault("extras", {}).setdefault("T6", {})["blenderImportSafeCarrier"] = {
        "format": FORMAT,
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "removedBindingsOnly": list(CUSTOM),
        "sourceCustomAccessorBytesUntouched": True,
    }
    glb._save_glb(out, doc, raw)


def _flatten_source(doc, raw, prims, name: str) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for prim in prims:
        rows.extend(glb._accessor_values(doc, raw, int(prim["attributes"][name])))
    return rows


def _skin_joint_names(doc: dict[str, Any]) -> list[str]:
    skin = doc["skins"][0]
    names = []
    for node_index in skin["joints"]:
        node = doc["nodes"][int(node_index)]
        name = str(node.get("name") or "")
        if not name:
            raise BlenderShaderCarrierError(f"skin joint node {node_index} lacks name")
        names.append(name)
    if len(names) != 102 or len(set(names)) != 102:
        raise BlenderShaderCarrierError("skin joint names are not unique 102-entry identities")
    return names


def _main_mesh_object():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    exact = [o for o in meshes if o.name == "c_usa_mp_seal6_smg_fb_mesh"]
    if len(exact) != 1:
        raise BlenderShaderCarrierError(f"expected exact SEAL6 mesh once, got {[o.name for o in meshes]}")
    main = exact[0]
    for obj in list(meshes):
        if obj is main:
            continue
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    return main


def _vertex_uvs(mesh) -> list[tuple[float, float]]:
    layer = mesh.uv_layers.active
    if layer is None:
        raise BlenderShaderCarrierError("imported mesh has no active UV layer")
    per_vertex: list[list[tuple[float, float]]] = [[] for _ in mesh.vertices]
    for loop in mesh.loops:
        uv = layer.data[loop.index].uv
        per_vertex[loop.vertex_index].append((float(uv.x), float(uv.y)))
    out = []
    for i, rows in enumerate(per_vertex):
        if not rows:
            raise BlenderShaderCarrierError(f"imported vertex {i} has no UV loop")
        first = rows[0]
        if any(not _row_close(first, row) for row in rows[1:]):
            raise BlenderShaderCarrierError(f"imported vertex {i} has multiple TEXCOORD_0 values")
        out.append(first)
    return out


def _expected_skin_rows(doc, raw, prims) -> list[list[tuple[str, float]]]:
    joint_names = _skin_joint_names(doc)
    joints = _flatten_source(doc, raw, prims, "JOINTS_0")
    weights = _flatten_source(doc, raw, prims, "WEIGHTS_0")
    if len(joints) != len(weights):
        raise BlenderShaderCarrierError("source JOINTS/WEIGHTS row count mismatch")
    out = []
    for js, ws in zip(joints, weights):
        row = []
        for j, w in zip(js, ws):
            w = float(w)
            if abs(w) <= 1.0e-8:
                continue
            ji = int(j)
            if ji < 0 or ji >= len(joint_names):
                raise BlenderShaderCarrierError(f"source joint index {ji} outside 102-joint skin")
            row.append((joint_names[ji], w))
        row.sort(key=lambda x: x[0])
        out.append(row)
    return out


def _actual_skin_row(obj, vertex) -> list[tuple[str, float]]:
    row = []
    for g in vertex.groups:
        w = float(g.weight)
        if abs(w) <= 1.0e-8:
            continue
        row.append((obj.vertex_groups[g.group].name, w))
    row.sort(key=lambda x: x[0])
    return row


def _skin_close(expected, actual) -> bool:
    return (
        len(expected) == len(actual)
        and all(a[0] == b[0] and _close(a[1], b[1], 3.0e-6) for a, b in zip(expected, actual))
    )


def _prove_vertex_sequence(obj, doc, raw, prims) -> dict[str, Any]:
    mesh = obj.data
    positions = _flatten_source(doc, raw, prims, "POSITION")
    uvs = _flatten_source(doc, raw, prims, "TEXCOORD_0")
    skins = _expected_skin_rows(doc, raw, prims)
    if not (len(positions) == len(uvs) == len(skins) == len(mesh.vertices) == 13490):
        raise BlenderShaderCarrierError(
            f"source/import vertex cardinality mismatch pos={len(positions)} uv={len(uvs)} skin={len(skins)} blender={len(mesh.vertices)}"
        )
    imported_uvs = _vertex_uvs(mesh)
    for i, vertex in enumerate(mesh.vertices):
        actual_pos = tuple(float(x) for x in vertex.co)
        expected_pos = _gltf_to_blender_vec(positions[i])
        if not _row_close(actual_pos, expected_pos):
            raise BlenderShaderCarrierError(
                f"vertex {i}: imported POSITION sequence drift actual={actual_pos} expected={expected_pos}"
            )
        expected_uv = _uv_to_blender(uvs[i])
        if not _row_close(imported_uvs[i], expected_uv):
            raise BlenderShaderCarrierError(
                f"vertex {i}: imported UV sequence drift actual={imported_uvs[i]} expected={expected_uv}"
            )
        actual_skin = _actual_skin_row(obj, vertex)
        if not _skin_close(skins[i], actual_skin):
            raise BlenderShaderCarrierError(
                f"vertex {i}: imported skin sequence drift actual={actual_skin} expected={skins[i]}"
            )
    return {
        "vertices": 13490,
        "positionSequenceExact": True,
        "uvSequenceExact": True,
        "namedSkinWeightSequenceExact": True,
        "gltfToBlenderPositionRule": "(x,y,z)->(x,-z,y)",
        "gltfToBlenderUvRule": "(u,v)->(u,1-v)",
    }


def _remove_existing(mesh, name: str) -> None:
    attr = mesh.attributes.get(name)
    if attr is not None:
        mesh.attributes.remove(attr)
    color = mesh.color_attributes.get(name)
    if color is not None:
        mesh.color_attributes.remove(color)


def _inject(mesh, doc, raw, prims) -> dict[str, Any]:
    source = {name: _flatten_source(doc, raw, prims, name) for name in CUSTOM}
    if any(len(rows) != 13490 for rows in source.values()):
        raise BlenderShaderCarrierError("custom source attribute cardinality drift")
    for name in CUSTOM:
        _remove_existing(mesh, name)

    color = mesh.color_attributes.new(name="_T6_COLOR_RGBA", type="FLOAT_COLOR", domain="POINT")
    color.data.foreach_set("color", [float(v) for row in source["_T6_COLOR_RGBA"] for v in row])
    normal = mesh.attributes.new(name="_T6_XMODEL_NORMAL", type="FLOAT_VECTOR", domain="POINT")
    normal.data.foreach_set("vector", [float(v) for row in source["_T6_XMODEL_NORMAL"] for v in row])
    tangent = mesh.attributes.new(name="_T6_XMODEL_TANGENT", type="FLOAT_VECTOR", domain="POINT")
    tangent.data.foreach_set("vector", [float(v) for row in source["_T6_XMODEL_TANGENT"] for v in row])
    handed = mesh.attributes.new(name="_T6_TANGENT_HANDEDNESS", type="FLOAT", domain="POINT")
    handed.data.foreach_set("value", [float(row[0]) for row in source["_T6_TANGENT_HANDEDNESS"]])

    # Read the Blender datablocks back immediately. This catches color or domain
    # conversions before the .blend is promoted.
    for i in range(13490):
        if not _row_close(tuple(color.data[i].color), source["_T6_COLOR_RGBA"][i]):
            raise BlenderShaderCarrierError(f"vertex {i}: FLOAT_COLOR write/read drift")
        if not _row_close(tuple(normal.data[i].vector), source["_T6_XMODEL_NORMAL"][i]):
            raise BlenderShaderCarrierError(f"vertex {i}: XModel normal write/read drift")
        if not _row_close(tuple(tangent.data[i].vector), source["_T6_XMODEL_TANGENT"][i]):
            raise BlenderShaderCarrierError(f"vertex {i}: tangent write/read drift")
        if not _close(float(handed.data[i].value), float(source["_T6_TANGENT_HANDEDNESS"][i][0])):
            raise BlenderShaderCarrierError(f"vertex {i}: handedness write/read drift")

    return {
        "attributes": {
            "_T6_COLOR_RGBA": {"dataType": color.data_type, "domain": color.domain, "count": len(color.data)},
            "_T6_XMODEL_NORMAL": {"dataType": normal.data_type, "domain": normal.domain, "count": len(normal.data)},
            "_T6_XMODEL_TANGENT": {"dataType": tangent.data_type, "domain": tangent.domain, "count": len(tangent.data)},
            "_T6_TANGENT_HANDEDNESS": {"dataType": handed.data_type, "domain": handed.domain, "count": len(handed.data)},
        },
        "allValuesReadBackExactWithinFloat32Tolerance": True,
        "customAttributeBasis": "raw T6 local carrier basis",
    }


def _verify_injected(mesh, doc, raw, prims) -> dict[str, Any]:
    source = {name: _flatten_source(doc, raw, prims, name) for name in CUSTOM}
    color = mesh.color_attributes.get("_T6_COLOR_RGBA")
    normal = mesh.attributes.get("_T6_XMODEL_NORMAL")
    tangent = mesh.attributes.get("_T6_XMODEL_TANGENT")
    handed = mesh.attributes.get("_T6_TANGENT_HANDEDNESS")
    if None in (color, normal, tangent, handed):
        raise BlenderShaderCarrierError("reopened .blend lacks one or more exact _T6_* attributes")
    if not (color.domain == normal.domain == tangent.domain == handed.domain == "POINT"):
        raise BlenderShaderCarrierError("reopened _T6_* attribute domain drift")
    if not all(len(x.data) == 13490 for x in (color, normal, tangent, handed)):
        raise BlenderShaderCarrierError("reopened _T6_* attribute cardinality drift")
    for i in range(13490):
        if not _row_close(tuple(color.data[i].color), source["_T6_COLOR_RGBA"][i]):
            raise BlenderShaderCarrierError(f"reopen vertex {i}: color drift")
        if not _row_close(tuple(normal.data[i].vector), source["_T6_XMODEL_NORMAL"][i]):
            raise BlenderShaderCarrierError(f"reopen vertex {i}: normal drift")
        if not _row_close(tuple(tangent.data[i].vector), source["_T6_XMODEL_TANGENT"][i]):
            raise BlenderShaderCarrierError(f"reopen vertex {i}: tangent drift")
        if not _close(float(handed.data[i].value), float(source["_T6_TANGENT_HANDEDNESS"][i][0])):
            raise BlenderShaderCarrierError(f"reopen vertex {i}: handedness drift")
    return {"reopenedAttributesExact": True, "verticesVerified": 13490}


def build(source: Path, output: Path, report: Path) -> dict[str, Any]:
    _require_bpy()
    doc, raw, prims = _source(source)
    with tempfile.TemporaryDirectory(prefix="t6-seal6-import-safe-") as td:
        safe = Path(td) / "carrier_import_safe.glb"
        _make_import_safe(source, safe)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(safe), import_pack_images=True)
    if len(bpy.data.armatures) != 1 or len(bpy.data.actions) != 6 or len(bpy.data.materials) != 12:
        raise BlenderShaderCarrierError(
            f"Blender import cardinality drift armatures={len(bpy.data.armatures)} actions={len(bpy.data.actions)} materials={len(bpy.data.materials)}"
        )
    obj = _main_mesh_object()
    if len(obj.data.vertices) != 13490 or len(obj.data.polygons) != 14968:
        raise BlenderShaderCarrierError(
            f"Blender mesh cardinality drift {len(obj.data.vertices)} vertices/{len(obj.data.polygons)} triangles"
        )
    sequence = _prove_vertex_sequence(obj, doc, raw, prims)
    injection = _inject(obj.data, doc, raw, prims)
    if "COLOR_0" in obj.data.attributes or "COLOR_0" in obj.data.color_attributes:
        raise BlenderShaderCarrierError("forbidden COLOR_0 appeared in Blender")

    scene = bpy.context.scene
    scene.name = "T6_SEAL6_SMG_LOD0_FULL_RETAIL_SHADER_CARRIER_V1"
    scene["t6_shader_attribute_carrier"] = FORMAT
    scene["t6_source_glb_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    scene["t6_vertex_sequence_proven"] = True
    scene["t6_exact_shader_custom_attributes"] = True
    scene["t6_color0_present"] = False
    scene["t6_complete_retail_pixel_output"] = False
    scene["t6_shader_custom_attribute_basis"] = "raw T6 local carrier basis"
    notice = bpy.data.texts.get("T6_SHADER_ATTRIBUTE_NOTICE.txt") or bpy.data.texts.new("T6_SHADER_ATTRIBUTE_NOTICE.txt")
    notice.clear()
    notice.write(
        "Exact T6 shader-only vertex data is stored as custom POINT-domain _T6_* attributes.\n"
        "The authoritative source is the SHA-pinned full-retail shader-attribute GLB; Blender 4.0.2 custom glTF import is bypassed only because its mixed-width custom-attribute accumulator fails across primitives.\n"
        "Vertex sequence was proven after normal carrier import using object-local POSITION, imported UV, and named skin weights before any custom data was injected.\n"
        "Standard COLOR_0/TANGENT remain absent. Values stay in raw T6 local carrier basis; shader nodes must apply the explicit custom-attribute axis conversion before OBJECT->WORLD.\n"
        "Complete retail pixel output remains false until exact runtime-global lighting/probe/fog/HDR values or exact bakes are supplied.\n"
    )
    bpy.ops.file.pack_all()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=False)

    out = {
        "format": FORMAT,
        "source": str(source),
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "outputBlend": str(output),
        "outputBlendSha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "blenderVersion": bpy.app.version_string,
        "geometry": {"primitives": 14, "vertices": 13490, "triangles": 14968, "joints": 102, "materials": 12, "animations": 6},
        "vertexSequenceProof": sequence,
        "shaderAttributeInjection": injection,
        "color0Present": False,
        "standardTangentPresent": False,
        "completeRetailPixelOutput": False,
        "proofBoundary": (
            "The authoritative augmented GLB is not reinterpreted. Blender imports an otherwise byte-equivalent carrier with only the four custom bindings omitted to avoid a Blender 4.0.2 mixed-width custom-attribute importer defect. Imported vertex order is independently closed by position, UV and named skin-weight sequence before exact raw custom accessor values are injected and read back. No standard COLOR_0/TANGENT or guessed shader input is introduced."
        ),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("T6_BLENDER_SHADER_CARRIER_V1=" + json.dumps(out, sort_keys=True))
    return out


def verify_existing(source: Path, report: Path | None = None) -> dict[str, Any]:
    _require_bpy()
    doc, raw, prims = _source(source)
    obj = _main_mesh_object()
    sequence = _prove_vertex_sequence(obj, doc, raw, prims)
    attrs = _verify_injected(obj.data, doc, raw, prims)
    if "COLOR_0" in obj.data.attributes or "COLOR_0" in obj.data.color_attributes:
        raise BlenderShaderCarrierError("reopened blend contains forbidden COLOR_0")
    out = {
        "format": FORMAT + "-reopen",
        "blenderVersion": bpy.app.version_string,
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "vertexSequenceProof": sequence,
        "shaderAttributes": attrs,
        "materials": len(bpy.data.materials),
        "animations": len(bpy.data.actions),
        "armatures": len(bpy.data.armatures),
        "color0Present": False,
    }
    if report is not None:
        report.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("T6_BLENDER_SHADER_CARRIER_V1_REOPEN=" + json.dumps(out, sort_keys=True))
    return out


def main() -> int:
    _require_bpy()
    args_raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--verify-existing", action="store_true")
    args = ap.parse_args(args_raw)
    if args.verify_existing:
        verify_existing(args.source, args.report)
    else:
        if args.output is None or args.report is None:
            raise BlenderShaderCarrierError("build mode requires --output and --report")
        build(args.source, args.output, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
