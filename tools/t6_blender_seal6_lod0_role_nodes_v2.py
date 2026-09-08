#!/usr/bin/env python3
"""Compile the exact 12-Material SEAL6 LOD0 role plan into Blender nodes.

All 41 native OAT texture slots become first-class nodes. Forty streamed slots
load their exact SHA-verified retail PNG derivatives. The sole non-streamed slot,
cornea ``sw_radiant_default``, becomes an explicitly unbound dependency node; no
pixel value or fabricated image is invented for it.

The historical baseColor/normal selection remains an authoring preview only.
Exact ordinary-lit shader lowering is applied by a separate backend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import bpy  # type: ignore
except ImportError:
    bpy = None

PLAN_FORMAT = "t6-seal6-lod0-blender-role-plan-v2"
FORMAT = "t6-blender-seal6-lod0-role-nodes-v2"
EXPECTED_MATERIALS = 12
EXPECTED_SLOTS = 41
EXPECTED_STREAMED = 40
EXPECTED_SHARED = 1


class Seal6Lod0RoleNodeError(RuntimeError):
    pass


def _require_bpy() -> None:
    if bpy is None:
        raise Seal6Lod0RoleNodeError("bpy unavailable; run inside Blender")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _socket(collection, name: str):
    sock = collection.get(name)
    if sock is None:
        raise Seal6Lod0RoleNodeError(f"Blender node lacks {name!r} socket")
    return sock


def _material_exact(name: str):
    exact = bpy.data.materials.get(name)
    if exact is not None:
        return exact
    matches = [m for m in bpy.data.materials if m.name == name or m.name.startswith(name + ".")]
    if len(matches) != 1:
        raise Seal6Lod0RoleNodeError(f"exact Material {name!r} is not uniquely present: {[m.name for m in matches]}")
    return matches[0]


def validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("format") != PLAN_FORMAT:
        raise Seal6Lod0RoleNodeError(f"unsupported plan {plan.get('format')!r}")
    s = plan.get("summary") or {}
    expected = {
        "targetMaterials": EXPECTED_MATERIALS,
        "nativeTextureSlots": EXPECTED_SLOTS,
        "streamedNativeTextureSlots": EXPECTED_STREAMED,
        "sharedBuiltInAliasSlots": EXPECTED_SHARED,
        "uniqueStreamedRetailImages": 39,
        "clothMaterials": 7,
    }
    for key, value in expected.items():
        if int(s.get(key, -1)) != value:
            raise Seal6Lod0RoleNodeError(f"plan {key}={s.get(key)!r} != {value}")
    if s.get("allNativeTextureSlotsRepresented") is not True:
        raise Seal6Lod0RoleNodeError("plan does not preserve every native slot")
    if s.get("allStreamedPayloadsExactKeyAndCrcValidated") is not True:
        raise Seal6Lod0RoleNodeError("streamed payload closure false")
    if s.get("sharedRadiantAliasPreservedWithoutFabrication") is not True:
        raise Seal6Lod0RoleNodeError("shared radiant alias closure false")
    if s.get("completeRetailPixelOutput") is not False:
        raise Seal6Lod0RoleNodeError("role-only plan must not claim complete retail output")
    rows = plan.get("materials")
    if not isinstance(rows, list) or len(rows) != EXPECTED_MATERIALS:
        raise Seal6Lod0RoleNodeError("materials[] is not exact 12 rows")
    seen = set()
    slots = streamed = shared = 0
    for row in rows:
        material = str(row.get("material") or "")
        if not material or material in seen:
            raise Seal6Lod0RoleNodeError(f"invalid/duplicate Material {material!r}")
        seen.add(material)
        native = row.get("nativeSlots")
        if not isinstance(native, list) or len(native) != int(row.get("nativeSlotCount", -1)):
            raise Seal6Lod0RoleNodeError(f"{material}: native slot count malformed")
        if [int(x.get("slotIndex", -1)) for x in native] != list(range(len(native))):
            raise Seal6Lod0RoleNodeError(f"{material}: native slots are not ordered/contiguous")
        for slot in native:
            resource = slot.get("resource")
            if not isinstance(resource, dict):
                raise Seal6Lod0RoleNodeError(f"{material}: slot resource missing")
            kind = resource.get("kind")
            if kind == "exact-streamed-retail-payload":
                if resource.get("exactKeyValidated") is not True or resource.get("crc29Validated") is not True:
                    raise Seal6Lod0RoleNodeError(f"{material}: streamed slot lacks exact key/CRC closure")
                if len(str(resource.get("pngSha256") or "")) != 64 or not resource.get("pngFile"):
                    raise Seal6Lod0RoleNodeError(f"{material}: streamed slot lacks exact PNG identity")
                streamed += 1
            elif kind == "exact-shared-built-in-alias":
                if not (
                    material == "mc/mtl_gen_eye_cornea"
                    and int(slot.get("slotIndex", -1)) == 2
                    and slot.get("image") == "sw_radiant_default"
                    and resource.get("identityEvidence") == "exact-shared-radiant-alias-proof"
                    and resource.get("streamedPayloadRequired") is False
                    and resource.get("fabricatedPng") is False
                ):
                    raise Seal6Lod0RoleNodeError("unrecognized non-streamed native slot")
                shared += 1
            else:
                raise Seal6Lod0RoleNodeError(f"{material}: unsupported resource kind {kind!r}")
            slots += 1
    if (slots, streamed, shared) != (EXPECTED_SLOTS, EXPECTED_STREAMED, EXPECTED_SHARED):
        raise Seal6Lod0RoleNodeError(f"slot recount drift {(slots,streamed,shared)}")


def _load_streamed_image(slot: dict[str, Any], texture_root: Path, cache: dict[tuple[str, str], Any]):
    image_name = str(slot.get("image") or "")
    resource = slot["resource"]
    png = (texture_root / str(resource["pngFile"])).resolve()
    if not png.is_file():
        raise Seal6Lod0RoleNodeError(f"{image_name}: exact PNG missing: {png}")
    expected = str(resource["pngSha256"]).lower()
    actual = _sha(png)
    if actual != expected:
        raise Seal6Lod0RoleNodeError(f"{image_name}: PNG SHA mismatch {actual} != {expected}")
    key = (image_name, expected)
    if key in cache:
        return cache[key]
    image = bpy.data.images.load(str(png), check_existing=False)
    image.name = f"{image_name}__T6_EXACT_DATA"
    image.colorspace_settings.name = "Non-Color"
    image["t6_exact_image_identity"] = image_name
    image["t6_png_sha256"] = expected
    image["t6_iwi_sha256"] = str(resource.get("iwiSha256") or "")
    image["t6_repository"] = str(resource.get("repository") or "")
    image["t6_exact_key_validated"] = True
    image["t6_crc29_validated"] = True
    cache[key] = image
    return image


def _slot_node(nodes, links, frame, uv_socket, slot: dict[str, Any], texture_root: Path, cache: dict, y: float):
    index = int(slot["slotIndex"])
    native_name = str(slot.get("nativeName") or "")
    native_sem = str(slot.get("nativeSemantic") or "")
    image_name = str(slot.get("image") or "")
    kind = str(slot["resource"].get("kind") or "")
    safe = native_name or native_sem or "unnamed"
    node_name = f"T6_SLOT_{index:02d}_{safe}"
    if kind == "exact-streamed-retail-payload":
        node = nodes.new("ShaderNodeTexImage")
        node.image = _load_streamed_image(slot, texture_root, cache)
        node.interpolation = "Linear"
        node.extension = "REPEAT"
        links.new(uv_socket, _socket(node.inputs, "Vector"))
        source_type = "exact-streamed-retail-payload"
    elif kind == "exact-shared-built-in-alias":
        # This is deliberately not a color/image node. The exact dependency is
        # present, but no value is fabricated for a non-streamed engine resource.
        node = nodes.new("ShaderNodeValue")
        node.outputs[0].default_value = 0.0
        node["t6_value_is_placeholder"] = True
        node["t6_must_remain_unconnected_without_exact_runtime_provider"] = True
        source_type = "exact-shared-built-in-alias-unbound"
    else:
        raise Seal6Lod0RoleNodeError(f"unsupported slot kind {kind!r}")
    node.name = node_name
    node.label = f"slot {index} | {native_sem} | {native_name or '(unnamed)'} | {image_name} | {source_type}"
    node.location = (-900, y)
    node.parent = frame
    node["t6_slot_index"] = index
    node["t6_native_semantic"] = native_sem
    node["t6_native_argument_name"] = native_name
    node["t6_native_image"] = image_name
    node["t6_resource_kind"] = kind
    return node


def compile_material(material, row: dict[str, Any], texture_root: Path, cache: dict) -> dict[str, Any]:
    slots = row["nativeSlots"]
    material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        raise Seal6Lod0RoleNodeError(f"{material.name}: no node tree")
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "T6_AUTHORING_OUTPUT"
    output.label = "AUTHORING OUTPUT — runtime T6 globals not bound"
    output.location = (1400, 100)

    preview_frame = nodes.new("NodeFrame")
    preview_frame.name = "T6_AUTHORING_PREVIEW_FRAME"
    preview_frame.label = "APPROXIMATE AUTHORING PREVIEW ONLY"
    preview_frame.location = (500, 100)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.name = "T6_AUTHORING_PREVIEW_BSDF"
    principled.label = "DO NOT TREAT AS RETAIL PIXEL SHADER"
    principled.location = (950, 100)
    principled.parent = preview_frame
    links.new(_socket(principled.outputs, "BSDF"), _socket(output.inputs, "Surface"))

    source_frame = nodes.new("NodeFrame")
    source_frame.name = "T6_EXACT_NATIVE_SOURCE_SLOTS"
    source_frame.label = "EXACT T6 NATIVE SOURCE SLOTS — ALL 41-PLAN INPUTS PRESERVED"
    source_frame.location = (-950, 0)

    uv = nodes.new("ShaderNodeUVMap")
    uv.name = "T6_TEXCOORD0"
    uv.label = "T6 texcoord[0] / UVMap"
    uv.uv_map = "UVMap"
    uv.location = (-1300, 0)
    uv.parent = source_frame
    uv_socket = _socket(uv.outputs, "UV")

    slot_nodes: dict[int, Any] = {}
    streamed = shared = 0
    for i, slot in enumerate(slots):
        node = _slot_node(nodes, links, source_frame, uv_socket, slot, texture_root, cache, 650 - 250*i)
        slot_nodes[int(slot["slotIndex"])] = node
        if slot["resource"]["kind"] == "exact-streamed-retail-payload": streamed += 1
        else: shared += 1

    preview = row.get("authoringPreview") or {}
    color = preview.get("baseColor") or {}
    normal = preview.get("normal") or {}
    cidx, nidx = int(color.get("slotIndex", -1)), int(normal.get("slotIndex", -1))
    cnode, nnode = slot_nodes.get(cidx), slot_nodes.get(nidx)
    if cnode is None or nnode is None or cnode.bl_idname != "ShaderNodeTexImage" or nnode.bl_idname != "ShaderNodeTexImage":
        raise Seal6Lod0RoleNodeError(f"{material.name}: authoring preview does not resolve to exact streamed nodes")
    links.new(_socket(cnode.outputs, "Color"), _socket(principled.inputs, "Base Color"))
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.name = "T6_AUTHORING_PREVIEW_NORMAL"
    normal_map.label = "APPROXIMATE preview normal only"
    normal_map.space = "TANGENT"
    normal_map.location = (650, -180)
    normal_map.parent = preview_frame
    links.new(_socket(nnode.outputs, "Color"), _socket(normal_map.inputs, "Color"))
    links.new(_socket(normal_map.outputs, "Normal"), _socket(principled.inputs, "Normal"))

    material["t6_shader_backend"] = FORMAT
    material["t6_native_material_identity"] = str(row["material"])
    material["t6_technique_set"] = str(row.get("techniqueSet") or "")
    material["t6_role_complete_native_inputs"] = True
    material["t6_native_slot_count"] = len(slots)
    material["t6_native_slots_json"] = json.dumps(slots, sort_keys=True)
    material["t6_shared_builtin_alias_slots"] = shared
    material["t6_authoring_preview_approximate"] = True
    material["t6_complete_retail_pixel_output"] = False

    return {
        "material": str(row["material"]),
        "nativeSlotCount": len(slots),
        "streamedSlotNodes": streamed,
        "sharedBuiltInAliasNodes": shared,
        "authoringPreviewBaseColorSlot": cidx,
        "authoringPreviewNormalSlot": nidx,
        "completeNativeInputGraph": True,
    }


def compile_plan(plan: dict[str, Any], texture_root: Path) -> dict[str, Any]:
    _require_bpy()
    validate_plan(plan)
    texture_root = texture_root.resolve()
    if not texture_root.is_dir():
        raise Seal6Lod0RoleNodeError(f"texture root missing: {texture_root}")
    cache: dict[tuple[str, str], Any] = {}
    rows = []
    for row in plan["materials"]:
        rows.append(compile_material(_material_exact(str(row["material"])), row, texture_root, cache))
    out = {
        "format": FORMAT,
        "summary": {
            "materialsCompiled": len(rows),
            "nativeSlotsCompiled": sum(r["nativeSlotCount"] for r in rows),
            "streamedSlotNodes": sum(r["streamedSlotNodes"] for r in rows),
            "sharedBuiltInAliasNodes": sum(r["sharedBuiltInAliasNodes"] for r in rows),
            "uniqueExactPngImagesLoaded": len(cache),
            "allNativeInputsRepresented": all(r["completeNativeInputGraph"] for r in rows),
            "completeRetailPixelOutput": False,
        },
        "materials": rows,
        "proofBoundary": plan.get("proofBoundary"),
    }
    expected = {
        "materialsCompiled": 12,
        "nativeSlotsCompiled": 41,
        "streamedSlotNodes": 40,
        "sharedBuiltInAliasNodes": 1,
        "uniqueExactPngImagesLoaded": 39,
        "allNativeInputsRepresented": True,
        "completeRetailPixelOutput": False,
    }
    if out["summary"] != expected:
        raise Seal6Lod0RoleNodeError(f"compiled role summary drift: {out['summary']!r}")
    return out


def _script_args(argv: list[str]) -> list[str]:
    return argv[argv.index("--")+1:] if "--" in argv else argv[1:]


def main() -> int:
    _require_bpy()
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--texture-root", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(_script_args(sys.argv))
    plan = json.loads(a.plan.read_text(encoding="utf-8-sig"))
    result = compile_plan(plan, a.texture_root)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print("T6_SEAL6_LOD0_ROLE_NODES_V2="+json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
