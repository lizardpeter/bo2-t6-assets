#!/usr/bin/env python3
"""Regression for deterministic T6 TGA texture staging."""
from __future__ import annotations

import copy
import hashlib
import struct
import tempfile
from pathlib import Path

from t6_texture_stage_v1 import (
    TextureStageError,
    _decode_tga,
    _encode_png_rgba,
    stage,
)


def _tga_rgba(
    width: int,
    height: int,
    pixels: list[tuple[int, int, int, int]],
    *,
    rle: bool,
    origin_top: bool,
    origin_right: bool,
    depth: int = 32,
) -> bytes:
    descriptor = (
        (0x20 if origin_top else 0)
        | (0x10 if origin_right else 0)
        | (8 if depth == 32 else 0)
    )
    image_type = 10 if rle else 2
    header = struct.pack(
        "<BBBHHBHHHHBB",
        0, 0, image_type, 0, 0, 0, 0, 0, width, height, depth, descriptor
    )
    stream: list[bytes] = []
    ys = range(height) if origin_top else range(height - 1, -1, -1)
    for y in ys:
        xs = range(width - 1, -1, -1) if origin_right else range(width)
        for x in xs:
            r, g, b, a = pixels[y * width + x]
            stream.append(bytes((b, g, r, a)) if depth == 32 else bytes((b, g, r)))
    if not rle:
        body = b"".join(stream)
    else:
        assert len(stream) <= 128
        body = bytes((len(stream) - 1,)) + b"".join(stream)
    return header + body


def _manifest() -> dict:
    return {
        "format": "t6-material-texture-manifest-v1",
        "materials": [
            {
                "materialIndex": 1,
                "material": "synthetic/a",
                "layered": False,
                "compositors": [],
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": "synthetic/a",
                        "textures": [
                            {
                                "role": "colorMap",
                                "textureIndex": 10,
                                "sourceTexture": "a_c.tga",
                                "compositors": [],
                            },
                            {
                                "role": "normalMap",
                                "textureIndex": 11,
                                "sourceTexture": "a_n.tga",
                                "compositors": [],
                            },
                        ],
                    }
                ],
                "standardPreview": {
                    "baseColorTexture": {
                        "role": "colorMap",
                        "textureIndex": 10,
                        "sourceTexture": "a_c.tga",
                    },
                    "normalTexture": {
                        "role": "normalMap",
                        "textureIndex": 11,
                        "sourceTexture": "a_n.tga",
                    },
                },
                "standardPreviewBlocked": [],
            }
        ],
    }


def main() -> int:
    pixels = [
        (255, 0, 0, 255),
        (0, 255, 0, 128),
        (0, 0, 255, 255),
        (255, 255, 255, 64),
    ]
    expected_rgba = bytes(component for pixel in pixels for component in pixel)

    for rle in (False, True):
        for origin_top in (False, True):
            for origin_right in (False, True):
                tga = _tga_rgba(
                    2,
                    2,
                    pixels,
                    rle=rle,
                    origin_top=origin_top,
                    origin_right=origin_right,
                )
                width, height, rgba, meta = _decode_tga(tga)
                assert (width, height) == (2, 2)
                assert rgba == expected_rgba
                assert meta["rle"] is rle
                assert meta["originTop"] is origin_top
                assert meta["originRight"] is origin_right

    png1 = _encode_png_rgba(2, 2, expected_rgba)
    png2 = _encode_png_rgba(2, 2, expected_rgba)
    assert png1 == png2
    assert png1[:8] == b"\x89PNG\r\n\x1a\n"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source"
        out1 = root / "out1"
        out2 = root / "out2"
        source.mkdir()

        (source / "a_c.tga").write_bytes(
            _tga_rgba(
                2, 2, pixels,
                rle=False, origin_top=False, origin_right=False,
            )
        )
        (source / "a_n.tga").write_bytes(
            _tga_rgba(
                2, 2,
                [(128, 128, 255, 255)] * 4,
                rle=True, origin_top=True, origin_right=True,
            )
        )

        manifest = _manifest()
        doc1 = stage(
            manifest,
            texture_root=source,
            output_dir=out1,
            material_manifest_name="material.json",
            material_manifest_sha256="abc",
        )
        doc2 = stage(
            copy.deepcopy(manifest),
            texture_root=source,
            output_dir=out2,
            material_manifest_name="material.json",
            material_manifest_sha256="abc",
        )

        assert doc1["stats"] == {
            "referencedTextureCount": 2,
            "stagedTextureCount": 2,
            "missingTextureCount": 0,
            "unsupportedTextureCount": 0,
            "standardPreviewSourceCount": 2,
        }
        by_source1 = {entry["sourceTexture"]: entry for entry in doc1["textures"]}
        by_source2 = {entry["sourceTexture"]: entry for entry in doc2["textures"]}
        assert sorted(by_source1) == ["a_c.tga", "a_n.tga"]
        for source_name in by_source1:
            p1 = by_source1[source_name]["png"]
            p2 = by_source2[source_name]["png"]
            assert p1["file"] == p2["file"]
            assert p1["sha256"] == p2["sha256"]
            assert (out1 / p1["file"]).read_bytes() == (out2 / p2["file"]).read_bytes()
            assert p1["file"] == (
                hashlib.sha256(source_name.encode("utf-8")).hexdigest() + ".png"
            )

        (source / "a_n.tga").unlink()
        try:
            stage(
                _manifest(),
                texture_root=source,
                output_dir=root / "missing",
            )
        except TextureStageError:
            pass
        else:
            raise AssertionError("strict missing exact texture was not rejected")

        palette = bytearray(18)
        palette[1] = 1
        palette[2] = 1
        try:
            _decode_tga(bytes(palette))
        except TextureStageError:
            pass
        else:
            raise AssertionError("paletted TGA was not rejected")

    print("PASS t6_texture_stage_v1 regression")
    print("pngSha256=" + hashlib.sha256(png1).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
