#!/usr/bin/env python3
"""Derive Blender-friendly PNG previews from exact archived T6 lightmap DDS.

The canonical source remains `extras.T6.lightmapArchive` v3 and its raw DDS
bufferViews.  This postpass decodes each unique *embedded* present lightmap
GfxImage through Pillow's DDS decoder and appends an RGBA PNG as an authoring
preview only.

Hard boundaries:
- archived DDS bytes/bufferViews are never rewritten;
- identity join is exact GfxImage + sourceTexture + DDS SHA-256;
- absent/null lightmap roles remain absent and create no preview;
- no glTF material binding is created;
- no T6 lightmap shader equation is implied by the preview image;
- the PNG is tagged as data/non-color authoring input, not sRGB albedo.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from typing import Any

from PIL import Image

from t6_world_lightmap_glb_embed_v1 import _append_buffer_view
from t6_world_lightmap_glb_embed_v3 import (
    ARCHIVE_FORMAT as SOURCE_ARCHIVE_FORMAT,
    LightmapGlbEmbedError,
    validate_lightmap_archive,
)

FORMAT = "t6-world-lightmap-preview-archive-v1"
ROOT_KEY = "lightmapPreviewArchive"


class LightmapPreviewEmbedError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload(document: dict, raw: bytes, view_index: int) -> bytes:
    try:
        view = document["bufferViews"][int(view_index)]
    except Exception as exc:
        raise LightmapPreviewEmbedError(f"invalid DDS bufferView {view_index}") from exc
    if int(view.get("buffer", 0)) != 0:
        raise LightmapPreviewEmbedError("lightmap DDS preview requires buffer 0")
    start = int(view.get("byteOffset", 0))
    length = int(view.get("byteLength", -1))
    end = start + length
    if start < 0 or length < 4 or end > len(raw):
        raise LightmapPreviewEmbedError(
            f"lightmap DDS bufferView {view_index} range {start}:{end} outside {len(raw)}"
        )
    return raw[start:end]


def _decode_png(dds: bytes) -> tuple[bytes, dict]:
    if len(dds) < 128 or dds[:4] != b"DDS ":
        raise LightmapPreviewEmbedError("archived lightmap preview source is not DDS")
    try:
        with Image.open(io.BytesIO(dds)) as image:
            image.load()
            source_mode = str(image.mode)
            width, height = map(int, image.size)
            if width <= 0 or height <= 0:
                raise LightmapPreviewEmbedError(
                    f"decoded DDS has invalid dimensions {width}x{height}"
                )
            rgba = image.convert("RGBA")
            out = io.BytesIO()
            rgba.save(out, format="PNG", compress_level=1, optimize=False)
            png = out.getvalue()
    except LightmapPreviewEmbedError:
        raise
    except Exception as exc:
        raise LightmapPreviewEmbedError(f"Pillow DDS decode failed: {exc}") from exc
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise LightmapPreviewEmbedError("derived lightmap preview lost PNG signature")
    return png, {
        "width": width,
        "height": height,
        "sourceMode": source_mode,
        "previewMode": "RGBA",
        "decoder": "Pillow-DDS-native",
    }


def embed_lightmap_previews(document: dict, raw: bytes) -> tuple[dict, bytes, dict]:
    try:
        validate_lightmap_archive(document, raw)
    except LightmapGlbEmbedError as exc:
        raise LightmapPreviewEmbedError(f"invalid canonical lightmap archive: {exc}") from exc

    out = copy.deepcopy(document)
    t6 = out.setdefault("extras", {}).setdefault("T6", {})
    if t6.get(ROOT_KEY) is not None:
        raise LightmapPreviewEmbedError("lightmap preview archive is already attached")
    archive = t6.get("lightmapArchive")
    if not isinstance(archive, dict) or archive.get("format") != SOURCE_ARCHIVE_FORMAT:
        raise LightmapPreviewEmbedError(
            f"expected canonical {SOURCE_ARCHIVE_FORMAT}, got {getattr(archive, 'get', lambda *_: None)('format')!r}"
        )

    source_raw = bytes(raw)
    images = out.setdefault("images", [])
    textures = out.setdefault("textures", [])
    samplers = out.setdefault("samplers", [])
    sampler_index = len(samplers)
    samplers.append({
        "magFilter": 9729,
        "minFilter": 9729,
        "wrapS": 33071,
        "wrapT": 33071,
        "name": "T6 lightmap preview clamp-linear",
        "extras": {"T6": {"previewOnly": True, "dataTexture": True}},
    })

    by_identity: dict[tuple[str, str, str], dict] = {}
    preview_rows: list[dict] = []
    present_role_count = 0
    embedded_role_count = 0
    absent_role_count = 0

    lightmaps = archive.get("lightmaps")
    if not isinstance(lightmaps, list):
        raise LightmapPreviewEmbedError("canonical lightmap archive has no lightmaps list")

    for expected_index, lightmap in enumerate(lightmaps):
        if int(lightmap.get("index", -1)) != expected_index:
            raise LightmapPreviewEmbedError("canonical lightmap indices are not dense/in-order")
        for role in ("primary", "secondary"):
            item = lightmap.get(role)
            if not isinstance(item, dict):
                raise LightmapPreviewEmbedError(
                    f"lightmap {expected_index} {role}: missing canonical role"
                )
            if not bool(item.get("present")):
                absent_role_count += 1
                continue
            present_role_count += 1
            if not bool(item.get("embedded")):
                # Canonical archive already accounts this as missing. Do not
                # manufacture a preview or a fallback texture.
                continue
            embedded_role_count += 1
            asset = str(item.get("gfxImageAsset") or "")
            source = str(item.get("sourceTexture") or "")
            dds_sha = str(item.get("sha256") or "")
            if not asset or not source or len(dds_sha) != 64:
                raise LightmapPreviewEmbedError(
                    f"lightmap {expected_index} {role}: embedded role lost exact identity/SHA"
                )
            dds = _payload(out, source_raw, int(item["bufferView"]))
            if len(dds) != int(item.get("bytes", -1)) or _sha(dds) != dds_sha:
                raise LightmapPreviewEmbedError(
                    f"lightmap {expected_index} {role}: canonical DDS bytes/SHA mismatch"
                )
            key = (asset, source, dds_sha)
            preview = by_identity.get(key)
            if preview is None:
                png, meta = _decode_png(dds)
                view_index, raw = _append_buffer_view(
                    out,
                    raw,
                    png,
                    name=f"T6 lightmap preview PNG:{asset}",
                )
                image_index = len(images)
                images.append({
                    "name": f"T6_LIGHTMAP_PREVIEW_{asset}",
                    "bufferView": view_index,
                    "mimeType": "image/png",
                    "extras": {"T6": {
                        "previewOnly": True,
                        "dataTexture": True,
                        "sourceKind": "canonical embedded lightmap DDS",
                        "gfxImageAsset": asset,
                        "sourceTexture": source,
                        "sourceDdsSha256": dds_sha,
                        "decoder": meta["decoder"],
                    }},
                })
                texture_index = len(textures)
                textures.append({
                    "name": f"T6_LIGHTMAP_PREVIEW_{asset}",
                    "source": image_index,
                    "sampler": sampler_index,
                    "extras": {"T6": {
                        "previewOnly": True,
                        "dataTexture": True,
                        "sourceDdsSha256": dds_sha,
                    }},
                })
                preview = {
                    "gfxImageAsset": asset,
                    "sourceTexture": source,
                    "sourceDdsSha256": dds_sha,
                    "sourceDdsBytes": len(dds),
                    "previewPngSha256": _sha(png),
                    "previewPngBytes": len(png),
                    "previewBufferView": view_index,
                    "previewImageIndex": image_index,
                    "previewTextureIndex": texture_index,
                    **meta,
                }
                by_identity[key] = preview
                preview_rows.append(preview)

            item["preview"] = {
                "format": FORMAT,
                "previewOnly": True,
                "dataTexture": True,
                "previewTextureIndex": int(preview["previewTextureIndex"]),
                "previewImageIndex": int(preview["previewImageIndex"]),
                "previewBufferView": int(preview["previewBufferView"]),
                "previewPngSha256": preview["previewPngSha256"],
                "sourceDdsSha256": dds_sha,
                "width": int(preview["width"]),
                "height": int(preview["height"]),
            }

    # The only allowed source mutation is append-only preview payload growth.
    if raw[:len(source_raw)] != source_raw:
        raise LightmapPreviewEmbedError(
            "lightmap preview derivation changed bytes inside canonical source BIN prefix"
        )

    stats = {
        "lightmapCount": len(lightmaps),
        "presentRoleCount": present_role_count,
        "embeddedRoleCount": embedded_role_count,
        "absentRoleCount": absent_role_count,
        "uniquePreviewImageCount": len(preview_rows),
        "sourceBinBytes": len(source_raw),
        "finalBinBytes": len(raw),
        "appendedPreviewBytes": len(raw) - len(source_raw),
        "sourceBinExactPrefix": True,
    }
    contract = {
        "format": FORMAT,
        "sourceArchiveFormat": SOURCE_ARCHIVE_FORMAT,
        "map": archive.get("map"),
        "stats": stats,
        "previews": preview_rows,
        "policy": {
            "canonicalSource": "raw DDS in extras.T6.lightmapArchive remains authoritative",
            "preview": "derived RGBA PNG via Pillow DDS decode; authoring/data texture only",
            "colorSpace": "data/non-color; no sRGB semantic asserted",
            "materialBindingsCreated": False,
            "lightmapEquation": "not implied by preview; consume separate retained directional-lightmap proof",
            "missingRoles": "no preview or fallback for absent/unembedded canonical roles",
        },
    }
    contract["contractSha256"] = _jhash(contract)
    t6[ROOT_KEY] = contract
    return out, raw, stats
