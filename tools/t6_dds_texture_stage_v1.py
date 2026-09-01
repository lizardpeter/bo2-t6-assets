#!/usr/bin/env python3
"""Deterministically stage exact T6/OAT DDS texture dependencies as PNG.

Supported first-mip DDS formats are deliberately limited to formats already
observed in retained T6 extraction proofs:
- BC1 / DXT1
- BC3 / DXT5
- BC5_UNORM / DXN (ATI2/BC5U or DX10 format 83)
- 32-bit RGBA/BGRA UNORM, including DX10 equivalents

For BC5 used by an approved normalTexture binding, R/G are interpreted as
biased tangent-space X/Y and positive Z is reconstructed. No green-channel
inversion is applied; T6 tangent handedness is preserved separately by the
world exporter. BC5 used ambiguously by both normal and non-normal preview
roles fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from t6_texture_stage_v1 import _collect_dependencies, _encode_png_rgba


class DdsStageError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rgb565(value: int) -> tuple[int, int, int]:
    r5 = (value >> 11) & 31
    g6 = (value >> 5) & 63
    b5 = value & 31
    return (
        (r5 * 255 + 15) // 31,
        (g6 * 255 + 31) // 63,
        (b5 * 255 + 15) // 31,
    )


def _bc1_colors(block: bytes, *, force_four_color: bool) -> list[tuple[int, int, int, int]]:
    c0, c1 = struct.unpack_from("<HH", block, 0)
    r0, g0, b0 = _rgb565(c0)
    r1, g1, b1 = _rgb565(c1)
    colors = [(r0, g0, b0, 255), (r1, g1, b1, 255)]
    if c0 > c1 or force_four_color:
        colors.extend(
            [
                (
                    (2 * r0 + r1) // 3,
                    (2 * g0 + g1) // 3,
                    (2 * b0 + b1) // 3,
                    255,
                ),
                (
                    (r0 + 2 * r1) // 3,
                    (g0 + 2 * g1) // 3,
                    (b0 + 2 * b1) // 3,
                    255,
                ),
            ]
        )
    else:
        colors.extend(
            [
                (
                    (r0 + r1) // 2,
                    (g0 + g1) // 2,
                    (b0 + b1) // 2,
                    255,
                ),
                (0, 0, 0, 0),
            ]
        )
    return colors


def _decode_bc1_block(block: bytes) -> list[tuple[int, int, int, int]]:
    if len(block) != 8:
        raise DdsStageError("BC1 block must be 8 bytes")
    colors = _bc1_colors(block, force_four_color=False)
    bits = struct.unpack_from("<I", block, 4)[0]
    return [colors[(bits >> (2 * i)) & 3] for i in range(16)]


def _decode_bc4_block(block: bytes) -> list[int]:
    if len(block) != 8:
        raise DdsStageError("BC4 channel block must be 8 bytes")
    e0, e1 = block[0], block[1]
    palette = [e0, e1]
    if e0 > e1:
        palette.extend(((7 - i) * e0 + i * e1) // 7 for i in range(1, 7))
    else:
        palette.extend(((5 - i) * e0 + i * e1) // 5 for i in range(1, 5))
        palette.extend((0, 255))
    bits = int.from_bytes(block[2:8], "little")
    return [palette[(bits >> (3 * i)) & 7] for i in range(16)]


def _decode_bc3_block(block: bytes) -> list[tuple[int, int, int, int]]:
    if len(block) != 16:
        raise DdsStageError("BC3 block must be 16 bytes")
    alphas = _decode_bc4_block(block[:8])
    colors = _bc1_colors(block[8:], force_four_color=True)
    bits = struct.unpack_from("<I", block, 12)[0]
    out = []
    for i in range(16):
        r, g, b, _ = colors[(bits >> (2 * i)) & 3]
        out.append((r, g, b, alphas[i]))
    return out


def _normal_z_u8(x_u8: int, y_u8: int) -> int:
    x = (x_u8 / 255.0) * 2.0 - 1.0
    y = (y_u8 / 255.0) * 2.0 - 1.0
    z = math.sqrt(max(0.0, 1.0 - x * x - y * y))
    return max(0, min(255, int(round((z * 0.5 + 0.5) * 255.0))))


def _decode_bc5_block(
    block: bytes,
    *,
    reconstruct_normal_z: bool,
) -> list[tuple[int, int, int, int]]:
    if len(block) != 16:
        raise DdsStageError("BC5 block must be 16 bytes")
    red = _decode_bc4_block(block[:8])
    green = _decode_bc4_block(block[8:])
    out = []
    for r, g in zip(red, green):
        b = _normal_z_u8(r, g) if reconstruct_normal_z else 0
        out.append((r, g, b, 255))
    return out


def _blit_blocks(
    width: int,
    height: int,
    data: bytes,
    *,
    block_bytes: int,
    decode_block,
) -> bytes:
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    needed = blocks_x * blocks_y * block_bytes
    if len(data) < needed:
        raise DdsStageError(
            f"truncated block-compressed mip: need {needed}, have {len(data)}"
        )
    rgba = bytearray(width * height * 4)
    offset = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            pixels = decode_block(data[offset : offset + block_bytes])
            offset += block_bytes
            for py in range(4):
                y = by * 4 + py
                if y >= height:
                    continue
                for px in range(4):
                    x = bx * 4 + px
                    if x >= width:
                        continue
                    pixel = pixels[py * 4 + px]
                    dst = (y * width + x) * 4
                    rgba[dst : dst + 4] = bytes(pixel)
    return bytes(rgba)


def _extract_mask(value: int, mask: int) -> int:
    if mask == 0:
        return 255
    shift = (mask & -mask).bit_length() - 1
    raw_mask = mask >> shift
    raw = (value & mask) >> shift
    if raw_mask <= 0:
        return 0
    return (raw * 255 + raw_mask // 2) // raw_mask


def _decode_rgba32(
    width: int,
    height: int,
    data: bytes,
    *,
    r_mask: int,
    g_mask: int,
    b_mask: int,
    a_mask: int,
) -> bytes:
    needed = width * height * 4
    if len(data) < needed:
        raise DdsStageError(f"truncated RGBA32 mip: need {needed}, have {len(data)}")
    out = bytearray(needed)
    for i in range(width * height):
        value = struct.unpack_from("<I", data, i * 4)[0]
        out[i * 4 + 0] = _extract_mask(value, r_mask)
        out[i * 4 + 1] = _extract_mask(value, g_mask)
        out[i * 4 + 2] = _extract_mask(value, b_mask)
        out[i * 4 + 3] = _extract_mask(value, a_mask) if a_mask else 255
    return bytes(out)


def _decode_dds(
    data: bytes,
    *,
    reconstruct_bc5_normal_z: bool,
) -> tuple[int, int, bytes, dict]:
    if len(data) < 128 or data[:4] != b"DDS ":
        raise DdsStageError("not a DDS file")
    if struct.unpack_from("<I", data, 4)[0] != 124:
        raise DdsStageError("DDS header size is not 124")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    mip_count = struct.unpack_from("<I", data, 28)[0] or 1
    if width <= 0 or height <= 0:
        raise DdsStageError(f"invalid DDS dimensions {width}x{height}")
    if struct.unpack_from("<I", data, 76)[0] != 32:
        raise DdsStageError("DDS pixel format size is not 32")

    pf_flags = struct.unpack_from("<I", data, 80)[0]
    fourcc = data[84:88]
    rgb_bits = struct.unpack_from("<I", data, 88)[0]
    r_mask, g_mask, b_mask, a_mask = struct.unpack_from("<IIII", data, 92)
    caps2 = struct.unpack_from("<I", data, 112)[0]
    if caps2 & (0x00000200 | 0x00200000):
        raise DdsStageError(
            "cubemap/volume DDS is not supported by 2D material staging"
        )

    offset = 128
    dxgi_format = None
    resource_dimension = None
    array_size = None
    format_name = None
    s_rgb = False

    if fourcc == b"DX10":
        if len(data) < 148:
            raise DdsStageError("truncated DDS DX10 header")
        dxgi_format, resource_dimension, _misc, array_size, _misc2 = struct.unpack_from(
            "<IIIII", data, 128
        )
        offset = 148
        if resource_dimension != 3 or array_size != 1:
            raise DdsStageError(
                f"unsupported DX10 DDS dimension/array {resource_dimension}/{array_size}"
            )
        if dxgi_format in (71, 72):
            format_name = "BC1_UNORM" + ("_SRGB" if dxgi_format == 72 else "")
            s_rgb = dxgi_format == 72
            rgba = _blit_blocks(
                width,
                height,
                data[offset:],
                block_bytes=8,
                decode_block=_decode_bc1_block,
            )
        elif dxgi_format in (77, 78):
            format_name = "BC3_UNORM" + ("_SRGB" if dxgi_format == 78 else "")
            s_rgb = dxgi_format == 78
            rgba = _blit_blocks(
                width,
                height,
                data[offset:],
                block_bytes=16,
                decode_block=_decode_bc3_block,
            )
        elif dxgi_format == 83:
            format_name = "BC5_UNORM"
            rgba = _blit_blocks(
                width,
                height,
                data[offset:],
                block_bytes=16,
                decode_block=lambda block: _decode_bc5_block(
                    block, reconstruct_normal_z=reconstruct_bc5_normal_z
                ),
            )
        elif dxgi_format in (28, 29):
            format_name = "R8G8B8A8_UNORM" + (
                "_SRGB" if dxgi_format == 29 else ""
            )
            s_rgb = dxgi_format == 29
            rgba = _decode_rgba32(
                width,
                height,
                data[offset:],
                r_mask=0x000000FF,
                g_mask=0x0000FF00,
                b_mask=0x00FF0000,
                a_mask=0xFF000000,
            )
        elif dxgi_format in (87, 91):
            format_name = "B8G8R8A8_UNORM" + (
                "_SRGB" if dxgi_format == 91 else ""
            )
            s_rgb = dxgi_format == 91
            rgba = _decode_rgba32(
                width,
                height,
                data[offset:],
                r_mask=0x00FF0000,
                g_mask=0x0000FF00,
                b_mask=0x000000FF,
                a_mask=0xFF000000,
            )
        else:
            raise DdsStageError(f"unsupported DXGI DDS format {dxgi_format}")
    elif fourcc == b"DXT1":
        format_name = "DXT1/BC1"
        rgba = _blit_blocks(
            width,
            height,
            data[offset:],
            block_bytes=8,
            decode_block=_decode_bc1_block,
        )
    elif fourcc == b"DXT5":
        format_name = "DXT5/BC3"
        rgba = _blit_blocks(
            width,
            height,
            data[offset:],
            block_bytes=16,
            decode_block=_decode_bc3_block,
        )
    elif fourcc in (b"ATI2", b"BC5U"):
        format_name = fourcc.decode("ascii") + "/BC5_UNORM"
        rgba = _blit_blocks(
            width,
            height,
            data[offset:],
            block_bytes=16,
            decode_block=lambda block: _decode_bc5_block(
                block, reconstruct_normal_z=reconstruct_bc5_normal_z
            ),
        )
    elif fourcc == b"\0\0\0\0" and rgb_bits == 32:
        format_name = "RGBA32_MASKED"
        rgba = _decode_rgba32(
            width,
            height,
            data[offset:],
            r_mask=r_mask,
            g_mask=g_mask,
            b_mask=b_mask,
            a_mask=a_mask,
        )
    else:
        fourcc_text = fourcc.decode("ascii", errors="replace")
        raise DdsStageError(
            f"unsupported DDS pixel format fourCC={fourcc_text!r} "
            f"flags=0x{pf_flags:08x} rgbBits={rgb_bits}"
        )

    return width, height, rgba, {
        "format": format_name,
        "fourCC": fourcc.decode("ascii", errors="replace").rstrip("\0"),
        "dxgiFormat": dxgi_format,
        "resourceDimension": resource_dimension,
        "arraySize": array_size,
        "mipCount": mip_count,
        "sRGB": s_rgb,
        "firstMipOffset": offset,
        "bc5NormalZReconstructed": bool(
            reconstruct_bc5_normal_z and "BC5" in (format_name or "")
        ),
        "bc5GreenInverted": False,
    }


def stage_dds(
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
        uses = dependencies[source_texture]
        source_path = texture_root / source_texture
        if not source_path.is_file():
            record = {"sourceTexture": source_texture, "uses": uses}
            missing.append(record)
            if not allow_missing:
                raise DdsStageError(f"missing exact source texture {source_path}")
            continue

        preview_targets = {
            use["standardPreviewTarget"]
            for use in uses
            if use.get("standardPreviewTarget")
        }
        reconstruct_bc5_normal_z = preview_targets == {"normalTexture"}
        if "normalTexture" in preview_targets and preview_targets != {"normalTexture"}:
            record = {
                "sourceTexture": source_texture,
                "reason": (
                    "DDS is shared by normalTexture and another standard preview role"
                ),
                "uses": uses,
            }
            unsupported.append(record)
            if not allow_missing:
                raise DdsStageError(record["reason"] + f": {source_texture}")
            continue

        source_bytes = source_path.read_bytes()
        source_sha = _sha256(source_bytes)
        try:
            width, height, rgba, dds_meta = _decode_dds(
                source_bytes,
                reconstruct_bc5_normal_z=reconstruct_bc5_normal_z,
            )
        except DdsStageError as exc:
            record = {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "reason": str(exc),
                "uses": uses,
            }
            unsupported.append(record)
            if not allow_missing:
                raise
            continue

        if "BC5" in (dds_meta["format"] or "") and preview_targets:
            if preview_targets != {"normalTexture"}:
                raise DdsStageError(
                    f"BC5 preview use is not exclusively normalTexture: {source_texture}"
                )

        png = _encode_png_rgba(width, height, rgba)
        output_name = hashlib.sha256(source_texture.encode("utf-8")).hexdigest() + ".png"
        output_path = output_dir / output_name
        output_path.write_bytes(png)
        staged.append(
            {
                "sourceTexture": source_texture,
                "sourcePath": str(source_path),
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_sha,
                "dds": dds_meta,
                "png": {
                    "file": output_name,
                    "path": str(output_path),
                    "bytes": len(png),
                    "sha256": _sha256(png),
                    "width": width,
                    "height": height,
                    "format": "RGBA8",
                },
                "uses": uses,
            }
        )

    return {
        "format": "t6-texture-stage-manifest-v1",
        "source": {
            "kind": "DDS",
            "materialManifest": material_manifest_name,
            "materialManifestSha256": material_manifest_sha256,
            "textureRoot": str(texture_root),
        },
        "policy": {
            "resolution": "exact sourceTexture basename under textureRoot only",
            "decode": (
                "first mip only; BC1/BC3/BC5_UNORM/RGBA8/BGRA8 "
                "source-closed subset"
            ),
            "bc5Normal": (
                "when and only when manifest standardPreviewTarget is normalTexture, "
                "decode UNORM R/G as biased X/Y and reconstruct positive Z; no Y inversion"
            ),
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
            "bc5NormalReconstructionCount": sum(
                1
                for entry in staged
                if entry["dds"].get("bc5NormalZReconstructed")
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
    doc = stage_dds(
        material_manifest,
        texture_root=args.texture_root,
        output_dir=args.out_dir,
        material_manifest_name=args.material_manifest.name,
        material_manifest_sha256=_sha256(raw),
        allow_missing=args.allow_missing,
    )
    manifest_out = args.manifest_out or (
        args.out_dir / "t6_texture_stage_manifest_v1.json"
    )
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_out.write_bytes(payload)
    print(
        json.dumps(
            {"out": str(manifest_out), "sha256": _sha256(payload), **doc["stats"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
