#!/usr/bin/env python3
"""Build role-complete SEAL6 Blender materials from the exact native role plan.

Every native texture slot becomes a first-class Blender image-texture node using
its exact retail PNG derivative. Repeated semantic classes remain distinct by
native slot index. The historical baseColor + normal pair is connected only to
an explicitly labelled authoring-preview Principled BSDF so artists can inspect
the model while exact hero-skin/rim/camo/detail-normal shader arithmetic remains
unpromoted.

No specular/gloss, mask, camouflage, detail-normal, cornea or rim source is
silently converted into a Principled parameter.
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

PLAN_FORMAT = "t6-seal6-blender-role-plan-v1"
FORMAT = "t6-blender-seal6-role-nodes-v1"


class Seal6BlenderNodeError(RuntimeError):
    pass


def _require_bpy() -> None:
    if bpy is None:
        raise Seal6BlenderNodeError("bpy is unavailable; run this backend inside Blender")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _socket(collection, name: str):
    sock = collection.get(name)
    if sock is None:
        raise Seal6BlenderNodeError(f"Blender node lacks {name!r} socket")
    return sock


def validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("format") != PLAN_FORMAT:
        raise Seal6BlenderNodeError(f"unsupported role plan {plan.get('format')!r}")
    summary = plan.get("summary") or {}
    if int(summary.get("targetMaterials", -1)) != 5:
        raise Seal6BlenderNodeError("role plan must contain exactly five target Materials")
    if int(summary.get("nativeTextureSlots", -1)) != 20:
        raise Seal6BlenderNodeError("role plan must contain exactly twenty native slots")
    if summary.get("allNativeTextureSlotsRepresented") is not True:
        raise Seal6BlenderNodeError("role plan does not claim complete native-slot representation")
    if summary.get("allExactRetailPayloadsValidated") is not True:
        raise Seal6BlenderNodeError("role plan lacks exact retail payload closure")
    if summary.get("completeRetailPixelOutput") is not False:
        raise Seal6BlenderNodeError("v1 backend requires retail pixel output to remain explicitly incomplete")
    rows = plan.get("materials")
    if not isinstance(rows, list) or len(rows) != 5:
        raise Seal6BlenderNodeError("role plan materials[] malformed")
    total = 0
    for row in rows:
        material = str(row.get("material") or "")
        slots = row.get("nativeSlots")
        if not material or not isinstance(slots, list):
            raise Seal6BlenderNodeError("role plan Material row malformed")
        if int(row.get("nativeSlotCount", -1)) != len(slots):
            raise Seal6BlenderNodeError(f"{material}: nativeSlotCount mismatch")
        indices = [int(slot.get("slotIndex", -1)) for slot in slots]
        if indices != list(range(len(slots))):
            raise Seal6BlenderNodeError(f"{material}: native slots are not contiguous/in-order")
        for slot in slots:
            image = str(slot.get("image") or "")
            payload = slot.get("exactRetailPayload")
            if not image or not isinstance(payload, dict):
                raise Seal6BlenderNodeError(f"{material}: malformed exact slot payload")
            if payload.get("exactKeyValidated") is not True or payload.get("crc29Validated") is not True:
                raise Seal6BlenderNodeError(f"{material}: {image} lacks exact payload validation")
            png_file = str(payload.get("pngFile") or "")
            png_sha = str(payload.get("pngSha256") or "")
            if not png_file or len(png_sha) != 64:
                raise Seal6BlenderNodeError(f"{material}: {image} lacks PNG path/SHA")
        total += len(slots)
    if total != 20:
        raise Seal6BlenderNodeError(f"role plan slot recount is {total}, expected 20")


def _material_exact(name: str):
    exact = bpy.data.materials.get(name)
    if exact is not None:
        return exact
    matches = [m for m in bpy.data.materials if m.name == name or m.name.startswith(name + ".")]
    if len(matches) != 1:
        raise Seal6BlenderNodeError(f"exact SEAL6 Material {name!r} is not uniquely present in Blender")
    return matches[0]


def _load_data_image(slot: dict[str, Any], texture_root: Path, cache: dict[tuple[str, str], Any]):
    image_name = str(slot["image"])
    payload = slot["exactRetailPayload"]
    png = (texture_root / str(payload["pngFile"])).resolve()
    if not png.is_file():
        raise Seal6BlenderNodeError(f"{image_name}: exact materialized PNG missing: {png}")
    expected = str(payload["pngSha256"]).lower()
    actual = _sha(png)
    if actual != expected:
        raise Seal6BlenderNodeError(f"{image_name}: PNG SHA-256 mismatch {actual} != {expected}")
    key = (image_name, expected)
    if key in cache:
        return cache[key]
    image = bpy.data.images.load(str(png), check_existing=False)
    image.name = f"{image_name}__T6_EXACT_DATA"
    try:
        image.colorspace_settings.name = "Non-Color"
    except Exception as exc:
        raise Seal6BlenderNodeError(f"cannot force Non-Color sampling for {image_name!r}: {exc}") from exc
    image["t6_exact_image_identity"] = image_name
    image["t6_png_sha256"] = expected
    image["t6_iwi_sha256"] = str(payload.get("iwiSha256") or "")
    image["t6_repository"] = str(payload.get("repository") or "")
    image["t6_exact_key_validated"] = True
    image["t6_crc29_validated"] = True
    cache[key] = image
    return image


def _texture_node(nodes, links, frame, uv_socket, slot: dict[str, Any], texture_root: Path, cache: dict, x: float, y: float):
    node = nodes.new("ShaderNodeTexImage")
    node.name = str(slot["nodeName"])
    semantic = str(slot.get("semantic") or "")
    native_name = str(slot.get("nativeName") or "")
    image_name = str(slot["image"])
    node.label = f"slot {slot['slotIndex']} | {semantic} | {native_name or '(unnamed)'} | {image_name}"
    node.image = _load_data_image(slot, texture_root, cache)
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    node.location = (x, y)
    node.parent = frame
    links.new(uv_socket, _socket(node.inputs, "Vector"))
    return node


def compile_material(material, material_plan: dict[str, Any], texture_root: Path, *, image_cache: dict | None = None) -> dict[str, Any]:
    _require_bpy()
    slots = material_plan.get("nativeSlots")
    if not isinstance(slots, list) or len(slots) != int(material_plan.get("nativeSlotCount", -1)):
        raise Seal6BlenderNodeError("material role plan malformed")
    cache = image_cache if image_cache is not None else {}

    material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        raise Seal6BlenderNodeError(f"{material.name}: no node tree")
    nodes, links = tree.nodes, tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "T6_AUTHORING_OUTPUT"
    output.label = "AUTHORING OUTPUT — complete retail T6 pixel shader not yet lowered"
    output.location = (1350, 100)

    preview_frame = nodes.new("NodeFrame")
    preview_frame.name = "T6_AUTHORING_PREVIEW_FRAME"
    preview_frame.label = "APPROXIMATE AUTHORING PREVIEW ONLY"
    preview_frame.location = (500, 100)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.name = "T6_AUTHORING_PREVIEW_BSDF"
    principled.label = "DO NOT TREAT AS RETAIL SHADER"
    principled.location = (950, 100)
    principled.parent = preview_frame
    links.new(_socket(principled.outputs, "BSDF"), _socket(output.inputs, "Surface"))

    source_frame = nodes.new("NodeFrame")
    source_frame.name = "T6_EXACT_NATIVE_SOURCE_SLOTS"
    source_frame.label = "EXACT T6 NATIVE SOURCE SLOTS — ALL PRESERVED"
    source_frame.location = (-900, 0)

    uv = nodes.new("ShaderNodeUVMap")
    uv.name = "T6_TEXCOORD0"
    uv.label = "T6 texcoord[0] / UVMap"
    uv.uv_map = "UVMap"
    uv.location = (-1250, 0)
    uv.parent = source_frame
    uv_socket = _socket(uv.outputs, "UV")

    texture_nodes: dict[int, Any] = {}
    for index, slot in enumerate(slots):
        node = _texture_node(nodes, links, source_frame, uv_socket, slot, texture_root, cache, -900, 650 - index * 260)
        texture_nodes[index] = node

    preview = material_plan.get("authoringPreview") or {}
    cidx = int(preview.get("baseColorSlotIndex", -1))
    nidx = int(preview.get("normalSlotIndex", -1))
    if cidx not in texture_nodes or nidx not in texture_nodes:
        raise Seal6BlenderNodeError(f"{material.name}: preview references missing native slot")

    # Keep this deliberately simple. It reproduces only the former visualization
    # pair and is labelled approximate; it is not evidence for retail shader math.
    links.new(_socket(texture_nodes[cidx].outputs, "Color"), _socket(principled.inputs, "Base Color"))
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.name = "T6_AUTHORING_PREVIEW_NORMAL"
    normal_map.label = "APPROXIMATE preview normal — native detail/rim math not applied"
    normal_map.space = "TANGENT"
    normal_map.location = (650, -180)
    normal_map.parent = preview_frame
    links.new(_socket(texture_nodes[nidx].outputs, "Color"), _socket(normal_map.inputs, "Color"))
    links.new(_socket(normal_map.outputs, "Normal"), _socket(principled.inputs, "Normal"))

    material["t6_shader_backend"] = FORMAT
    material["t6_role_complete_native_inputs"] = True
    material["t6_native_slot_count"] = len(slots)
    material["t6_native_slots_json"] = json.dumps(slots, sort_keys=True)
    material["t6_authoring_preview_approximate"] = True
    material["t6_complete_retail_pixel_output"] = False
    material["t6_shader_lowering_status"] = str((material_plan.get("shaderLowering") or {}).get("status") or "")
    material["t6_proof_boundary"] = (
        "All native source slots are exact; only the baseColor/normal authoring preview is connected. "
        "No unclosed T6 mask/camo/specular/detail-normal/rim/cornea math is inferred."
    )

    return {
        "format": FORMAT,
        "material": material_plan.get("material"),
        "nativeSlotCount": len(slots),
        "nativeImageNodes": len(texture_nodes),
        "authoringPreviewBaseColorSlot": cidx,
        "authoringPreviewNormalSlot": nidx,
        "completeNativeInputGraph": True,
        "completeRetailPixelOutput": False,
    }


def compile_plan(plan: dict[str, Any], texture_root: Path) -> dict[str, Any]:
    _require_bpy()
    validate_plan(plan)
    texture_root = texture_root.resolve()
    if not texture_root.is_dir():
        raise Seal6BlenderNodeError(f"texture root is not a directory: {texture_root}")
    cache: dict[tuple[str, str], Any] = {}
    rows = []
    for material_plan in plan["materials"]:
        material = _material_exact(str(material_plan["material"]))
        rows.append(compile_material(material, material_plan, texture_root, image_cache=cache))
    return {
        "format": FORMAT,
        "summary": {
            "materialsCompiled": len(rows),
            "nativeSlotsCompiled": sum(row["nativeSlotCount"] for row in rows),
            "uniqueExactPngImagesLoaded": len(cache),
            "allNativeInputsRepresented": all(row["completeNativeInputGraph"] for row in rows),
            "completeRetailPixelOutput": False,
        },
        "materials": rows,
        "proofBoundary": plan.get("proofBoundary"),
    }


def _script_args(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--texture-root", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args(_script_args(sys.argv))
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    result = compile_plan(plan, args.texture_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
