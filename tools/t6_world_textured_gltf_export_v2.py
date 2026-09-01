#!/usr/bin/env python3
"""Portable T6 textured world glTF/GLB v2: embed every exact dependency image.

v1 binds and embeds only source-approved core-glTF preview textures. v2 keeps
that conservative rendering policy, then additionally embeds every staged
texture dependency referenced by each exactly matched T6 material. Non-core
images are not wired into invented PBR slots; their glTF texture indices are
recorded beside the complete material dependency graph in extras.

Result: one GLB can carry the full decoded material image set needed by a future
Treyarch-aware Blender/wgpu shader while standard viewers still see only the
bindings whose semantics are independently safe.
"""
from __future__ import annotations

import copy
from pathlib import Path

from t6_world_textured_gltf_export_v1 import (
    TexturedExportError,
    _append_buffer_view,
    _material_lookup,
    _png_dimensions,
    _sha256,
    _stage_lookup,
    export_textured as export_preview,
    validate_textured,
)


def export_textured(
    world: dict,
    material_manifest: dict,
    texture_stage_manifest: dict,
    *,
    stage_root: Path,
    material_manifest_sha256: str | None = None,
    allow_missing_preview_textures: bool = False,
    allow_missing_dependency_textures: bool = False,
) -> tuple[dict, bytes]:
    gltf, raw = export_preview(
        world,
        material_manifest,
        texture_stage_manifest,
        stage_root=stage_root,
        material_manifest_sha256=material_manifest_sha256,
        allow_missing_preview_textures=allow_missing_preview_textures,
    )

    material_by_name = _material_lookup(material_manifest)
    stage_by_source = _stage_lookup(texture_stage_manifest, stage_root=stage_root)
    images = gltf.setdefault("images", [])
    textures = gltf.setdefault("textures", [])

    texture_index_by_source: dict[str, int] = {}
    for texture_index, texture in enumerate(textures):
        source = str(texture.get("extras", {}).get("T6", {}).get("sourceTexture") or "")
        if source:
            if source in texture_index_by_source:
                raise TexturedExportError(f"duplicate embedded sourceTexture {source!r}")
            texture_index_by_source[source] = texture_index

    preview_embedded_image_count = len(images)
    missing_sources: set[str] = set()
    all_dependency_sources: set[str] = set()

    def embed_dependency(source_texture: str) -> int | None:
        nonlocal raw
        existing = texture_index_by_source.get(source_texture)
        if existing is not None:
            return existing

        staged = stage_by_source.get(source_texture)
        if staged is None or not staged["path"].is_file():
            missing_sources.add(source_texture)
            if allow_missing_dependency_textures:
                return None
            raise TexturedExportError(
                f"material dependency texture {source_texture!r} was not staged"
            )

        payload = staged["path"].read_bytes()
        actual_sha = _sha256(payload)
        png_meta = staged["entry"].get("png", {})
        expected_sha = str(png_meta.get("sha256") or "")
        if expected_sha and actual_sha != expected_sha:
            raise TexturedExportError(
                f"staged PNG hash mismatch for dependency {source_texture!r}: "
                f"{actual_sha} != {expected_sha}"
            )
        width, height = _png_dimensions(payload)
        if png_meta.get("width") is not None and int(png_meta["width"]) != width:
            raise TexturedExportError(
                f"staged PNG width mismatch for dependency {source_texture!r}"
            )
        if png_meta.get("height") is not None and int(png_meta["height"]) != height:
            raise TexturedExportError(
                f"staged PNG height mismatch for dependency {source_texture!r}"
            )

        view_index, raw = _append_buffer_view(
            gltf,
            raw,
            payload,
            f"T6 dependency image:{source_texture}",
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
                        "bindingPolicy": "embedded dependency; not implicitly PBR-bound",
                    }
                },
            }
        )
        texture_index = len(textures)
        textures.append(
            {
                "name": source_texture,
                "source": image_index,
                "extras": {
                    "T6": {
                        "sourceTexture": source_texture,
                        "bindingPolicy": "dependency graph only unless separately preview-bound",
                    }
                },
            }
        )
        texture_index_by_source[source_texture] = texture_index
        return texture_index

    for gltf_material in gltf.get("materials", []):
        name = str(gltf_material.get("name") or "")
        manifest_material = material_by_name.get(name)
        if manifest_material is None:
            continue

        embedded_for_material: list[dict] = []
        seen_for_material: set[tuple[int, int, str]] = set()
        for layer in manifest_material.get("layers", []):
            layer_index = int(layer["layerIndex"])
            for dependency in layer.get("textures", []):
                source = str(dependency.get("sourceTexture") or "")
                if not source:
                    raise TexturedExportError(
                        f"material {name!r} layer {layer_index} has empty dependency sourceTexture"
                    )
                all_dependency_sources.add(source)
                texture_index = embed_dependency(source)
                if texture_index is None:
                    continue
                key = (layer_index, int(dependency["textureIndex"]), source)
                if key in seen_for_material:
                    continue
                seen_for_material.add(key)
                embedded_for_material.append(
                    {
                        "layerIndex": layer_index,
                        "layer": layer.get("layer"),
                        "role": dependency.get("role"),
                        "semantic": dependency.get("semantic"),
                        "sourceTexture": source,
                        "sourceTextureIndex": dependency.get("sourceTextureIndex"),
                        "generatedTextureIndex": int(dependency["textureIndex"]),
                        "gltfTextureIndex": texture_index,
                    }
                )

        t6 = gltf_material.setdefault("extras", {}).setdefault("T6", {})
        t6["embeddedDependencyTextures"] = embedded_for_material
        t6["dependencyEmbeddingPolicy"] = (
            "all exact staged dependencies embedded; only standardPreview entries are core-glTF-bound"
        )

    stats = gltf["extras"]["T6"]["exportStats"]
    stats.update(
        {
            "standardPreviewEmbeddedImageCount": preview_embedded_image_count,
            "materialDependencySourceCount": len(all_dependency_sources),
            "embeddedDependencyImageCount": len(images),
            "unboundEmbeddedDependencyImageCount": max(
                0, len(images) - preview_embedded_image_count
            ),
            "missingDependencyTextureCount": len(missing_sources),
            "embeddedImageCount": len(images),
        }
    )
    texture_export = gltf["extras"]["T6"].setdefault("textureExport", {})
    texture_export["dependencyEmbedding"] = {
        "policy": (
            "embed every staged sourceTexture referenced by an exactly matched material; "
            "do not create implicit PBR bindings for non-standard semantics"
        ),
        "uniqueDependencySources": len(all_dependency_sources),
        "embeddedSources": sorted(
            source for source in all_dependency_sources if source in texture_index_by_source
        ),
        "missingSources": sorted(missing_sources),
    }

    validate_textured(gltf, raw)
    for source in all_dependency_sources:
        if source not in texture_index_by_source and not allow_missing_dependency_textures:
            raise TexturedExportError(
                f"validated export still lacks dependency texture {source!r}"
            )
    return gltf, raw
