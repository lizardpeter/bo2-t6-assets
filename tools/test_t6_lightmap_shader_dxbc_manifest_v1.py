#!/usr/bin/env python3
"""Regression for T6 lightmap code sampler -> DXBC t# resolution."""
from __future__ import annotations

import copy
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from t6_lightmap_shader_dxbc_manifest_v1 import (
    LightmapShaderDxbcError,
    build_manifest,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rdef(primary_type: int = 2) -> bytes:
    creator = b"fixture\0"
    primary = b"lmP\0"
    secondary = b"lmS\0"
    resource_offset = 28
    strings_offset = resource_offset + 64
    creator_offset = strings_offset
    primary_offset = creator_offset + len(creator)
    secondary_offset = primary_offset + len(primary)
    header = struct.pack("<IIIIBBHII", 0, 0, 2, resource_offset, 0, 4, 0, 0, creator_offset)
    pr = struct.pack("<IIIIIIII", primary_offset, primary_type, 5, 4, 0, 3, 1, 0)
    sr = struct.pack("<IIIIIIII", secondary_offset, 2, 5, 4, 0, 7, 1, 0)
    return header + pr + sr + creator + primary + secondary


def _program(program_type: int = 0, major: int = 4) -> bytes:
    return struct.pack("<II", (program_type << 16) | (major << 4), 2)


def _dxbc(rdef: bytes | None = None, *, program_type: int = 0, major: int = 4) -> bytes:
    chunks = []
    if rdef is not None:
        chunks.append((b"RDEF", rdef))
    chunks.append((b"SHDR", _program(program_type=program_type, major=major)))
    table_end = 32 + len(chunks) * 4
    offsets = []
    body = bytearray()
    cursor = table_end
    for tag, payload in chunks:
        offsets.append(cursor)
        encoded = tag + struct.pack("<I", len(payload)) + payload
        body.extend(encoded)
        cursor += len(encoded)
    total = table_end + len(body)
    return (
        b"DXBC"
        + b"\0" * 16
        + struct.pack("<III", 1, total, len(chunks))
        + struct.pack("<" + "I" * len(offsets), *offsets)
        + bytes(body)
    )


def _inventory(shader: bytes, *, shader_model: str = "4.0") -> dict:
    return {
        "format": "t6-lightmap-shader-inventory-v2",
        "source": {"producer": "t6_lightmap_shader_inventory_v2.py"},
        "uniqueLightmapPixelShaders": [
            {
                "pixelShader": "world_lm",
                "file": "ps_world_lm.cso",
                "present": True,
                "bytes": len(shader),
                "sha256": _sha256(shader),
                "lightmapCodeSamplers": [
                    "lightmapSamplerPrimary",
                    "lightmapSamplerSecondary",
                ],
                "lightmapShaderResources": ["lmP", "lmS"],
            }
        ],
        "provenance": [
            {
                "material": "wpc/wall",
                "techniqueSet": "world",
                "technique": "world_lm",
                "techniqueTypes": ["lit"],
                "passIndex": 0,
                "shaderModel": shader_model,
                "pixelShader": "world_lm",
                "usesPrimary": True,
                "usesSecondary": True,
                "lightmapBindings": [
                    {"codeSampler": "lightmapSamplerPrimary", "shaderResource": "lmP"},
                    {"codeSampler": "lightmapSamplerSecondary", "shaderResource": "lmS"},
                ],
            }
        ],
    }


def _expect_error(fn, needle: str) -> None:
    try:
        fn()
    except LightmapShaderDxbcError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected {needle!r} in {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected LightmapShaderDxbcError containing {needle!r}")


def main() -> int:
    shader = _dxbc(_rdef())
    inventory = _inventory(shader)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "ps_world_lm.cso").write_bytes(shader)
        doc = build_manifest(inventory, shader_root=root)
        assert doc["format"] == "t6-lightmap-shader-dxbc-manifest-v1"
        assert doc["stats"] == {
            "provenanceEdgeCount": 1,
            "presentPixelShaderCount": 1,
            "missingPixelShaderCount": 0,
            "bothPrimarySecondaryEdgeCount": 1,
            "primaryTextureRegisterCount": 1,
            "secondaryTextureRegisterCount": 1,
        }
        assert doc["primaryTextureBindPoints"] == [3]
        assert doc["secondaryTextureBindPoints"] == [7]
        shader_doc = doc["pixelShaders"][0]
        assert shader_doc["sha256"] == _sha256(shader)
        assert shader_doc["dxbc"]["program"]["programType"] == "pixel"
        resolved = doc["provenance"][0]["resolvedLightmapBindings"]
        assert resolved == [
            {
                "codeSampler": "lightmapSamplerPrimary",
                "shaderResource": "lmP",
                "textureRegister": "t3",
                "bindPoint": 3,
                "bindCount": 1,
                "returnType": "FLOAT",
                "dimension": "TEXTURE2D",
                "rdefResourceIndex": 0,
            },
            {
                "codeSampler": "lightmapSamplerSecondary",
                "shaderResource": "lmS",
                "textureRegister": "t7",
                "bindPoint": 7,
                "bindCount": 1,
                "returnType": "FLOAT",
                "dimension": "TEXTURE2D",
                "rdefResourceIndex": 1,
            },
        ]

        # Deterministic output.
        doc2 = build_manifest(copy.deepcopy(inventory), shader_root=root)
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == json.dumps(
            doc2, sort_keys=True, separators=(",", ":")
        )

        changed = copy.deepcopy(inventory)
        changed["uniqueLightmapPixelShaders"][0]["sha256"] = "0" * 64
        _expect_error(lambda: build_manifest(changed, shader_root=root), "SHA-256 changed")

        model = copy.deepcopy(inventory)
        model["provenance"][0]["shaderModel"] = "5.0"
        _expect_error(lambda: build_manifest(model, shader_root=root), "shader-model disagreement")

        missing_resource = copy.deepcopy(inventory)
        missing_resource["provenance"][0]["lightmapBindings"][0]["shaderResource"] = "noSuchTexture"
        _expect_error(
            lambda: build_manifest(missing_resource, shader_root=root),
            "resolved to 0 RDEF entries",
        )

        wrong_type_shader = _dxbc(_rdef(primary_type=3))  # SAMPLER instead of TEXTURE
        (root / "ps_world_lm.cso").write_bytes(wrong_type_shader)
        wrong_type_inventory = _inventory(wrong_type_shader)
        _expect_error(
            lambda: build_manifest(wrong_type_inventory, shader_root=root),
            "expected TEXTURE",
        )

        vertex_shader = _dxbc(_rdef(), program_type=1)
        (root / "ps_world_lm.cso").write_bytes(vertex_shader)
        vertex_inventory = _inventory(vertex_shader)
        _expect_error(
            lambda: build_manifest(vertex_inventory, shader_root=root),
            "not pixel",
        )

        # Missing shader can be preserved only through an explicit incomplete mode.
        (root / "ps_world_lm.cso").unlink()
        _expect_error(
            lambda: build_manifest(inventory, shader_root=root),
            "missing exact DXBC shader",
        )
        allowed = build_manifest(
            inventory, shader_root=root, allow_missing_shaders=True
        )
        assert allowed["stats"]["presentPixelShaderCount"] == 0
        assert allowed["stats"]["missingPixelShaderCount"] == 1
        assert allowed["provenance"][0]["shaderPresent"] is False

    print("PASS t6_lightmap_shader_dxbc_manifest_v1 regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
