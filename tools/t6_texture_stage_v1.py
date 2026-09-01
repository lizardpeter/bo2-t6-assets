#!/usr/bin/env python3
"""Deterministically stage exact T6 material texture dependencies as PNG.

Input is a t6-material-texture-manifest-v1 document. Every dependency is
resolved by its exact sourceTexture basename under --texture-root. No fuzzy
matching, suffix inference, or role guessing is performed.

Supported TGA inputs are the source-closed subset used by the retained BO2
texture workflow:
- true-color uncompressed/RLE (type 2/10), 24-bit or 32-bit
- grayscale uncompressed/RLE (type 3/11), 8-bit or 16-bit intensity+alpha

Palette/color-mapped TGA is rejected rather than approximated.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import zlib
from pathlib import Path


class TextureStageError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _encode_png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    if width <= 0 or height <= 0:
        raise TextureStageError("PNG dimensions must be positive")
    expected = width * height * 4
    if len(rgba) != expected:
        raise TextureStageError(f"RGBA payload length {len(rgba)} != {expected}")

    scanlines = bytearray()
    stride = width * 4
    for y in range(height):
        scanlines.append(0)
        start = y * stride
        scanlines.extend(rgba[start : start + stride])

    compressor = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=15,
        memLevel=9,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    compressed = compressor.compress(bytes(scanlines)) + compressor.flush()
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _decode_tga(data: bytes) -> tuple[int, int, bytes, dict]:
    if len(data) < 18:
        raise TextureStageError("TGA shorter than 18-byte header")
    (
        id_length,
        color_map_type,
        image_type,
        cmap_first,
        cmap_length,
        cmap_depth,
        x_origin,
        y_origin,
        width,
        height,
        pixel_depth,
        descriptor,
    ) = struct.unpack_from("<BBBHHBHHHHBB", data, 0)

    if color_map_type != 0:
        raise TextureStageError("color-mapped/paletted TGA is not source-closed")
    if image_type not in (2, 3, 10, 11):
        raise TextureStageError(f"unsupported TGA image type {image_type}")
    true_color = image_type in (2, 10)
    rle = image_type in (10, 11)
    if true_color and pixel_depth not in (24, 32):
        raise TextureStageError(f"unsupported true-color TGA depth {pixel_depth}")
    if not true_color and pixel_depth not in (8, 16):
        raise TextureStageError(f"unsupported grayscale TGA depth {pixel_depth}")
    if width <= 0 or height <= 0:
        raise TextureStageError(f"invalid TGA dimensions {width}x{height}")

    bytes_per_pixel = pixel_depth // 8
    offset = 18 + id_length
    if offset > len(data):
        raise TextureStageError("TGA ID field exceeds file")

    pixel_count = width * height
    raw_pixels: list[bytes] = []

    def read_pixel() -> bytes:
        nonlocal offset
        end = offset + bytes_per_pixel
        if end > len(data):
            raise TextureStageError("truncated TGA pixel data")
        pixel = data[offset:end]
        offset = end
        return pixel

    if not rle:
        needed = pixel_count * bytes_per_pixel
        if offset + needed > len(data):
            raise TextureStageError("truncated uncompressed TGA pixels")
        raw_pixels = [
            data[offset + i * bytes_per_pixel : offset + (i + 1) * bytes_per_pixel]
            for i in range(pixel_count)
        ]
        offset += needed
    else:
        while len(raw_pixels) < pixel_count:
            if offset >= len(data):
                raise TextureStageError("truncated TGA RLE packet header")
            header = data[offset]
            offset += 1
            count = (header & 0x7F) + 1
            if len(raw_pixels) + count > pixel_count:
                raise TextureStageError("TGA RLE packet exceeds pixel count")
            if header & 0x80:
                pixel = read_pixel()
                raw_pixels.extend([pixel] * count)
            else:
                for _ in range(count):
                    raw_pixels.append(read_pixel())

    def to_rgba(pixel: bytes) -> bytes:
        if true_color:
            b, g, r = pixel[0], pixel[1], pixel[2]
            a = pixel[3] if bytes_per_pixel == 4 else 255
            return bytes((r, g, b, a))
        intensity = pixel[0]
        alpha = pixel[1] if bytes_per_pixel == 2 else 255
        return bytes((intensity, intensity, intensity, alpha))

    converted = [to_rgba(pixel) for pixel in raw_pixels]

    origin_right = bool(descriptor & 0x10)
    origin_top = bool(descriptor & 0x20)
    rgba = bytearray(pixel_count * 4)
    for stream_index, pixel in enumerate(converted):
        row = stream_index // width
        col = stream_index % width
        x = (width - 1 - col) if origin_right else col
        y = row if origin_top else (height - 1 - row)
        dst = (y * width + x) * 4
        rgba[dst : dst + 4] = pixel

    return width, height, bytes(rgba), {
        "imageType": image_type,
        "pixelDepth": pixel_depth,
        "descriptor": descriptor,
        "originTop": origin_top,
        "originRight": origin_right,
        "rle": rle,
        "xOrigin": x_origin,
        "yOrigin": y_origin,
        "idLength": id_length,
        "colorMapFirst": cmap_first,
        "colorMapLength": cmap_length,
        "colorMapDepth": cmap_depth,
    }


def _safe_source_basename(source_texture: str) -> str:
    if not source_texture or source_texture in (".", ".."):
        raise TextureStageError(f"invalid sourceTexture {source_texture!r}")
    if "/" in source_texture or "\\" in source_texture or "\0" in source_texture:
        raise TextureStageError(
            f"sourceTexture must be an exact basename, not a path: {source_texture!r}"
        )
    return source_texture


def _collect_dependencies(material_manifest: dict) -> dict[str, list[dict]]:
    if material_manifest.get("format") != "t6-material-texture-manifest-v1":
        raise TextureStageError(
            f"unsupported material manifest {material_manifest.get('format')!r}"
        )

    dependencies: dict[str, list[dict]] = {}
    for material in material_manifest.get("materials", []):
        material_name = str(material.get("material") or "")
        material_index = int(material["materialIndex"])
        preview_by_source: dict[str, str] = {}
        for target, binding in material.get("standardPreview", {}).items():
            source = str(binding.get("sourceTexture") or "")
            if source:
                preview_by_source[source] = str(target)

        for layer in material.get("layers", []):
            layer_index = int(layer["layerIndex"])
            layer_name = str(layer.get("layer") or "")
            for texture in layer.get("textures", []):
                source = _safe_source_basename(str(texture.get("sourceTexture") or ""))
                dependencies.setdefault(source, []).append(
                    {
                        "materialIndex": material_index,
                        "material": material_name,
                        "layerIndex": layer_index,
                        "layer": layer_name,
                        "role": str(texture.get("role") or ""),
                        "textureIndex": int(texture["textureIndex"]),
                        "compositors": list(texture.get("compositors", [])),
                        "standardPreviewTarget": preview_by_source.get(source),
                    }
                )
    for uses in dependencies.values():
        uses.sort(
            key=lambda use: (
                use["materialIndex"],
                use["layerIndex"],
                use["role"],
                use["textureIndex"],
            )
        )
    return dependencies


def stage(
    material_manifest: dict,
    *,
    texture_root: Path,
    output_dir: Path,
    material_manifest_name: str | None = None,
    material_manifest_sha256: str | None = None,
    allow_missing: bool = False,
) -> dict:
    dependencies = _collect_dependencies(material_manifest)
    output_dir.mkdir(parents=True, exist_ok=True)

    staged: list[dict] = []
    missing: list[dict] = []
    unsupported: list[dict] = []

    for source_texture in sorted(dependencies):
        source_path = texture_root / source_texture
        if not source_path.is_file():
            record = {"sourceTexture": source_texture, "uses": dependencies[source_texture]}
            missing.append(record)
            if not allow_missing:
                raise TextureStageError(f"missing exact source texture {source_path}")
            continue

        source_bytes = source_path.read_bytes()
        source_sha = _sha256(source_bytes)
        try:
            width, height, rgba, tga_meta = _decode_tga(source_bytes)
        except TextureStageError as exc:
            record = {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "reason": str(exc),
                "uses": dependencies[source_texture],
            }
            unsupported.append(record)
            if not allow_missing:
                raise
            continue

        png = _encode_png_rgba(width, height, rgba)
        name_hash = hashlib.sha256(source_texture.encode("utf-8")).hexdigest()
        output_name = f"{name_hash}.png"
        output_path = output_dir / output_name
        output_path.write_bytes(png)
        staged.append(
            {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "tga": tga_meta,
                "png": {
                    "file": output_name,
                    "path": str(output_path),
                    "bytes": len(png),
                    "sha256": _sha256(png),
                    "width": width,
                    "height": height,
                    "format": "RGBA8",
                },
                "uses": dependencies[source_texture],
            }
        )

    return {
        "format": "t6-texture-stage-manifest-v1",
        "source": {
            "materialManifest": material_manifest_name,
            "materialManifestSha256": material_manifest_sha256,
            "textureRoot": str(texture_root),
        },
        "policy": {
            "resolution": "exact sourceTexture basename under textureRoot only",
            "decode": "source-closed TGA types 2/3/10/11 only; fail closed otherwise",
            "orientation": "normalize TGA origin to top-left/left-right PNG rows",
            "png": "RGBA8, filter 0, zlib level 9, no metadata chunks",
            "outputNaming": "sha256(sourceTexture UTF-8) + .png",
            "deduplication": "one staged PNG per exact sourceTexture",
        },
        "stats": {
            "referencedTextureCount": len(dependencies),
            "stagedTextureCount": len(staged),
            "missingTextureCount": len(missing),
            "unsupportedTextureCount": len(unsupported),
            "standardPreviewSourceCount": len(
                {
                    source
                    for source, uses in dependencies.items()
                    if any(use.get("standardPreviewTarget") for use in uses)
                }
            ),
        },
        "textures": staged,
        "missing": missing,
        "unsupported": unsupported,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_manifest", type=Path)
    parser.add_argument("--texture-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    raw = args.material_manifest.read_bytes()
    material_manifest = json.loads(raw.decode("utf-8"))
    doc = stage(
        material_manifest,
        texture_root=args.texture_root,
        output_dir=args.out_dir,
        material_manifest_name=args.material_manifest.name,
        material_manifest_sha256=_sha256(raw),
        allow_missing=args.allow_missing,
    )
    manifest_out = args.manifest_out or (args.out_dir / "t6_texture_stage_manifest_v1.json")
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_out.write_bytes(payload)
    print(
        json.dumps(
            {
                "out": str(manifest_out),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                **doc["stats"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
