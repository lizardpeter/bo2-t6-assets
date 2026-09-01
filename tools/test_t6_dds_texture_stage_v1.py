#!/usr/bin/env python3
"""Regression for deterministic T6/OAT DDS texture staging."""
from __future__ import annotations

import copy
import struct
import tempfile
from pathlib import Path

from t6_dds_texture_stage_v1 import DdsStageError, _decode_dds, stage_dds


def _dds_header(
    width: int,
    height: int,
    *,
    fourcc: bytes = b"\0\0\0\0",
    rgb_bits: int = 0,
    masks=(0, 0, 0, 0),
    dx10: tuple[int, int, int] | None = None,
) -> bytes:
    out = bytearray(148 if dx10 else 128)
    out[:4] = b"DDS "
    struct.pack_into("<I", out, 4, 124)
    struct.pack_into("<I", out, 8, 0x0002100F)
    struct.pack_into("<I", out, 12, height)
    struct.pack_into("<I", out, 16, width)
    struct.pack_into("<I", out, 28, 1)
    struct.pack_into("<I", out, 76, 32)
    struct.pack_into(
        "<I", out, 80, 0x4 if fourcc != b"\0\0\0\0" else 0x41
    )
    out[84:88] = fourcc
    struct.pack_into("<I", out, 88, rgb_bits)
    struct.pack_into("<IIII", out, 92, *masks)
    struct.pack_into("<I", out, 108, 0x1000)
    if dx10:
        dxgi, dimension, array_size = dx10
        struct.pack_into(
            "<IIIII", out, 128, dxgi, dimension, 0, array_size, 0
        )
    return bytes(out)


def _bc4(endpoint: int) -> bytes:
    return bytes((endpoint, 0)) + b"\0" * 6


def _manifest() -> dict:
    materials = []
    specs = [
        (0, "bc1", "colorMap", "baseColorTexture", "bc1.dds"),
        (1, "bc3", "colorMap", "baseColorTexture", "bc3.dds"),
        (2, "bc5", "normalMap", "normalTexture", "bc5.dds"),
        (3, "rgba", "colorMap", "baseColorTexture", "rgba.dds"),
    ]
    for index, name, role, target, source in specs:
        dependency = {
            "role": role,
            "textureIndex": index,
            "sourceTexture": source,
            "compositors": [],
        }
        materials.append(
            {
                "materialIndex": index,
                "material": f"synthetic/{name}",
                "layered": False,
                "compositors": [],
                "layers": [
                    {
                        "layerIndex": 0,
                        "layer": f"synthetic/{name}",
                        "textures": [dependency],
                    }
                ],
                "standardPreview": {
                    target: {
                        "role": role,
                        "textureIndex": index,
                        "sourceTexture": source,
                    }
                },
                "standardPreviewBlocked": [],
            }
        )
    return {"format": "t6-material-texture-manifest-v1", "materials": materials}


def main() -> int:
    bc1 = _dds_header(4, 4, fourcc=b"DXT1") + struct.pack(
        "<HHI", 0xF800, 0, 0
    )
    width, height, rgba, meta = _decode_dds(
        bc1, reconstruct_bc5_normal_z=False
    )
    assert (width, height) == (4, 4)
    assert rgba == bytes((255, 0, 0, 255)) * 16
    assert meta["format"] == "DXT1/BC1"

    bc3_block = _bc4(128) + struct.pack("<HHI", 0x07E0, 0, 0)
    bc3 = _dds_header(4, 4, fourcc=b"DXT5") + bc3_block
    _, _, rgba3, meta3 = _decode_dds(bc3, reconstruct_bc5_normal_z=False)
    assert rgba3 == bytes((0, 255, 0, 128)) * 16
    assert meta3["format"] == "DXT5/BC3"

    bc5_block = _bc4(128) + _bc4(128)
    bc5 = _dds_header(4, 4, fourcc=b"DX10", dx10=(83, 3, 1)) + bc5_block
    _, _, rgba5, meta5 = _decode_dds(bc5, reconstruct_bc5_normal_z=True)
    assert rgba5 == bytes((128, 128, 255, 255)) * 16
    assert meta5["format"] == "BC5_UNORM"
    assert meta5["bc5NormalZReconstructed"] is True

    pixels = bytes((10, 20, 30, 40)) * 4
    rgba_dds = _dds_header(
        2,
        2,
        rgb_bits=32,
        masks=(0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000),
    ) + pixels
    _, _, rgba4, meta4 = _decode_dds(
        rgba_dds, reconstruct_bc5_normal_z=False
    )
    assert rgba4 == pixels
    assert meta4["format"] == "RGBA32_MASKED"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "dds"
        out1 = root / "out1"
        out2 = root / "out2"
        source.mkdir()
        for name, payload in {
            "bc1.dds": bc1,
            "bc3.dds": bc3,
            "bc5.dds": bc5,
            "rgba.dds": rgba_dds,
        }.items():
            (source / name).write_bytes(payload)

        manifest = _manifest()
        doc1 = stage_dds(
            manifest,
            texture_root=source,
            output_dir=out1,
            material_manifest_name="m.json",
            material_manifest_sha256="abc",
        )
        doc2 = stage_dds(
            copy.deepcopy(manifest),
            texture_root=source,
            output_dir=out2,
            material_manifest_name="m.json",
            material_manifest_sha256="abc",
        )
        assert doc1["stats"] == {
            "referencedTextureCount": 4,
            "stagedTextureCount": 4,
            "missingTextureCount": 0,
            "unsupportedTextureCount": 0,
            "standardPreviewSourceCount": 4,
            "bc5NormalReconstructionCount": 1,
        }
        by1 = {entry["sourceTexture"]: entry for entry in doc1["textures"]}
        by2 = {entry["sourceTexture"]: entry for entry in doc2["textures"]}
        for name in by1:
            assert by1[name]["png"]["sha256"] == by2[name]["png"]["sha256"]
            assert (
                (out1 / by1[name]["png"]["file"]).read_bytes()
                == (out2 / by2[name]["png"]["file"]).read_bytes()
            )
        assert by1["bc5.dds"]["dds"]["bc5NormalZReconstructed"] is True

        bad = bytearray(bc5)
        struct.pack_into("<I", bad, 128, 84)  # BC5_SNORM is not yet supported.
        (source / "bc5.dds").write_bytes(bad)
        try:
            stage_dds(manifest, texture_root=source, output_dir=root / "bad")
        except DdsStageError:
            pass
        else:
            raise AssertionError("BC5_SNORM was not rejected")

    print("PASS t6_dds_texture_stage_v1 regression")
    print("bc5PngExpectedFlatNormal=128,128,255,255")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
