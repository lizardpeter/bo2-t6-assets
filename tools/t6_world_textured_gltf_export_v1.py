#!/usr/bin/env python3
"""Add exact source-closed T6 preview textures to audited world glTF/GLB.

This wrapper deliberately leaves t6_world_gltf_export_v1.py unchanged. It
starts from that validated geometry export, then:
- joins materials by exact source material name,
- consumes only standardPreview bindings already approved by
  t6_material_texture_manifest_v1.py,
- embeds staged PNGs as glTF image bufferViews,
- preserves the complete Treyarch material dependency graph in extras.

No role, channel, layer, or compositor semantics are inferred here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

from t6_world_gltf_export_v1 import export as export_world
from t6_world_gltf_export_v1 import glb_bytes, gltf_bytes, validate as validate_world


class TexturedExportError(RuntimeError):
    pass


PREVIEW_TARGETS = ("baseColorTexture", "normalTexture")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise TexturedExportError("staged texture is not a PNG")
    if data[12:16] != b"IHDR":
        raise TexturedExportError("PNG first chunk is not IHDR")
    width, height = struct.unpack_from(">II", data, 16)
    if width <= 0 or height <= 0:
        raise TexturedExportError("PNG has invalid dimensions")
    return width, height


def _append_buffer_view(gltf: dict, raw: bytes, payload: bytes, name: str) -> tuple[int, bytes]:
    mutable = bytearray(raw)
    while len(mutable) % 4:
        mutable.append(0)
    offset = len(mutable)
    mutable.extend(payload)
    view_index = len(gltf.setdefault("bufferViews", []))
    gltf["bufferViews"].append(
        {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(payload),
            "name": name,
        }
    )
    out = bytes(mutable)
    gltf["buffers"][0]["byteLength"] = len(out)
    return view_index, out


def _material_lookup(material_manifest: dict) -> dict[str, dict]:
    if material_manifest.get("format") != "t6-material-texture-manifest-v1":
        raise TexturedExportError(
            f"unsupported material manifest {material_manifest.get('format')!r}"
        )
    result: dict[str, dict] = {}
    for entry in material_manifest.get("materials", []):
        name = str(entry.get("material") or "")
        if not name:
            raise TexturedExportError("material manifest contains empty material name")
        if name in result:
            raise TexturedExportError(f"duplicate material manifest name {name!r}")
        result[name] = entry
    return result


def _stage_lookup(
    texture_stage_manifest: dict,
    *,
    stage_root: Path,
) -> dict[str, dict]:
    if texture_stage_manifest.get("format") != "t6-texture-stage-manifest-v1":
        raise TexturedExportError(
            f"unsupported texture stage manifest "
            f"{texture_stage_manifest.get('format')!r}"
        )
    result: dict[str, dict] = {}
    for entry in texture_stage_manifest.get("textures", []):
        source = str(entry.get("sourceTexture") or "")
        if not source:
            raise TexturedExportError("texture stage entry has empty sourceTexture")
        if source in result:
            raise TexturedExportError(f"duplicate staged sourceTexture {source!r}")
        png = entry.get("png", {})
        file_name = str(png.get("file") or "")
        if not file_name or "/" in file_name or "\\" in file_name or "\0" in file_name:
            raise TexturedExportError(
                f"staged PNG file must be a basename for {source!r}: {file_name!r}"
            )
        path = stage_root / file_name
        result[source] = {
            "entry": entry,
            "path": path,
        }
    return result


def export_textured(
    world: dict,
    material_manifest: dict,
    texture_stage_manifest: dict,
    *,
    stage_root: Path,
    material_manifest_sha256: str | None = None,
    allow_missing_preview_textures: bool = False,
) -> tuple[dict, bytes]:
    gltf, raw = export_world(world)
    validate_world(gltf, raw)

    stage_source_sha = (
        texture_stage_manifest.get("source", {}).get("materialManifestSha256")
    )
    if (
        material_manifest_sha256 is not None
        and stage_source_sha is not None
        and str(stage_source_sha) != material_manifest_sha256
    ):
        raise TexturedExportError(
            "texture stage manifest was built from a different material manifest"
        )

    material_by_name = _material_lookup(material_manifest)
    stage_by_source = _stage_lookup(texture_stage_manifest, stage_root=stage_root)

    images: list[dict] = []
    textures: list[dict] = []
    texture_index_by_source: dict[str, int] = {}
    embedded_sha_by_source: dict[str, str] = {}

    def embed_source(source_texture: str) -> int | None:
        nonlocal raw
        if source_texture in texture_index_by_source:
            return texture_index_by_source[source_texture]

        staged = stage_by_source.get(source_texture)
        if staged is None:
            if allow_missing_preview_textures:
                return None
            raise TexturedExportError(
                f"standard preview texture {source_texture!r} was not staged"
            )
        path = staged["path"]
        if not path.is_file():
            if allow_missing_preview_textures:
                return None
            raise TexturedExportError(f"staged PNG is missing: {path}")

        payload = path.read_bytes()
        actual_sha = _sha256(payload)
        png_meta = staged["entry"].get("png", {})
        expected_sha = str(png_meta.get("sha256") or "")
        if expected_sha and actual_sha != expected_sha:
            raise TexturedExportError(
                f"staged PNG hash mismatch for {source_texture!r}: "
                f"{actual_sha} != {expected_sha}"
            )
        width, height = _png_dimensions(payload)
        expected_width = png_meta.get("width")
        expected_height = png_meta.get("height")
        if expected_width is not None and int(expected_width) != width:
            raise TexturedExportError(f"staged PNG width mismatch for {source_texture!r}")
        if expected_height is not None and int(expected_height) != height:
            raise TexturedExportError(f"staged PNG height mismatch for {source_texture!r}")

        view_index, raw = _append_buffer_view(
            gltf,
            raw,
            payload,
            f"T6 image:{source_texture}",
        )
        image_index = len(images)
        images.append(
            {
                "name": source_texture,
                "bufferView": view_index,
                "mimeType": "image/png",
                "extras": {
                    "T6": {
                        "sourceTexture": source_texture,
                        "pngSha256": actual_sha,
                        "width": width,
                        "height": height,
                    }
                },
            }
        )
        texture_index = len(textures)
        textures.append(
            {
                "name": source_texture,
                "source": image_index,
                "extras": {"T6": {"sourceTexture": source_texture}},
            }
        )
        texture_index_by_source[source_texture] = texture_index
        embedded_sha_by_source[source_texture] = actual_sha
        return texture_index

    matched_material_count = 0
    textured_material_count = 0
    preview_binding_count = 0
    unmatched_materials: list[str] = []
    missing_preview_sources: list[str] = []

    for material in gltf.get("materials", []):
        name = str(material.get("name") or "")
        source_entry = material_by_name.get(name)
        t6_extras = material.setdefault("extras", {}).setdefault("T6", {})
        if source_entry is None:
            unmatched_materials.append(name)
            t6_extras["materialTextureJoin"] = "no exact manifest material-name match"
            continue

        matched_material_count += 1
        t6_extras["materialDependencyGraph"] = copy.deepcopy(source_entry)
        t6_extras["materialTextureJoin"] = "exact source material-name match"

        preview = source_entry.get("standardPreview", {})
        applied: dict[str, dict] = {}
        for target in PREVIEW_TARGETS:
            binding = preview.get(target)
            if binding is None:
                continue
            source_texture = str(binding.get("sourceTexture") or "")
            if not source_texture:
                raise TexturedExportError(
                    f"material {name!r} preview {target} has empty sourceTexture"
                )
            texture_index = embed_source(source_texture)
            if texture_index is None:
                missing_preview_sources.append(source_texture)
                continue

            texture_info = {"index": texture_index, "texCoord": 0}
            if target == "baseColorTexture":
                material.setdefault("pbrMetallicRoughness", {})[
                    "baseColorTexture"
                ] = texture_info
            elif target == "normalTexture":
                material["normalTexture"] = texture_info
            else:
                raise AssertionError(target)

            applied[target] = {
                "sourceTexture": source_texture,
                "textureIndex": texture_index,
                "pngSha256": embedded_sha_by_source[source_texture],
                "texCoord": 0,
            }
            preview_binding_count += 1

        if applied:
            textured_material_count += 1
            t6_extras["standardPreviewApplied"] = applied

    if images:
        gltf["images"] = images
        gltf["textures"] = textures

    stats = gltf["extras"]["T6"]["exportStats"]
    stats.update(
        {
            "materialManifestMatchedCount": matched_material_count,
            "materialManifestUnmatchedCount": len(unmatched_materials),
            "texturedMaterialCount": textured_material_count,
            "standardPreviewBindingCount": preview_binding_count,
            "embeddedImageCount": len(images),
            "missingPreviewTextureCount": len(set(missing_preview_sources)),
        }
    )
    gltf["extras"]["T6"]["textureExport"] = {
        "policy": {
            "materialJoin": "exact material name only",
            "bindingJoin": "standardPreview sourceTexture only",
            "uv": "TEXCOORD_0 for source-approved standard preview bindings",
            "sampler": "no explicit sampler; source sampler state not present in flat mapping",
            "nonCoreSemantics": (
                "preserved in materialDependencyGraph extras; no implicit PBR remap"
            ),
        },
        "unmatchedMaterials": unmatched_materials,
        "missingPreviewSources": sorted(set(missing_preview_sources)),
        "stageStats": copy.deepcopy(texture_stage_manifest.get("stats", {})),
    }

    validate_textured(gltf, raw)
    return gltf, raw


def validate_textured(gltf: dict, raw: bytes) -> bool:
    validate_world(gltf, raw)
    views = gltf.get("bufferViews", [])
    images = gltf.get("images", [])
    textures = gltf.get("textures", [])

    for image_index, image in enumerate(images):
        if image.get("mimeType") != "image/png":
            raise TexturedExportError(f"image {image_index} is not PNG")
        view_index = int(image["bufferView"])
        if view_index < 0 or view_index >= len(views):
            raise TexturedExportError(f"image {image_index} bad bufferView")
        view = views[view_index]
        start = int(view.get("byteOffset", 0))
        end = start + int(view["byteLength"])
        if start < 0 or end > len(raw):
            raise TexturedExportError(f"image {image_index} outside buffer")
        _png_dimensions(raw[start:end])

    for texture_index, texture in enumerate(textures):
        source = int(texture["source"])
        if source < 0 or source >= len(images):
            raise TexturedExportError(f"texture {texture_index} bad image source")

    for material_index, material in enumerate(gltf.get("materials", [])):
        bindings = []
        pbr = material.get("pbrMetallicRoughness", {})
        if "baseColorTexture" in pbr:
            bindings.append(pbr["baseColorTexture"])
        if "normalTexture" in material:
            bindings.append(material["normalTexture"])
        for binding in bindings:
            index = int(binding["index"])
            if index < 0 or index >= len(textures):
                raise TexturedExportError(
                    f"material {material_index} has bad texture index {index}"
                )
            if int(binding.get("texCoord", 0)) != 0:
                raise TexturedExportError(
                    f"material {material_index} preview binding is not TEXCOORD_0"
                )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("world_json", type=Path)
    parser.add_argument("material_manifest", type=Path)
    parser.add_argument("texture_stage_manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--allow-missing-preview-textures", action="store_true")
    args = parser.parse_args()

    world = json.loads(args.world_json.read_text(encoding="utf-8"))
    material_raw = args.material_manifest.read_bytes()
    material_manifest = json.loads(material_raw.decode("utf-8"))
    texture_stage_manifest = json.loads(
        args.texture_stage_manifest.read_text(encoding="utf-8")
    )
    stage_root = args.stage_root or args.texture_stage_manifest.parent

    gltf, raw = export_textured(
        world,
        material_manifest,
        texture_stage_manifest,
        stage_root=stage_root,
        material_manifest_sha256=_sha256(material_raw),
        allow_missing_preview_textures=args.allow_missing_preview_textures,
    )
    suffix = args.output.suffix.lower()
    if suffix == ".gltf":
        payload = gltf_bytes(gltf, raw)
    elif suffix == ".glb":
        payload = glb_bytes(gltf, raw)
    else:
        raise SystemExit("output must end in .gltf or .glb")

    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "out": str(args.output),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                "bufferBytes": len(raw),
                **gltf["extras"]["T6"]["exportStats"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
