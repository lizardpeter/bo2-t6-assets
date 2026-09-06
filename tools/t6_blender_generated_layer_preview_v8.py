#!/usr/bin/env python3
"""Blender generated-layer preview v8: exact directional lightmap RGB state.

v8 preserves v7 generated diffuse/height/normal playback and understands v23's
preview-only per-surface lightmap material shells.  A shell is accepted only
when `lightmapPreviewBindingV1.retailMaterialName` matches the embedded canonical
recipe identity; the shell name itself is never promoted to retail identity.

For eligible shells with an exact secondary lightmap preview and exact v7
reconstructed normal, v8 builds the retained directional secondary-lightmap
equation.  The resulting RGB state is intentionally *not* connected to final
material shading because the final T6 material/lightmap/specular/reflection
composition remains a separate proof boundary.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sys

import t6_blender_directional_lightmap_nodes_v1 as lightmap_nodes
import t6_blender_generated_layer_preview_v1 as v1
import t6_blender_generated_layer_preview_v3 as v3
import t6_blender_generated_layer_preview_v6 as v6
import t6_blender_generated_layer_preview_v7 as v7
from t6_generated_shader_recipe_contract_v1 import (
    EXTRA_KEY,
    GeneratedShaderRecipeError,
    validate_recipe,
)
from t6_glb_parse_v1 import parse_glb
from t6_world_lightmap_material_specialize_v1 import (
    BINDING_KEY,
    FORMAT as SPECIALIZATION_FORMAT,
    ROOT_KEY as SPECIALIZATION_ROOT,
)
from t6_world_lightmap_preview_embed_v1 import FORMAT as PREVIEW_FORMAT

bpy = v1.bpy
BlenderLayerPreviewError = v1.BlenderLayerPreviewError
FORMAT = "t6-blender-generated-layer-preview-v8"

_BASE_MATERIAL_TECHNIQUE = v3._material_technique
_BASE_BUILD_V6 = v6._build_material_v6
_ACTIVE_DOC = None
_ACTIVE_RAW = None
_ACTIVE_TEMP = None
_ACTIVE_IMAGE_CACHE: dict[str, object] = {}


def _read_doc_raw(path: Path) -> tuple[dict, bytes]:
    if path.suffix.lower() == ".glb":
        try:
            return parse_glb(path.read_bytes())
        except Exception as exc:
            raise BlenderLayerPreviewError(f"cannot parse v23 GLB: {exc}") from exc
    doc = v1._read_gltf_json(path)
    buffers = doc.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise BlenderLayerPreviewError("v8 glTF requires one embedded buffer")
    uri = str(buffers[0].get("uri") or "")
    prefix = "data:application/octet-stream;base64,"
    if not uri.startswith(prefix):
        raise BlenderLayerPreviewError(
            "v8 .gltf input requires the production embedded base64 buffer"
        )
    try:
        raw = base64.b64decode(uri[len(prefix):], validate=True)
    except Exception as exc:
        raise BlenderLayerPreviewError(f"cannot decode embedded glTF buffer: {exc}") from exc
    if len(raw) != int(buffers[0].get("byteLength", -1)):
        raise BlenderLayerPreviewError("embedded glTF buffer byteLength mismatch")
    return doc, raw


def _root_v23_preflight(doc: dict) -> dict:
    root = doc.get("extras", {}).get("T6", {})
    contract = root.get(SPECIALIZATION_ROOT)
    if not isinstance(contract, dict) or contract.get("format") != SPECIALIZATION_FORMAT:
        raise BlenderLayerPreviewError(
            f"input lacks authoritative {SPECIALIZATION_FORMAT}; v8 requires per-surface lightmap ownership"
        )
    stats = contract.get("stats")
    if not isinstance(stats, dict) or int(stats.get("specializedMaterialCount", -1)) < 0:
        raise BlenderLayerPreviewError("v23 lightmap specialization stats are invalid")
    materials = doc.get("materials")
    if not isinstance(materials, list):
        raise BlenderLayerPreviewError("v23 input has no materials list")
    variant_count = 0
    for material in materials:
        t6 = material.get("extras", {}).get("T6", {})
        binding = t6.get(BINDING_KEY)
        if not isinstance(binding, dict):
            continue
        variant_count += 1
        if binding.get("format") != SPECIALIZATION_FORMAT:
            raise BlenderLayerPreviewError(
                f"{material.get('name')!r}: invalid lightmap preview binding format"
            )
        retail = str(binding.get("retailMaterialName") or "")
        variant = str(binding.get("variantMaterialName") or "")
        if not retail or variant != str(material.get("name") or ""):
            raise BlenderLayerPreviewError(
                f"{material.get('name')!r}: lightmap preview shell identity is malformed"
            )
        recipe = t6.get(EXTRA_KEY)
        if isinstance(recipe, dict):
            try:
                validate_recipe(recipe, expected_material=retail)
            except GeneratedShaderRecipeError as exc:
                raise BlenderLayerPreviewError(
                    f"{variant!r}: embedded recipe does not belong to retail material {retail!r}: {exc}"
                ) from exc
    if variant_count != int(stats.get("specializedMaterialCount", -1)):
        raise BlenderLayerPreviewError(
            f"v23 material variant accounting {variant_count} != {stats.get('specializedMaterialCount')}"
        )
    return contract


def _variant_material_technique(name: str, t6: dict, sidecars: dict[str, dict]):
    binding = t6.get(BINDING_KEY)
    if not isinstance(binding, dict):
        return _BASE_MATERIAL_TECHNIQUE(name, t6, sidecars)
    retail = str(binding.get("retailMaterialName") or "")
    if not retail or binding.get("variantMaterialName") != name:
        raise BlenderLayerPreviewError(f"{name!r}: malformed preview retail-material binding")
    embedded = t6.get(EXTRA_KEY)
    sidecar = sidecars.get(retail)
    if embedded is None and sidecar is None:
        return None, None
    if embedded is not None:
        try:
            embedded = validate_recipe(embedded, expected_material=retail)
        except GeneratedShaderRecipeError as exc:
            raise BlenderLayerPreviewError(
                f"{name!r}: embedded variant recipe is not canonical retail identity: {exc}"
            ) from exc
    if sidecar is not None:
        if embedded is not None and sidecar != embedded:
            raise BlenderLayerPreviewError(
                f"{name!r}: retail sidecar and embedded recipe disagree"
            )
        row = sidecar
    else:
        row = embedded
    return str(row["techniqueSet"]), row


def _buffer_payload(view_index: int) -> bytes:
    if _ACTIVE_DOC is None or _ACTIVE_RAW is None:
        raise BlenderLayerPreviewError("v8 lightmap input context is not active")
    try:
        view = _ACTIVE_DOC["bufferViews"][int(view_index)]
    except Exception as exc:
        raise BlenderLayerPreviewError(f"invalid preview bufferView {view_index}") from exc
    start = int(view.get("byteOffset", 0)); length = int(view.get("byteLength", -1))
    end = start + length
    if start < 0 or length <= 0 or end > len(_ACTIVE_RAW):
        raise BlenderLayerPreviewError(
            f"preview bufferView {view_index} range {start}:{end} outside {_ACTIVE_RAW and len(_ACTIVE_RAW)}"
        )
    return _ACTIVE_RAW[start:end]


def _load_preview_image(role: dict):
    if not bool(role.get("previewAvailable")):
        return None
    sha = str(role.get("previewPngSha256") or "")
    if len(sha) != 64:
        raise BlenderLayerPreviewError("lightmap preview binding lacks PNG SHA-256")
    cached = _ACTIVE_IMAGE_CACHE.get(sha)
    if cached is not None:
        return cached
    image_index = int(role.get("previewImageIndex", -1))
    try:
        image_row = _ACTIVE_DOC["images"][image_index]
    except Exception as exc:
        raise BlenderLayerPreviewError(f"invalid lightmap preview image {image_index}") from exc
    if image_row.get("mimeType") != "image/png":
        raise BlenderLayerPreviewError("lightmap preview image is not PNG")
    it6 = image_row.get("extras", {}).get("T6", {})
    if not bool(it6.get("previewOnly")) or not bool(it6.get("dataTexture")):
        raise BlenderLayerPreviewError("lightmap PNG is not tagged preview/data")
    if it6.get("sourceDdsSha256") != role.get("sourceDdsSha256"):
        raise BlenderLayerPreviewError("lightmap preview image DDS provenance disagrees")
    payload = _buffer_payload(int(image_row["bufferView"]))
    if payload[:8] != b"\x89PNG\r\n\x1a\n" or hashlib.sha256(payload).hexdigest() != sha:
        raise BlenderLayerPreviewError("embedded lightmap preview PNG bytes/SHA mismatch")
    if _ACTIVE_TEMP is None:
        raise BlenderLayerPreviewError("v8 temporary image directory is not active")
    path = Path(_ACTIVE_TEMP) / f"{sha}.png"
    path.write_bytes(payload)
    try:
        image = bpy.data.images.load(str(path), check_existing=False)
        image.name = f"T6_LIGHTMAP_PREVIEW_{sha[:16]}"
        image.colorspace_settings.name = "Non-Color"
        image.pack()
    except Exception as exc:
        raise BlenderLayerPreviewError(f"Blender could not load embedded lightmap PNG: {exc}") from exc
    _ACTIVE_IMAGE_CACHE[sha] = image
    return image


def _final_normal_socket(blender_material):
    matches = [
        node for node in blender_material.node_tree.nodes
        if node.label == "T6 retail normalize(rawNormal)"
    ]
    if len(matches) != 1:
        return None
    return matches[0].outputs.get("Vector")


def _build_material_v8(blender_material, gltf_material: dict, technique: str, recipe: dict | None, image_cache: dict):
    t6 = gltf_material.get("extras", {}).get("T6", {})
    binding = t6.get(BINDING_KEY)
    if isinstance(binding, dict):
        retail = str(binding.get("retailMaterialName") or "")
        if recipe is not None and str(recipe.get("material") or "") != retail:
            raise BlenderLayerPreviewError(
                f"{gltf_material.get('name')!r}: recipe retail identity != {retail!r}"
            )
        # Feed the existing v6/v7 graph the retail identity it was designed to
        # validate, while retaining this Blender material as the variant shell.
        retail_view = copy.deepcopy(gltf_material)
        retail_view["name"] = retail
        details = _BASE_BUILD_V6(
            blender_material, retail_view, technique, recipe, image_cache
        )
        blender_material["T6_preview_variant_name"] = str(gltf_material.get("name") or "")
        blender_material["T6_retail_material_name"] = retail
        blender_material["T6_lightmap_preview_binding_json"] = json.dumps(binding, sort_keys=True)
    else:
        details = _BASE_BUILD_V6(
            blender_material, gltf_material, technique, recipe, image_cache
        )

    directional = False
    directional_meta = None
    if isinstance(binding, dict):
        secondary = binding.get("secondary")
        if not isinstance(secondary, dict):
            raise BlenderLayerPreviewError("lightmap preview binding lacks secondary role")
        if bool(details.get("normalPlayback")) and bool(secondary.get("previewAvailable")):
            normal_socket = _final_normal_socket(blender_material)
            if normal_socket is None:
                raise BlenderLayerPreviewError(
                    "v7 reported normal playback but reconstructed normal socket is unavailable"
                )
            image = _load_preview_image(secondary)
            try:
                _, directional_meta = lightmap_nodes.build_directional_secondary(
                    blender_material.node_tree.nodes,
                    blender_material.node_tree.links,
                    image=image,
                    lightmap_texcoord=int(binding["lightmapTexCoord"]),
                    world_normal_socket=normal_socket,
                )
            except lightmap_nodes.BlenderDirectionalLightmapError as exc:
                raise BlenderLayerPreviewError(
                    f"directional secondary-lightmap node build failed: {exc}"
                ) from exc
            directional = True
            blender_material["T6_directional_lightmap_state"] = True
            blender_material["T6_directional_lightmap_state_json"] = json.dumps(
                directional_meta, sort_keys=True
            )
        else:
            blender_material["T6_directional_lightmap_state"] = False

    return {
        **details,
        "lightmapPreviewVariant": isinstance(binding, dict),
        "directionalLightmapState": directional,
        "directionalLightmap": directional_meta,
    }


def apply_preview(input_path: Path, output_blend: Path, *, recipes: Path | None = None, strict: bool = False) -> dict:
    global _ACTIVE_DOC, _ACTIVE_RAW, _ACTIVE_TEMP, _ACTIVE_IMAGE_CACHE
    if bpy is None:
        raise BlenderLayerPreviewError("this adapter must run inside Blender's Python")
    doc, raw = _read_doc_raw(input_path)
    specialization = _root_v23_preflight(doc)
    _ACTIVE_DOC, _ACTIVE_RAW = doc, raw
    _ACTIVE_IMAGE_CACHE = {}
    old_technique = v3._material_technique
    old_builder = v6._build_material_v6
    with tempfile.TemporaryDirectory(prefix="t6_blender_lm_") as td:
        _ACTIVE_TEMP = td
        v3._material_technique = _variant_material_technique
        v6._build_material_v6 = _build_material_v8
        try:
            result = v7.apply_preview(
                input_path, output_blend, recipes=recipes, strict=strict
            )
        finally:
            v3._material_technique = old_technique
            v6._build_material_v6 = old_builder
            _ACTIVE_TEMP = None
            _ACTIVE_DOC = None
            _ACTIVE_RAW = None
            _ACTIVE_IMAGE_CACHE = {}

    variant_count = sum(1 for row in result.get("rebuilt", []) if bool(row.get("lightmapPreviewVariant")))
    directional_count = sum(1 for row in result.get("rebuilt", []) if bool(row.get("directionalLightmapState")))
    result["format"] = FORMAT
    result["lightmapMaterialSpecialization"] = SPECIALIZATION_FORMAT
    result["lightmapMaterialSpecializationSha256"] = specialization.get("contractSha256")
    result["lightmapPreviewVariantRebuiltCount"] = variant_count
    result["directionalLightmapStateMaterialCount"] = directional_count
    result["directionalLightmapPolicy"] = (
        "exact retained directional secondary-lightmap coordinates/equation over exact-DDS-derived Non-Color PNG; "
        "requires exact v7 reconstructed T6 normal; final material/lightmap/specular/reflection composition remains unassigned"
    )
    result["proofBoundary"] = (
        "v7 exact generated diffuse/normal graph plus per-surface v23 lightmap ownership and retained directional "
        "secondary-lightmap equation. Authoring texture sampling is not claimed D3D11-bit-identical and directional "
        "RGB is not silently connected to an unproved final lighting combine."
    )
    report = output_blend.with_suffix(output_blend.suffix + ".t6_preview.json")
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _argv() -> list[str]:
    return [] if "--" not in sys.argv else sys.argv[sys.argv.index("--") + 1:]


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument("input",type=Path);p.add_argument("output_blend",type=Path)
    p.add_argument("--recipes",type=Path);p.add_argument("--strict",action="store_true");a=p.parse_args(_argv())
    r=apply_preview(a.input,a.output_blend,recipes=a.recipes,strict=a.strict)
    print(json.dumps({"out":r["output"],"rebuiltMaterialCount":r["rebuiltMaterialCount"],
                      "lightmapPreviewVariantRebuiltCount":r["lightmapPreviewVariantRebuiltCount"],
                      "directionalLightmapStateMaterialCount":r["directionalLightmapStateMaterialCount"]},indent=2));return 0

if __name__=="__main__": raise SystemExit(main())
